"""Node 4 — Legal Reasoner: EUDR compliance verdict via DeepSeek R1 + RAG."""
from __future__ import annotations

import logging
from datetime import date

from core.config import settings
from core.exceptions import LegalReasoningError
from schemas.agent_state import AgentState
from schemas.outputs import ComplianceVerdict, LegalRationale
from services.oxlo_client import OxloReasoningClient
from services.supabase_client import SupabaseService

logger = logging.getLogger(__name__)

# Estimated coffee productivity for volume coherence check (t/ha)
_PRODUCTIVITY_ESTIMATES: dict[str, tuple[float, float]] = {
    "Café":            (0.3, 1.5),   # (min, max) t/ha
    "Cacao":           (0.2, 1.0),
    "Soya":            (1.5, 4.0),
    "Aceite de Palma": (2.0, 6.0),
    "Carne de Res":    (0.05, 0.3),
    "Madera":          (0.5, 5.0),
    "Caucho":          (0.5, 2.0),
    "Otro":            (0.1, 10.0),
}

_SYSTEM_PROMPT = (
    "You are an expert EU Deforestation Regulation (EUDR) compliance officer. "
    "You reason strictly based on Regulation (EU) 2023/1115. "
    "Always cite specific articles. Respond in English. "
    "Format your response as Markdown."
)


def legal_reasoner(state: AgentState) -> AgentState:
    """
    LangGraph node: builds the compliance verdict using DeepSeek R1 + EUDR RAG context.

    Business Rules applied here:
        1. Post-2020 deforestation → automatic FAIL (Art. 3.1)
        2. requires_human_review=True → REQUIRES_HUMAN_REVIEW overrides PASS
        3. Volume coherence: reported_tons must fall within estimated productivity range

    Populates:
        - rag_context
        - legal_rationale (LegalRationale)
        - verdict (str)
        - risk_score (int)
    """
    logger.info("[legal_reasoner] Building EUDR compliance verdict")

    vision_report = state.get("vision_report")
    metadata = state.get("metadata")
    area_ha = state.get("polygon_area_ha", 0.0)

    if not vision_report or not metadata:
        raise LegalReasoningError(
            "vision_report or metadata missing from state — ensure prior nodes completed"
        )

    # ── Business Rule 1: Post-2020 deforestation date → auto FAIL ─────────────
    earliest_deforestation = vision_report.earliest_deforestation_date
    cutoff = settings.deforestation_cutoff_date
    post_cutoff_deforestation = (
        earliest_deforestation is not None
        and earliest_deforestation > cutoff
        and vision_report.deforestation_detected
    )

    if post_cutoff_deforestation:
        logger.warning(
            "[legal_reasoner] Deforestation detected AFTER 2020-12-31 (%s) — auto FAIL",
            earliest_deforestation,
        )

    # ── Volume coherence check ─────────────────────────────────────────────────
    volume_ok, volume_notes = _check_volume_coherence(
        crop_type=metadata.crop_type.value,
        area_ha=area_ha,
        reported_tons=metadata.reported_tons,
    )

    # ── RAG Context ────────────────────────────────────────────────────────────
    supabase = SupabaseService()
    rag_query = (
        f"EUDR compliance deforestation {metadata.crop_type.value} {earliest_deforestation} cutoff 2020"
    )
    rag_context = supabase.rag_search(query=rag_query)
    logger.info("[legal_reasoner] Retrieved %d RAG chunks", len(rag_context))

    # ── Build prompt ───────────────────────────────────────────────────────────
    prompt = _build_prompt(
        metadata=metadata,
        area_ha=area_ha,
        vision_report_summary=vision_report.model_dump(exclude={"raw_response"}),
        rag_chunks=rag_context,
        volume_notes=volume_notes,
        post_cutoff=post_cutoff_deforestation,
        requires_review=state.get("requires_human_review", False),
    )

    # ── Call DeepSeek R1 ───────────────────────────────────────────────────────
    client = OxloReasoningClient()
    if settings.oxlo_configured:
        raw_rationale = client.reason(prompt=prompt, system_prompt=_SYSTEM_PROMPT)
    else:
        raw_rationale = client.reason_mock(prompt=prompt)

    # ── Determine verdict ──────────────────────────────────────────────────────
    requires_review = state.get("requires_human_review", False)

    if post_cutoff_deforestation:
        verdict = ComplianceVerdict.FAIL
        risk_score = 95
    elif requires_review:
        verdict = ComplianceVerdict.REQUIRES_HUMAN_REVIEW
        risk_score = 60
    elif vision_report.deforestation_detected:
        verdict = ComplianceVerdict.FAIL
        risk_score = 80
    else:
        verdict = ComplianceVerdict.PASS
        risk_score = 10 + int(vision_report.max_confidence * 20)

    # Penalise for volume incoherence
    if not volume_ok:
        risk_score = min(risk_score + 15, 100)

    legal_rationale = LegalRationale(
        model=settings.oxlo_reasoning_model,
        summary=_extract_summary(raw_rationale),
        detailed_rationale=raw_rationale,
        volume_coherence_ok=volume_ok,
        volume_coherence_notes=volume_notes,
        eudr_articles_cited=_extract_articles(raw_rationale),
    )

    logger.info("[legal_reasoner] Verdict=%s  risk_score=%d", verdict, risk_score)

    return {
        **state,
        "rag_context": rag_context,
        "legal_rationale": legal_rationale,
        "verdict": verdict.value,
        "risk_score": risk_score,
    }


# ── Helpers ────────────────────────────────────────────────────────────────────


def _check_volume_coherence(crop_type: str, area_ha: float, reported_tons: float) -> tuple[bool, str]:
    """Check that reported_tons is plausible for the polygon area."""
    bounds = _PRODUCTIVITY_ESTIMATES.get(crop_type, (0.05, 15.0))
    min_est = bounds[0] * area_ha
    max_est = bounds[1] * area_ha

    if min_est <= reported_tons <= max_est:
        return True, (
            f"Reported {reported_tons} t is within the expected range for "
            f"{crop_type} on {area_ha:.1f} ha ({min_est:.1f}–{max_est:.1f} t)."
        )
    else:
        return False, (
            f"⚠️ Reported {reported_tons} t is OUTSIDE the expected range for "
            f"{crop_type} on {area_ha:.1f} ha (expected {min_est:.1f}–{max_est:.1f} t). "
            "This may indicate fraudulent declaration or measurement error."
        )


def _build_prompt(
    metadata,
    area_ha: float,
    vision_report_summary: dict,
    rag_chunks: list[str],
    volume_notes: str,
    post_cutoff: bool,
    requires_review: bool,
) -> str:
    rag_text = "\n\n".join(f"• {chunk}" for chunk in rag_chunks) or "No RAG context available."
    return f"""
## EUDR Compliance Analysis Request

### Farm Details
- Crop type: {metadata.crop_type.value}
- Harvest date: {metadata.harvest_date}
- Invoice ID: {metadata.invoice_id}
- Reported volume: {metadata.reported_tons} metric tons
- Polygon area: {area_ha:.2f} ha

### Vision Analysis Summary (YOLOv9)
```json
{vision_report_summary}
```

### Deforestation Date Rule
- Post-2020 deforestation detected: **{post_cutoff}**
- EUDR cutoff date: 2020-12-31

### Volume Coherence
{volume_notes}

### Human Review Required
{requires_review} (confidence below threshold)

### Relevant EUDR Regulation Excerpts (RAG)
{rag_text}

---
Based on all the above, provide:
1. A one-sentence compliance verdict.
2. A detailed Markdown rationale citing specific EUDR articles.
3. List of EUDR articles referenced (e.g. ["Art. 3.1", "Art. 4"]).
""".strip()


def _extract_summary(rationale: str) -> str:
    """Extract the first non-empty line as a summary."""
    for line in rationale.splitlines():
        line = line.strip("# *").strip()
        if line:
            return line[:300]
    return "Compliance assessment completed."


def _extract_articles(rationale: str) -> list[str]:
    """Extract EUDR article references from the rationale text."""
    import re

    pattern = r"Art(?:icle)?\.?\s+\d+(?:\.\d+)?"
    matches = re.findall(pattern, rationale, re.IGNORECASE)
    return sorted(set(matches))
