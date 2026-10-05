"""Configuration management for EvidenceOS."""

from functools import lru_cache
from pathlib import Path
from typing import List

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Centralized configuration loaded from environment variables or .env."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_env: str = "development"
    app_name: str = "EvidenceOS"
    app_port: int = 8000

    # Database
    database_url: str = "sqlite:///./data/evidenceos.db"

    # Storage
    storage_backend: str = "local"
    local_storage_path: str = "./data/evidence_store"
    max_upload_size_mb: int = 25

    # AI Provider
    ai_provider: str = "heuristic_local"
    gemini_api_key: str = ""
    gemini_model: str = "gemini-2.5-flash"

    # Security
    auth_required: bool = False
    api_secret_key: str = "dev-evidenceos-secret-key-change-in-prod"
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"

    # VeriDock SLA & Contract Rules
    sla_max_auto_approve_damage_ratio: float = 0.25
    sla_min_confidence_threshold: float = 0.75
    perceptual_hash_hamming_threshold: int = 10

    @property
    def cors_origin_list(self) -> List[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def storage_dir(self) -> Path:
        path = Path(self.local_storage_path)
        path.mkdir(parents=True, exist_ok=True)
        return path


@lru_cache
def get_settings() -> Settings:
    return Settings()
