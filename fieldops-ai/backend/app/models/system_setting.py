"""
System Setting ORM Model.
Persists platform configuration parameters in PostgreSQL.
"""

import uuid
from typing import Optional

from sqlalchemy import Boolean, Float, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base, TimestampMixin, UUIDMixin


class SystemSetting(Base, UUIDMixin, TimestampMixin):
    """Platform configuration parameters model."""

    __tablename__ = "system_settings"

    jwt_expiration_hours: Mapped[int] = mapped_column(
        Integer, default=24, nullable=False
    )
    max_concurrent_sessions: Mapped[int] = mapped_column(
        Integer, default=5, nullable=False
    )
    weather_refresh_interval_minutes: Mapped[int] = mapped_column(
        Integer, default=15, nullable=False
    )
    traffic_provider_mode: Mapped[str] = mapped_column(
        String(50), default="REAL_MOCK_FALLBACK", nullable=False
    )
    baseline_eta_speed_mph: Mapped[float] = mapped_column(
        Float, default=25.0, nullable=False
    )
    weather_delay_weight: Mapped[float] = mapped_column(
        Float, default=1.25, nullable=False
    )
    audit_log_retention_days: Mapped[int] = mapped_column(
        Integer, default=90, nullable=False
    )
    auto_unassign_on_tech_inactive: Mapped[bool] = mapped_column(
        Boolean, default=True, nullable=False
    )
    max_service_radius_miles: Mapped[float] = mapped_column(
        Float, default=100.0, nullable=True
    )
    updated_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    def __repr__(self) -> str:
        return (
            f"<SystemSetting(id={self.id}, jwt_exp={self.jwt_expiration_hours}h, "
            f"baseline_speed={self.baseline_eta_speed_mph}mph)>"
        )


__all__ = ["SystemSetting"]
