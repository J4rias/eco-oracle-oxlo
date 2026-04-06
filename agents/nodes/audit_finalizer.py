"""Node 5 — Audit Finalizer: assembles the ComplianceResponse and persists to Supabase."""
from __future__ import annotations

import base64
import hashlib
import json
import logging
import uuid
from datetime import datetime

from core.exceptions import AuditPersistenceError
from schemas.agent_state import AgentState
from schemas.outputs import (
    ComplianceReport,
    ComplianceResponse,
    ComplianceVerdict,
    EvidenceBundle,
)
from services.supabase_client import SupabaseService

logger = logging.getLogger(__name__)

# ── In-Memory Certificate Cache ────────────────────────────────────────────────
# Keyed by audit_hash → ComplianceResponse, used for lazy PDF generation.
# Acceptable for MVP; replace with Redis for production multi-worker setups.
_CERTIFICATE_CACHE: dict[str, "ComplianceResponse"] = {}
_MAX_CACHE_SIZE = 50  # Keep last N reports in memory


def audit_finalizer(state: AgentState) -> AgentState:
    """
    LangGraph node: assembles the final ComplianceResponse and persists the audit.

    Populates:
        - audit_hash (SHA-256 of the full report JSON)
        - audit_stored (bool — whether Supabase persistence succeeded)
        - final_response (ComplianceResponse)
    """
    logger.info("[audit_finalizer] Assembling compliance report")

    metadata = state["metadata"]
    vision_report = state["vision_report"]
    legal_rationale = state["legal_rationale"]
    verdict_str = state.get("verdict", ComplianceVerdict.REQUIRES_HUMAN_REVIEW.value)
    risk_score = state.get("risk_score", 50)
    area_ha = state.get("polygon_area_ha", 0.0)

    # ── Build compliance report ────────────────────────────────────────────────
    report = ComplianceReport(
        report_id=str(uuid.uuid4()),
        created_at=datetime.utcnow(),
        verdict=ComplianceVerdict(verdict_str),
        risk_score=risk_score,
        rationale=legal_rationale.detailed_rationale,
        vision_report=vision_report,
        legal_rationale=legal_rationale,
        polygon_area_ha=area_ha,
        crop_type=metadata.crop_type.value,
        harvest_date=metadata.harvest_date,
        invoice_id=metadata.invoice_id,
        reported_tons=metadata.reported_tons,
    )

    def to_data_url(data: bytes | None, mime: str = "image/png") -> str | None:
        if not data:
            return None
        encoded = base64.b64encode(data).decode("utf-8")
        return f"data:{mime};base64,{encoded}"

    # ── Build evidence bundle ──────────────────────────────────────────────────
    evidence = EvidenceBundle(
        sentinel_image_url=to_data_url(state.get("satellite_rgb_bytes")),
        detection_overlay_url=to_data_url(state.get("satellite_swir_bytes")),
        ndvi_image_url=to_data_url(state.get("satellite_ndvi_bytes")),
        ndmi_image_url=to_data_url(state.get("satellite_ndmi_bytes")),
        acquisition_date=state.get("acquisition_date"),
        cloud_cover_pct=state.get("cloud_cover_pct"),
        bounding_box=state.get("bounding_box"),
        centroid=state.get("centroid"),
        ndmi_stats=state.get("ndmi_stats"),
    )

    # ── Generate audit hash ────────────────────────────────────────────────────
    report_json = report.model_dump_json(indent=None)
    audit_hash = hashlib.sha256(report_json.encode("utf-8")).hexdigest()
    logger.info("[audit_finalizer] Audit hash: %s", audit_hash)

    # ── Persist to Supabase ────────────────────────────────────────────────────
    supabase = SupabaseService()
    audit_stored = supabase.save_audit(
        report_dict=json.loads(report_json),
        audit_hash=audit_hash,
    )

    final_response = ComplianceResponse(
        report=report,
        evidence=evidence,
        audit_hash=audit_hash,
        audit_stored=audit_stored,
    )

    logger.info(
        "[audit_finalizer] Done — verdict=%s  risk=%d  stored=%s",
        verdict_str, risk_score, audit_stored,
    )

    # ── Populate in-memory cache for lazy PDF generation ──────────────────────
    if len(_CERTIFICATE_CACHE) >= _MAX_CACHE_SIZE:
        # Evict oldest entry (FIFO)
        evict_key = next(iter(_CERTIFICATE_CACHE))
        del _CERTIFICATE_CACHE[evict_key]
        logger.debug("[audit_finalizer] Cache evicted oldest entry: %s", evict_key[:16])
    _CERTIFICATE_CACHE[audit_hash] = final_response
    logger.info("[audit_finalizer] Cached report for certificate generation: %s", audit_hash[:16])

    return {
        **state,
        "audit_hash": audit_hash,
        "audit_stored": audit_stored,
        "final_response": final_response,
    }
