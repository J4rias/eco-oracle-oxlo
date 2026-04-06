"""Node 2 — Satellite Fetcher: downloads Sentinel-2 RGB + NDVI for the polygon area."""
from __future__ import annotations

import logging
from datetime import date, timedelta

from core.config import settings
from core.exceptions import ConfigurationError, SatelliteFetchError
from schemas.agent_state import AgentState
from services.sentinel_client import SentinelHubService

logger = logging.getLogger(__name__)

# Search window: go back up to 90 days from harvest_date to find a clear scene
_SEARCH_WINDOW_DAYS = 90


def satellite_fetcher(state: AgentState) -> AgentState:
    """
    LangGraph node: fetches the best Sentinel-2 L2A scene for the polygon bounding box.

    Business rule:
        - Cloud cover must be < settings.max_cloud_cover_pct (default 10%)

    Populates:
        - satellite_rgb_bytes
        - satellite_ndvi_bytes
        - acquisition_date
        - cloud_cover_pct

    Rate limiting:
        The SentinelHubService wraps all calls with tenacity retry (exponential backoff).
        If 429 persists after 5 attempts, SatelliteRateLimitError is raised and propagated.
    """
    logger.info("[satellite_fetcher] Fetching Sentinel-2 imagery")

    bbox = state.get("bounding_box")
    metadata = state.get("metadata")

    if not bbox:
        raise SatelliteFetchError("bounding_box is missing from state — run input_validator first")

    # ── Build date range ───────────────────────────────────────────────────────
    if metadata and metadata.harvest_date:
        end_date = metadata.harvest_date
    else:
        end_date = date.today()

    start_date = end_date - timedelta(days=_SEARCH_WINDOW_DAYS)
    time_range = (start_date.isoformat(), end_date.isoformat())

    logger.info(
        "[satellite_fetcher] bbox=%s  time_range=%s  cloud_cover_limit=%d%%",
        bbox, time_range, settings.max_cloud_cover_pct,
    )

    if not settings.sentinel_hub_configured:
        logger.warning("[satellite_fetcher] SentinelHub not configured — using MOCK imagery")
        return _mock_imagery(state)

    service = SentinelHubService()
    imagery = service.fetch_rgb_ndvi(bbox_coords=bbox, time_range=time_range)

    logger.info(
        "[satellite_fetcher] Scene acquired: date=%s  cloud_cover=%.1f%%",
        imagery.acquisition_date, imagery.cloud_cover_pct or 0,
    )

    return {
        **state,
        "satellite_rgb_bytes": imagery.rgb_bytes,
        "satellite_ndvi_bytes": imagery.ndvi_bytes,
        "acquisition_date": imagery.acquisition_date,
        "cloud_cover_pct": imagery.cloud_cover_pct,
    }


def _mock_imagery(state: AgentState) -> AgentState:
    """Return 1×1 pixel PNG bytes when SentinelHub credentials are absent."""
    from io import BytesIO

    from PIL import Image

    buf = BytesIO()
    Image.new("RGB", (256, 256), color=(34, 85, 34)).save(buf, format="PNG")
    mock_bytes = buf.getvalue()

    return {
        **state,
        "satellite_rgb_bytes": mock_bytes,
        "satellite_ndvi_bytes": None,
        "acquisition_date": date.today(),
        "cloud_cover_pct": 0.0,
    }
