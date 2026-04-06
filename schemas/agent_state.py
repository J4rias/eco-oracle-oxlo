"""LangGraph AgentState — the central data bag flowing between all nodes."""
from __future__ import annotations

from datetime import date
from typing import Any, Optional
from typing_extensions import TypedDict

from schemas.inputs import FarmMetadata, GeoJSONFeature
from schemas.outputs import ComplianceResponse, EvidenceBundle, LegalRationale, VisionReport


class AgentState(TypedDict, total=False):
    # ── Input stage ───────────────────────────────────────────────────────────
    raw_geojson: dict[str, Any]           # Original parsed GeoJSON dict
    feature: GeoJSONFeature               # Validated first feature
    metadata: FarmMetadata                # Crop / invoice metadata
    polygon_area_ha: float                # Computed from geometry
    bounding_box: list[float]             # [west, south, east, north]
    centroid: tuple[float, float]         # (lon, lat)

    # ── Satellite stage ────────────────────────────────────────────────────────
    satellite_rgb_bytes: bytes            # PNG/TIFF of the RGB composite
    satellite_ndvi_bytes: Optional[bytes] # NDVI band (greyscale)
    satellite_ndmi_bytes: Optional[bytes] # NDMI band (moisture index)
    satellite_swir_bytes: Optional[bytes] # SWIR band (B11)
    acquisition_date: Optional[date]      # Date of the best scene found
    cloud_cover_pct: Optional[float]
    ndmi_stats: Optional[dict[str, float]] # mean, min, max, etc.

    # ── Vision stage ──────────────────────────────────────────────────────────
    vision_report: Optional[VisionReport]
    requires_human_review: bool           # Set True if max_confidence < threshold

    # ── Legal reasoning stage ─────────────────────────────────────────────────
    rag_context: list[str]                # EUDR law chunks from pgvector
    legal_rationale: Optional[LegalRationale]
    verdict: Optional[str]               # PASS | FAIL | REQUIRES_HUMAN_REVIEW
    risk_score: Optional[int]

    # ── Audit stage ───────────────────────────────────────────────────────────
    audit_hash: Optional[str]
    audit_stored: bool
    final_response: Optional[ComplianceResponse]

    # ── Error propagation ─────────────────────────────────────────────────────
    error: Optional[str]
    error_node: Optional[str]
