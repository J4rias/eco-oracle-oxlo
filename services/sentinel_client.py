"""Sentinel Hub service — OAuth2 via SHConfig, with retry logic for 429."""
from __future__ import annotations

import io
import logging
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Optional

import numpy as np
from sentinelhub import (
    BBox,
    BBoxSplitter,
    CRS,
    DataCollection,
    MimeType,
    MosaickingOrder,
    SHConfig,
    SentinelHubCatalog,
    SentinelHubRequest,
    bbox_to_dimensions,
)
from tenacity import (
    RetryError,
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from core.config import settings
from core.exceptions import ConfigurationError, SatelliteFetchError, SatelliteRateLimitError

logger = logging.getLogger(__name__)

# ── SentinelHub Evalscripts ────────────────────────────────────────────────────

_EVALSCRIPT_RGB = """
//VERSION=3
function setup() {
    return {
        input: [{ bands: ["B04", "B03", "B02"] }],
        output: { bands: 3 }
    };
}
function evaluatePixel(sample) {
    return [3.5 * sample.B04, 3.5 * sample.B03, 3.5 * sample.B02];
}
"""

_EVALSCRIPT_NDVI = """
//VERSION=3
function setup() {
    return {
        input: [{ bands: ["B08", "B04"] }],
        output: { bands: 1, sampleType: "FLOAT32" }
    };
}
function evaluatePixel(sample) {
    return [(sample.B08 - sample.B04) / (sample.B08 + sample.B04 + 0.0001)];
}
"""

_EVALSCRIPT_NDMI = """
//VERSION=3
function setup() {
    return {
        input: [{ bands: ["B08", "B11"] }],
        output: { bands: 1, sampleType: "FLOAT32" }
    };
}
function evaluatePixel(sample) {
    return [(sample.B08 - sample.B11) / (sample.B08 + sample.B11 + 0.0001)];
}
"""

_EVALSCRIPT_SWIR = """
//VERSION=3
function setup() {
    return {
        input: [{ bands: ["B11"] }],
        output: { bands: 1 }
    };
}
function evaluatePixel(sample) {
    return [sample.B11 * 2.5];
}
"""


@dataclass
class SentinelImagery:
    rgb_bytes: bytes
    ndvi_bytes: Optional[bytes]
    ndmi_bytes: Optional[bytes]
    swir_bytes: Optional[bytes]
    acquisition_date: Optional[date]
    cloud_cover_pct: Optional[float]
    bbox: list[float]


def _get_sh_config() -> SHConfig:
    """Build SHConfig from env credentials."""
    if not settings.sentinel_hub_configured:
        raise ConfigurationError(
            "Sentinel Hub credentials are missing. "
            "Set SH_CLIENT_ID and SH_CLIENT_SECRET in .env"
        )
    config = SHConfig()
    config.sh_client_id = settings.sh_client_id
    config.sh_client_secret = settings.sh_client_secret
    if settings.sh_instance_id:
        config.instance_id = settings.sh_instance_id
    return config


class _RateLimitException(Exception):
    """Internal signal for 429 responses, used by tenacity."""


class SentinelHubService:
    """Wraps sentinelhub-py with OAuth2, cloud filtering and 429 retries."""

    RESOLUTION_M = 10  # 10 m/px for Sentinel-2

    def __init__(self) -> None:
        self._config = _get_sh_config()

    # ── Public API ─────────────────────────────────────────────────────────────

    def fetch_compliance_imagery(
        self,
        bbox_coords: list[float],
        time_range: tuple[str, str],
    ) -> SentinelImagery:
        """
        Download the best Sentinel-2 L2A scene for `bbox_coords` in `time_range`.
        Acquires RGB, NDVI, NDMI (Moisture Index), and SWIR layers.
        """
        try:
            best_scene = self._find_best_scene(bbox_coords, time_range)
            if best_scene is None:
                raise SatelliteFetchError(
                    f"No Sentinel-2 scenes with <{settings.max_cloud_cover_pct}% cloud cover "
                    f"found in the date range {time_range}",
                    {"bbox": bbox_coords, "time_range": time_range},
                )

            scene_date = best_scene.get("properties", {}).get("datetime", "")[:10]
            cloud_cover = best_scene.get("properties", {}).get("eo:cloud_cover")

            bbox = BBox(bbox=bbox_coords, crs=CRS.WGS84)
            size = bbox_to_dimensions(bbox, resolution=self.RESOLUTION_M)

            # RGB for reference
            rgb_bytes = self._download_band(bbox, size, _EVALSCRIPT_RGB, time_range, MimeType.PNG)
            # NDVI for biomass
            ndvi_bytes = self._download_band(bbox, size, _EVALSCRIPT_NDVI, time_range, MimeType.TIFF)
            # NDMI for moisture / stress
            ndmi_bytes = self._download_band(bbox, size, _EVALSCRIPT_NDMI, time_range, MimeType.TIFF)
            # SWIR for Vision AI
            swir_bytes = self._download_band(bbox, size, _EVALSCRIPT_SWIR, time_range, MimeType.PNG)

            return SentinelImagery(
                rgb_bytes=rgb_bytes,
                ndvi_bytes=ndvi_bytes,
                ndmi_bytes=ndmi_bytes,
                swir_bytes=swir_bytes,
                acquisition_date=date.fromisoformat(scene_date) if scene_date else None,
                cloud_cover_pct=cloud_cover,
                bbox=bbox_coords,
            )

        except SatelliteFetchError:
            raise
        except RetryError as exc:
            raise SatelliteRateLimitError(
                "Sentinel Hub rate limit (429) persisted after 5 retries. "
                "Wait a few minutes and try again.",
            ) from exc
        except Exception as exc:
            logger.exception("Unexpected error fetching Sentinel-2 imagery")
            raise SatelliteFetchError(f"Satellite fetch failed: {exc}") from exc

    # ── Internal helpers ───────────────────────────────────────────────────────

    @retry(
        retry=retry_if_exception_type(_RateLimitException),
        wait=wait_exponential(multiplier=2, min=4, max=60),
        stop=stop_after_attempt(5),
        reraise=False,
    )
    def _find_best_scene(
        self,
        bbox_coords: list[float],
        time_range: tuple[str, str],
    ) -> dict | None:
        """Search catalog for the lowest-cloud scene. Retries on 429."""
        try:
            catalog = SentinelHubCatalog(config=self._config)
            bbox = BBox(bbox=bbox_coords, crs=CRS.WGS84)

            results = list(
                catalog.search(
                    collection=DataCollection.SENTINEL2_L2A,
                    bbox=bbox,
                    time=(time_range[0], time_range[1]),
                    filter=f"eo:cloud_cover < {settings.max_cloud_cover_pct}",
                    fields={"include": ["id", "properties.datetime", "properties.eo:cloud_cover"]},
                )
            )

            if not results:
                return None

            # Pick scene with lowest cloud cover
            return min(results, key=lambda x: x.get("properties", {}).get("eo:cloud_cover", 100))

        except Exception as exc:
            # sentinelhub raises generic exceptions; inspect message for 429
            if "429" in str(exc) or "Too Many Requests" in str(exc):
                logger.warning("Sentinel Hub 429 — backing off...")
                raise _RateLimitException() from exc
            raise


    @retry(
        retry=retry_if_exception_type(_RateLimitException),
        wait=wait_exponential(multiplier=2, min=4, max=60),
        stop=stop_after_attempt(5),
        reraise=False,
    )
    def _download_band(
        self,
        bbox: BBox,
        size: tuple[int, int],
        evalscript: str,
        time_interval: tuple[str, str],
        mime_type: MimeType,
    ) -> bytes:
        """Download a single band/composite. Retries on 429."""
        try:
            # Convert ISO strings → datetime
            dt_start = datetime.fromisoformat(time_interval[0])
            dt_end = datetime.fromisoformat(time_interval[1])

            request = SentinelHubRequest(
                evalscript=evalscript,
                input_data=[
                    SentinelHubRequest.input_data(
                        data_collection=DataCollection.SENTINEL2_L2A,
                        time_interval=(dt_start, dt_end),
                        mosaicking_order=MosaickingOrder.LEAST_CC,
                    )
                ],
                responses=[SentinelHubRequest.output_response("default", mime_type)],
                bbox=bbox,
                size=size,
                config=self._config,
            )
            data = request.get_data()[0]

            # Convert numpy array → bytes
            if isinstance(data, np.ndarray):
                from PIL import Image

                if data.dtype != np.uint8:
                    # Normalise float NDVI → 0-255 for storage
                    data_range = float(data.max()) - float(data.min())
                    data = ((data - data.min()) / (data_range + 1e-6) * 255).astype(np.uint8)
                if data.ndim == 3:
                    img = Image.fromarray(data, mode="RGB")
                else:
                    img = Image.fromarray(data.squeeze(), mode="L")
                buf = io.BytesIO()
                img.save(buf, format="PNG")
                return buf.getvalue()

            return bytes(data)

        except Exception as exc:
            if "429" in str(exc) or "Too Many Requests" in str(exc):
                logger.warning("Sentinel Hub 429 during band download — backing off...")
                raise _RateLimitException() from exc
            raise
