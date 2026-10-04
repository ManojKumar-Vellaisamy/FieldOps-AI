"""
Application configuration using Pydantic Settings v2.
All settings are loaded from environment variables / .env file.
"""

from functools import lru_cache
from typing import Any

from pydantic import AnyHttpUrl, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings — validated at startup."""

    model_config = SettingsConfigDict(
        env_file=("backend/.env", ".env"),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── Application ──────────────────────────────────────────────────────────
    APP_ENV: str = "development"
    APP_NAME: str = "FieldOps AI API"
    APP_VERSION: str = "1.0.0"
    APP_DEBUG: bool = False

    # ── Server ───────────────────────────────────────────────────────────────
    HOST: str = "0.0.0.0"
    PORT: int = 8000

    # ── Security ─────────────────────────────────────────────────────────────
    SECRET_KEY: str = "change-me-in-production"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # ── Database ─────────────────────────────────────────────────────────────
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/fieldops_ai"
    TEST_DATABASE_URL: str | None = None
    DATABASE_POOL_SIZE: int = 10
    DATABASE_MAX_OVERFLOW: int = 20

    # ── CORS ─────────────────────────────────────────────────────────────────
    BACKEND_CORS_ORIGINS: list[str] = [
        "http://localhost:5173",
        "http://localhost:3000",
    ]

    # ── Logging ──────────────────────────────────────────────────────────────
    LOG_LEVEL: str = "DEBUG"

    # ── API ──────────────────────────────────────────────────────────────────
    API_PREFIX: str = "/api/v1"

    # ── Traffic Data Provider ────────────────────────────────────────────────
    TRAFFIC_PROVIDER: str = "osrm"  # Options: "osrm", "tomtom", "openrouteservice", "none"
    TRAFFIC_API_KEY: str | None = None
    TOMTOM_API_KEY: str | None = None  # Alias for TRAFFIC_API_KEY
    TRAFFIC_API_URL: str | None = None
    TRAFFIC_TIMEOUT_SECONDS: float = 4.0

    # ── Events & Road Restriction Data Providers ──────────────────────────────
    EVENTS_API_KEY: str | None = None
    EVENTS_API_URL: str = "https://api.predicthq.com/v1/events/"
    EVENTS_TIMEOUT_SECONDS: float = 4.0
    ROAD_RESTRICTION_API_KEY: str | None = None
    ROAD_RESTRICTION_API_URL: str = "https://api.tomtom.com/traffic/services/5/incidentDetails"
    ROAD_RESTRICTION_TIMEOUT_SECONDS: float = 4.0

    # ── Operational Service Territory Guard ───────────────────────────────────
    MAX_SERVICE_RADIUS_MILES: float = 100.0

    @property
    def is_development(self) -> bool:
        return self.APP_ENV == "development"

    @property
    def is_production(self) -> bool:
        return self.APP_ENV == "production"

    @property
    def effective_test_database_url(self) -> str:
        """Dedicated test database connection string — completely isolated from development."""
        if self.TEST_DATABASE_URL:
            return self.TEST_DATABASE_URL
        from urllib.parse import urlparse, urlunparse
        parsed = urlparse(self.DATABASE_URL)
        path = parsed.path
        if path and path != "/" and not path.endswith("_test"):
            test_path = path.rstrip("/") + "_test"
        else:
            test_path = "/fieldops_ai_test"
        return urlunparse(parsed._replace(path=test_path))

    @property
    def is_test_database(self) -> bool:
        """Safety helper: returns True ONLY if active DATABASE_URL targets a dedicated test database."""
        from urllib.parse import urlparse
        db_name = urlparse(self.DATABASE_URL).path.lstrip("/").lower()
        return db_name.endswith("_test") or "fieldops_ai_test" in db_name

    @field_validator("BACKEND_CORS_ORIGINS", mode="before")
    @classmethod
    def assemble_cors_origins(cls, v: Any) -> list[str]:
        if isinstance(v, str):
            import json
            try:
                return json.loads(v)
            except ValueError:
                return [origin.strip() for origin in v.split(",")]
        return v


@lru_cache
def get_settings() -> Settings:
    """Return cached Settings instance — safe for FastAPI Depends()."""
    return Settings()


# Singleton for direct import
settings: Settings = get_settings()
