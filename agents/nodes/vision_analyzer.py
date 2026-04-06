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

    rgb_bytes = state.get("satellite_rgb_bytes")
    if not rgb_bytes:
        raise OxloAPIError("satellite_rgb_bytes missing from state — run satellite_fetcher first")

    client = OxloVisionClient()

    if settings.oxlo_configured:
        vision_report = client.analyze(image_bytes=rgb_bytes, image_name="sentinel_rgb.png")
    else:
        logger.warning("[vision_analyzer] OXLO_API_KEY not set — using mock vision response")
        vision_report = client.analyze_mock(image_bytes=rgb_bytes)

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
