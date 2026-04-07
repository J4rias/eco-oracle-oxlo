"""Pydantic output schemas for the EcoOracle compliance API."""
from __future__ import annotations

from datetime import date, datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class ComplianceVerdict(str, Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    REQUIRES_HUMAN_REVIEW = "REQUIRES_HUMAN_REVIEW"
    REJECTED_URBAN_AREA = "REJECTED_URBAN_AREA"


class DeforestationDetection(BaseModel):
    """Single object detection result from YOLOv9."""

    label: str
    confidence: float = Field(..., ge=0.0, le=1.0)
    bbox: list[float] = Field(..., description="[x_min, y_min, x_max, y_max] normalised 0-1")
    estimated_area_ha: Optional[float] = None
    detection_date: Optional[date] = None


class VisionReport(BaseModel):
    """Structured output from Oxlo YOLOv9 vision node."""

    model: str
    detections: list[DeforestationDetection] = Field(default_factory=list)
    deforestation_detected: bool = False
    urban_detected: bool = False
    earliest_deforestation_date: Optional[date] = None
    max_confidence: float = 0.0
    raw_response: dict = Field(default_factory=dict)


class LegalRationale(BaseModel):
    """DeepSeek R1 reasoning output."""

    model: str
    summary: str = Field(..., description="One-sentence compliance verdict explanation")
    detailed_rationale: str = Field(..., description="Full Markdown rationale")
    volume_coherence_ok: bool = Field(..., description="True if reported tons match estimated productivity")
    volume_coherence_notes: str = ""
    eudr_articles_cited: list[str] = Field(default_factory=list)


class ComplianceReport(BaseModel):
    """Core compliance analysis result."""

    report_id: str
    created_at: datetime = Field(default_factory=datetime.utcnow)
    verdict: ComplianceVerdict
    risk_score: int = Field(..., ge=0, le=100, description="Risk score 0 (low) – 100 (critical)")
    rationale: str = Field(..., description="Markdown-formatted reasoning")
    vision_report: VisionReport
    legal_rationale: LegalRationale
    polygon_area_ha: float
    crop_type: str
    harvest_date: date
    invoice_id: str
    reported_tons: float


class EvidenceBundle(BaseModel):
    """Satellite imagery and detection overlay references."""

    sentinel_image_url: Optional[str] = None
    detection_overlay_url: Optional[str] = None
    ndvi_image_url: Optional[str] = None
    ndmi_image_url: Optional[str] = None
    acquisition_date: Optional[date] = None
    cloud_cover_pct: Optional[float] = None
    # Geo-spatial context
    bounding_box: Optional[list[float]] = None       # [west, south, east, north]
    centroid: Optional[tuple[float, float]] = None   # (lon, lat)
    ndmi_stats: Optional[dict[str, float | str]] = None  # mean, status


class ComplianceResponse(BaseModel):
    """Top-level API response."""

    report: ComplianceReport
    evidence: EvidenceBundle
    audit_hash: str = Field(..., description="SHA-256 hex digest for immutable verification")
    audit_stored: bool = Field(..., description="True if successfully persisted to Supabase")
