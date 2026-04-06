"""Custom exception hierarchy for EcoOracle."""
from __future__ import annotations


class EcoOracleError(Exception):
    """Base exception for all EcoOracle errors."""

    def __init__(self, message: str, details: dict | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.details = details or {}


class GeoJSONValidationError(EcoOracleError):
    """Raised when the uploaded GeoJSON is invalid or unsupported."""


class SatelliteFetchError(EcoOracleError):
    """Raised when Sentinel Hub imagery cannot be acquired."""


class SatelliteRateLimitError(SatelliteFetchError):
    """Raised on HTTP 429 from Sentinel Hub (propagated after exhausting retries)."""


class OxloAPIError(EcoOracleError):
    """Raised when Oxlo.ai returns an unexpected response."""


class OxloRateLimitError(OxloAPIError):
    """Raised on HTTP 429 from Oxlo.ai."""


class LegalReasoningError(EcoOracleError):
    """Raised when the DeepSeek R1 reasoning node fails."""


class AuditPersistenceError(EcoOracleError):
    """Raised when the audit record cannot be written to Supabase."""


class ConfigurationError(EcoOracleError):
    """Raised when a required environment variable / credential is missing."""
