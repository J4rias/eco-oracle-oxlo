"""Node 3 — Vision Analyzer: sends satellite image to Oxlo YOLOv9 for deforestation detection."""
from __future__ import annotations

import logging

from core.config import settings
from core.exceptions import OxloAPIError
from schemas.agent_state import AgentState
from services.oxlo_client import OxloVisionClient

logger = logging.getLogger(__name__)


def vision_analyzer(state: AgentState) -> AgentState:
    """
    LangGraph node: runs YOLOv9 (via Oxlo) on the Sentinel-2 RGB image.

    Business Rule (Confidence Threshold):
        If max_confidence < settings.confidence_threshold (default 0.7),
        requires_human_review is set True and propagated to the legal_reasoner.

    Populates:
        - vision_report (VisionReport)
        - requires_human_review (bool)
    """
    logger.info("[vision_analyzer] Starting deforestation detection")

    swir_bytes = state.get("satellite_swir_bytes")
    # Fallback to RGB if SWIR is missing (e.g. from a previous state or mock run)
    image_to_analyze = swir_bytes if swir_bytes else state.get("satellite_rgb_bytes")
    
    if not image_to_analyze:
        raise OxloAPIError("satellite_swir_bytes / rgb_bytes missing from state")

    client = OxloVisionClient()

    if settings.oxlo_configured:
        # Use SWIR for high-fidelity change detection
        vision_report = client.analyze(image_bytes=image_to_analyze, image_name="sentinel_swir.png")
    else:
        logger.warning("[vision_analyzer] OXLO_API_KEY not set — using mock vision response")
        vision_report = client.analyze_mock(image_bytes=image_to_analyze)

    # ── Business Rule: confidence threshold ───────────────────────────────────
    requires_review = vision_report.deforestation_detected and (vision_report.max_confidence < settings.confidence_threshold)
    if requires_review:
        logger.warning(
            "[vision_analyzer] Deforestation detected with Low confidence (%.2f < %.2f) — flagging REQUIRES_HUMAN_REVIEW",
            vision_report.max_confidence, settings.confidence_threshold,
        )
    else:
        logger.info(
            "[vision_analyzer] Confidence OK (%.2f) — deforestation_detected=%s",
            vision_report.max_confidence, vision_report.deforestation_detected,
        )

    return {
        **state,
        "vision_report": vision_report,
        "requires_human_review": requires_review,
    }
