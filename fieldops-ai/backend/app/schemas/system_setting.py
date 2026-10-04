"""
System Setting Pydantic Schemas.
Enforces range validation, type checking, and serialization for platform configuration parameters.
"""

from datetime import datetime
from typing import Optional
import uuid

from pydantic import BaseModel, ConfigDict, Field


class SystemSettingsPayload(BaseModel):
    """Payload for creating or updating platform settings."""

    jwt_expiration_hours: int = Field(
        default=24,
        ge=1,
        le=168,
        description="JWT token expiration lifetime in hours (1-168)",
    )
    max_concurrent_sessions: int = Field(
        default=5,
        ge=1,
        le=20,
        description="Maximum concurrent active sessions per user (1-20)",
    )
    weather_refresh_interval_minutes: int = Field(
        default=15,
        ge=5,
        le=60,
        description="Weather telemetry cache refresh interval in minutes (5-60)",
    )
    traffic_provider_mode: str = Field(
        default="REAL_MOCK_FALLBACK",
        description="Traffic provider operational mode",
    )
    baseline_eta_speed_mph: float = Field(
        default=25.0,
        ge=10.0,
        le=65.0,
        description="Baseline transit speed tuning in MPH (10.0-65.0)",
    )
    weather_delay_weight: float = Field(
        default=1.25,
        ge=1.0,
        le=3.0,
        description="Weather delay impact weight multiplier (1.0-3.0)",
    )
    audit_log_retention_days: int = Field(
        default=90,
        ge=30,
        le=365,
        description="Audit record archiving/retention threshold in days (30-365)",
    )
    auto_unassign_on_tech_inactive: bool = Field(
        default=True,
        description="Auto-unassign active jobs when technician profile becomes INACTIVE",
    )
    max_service_radius_miles: float = Field(
        default=100.0,
        ge=5.0,
        le=1000.0,
        description="Practical field-service operational territory radius in miles (5.0-1000.0)",
    )


class SystemSettingsResponse(SystemSettingsPayload):
    """API Response model for platform settings."""

    model_config = ConfigDict(from_attributes=True)

    id: Optional[uuid.UUID] = None
    updated_at: Optional[datetime] = None
    updated_by: Optional[uuid.UUID] = None


__all__ = ["SystemSettingsPayload", "SystemSettingsResponse"]
