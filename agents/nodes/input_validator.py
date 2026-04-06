"""Node 1 — Input Validator: validates GeoJSON + metadata, extracts geometry stats."""
from __future__ import annotations

import json
import logging

import geopandas as gpd
from shapely.geometry import shape

from core.exceptions import GeoJSONValidationError
from schemas.agent_state import AgentState
from schemas.inputs import GeoJSONFeatureCollection

logger = logging.getLogger(__name__)


def input_validator(state: AgentState) -> AgentState:
    """
    LangGraph node: validates the raw GeoJSON and extracts polygon metadata.

    Populates:
        - feature (validated GeoJSONFeature)
        - polygon_area_ha
        - bounding_box [west, south, east, north]
        - centroid (lon, lat)
    """
    logger.info("[input_validator] Starting GeoJSON validation")

    try:
        raw = state.get("raw_geojson")
        if not raw:
            raise GeoJSONValidationError("raw_geojson is empty or missing from agent state")

        # ── Pydantic validation ───────────────────────────────────────────────
        try:
            geojson_obj = GeoJSONFeatureCollection.model_validate(raw)
            feature = geojson_obj.first_feature()
        except Exception as exc:
            raise GeoJSONValidationError(f"GeoJSON schema validation failed: {exc}") from exc

        # ── Shapely geometry ──────────────────────────────────────────────────
        try:
            geom = shape(feature.geometry.model_dump())
        except Exception as exc:
            raise GeoJSONValidationError(f"Cannot parse geometry with Shapely: {exc}") from exc

        if not geom.is_valid:
            raise GeoJSONValidationError(
                "Polygon geometry is invalid (self-intersecting or degenerate). "
                "Use Shapely's buffer(0) to repair before uploading."
            )

        # ── GeoDataFrame for area + CRS ops ───────────────────────────────────
        gdf = gpd.GeoDataFrame(geometry=[geom], crs="EPSG:4326")
        gdf_utm = gdf.to_crs(gdf.estimate_utm_crs())  # reproject for accurate area
        area_ha = float(gdf_utm.geometry.area.iloc[0] / 10_000)

        bbox = list(geom.bounds)                   # (minx, miny, maxx, maxy)
        centroid = (geom.centroid.x, geom.centroid.y)

        logger.info(
            "[input_validator] Polygon OK — area=%.2f ha, bbox=%s, centroid=%s",
            area_ha, bbox, centroid,
        )

        return {
            **state,
            "feature": feature,
            "polygon_area_ha": area_ha,
            "bounding_box": bbox,
            "centroid": centroid,
        }

    except GeoJSONValidationError:
        raise
    except Exception as exc:
        logger.exception("[input_validator] Unexpected error")
        raise GeoJSONValidationError(f"Input validation failed unexpectedly: {exc}") from exc
