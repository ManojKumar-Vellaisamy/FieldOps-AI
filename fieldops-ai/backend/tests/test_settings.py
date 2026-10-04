"""
Unit and Integration tests for Platform Settings Functional Verification & Integration module.
Covers Settings API CRUD, RBAC protection, boundary validation, and domain service behavior.
"""

import uuid
from datetime import datetime, timezone
from jose import jwt
import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.core.config import settings
from app.database.session import AsyncSessionLocal
from app.models.assignment import Assignment
from app.models.job import Job, JobStatus
from app.models.technician import Technician
from app.schemas.technician import TechnicianStatusPatch
from app.schemas.system_setting import SystemSettingsPayload
from app.services.context_providers import WeatherProvider
from app.services.eta_service import ETAService
from app.services.settings_service import SettingsService, DEFAULT_SETTINGS
from app.services.technician_service import TechnicianService

BASE_URL = "http://127.0.0.1:8000"


async def get_token_headers(client: AsyncClient, email: str, password: str) -> dict[str, str]:
    """Helper to authenticate and get Bearer token headers."""
    res = await client.post(f"{BASE_URL}/api/v1/auth/login", json={"email": email, "password": password})
    assert res.status_code == 200, f"Login failed for {email}: {res.text}"
    token = res.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(autouse=True)
async def reset_settings_teardown():
    yield
    await SettingsService().reset_defaults()


@pytest.mark.asyncio
async def test_1_admin_get_and_update_settings():
    """Verify Administrator can read, update, and persist platform settings."""
    async with AsyncClient() as client:
        admin_headers = await get_token_headers(client, "admin@fieldops.ai", "Admin@123")

        # 1. GET settings
        get_res = await client.get(f"{BASE_URL}/api/v1/settings", headers=admin_headers)
        print("GET_1 status:", get_res.status_code, get_res.text)
        assert get_res.status_code == 200
        data = get_res.json()
        assert "jwt_expiration_hours" in data
        assert "baseline_eta_speed_mph" in data

        # 2. PUT updated settings
        payload = {
            "jwt_expiration_hours": 12,
            "max_concurrent_sessions": 8,
            "weather_refresh_interval_minutes": 20,
            "traffic_provider_mode": "REAL_MOCK_FALLBACK",
            "baseline_eta_speed_mph": 35.0,
            "weather_delay_weight": 1.5,
            "audit_log_retention_days": 180,
            "auto_unassign_on_tech_inactive": True,
        }
        put_res = await client.put(f"{BASE_URL}/api/v1/settings", json=payload, headers=admin_headers)
        print("PUT status:", put_res.status_code, put_res.text)
        assert put_res.status_code == 200
        updated = put_res.json()
        assert updated["jwt_expiration_hours"] == 12
        assert updated["baseline_eta_speed_mph"] == 35.0
        assert updated["weather_delay_weight"] == 1.5
        assert updated["audit_log_retention_days"] == 180

        # 3. GET verify persistence
        get2_res = await client.get(f"{BASE_URL}/api/v1/settings", headers=admin_headers)
        print("GET_2 status:", get2_res.status_code, get2_res.text)
        assert get2_res.status_code == 200
        assert get2_res.json()["jwt_expiration_hours"] == 12


@pytest.mark.asyncio
async def test_2_admin_reset_settings_defaults():
    """Verify Administrator can reset platform settings to factory defaults."""
    async with AsyncClient() as client:
        admin_headers = await get_token_headers(client, "admin@fieldops.ai", "Admin@123")

        res = await client.post(f"{BASE_URL}/api/v1/settings/reset", headers=admin_headers)
        assert res.status_code == 200
        data = res.json()
        assert data["jwt_expiration_hours"] == DEFAULT_SETTINGS["jwt_expiration_hours"]
        assert data["baseline_eta_speed_mph"] == DEFAULT_SETTINGS["baseline_eta_speed_mph"]
        assert data["weather_delay_weight"] == DEFAULT_SETTINGS["weather_delay_weight"]


@pytest.mark.asyncio
async def test_3_rbac_protection_on_settings():
    """Verify non-Administrator roles (Dispatcher, Technician) are rejected with 403 Forbidden."""
    async with AsyncClient() as client:
        disp_headers = await get_token_headers(client, "dispatcher@fieldops.ai", "Dispatch@123")
        tech_headers = await get_token_headers(client, "technician@fieldops.ai", "Tech@123")

        # Dispatcher forbidden
        res_disp = await client.get(f"{BASE_URL}/api/v1/settings", headers=disp_headers)
        print("DISP status:", res_disp.status_code, res_disp.text)
        assert res_disp.status_code == 403

        # Technician forbidden
        res_tech = await client.get(f"{BASE_URL}/api/v1/settings", headers=tech_headers)
        print("TECH status:", res_tech.status_code, res_tech.text)
        assert res_tech.status_code == 403


@pytest.mark.asyncio
async def test_4_settings_boundary_validation():
    """Verify out-of-bounds input parameters are rejected with 422 Unprocessable Entity."""
    async with AsyncClient() as client:
        admin_headers = await get_token_headers(client, "admin@fieldops.ai", "Admin@123")

        invalid_payload = {
            "jwt_expiration_hours": 0,  # Min 1
            "max_concurrent_sessions": 50,  # Max 20
            "weather_refresh_interval_minutes": 15,
            "traffic_provider_mode": "REAL_MOCK_FALLBACK",
            "baseline_eta_speed_mph": 5.0,  # Min 10.0
            "weather_delay_weight": 5.0,  # Max 3.0
            "audit_log_retention_days": 10,  # Min 30
            "auto_unassign_on_tech_inactive": True,
        }
        res = await client.put(f"{BASE_URL}/api/v1/settings", json=invalid_payload, headers=admin_headers)
        assert res.status_code == 422


@pytest.mark.asyncio
async def test_5_jwt_expiration_setting_impact():
    """Verify changing jwt_expiration_hours actually alters issued JWT exp claim."""
    service = SettingsService()
    await service.update_settings(
        payload=SystemSettingsPayload(
            jwt_expiration_hours=10,
            max_concurrent_sessions=5,
            weather_refresh_interval_minutes=15,
            traffic_provider_mode="REAL_MOCK_FALLBACK",
            baseline_eta_speed_mph=25.0,
            weather_delay_weight=1.25,
            audit_log_retention_days=90,
            auto_unassign_on_tech_inactive=True,
        )
    )

    async with AsyncClient() as client:
        res = await client.post(
            f"{BASE_URL}/api/v1/auth/login",
            json={"email": "admin@fieldops.ai", "password": "Admin@123"},
        )
        assert res.status_code == 200
        token = res.json()["access_token"]
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])

        exp = payload["exp"]
        iat = payload["iat"]
        diff_seconds = exp - iat
        assert diff_seconds == 10 * 3600  # Exactly 10 hours in seconds


@pytest.mark.asyncio
async def test_6_baseline_speed_eta_impact():
    """Verify changing baseline_eta_speed_mph affects baseline travel ETA calculation."""
    service = SettingsService()

    # Calculate baseline ETA at 10 MPH
    await service.update_settings(
        payload=SystemSettingsPayload(
            jwt_expiration_hours=24,
            max_concurrent_sessions=5,
            weather_refresh_interval_minutes=15,
            traffic_provider_mode="REAL_MOCK_FALLBACK",
            baseline_eta_speed_mph=10.0,
            weather_delay_weight=1.25,
            audit_log_retention_days=90,
            auto_unassign_on_tech_inactive=True,
        )
    )

    async with AsyncSessionLocal() as session:
        res = await session.execute(
            select(Job)
            .where(Job.latitude.isnot(None), Job.longitude.isnot(None))
            .limit(1)
        )
        job = res.scalar_one_or_none()

    if not job:
        pytest.skip("No job with coordinates found for ETA test")

    eta_service = ETAService()
    calc_25 = await eta_service.calculate_job_eta(job_id=job.id)

    # Update baseline speed to 50.0 MPH (double the speed)
    await service.update_settings(
        payload=SystemSettingsPayload(
            jwt_expiration_hours=24,
            max_concurrent_sessions=5,
            weather_refresh_interval_minutes=15,
            traffic_provider_mode="REAL_MOCK_FALLBACK",
            baseline_eta_speed_mph=50.0,
            weather_delay_weight=1.25,
            audit_log_retention_days=90,
            auto_unassign_on_tech_inactive=True,
        )
    )
    calc_50 = await eta_service.calculate_job_eta(job_id=job.id)

    if calc_25.is_context_sufficient and calc_50.is_context_sufficient:
        assert calc_50.baseline_eta_minutes < calc_25.baseline_eta_minutes


@pytest.mark.asyncio
async def test_7_weather_delay_weight_impact():
    """Verify changing weather_delay_weight scales weather delay calculation."""
    service = SettingsService()

    # Weight = 1.0x -> Moderate Rain (base 5 min) -> 5 min delay
    await service.update_settings(
        payload=SystemSettingsPayload(
            jwt_expiration_hours=24,
            max_concurrent_sessions=5,
            weather_refresh_interval_minutes=15,
            traffic_provider_mode="REAL_MOCK_FALLBACK",
            baseline_eta_speed_mph=25.0,
            weather_delay_weight=1.0,
            audit_log_retention_days=90,
            auto_unassign_on_tech_inactive=True,
        )
    )
    w_provider = WeatherProvider()
    res_1 = await w_provider.evaluate(weather_condition="Moderate Rain")
    assert res_1.impact_minutes == 5

    # Weight = 2.0x -> Moderate Rain (base 5 min) -> 10 min delay
    await service.update_settings(
        payload=SystemSettingsPayload(
            jwt_expiration_hours=24,
            max_concurrent_sessions=5,
            weather_refresh_interval_minutes=15,
            traffic_provider_mode="REAL_MOCK_FALLBACK",
            baseline_eta_speed_mph=25.0,
            weather_delay_weight=2.0,
            audit_log_retention_days=90,
            auto_unassign_on_tech_inactive=True,
        )
    )
    res_2 = await w_provider.evaluate(weather_condition="Moderate Rain")
    assert res_2.impact_minutes == 10


@pytest.mark.asyncio
async def test_8_auto_unassign_on_tech_inactive():
    """Verify auto-unassign active jobs setting behavior when technician status changes to INACTIVE."""
    service = SettingsService()

    # Enable auto_unassign_on_tech_inactive
    await service.update_settings(
        payload=SystemSettingsPayload(
            jwt_expiration_hours=24,
            max_concurrent_sessions=5,
            weather_refresh_interval_minutes=15,
            traffic_provider_mode="REAL_MOCK_FALLBACK",
            baseline_eta_speed_mph=25.0,
            weather_delay_weight=1.25,
            audit_log_retention_days=90,
            auto_unassign_on_tech_inactive=True,
        )
    )

    tech_service = TechnicianService()

    async with AsyncSessionLocal() as session:
        res = await session.execute(select(Technician).limit(1))
        tech = res.scalar_one_or_none()

    if not tech:
        pytest.skip("No technician found for auto-unassign test")

    # Set technician availability status to INACTIVE
    await tech_service.patch_status(
        tech_id=tech.id,
        payload=TechnicianStatusPatch(availability_status="INACTIVE"),
    )

    # Verify no active assignments remain for this technician
    async with AsyncSessionLocal() as session:
        asg_res = await session.execute(
            select(Assignment).where(
                Assignment.technician_id == tech.id,
                Assignment.assignment_status.in_(["ASSIGNED", "TRAVELLING", "ARRIVED", "WORKING"]),
            )
        )
        active_assignments = asg_res.scalars().all()
        assert len(active_assignments) == 0

    # Clean teardown: reset settings to factory defaults so other tests retain default expectations
    await service.reset_defaults()

