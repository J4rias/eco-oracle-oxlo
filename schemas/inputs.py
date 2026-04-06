"""Pydantic input schemas for the EcoOracle compliance API."""
from __future__ import annotations

from datetime import date
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, field_validator


class CropType(str, Enum):
    COFFEE = "Café"
    COCOA = "Cacao"
    SOYA = "Soya"
    PALM_OIL = "Aceite de Palma"
    BEEF = "Carne de Res"
    WOOD = "Madera"
    RUBBER = "Caucho"
    OTHER = "Otro"


class FarmMetadata(BaseModel):
    """User-supplied crop and invoice metadata."""

    crop_type: CropType = Field(..., description="Type of agricultural product")
    harvest_date: date = Field(..., description="ISO 8601 harvest date (YYYY-MM-DD)")
    invoice_id: str = Field(..., min_length=1, max_length=128, description="Unique invoice identifier")
    reported_tons: float = Field(..., gt=0, description="Volume declared in the invoice (metric tons)")

    model_config = {"json_schema_extra": {"example": {
        "crop_type": "Café",
        "harvest_date": "2024-06-15",
        "invoice_id": "INV-2024-00123",
        "reported_tons": 12.5,
    }}}


class GeoJSONGeometry(BaseModel):
    """Minimal GeoJSON Polygon geometry."""

    type: str
    coordinates: list[Any]

    @field_validator("type")
    @classmethod
    def must_be_polygon(cls, v: str) -> str:
        if v not in {"Polygon", "MultiPolygon"}:
            raise ValueError("GeoJSON geometry must be Polygon or MultiPolygon")
        return v


class GeoJSONFeature(BaseModel):
    """Single GeoJSON Feature wrapping a polygon geometry."""

    type: str = "Feature"
    geometry: GeoJSONGeometry
    properties: dict[str, Any] = Field(default_factory=dict)

    @field_validator("type")
    @classmethod
    def must_be_feature(cls, v: str) -> str:
        if v != "Feature":
            raise ValueError("GeoJSON root type must be 'Feature'")
        return v


class GeoJSONFeatureCollection(BaseModel):
    """Supports both bare Feature and FeatureCollection uploads."""

    type: str
    features: list[GeoJSONFeature] | None = None
    geometry: GeoJSONGeometry | None = None
    properties: dict[str, Any] | None = None

    def first_feature(self) -> GeoJSONFeature:
        """Return first usable feature regardless of root type."""
        if self.type == "FeatureCollection" and self.features:
            return self.features[0]
        if self.type == "Feature" and self.geometry:
            return GeoJSONFeature(type="Feature", geometry=self.geometry, properties=self.properties or {})
        raise ValueError("No valid Feature found in GeoJSON input")
