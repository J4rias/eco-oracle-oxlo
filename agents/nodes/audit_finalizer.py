"""Node 5 — Audit Finalizer: assembles the ComplianceResponse and persists to Supabase."""
from __future__ import annotations

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

    # ── Build evidence bundle ──────────────────────────────────────────────────
    evidence = EvidenceBundle(
        sentinel_image_url=None,       # Would be a signed URL to cloud storage in production
        detection_overlay_url=None,    # Overlay image with YOLOv9 bounding boxes
        ndvi_image_url=None,
        acquisition_date=state.get("acquisition_date"),
        cloud_cover_pct=state.get("cloud_cover_pct"),
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

    return {
        **state,
        "audit_hash": audit_hash,
        "audit_stored": audit_stored,
        "final_response": final_response,
    }
