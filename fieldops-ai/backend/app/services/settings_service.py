"""
Platform Settings Business Service.
Provides centralized access, update, persistence, and audit logging for system configuration.
"""

from datetime import datetime, timezone
from typing import Optional
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.session import AsyncSessionLocal
from app.models.audit_log import AuditLog
from app.models.system_setting import SystemSetting
from app.schemas.system_setting import SystemSettingsPayload, SystemSettingsResponse

# Global default settings dictionary
DEFAULT_SETTINGS = {
    "jwt_expiration_hours": 24,
    "max_concurrent_sessions": 5,
    "weather_refresh_interval_minutes": 15,
    "traffic_provider_mode": "REAL_MOCK_FALLBACK",
    "baseline_eta_speed_mph": 25.0,
    "weather_delay_weight": 1.0,
    "audit_log_retention_days": 90,
    "auto_unassign_on_tech_inactive": True,
    "max_service_radius_miles": 100.0,
}

# Thread-safe in-memory cache for fast sync/async configuration lookup across services
_CACHED_SETTINGS: Optional[SystemSettingsResponse] = None


class SettingsService:
    """Business service layer managing platform configuration."""

    def __init__(self, session: Optional[AsyncSession] = None) -> None:
        self.session = session

    async def get_settings(self) -> SystemSettingsResponse:
        """Fetch current platform configuration from database with default fallback."""
        global _CACHED_SETTINGS

        if _CACHED_SETTINGS is not None and not self.session:
            return _CACHED_SETTINGS

        async def _query(db: AsyncSession) -> SystemSettingsResponse:
            stmt = select(SystemSetting).order_by(SystemSetting.created_at.desc())
            res = await db.execute(stmt)
            setting_obj = res.scalars().first()

            if not setting_obj:
                setting_obj = SystemSetting(
                    id=uuid.uuid4(),
                    **DEFAULT_SETTINGS,
                    created_at=datetime.now(timezone.utc),
                    updated_at=datetime.now(timezone.utc),
                )
                db.add(setting_obj)
                try:
                    await db.commit()
                    await db.refresh(setting_obj)
                except Exception:
                    await db.rollback()

            resp = SystemSettingsResponse.model_validate(setting_obj)
            return resp

        if self.session:
            resp = await _query(self.session)
        else:
            async with AsyncSessionLocal() as db_session:
                resp = await _query(db_session)

        _CACHED_SETTINGS = resp
        return resp

    async def update_settings(
        self,
        payload: SystemSettingsPayload,
        actor_id: Optional[uuid.UUID] = None,
    ) -> SystemSettingsResponse:
        """Update platform configuration with transaction safety and audit logging."""
        global _CACHED_SETTINGS
        now = datetime.now(timezone.utc)

        async def _execute_update(db: AsyncSession) -> SystemSettingsResponse:
            stmt = select(SystemSetting).order_by(SystemSetting.created_at.desc())
            res = await db.execute(stmt)
            setting_obj = res.scalars().first()

            old_summary = ""
            if setting_obj:
                old_summary = (
                    f"jwt_exp={setting_obj.jwt_expiration_hours}h, "
                    f"baseline_speed={setting_obj.baseline_eta_speed_mph}mph, "
                    f"weather_weight={setting_obj.weather_delay_weight}, "
                    f"auto_unassign={setting_obj.auto_unassign_on_tech_inactive}"
                )
            else:
                setting_obj = SystemSetting(id=uuid.uuid4())

            # Apply fields from payload
            setting_obj.jwt_expiration_hours = payload.jwt_expiration_hours
            setting_obj.max_concurrent_sessions = payload.max_concurrent_sessions
            setting_obj.weather_refresh_interval_minutes = payload.weather_refresh_interval_minutes
            setting_obj.traffic_provider_mode = payload.traffic_provider_mode
            setting_obj.baseline_eta_speed_mph = payload.baseline_eta_speed_mph
            setting_obj.weather_delay_weight = payload.weather_delay_weight
            setting_obj.audit_log_retention_days = payload.audit_log_retention_days
            setting_obj.auto_unassign_on_tech_inactive = payload.auto_unassign_on_tech_inactive
            if hasattr(setting_obj, "max_service_radius_miles"):
                setting_obj.max_service_radius_miles = payload.max_service_radius_miles
            setting_obj.updated_by = actor_id
            setting_obj.updated_at = now

            new_summary = (
                f"jwt_exp={payload.jwt_expiration_hours}h, "
                f"baseline_speed={payload.baseline_eta_speed_mph}mph, "
                f"weather_weight={payload.weather_delay_weight}, "
                f"auto_unassign={payload.auto_unassign_on_tech_inactive}, "
                f"max_radius={payload.max_service_radius_miles}mi"
            )

            db.add(setting_obj)

            # Audit log
            audit = AuditLog(
                id=uuid.uuid4(),
                user_id=actor_id,
                action="SYSTEM_SETTINGS_UPDATED",
                entity="SystemSetting",
                entity_id=str(setting_obj.id),
                reason="Administrator updated system configuration parameters",
                old_value=old_summary,
                new_value=new_summary,
                created_at=now,
            )
            db.add(audit)

            await db.commit()
            await db.refresh(setting_obj)

            return SystemSettingsResponse.model_validate(setting_obj)

        if self.session:
            resp = await _execute_update(self.session)
        else:
            async with AsyncSessionLocal() as db_session:
                resp = await _execute_update(db_session)

        _CACHED_SETTINGS = resp
        return resp

    async def reset_defaults(
        self,
        actor_id: Optional[uuid.UUID] = None,
    ) -> SystemSettingsResponse:
        """Reset platform settings to factory default values with audit log."""
        payload = SystemSettingsPayload(**DEFAULT_SETTINGS)
        return await self.update_settings(payload, actor_id=actor_id)


def get_cached_settings_snapshot() -> SystemSettingsResponse:
    """Return cached settings snapshot or fallback defaults for non-async calls."""
    if _CACHED_SETTINGS:
        return _CACHED_SETTINGS
    return SystemSettingsResponse(**DEFAULT_SETTINGS)


__all__ = ["SettingsService", "DEFAULT_SETTINGS", "get_cached_settings_snapshot"]
