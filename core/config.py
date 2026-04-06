from __future__ import annotations

from datetime import date
from functools import lru_cache

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── App ───────────────────────────────────────────────────────────────────
    app_env: str = Field(default="development")
    log_level: str = Field(default="INFO")

    # ── Business Rules ────────────────────────────────────────────────────────
    confidence_threshold: float = Field(default=0.7, ge=0.0, le=1.0)
    deforestation_cutoff_date: date = Field(default=date(2020, 12, 31))
    max_cloud_cover_pct: int = Field(default=10, ge=0, le=100)

    # ── Sentinel Hub ──────────────────────────────────────────────────────────
    sh_client_id: str = Field(default="")
    sh_client_secret: str = Field(default="")
    sh_instance_id: str = Field(default="")

    # ── Oxlo.ai ───────────────────────────────────────────────────────────────
    oxlo_api_key: str = Field(default="")
    oxlo_base_url: str = Field(default="https://api.oxlo.ai/v1")
    oxlo_vision_model: str = Field(default="yolo-v9")
    oxlo_reasoning_model: str = Field(default="deepseek-r1-70b")
    oxlo_embedding_model: str = Field(default="bge-large")

    # ── Supabase ──────────────────────────────────────────────────────────────
    supabase_url: str = Field(default="")
    supabase_anon_key: str = Field(default="")

    # ── Derived helpers ───────────────────────────────────────────────────────
    @property
    def sentinel_hub_configured(self) -> bool:
        return bool(self.sh_client_id and self.sh_client_secret)

    @property
    def supabase_configured(self) -> bool:
        return bool(self.supabase_url and self.supabase_anon_key)

    @property
    def oxlo_configured(self) -> bool:
        return bool(self.oxlo_api_key)

    @field_validator("log_level")
    @classmethod
    def validate_log_level(cls, v: str) -> str:
        allowed = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        upper = v.upper()
        if upper not in allowed:
            raise ValueError(f"log_level must be one of {allowed}")
        return upper


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return a cached singleton Settings instance."""
    return Settings()


settings = get_settings()
