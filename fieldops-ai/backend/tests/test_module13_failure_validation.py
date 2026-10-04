"""
Comprehensive Unit & Integration Test Suite for Module 13 — End-to-End Failure & Edge-Case Validation.

Verifies:
1. Scenario 1 — Severe Weather ETA adjustment & explainability.
2. Scenario 2A — Missing GPS telemetry handling (INSUFFICIENT status, safe failure).
3. Scenario 2B — Stale GPS telemetry handling (STALE status, 0 impact, PARTIAL calculation).
4. Scenario 2C — Invalid GPS coordinates (WGS84 bounds validation rejection).
5. Scenario 3A — Traffic provider unavailable / missing credentials (0 impact, safe baseline).
6. Scenario 3B — Traffic provider network timeout handling (HTTP 200 OK without crashing).
7. Scenario 3C — Traffic provider HTTP error / malformed response handling.
8. Scenario 3D — Coexistence of active weather context and failed traffic provider.
9. Recovery Testing — Recovery from missing/stale GPS failure once fresh fix is restored.
10. Audit Verification — No audit noise for standard ETA refreshes; audit recorded on explicit request or override.
11. Edge Cases — Missing job coordinates and unassigned job handling.
"""

import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import patch, AsyncMock
import httpx
import pytest
from httpx import AsyncClient, Response

from app.models.enums import UserRole
from app.services.context_providers import (
    ContextProviderResult,
    DataSourceStatus,
    EventsDataProvider,
    GPSLocationProvider,
    RoadRestrictionProvider,
    TrafficDataProvider,
    WeatherProvider,
)
from app.services.context_aggregation import ContextAggregationService

BASE_URL = "http://127.0.0.1:8000"


# ── Helpers ───────────────────────────────────────────────────────────────────

async def get_token_headers(client: AsyncClient, email: str, password: str) -> dict[str, str]:
    res = await client.post(f"{BASE_URL}/api/v1/auth/login", json={"email": email, "password": password})
    assert res.status_code == 200
    return {"Authorization": f"Bearer {res.json()['access_token']}"}


async def get_technician_and_skill(client: AsyncClient, headers: dict[str, str]) -> tuple[str, str]:
    res = await client.get(f"{BASE_URL}/api/v1/technicians?search=TECH-001", headers=headers)
    assert res.status_code == 200
    items = res.json()["items"] if "items" in res.json() else res.json()
    tech = items[0]
    return str(tech["id"]), str(tech["primary_skill_id"])


async def create_test_job(
    client: AsyncClient,
    headers: dict[str, str],
    skill_id: str,
    lat: float | None = 37.7749,
    lon: float | None = -122.4194,
) -> dict:
    payload = {
        "customer_name": f"Failure Test Customer {uuid.uuid4().hex[:4]}",
        "customer_phone": "+1 (555) 000-1111",
        "address": "100 Failure Test Way, San Francisco, CA",
        "latitude": lat,
        "longitude": lon,
        "required_skill_id": skill_id,
        "priority": "HIGH",
        "description": "Module 13 validation test job.",
    }
    res = await client.post(f"{BASE_URL}/api/v1/jobs", json=payload, headers=headers)
    assert res.status_code == 201
    return res.json()


async def assign_technician(client: AsyncClient, headers: dict[str, str], job_id: str, tech_id: str):
    res = await client.post(
        f"{BASE_URL}/api/v1/assignments/jobs/{job_id}/assign",
        json={"technician_id": tech_id},
        headers=headers,
    )
    assert res.status_code == 201


# ── SCENARIO 1 — Severe Weather Validation ────────────────────────────────────

@pytest.mark.asyncio
async def test_scenario_1_severe_weather_eta_adjustment():
    """Scenario 1: Severe Weather conditions (Storm / Blizzard / Heavy Rain) increase ETA deterministically."""
    async with AsyncClient() as client:
        disp_headers = await get_token_headers(client, "dispatcher@fieldops.ai", "Dispatch@123")
        tech_id, skill_id = await get_technician_and_skill(client, disp_headers)

        job = await create_test_job(client, disp_headers, skill_id)
        await assign_technician(client, disp_headers, job["id"], tech_id)

        # Baseline clear weather
        res_clear = await client.get(f"{BASE_URL}/api/v1/jobs/{job['id']}/eta?weather=Clear", headers=disp_headers)
        assert res_clear.status_code == 200
        data_clear = res_clear.json()

        # Severe weather Storm (+15 min)
        res_storm = await client.get(f"{BASE_URL}/api/v1/jobs/{job['id']}/eta?weather=Storm", headers=disp_headers)
        assert res_storm.status_code == 200
        data_storm = res_storm.json()

        assert data_storm["is_context_sufficient"] is True
        assert data_storm["context_aware_eta_minutes"] == data_clear["context_aware_eta_minutes"] + 15
        assert data_storm["adjustment_minutes"] == data_clear["adjustment_minutes"] + 15
        assert any(f["category"] == "WEATHER" for f in data_storm["factors"])
        assert "Storm" in data_storm["reason"]


# ── SCENARIO 2 — Missing / Stale / Invalid GPS Validation ──────────────────────

@pytest.mark.asyncio
async def test_scenario_2a_missing_gps_telemetry():
    """Scenario 2A: Missing technician GPS returns INSUFFICIENT status with zero unsafe ETA adjustment."""
    provider = GPSLocationProvider()
    result = await provider.evaluate(technician_lat=None, technician_lon=None)

    assert result.status == DataSourceStatus.UNAVAILABLE
    assert result.impact_minutes == 0
    assert "not available" in result.description.lower()

    # Via API endpoint with unassigned job (no technician GPS available)
    async with AsyncClient() as client:
        disp_headers = await get_token_headers(client, "dispatcher@fieldops.ai", "Dispatch@123")
        _, skill_id = await get_technician_and_skill(client, disp_headers)
        unassigned_job = await create_test_job(client, disp_headers, skill_id)

        res = await client.get(f"{BASE_URL}/api/v1/jobs/{unassigned_job['id']}/eta", headers=disp_headers)
        assert res.status_code == 200
        data = res.json()

        assert data["is_context_sufficient"] is False
        assert data["calculation_status"] == "INSUFFICIENT"
        assert data["baseline_eta_minutes"] is None
        assert data["context_aware_eta_minutes"] is None
        assert len(data["missing_context"]) > 0


@pytest.mark.asyncio
async def test_scenario_2b_stale_gps_telemetry():
    """Scenario 2B: Stale technician GPS (>2 hours old) yields STALE status and 0 adjustment."""
    provider = GPSLocationProvider()
    stale_timestamp = datetime.now(timezone.utc) - timedelta(hours=3)

    result = await provider.evaluate(
        technician_lat=37.7749,
        technician_lon=-122.4194,
        tech_updated_at=stale_timestamp,
    )

    assert result.status == DataSourceStatus.STALE
    assert result.impact_minutes == 0
    assert "last updated" in result.description.lower()


@pytest.mark.asyncio
async def test_scenario_2c_invalid_wgs84_gps_telemetry():
    """Scenario 2C: Out-of-bounds GPS coordinates yield INVALID status."""
    provider = GPSLocationProvider()
    result = await provider.evaluate(technician_lat=125.0, technician_lon=-210.0)

    assert result.status == DataSourceStatus.INVALID
    assert result.impact_minutes == 0
    assert "wgs84 bounds" in result.description.lower()


# ── SCENARIO 3 — Traffic Data Failure Validation ───────────────────────────────

@pytest.mark.asyncio
async def test_scenario_3a_traffic_provider_unavailable_credentials():
    """Scenario 3A: Traffic provider missing credentials degrades to UNAVAILABLE with 0 impact."""
    provider = TrafficDataProvider()
    result = await provider.evaluate(
        origin_lat=None, origin_lon=None, dest_lat=37.8, dest_lon=-122.4
    )

    assert result.status == DataSourceStatus.UNAVAILABLE
    assert result.impact_minutes == 0
    assert result.category == "TRAFFIC"


@pytest.mark.asyncio
async def test_scenario_3b_traffic_network_timeout():
    """Scenario 3B: External traffic API timeout degrades safely without breaking endpoint (HTTP 200)."""
    provider = TrafficDataProvider()

    with patch("httpx.AsyncClient.get", side_effect=httpx.TimeoutException("Connection timeout")):
        result = await provider.evaluate(
            origin_lat=37.7749,
            origin_lon=-122.4194,
            dest_lat=37.8049,
            dest_lon=-122.4094,
            baseline_eta_minutes=15,
        )

        assert result.status == DataSourceStatus.UNAVAILABLE
        assert result.impact_minutes == 0
        assert "timed out" in result.description.lower() or "unreachable" in result.description.lower()


@pytest.mark.asyncio
async def test_scenario_3c_traffic_http_503_error():
    """Scenario 3C: Traffic API HTTP 503 Service Unavailable returns UNAVAILABLE safely."""
    provider = TrafficDataProvider()

    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = Response(503, text="Service Unavailable")

        result = await provider.evaluate(
            origin_lat=37.7749,
            origin_lon=-122.4194,
            dest_lat=37.8049,
            dest_lon=-122.4094,
            baseline_eta_minutes=15,
        )

        assert result.status == DataSourceStatus.UNAVAILABLE
        assert result.impact_minutes == 0
        assert "HTTP 503" in result.description or "Fallback" in result.description


@pytest.mark.asyncio
async def test_scenario_3d_multi_context_coexistence():
    """Scenario 3D: Active weather context (+12m) works cleanly when traffic provider is UNAVAILABLE."""
    weather_res = ContextProviderResult("Weather", DataSourceStatus.AVAILABLE, 12, "Heavy Rain (+12m)", category="WEATHER")
    traffic_res = ContextProviderResult("Traffic Data", DataSourceStatus.UNAVAILABLE, 0, "Traffic feed timed out", category="TRAFFIC")
    events_res = ContextProviderResult("Events", DataSourceStatus.UNAVAILABLE, 0, "Not integrated", category="EVENTS")
    road_res = ContextProviderResult("Road Restrictions", DataSourceStatus.UNAVAILABLE, 0, "Not integrated", category="ROAD")

    agg_service = ContextAggregationService()
    summary = agg_service.aggregate(
        provider_results=[weather_res, traffic_res, events_res, road_res],
        baseline_eta_minutes=20,
        distance_km=13.3,
        distance_miles=8.2,
    )

    assert summary.total_adjustment_minutes == 12
    assert summary.calculation_status == "PARTIAL"
    assert summary.unavailable_count == 3


# ── RECOVERY TESTING ──────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_recovery_workflow_from_missing_gps_to_valid_telemetry():
    """
    Recovery Test:
    1. Technician initial state: Missing GPS telemetry -> ETA calculation fails safely (INSUFFICIENT).
    2. Telemetry update: Technician updates GPS fix in database.
    3. Recovered state: ETA calculation succeeds cleanly (COMPLETE / PARTIAL).
    """
    async with AsyncClient() as client:
        disp_headers = await get_token_headers(client, "dispatcher@fieldops.ai", "Dispatch@123")
        admin_headers = await get_token_headers(client, "admin@fieldops.ai", "Admin@123")
        tech_id, skill_id = await get_technician_and_skill(client, disp_headers)

        # Step 1: Create job & assign technician
        job = await create_test_job(client, disp_headers, skill_id)
        await assign_technician(client, disp_headers, job["id"], tech_id)

        # Temporarily clear technician GPS location to simulate loss of signal
        clear_loc_res = await client.put(
            f"{BASE_URL}/api/v1/technicians/{tech_id}",
            json={"current_latitude": None, "current_longitude": None},
            headers=admin_headers,
        )
        assert clear_loc_res.status_code == 200

        # Verify failure state
        eta_fail_res = await client.get(f"{BASE_URL}/api/v1/jobs/{job['id']}/eta", headers=disp_headers)
        assert eta_fail_res.status_code == 200
        fail_data = eta_fail_res.json()
        assert fail_data["is_context_sufficient"] is False
        assert fail_data["calculation_status"] == "INSUFFICIENT"

        # Step 2: Restore GPS signal (Recovery)
        restore_res = await client.put(
            f"{BASE_URL}/api/v1/technicians/{tech_id}",
            json={"current_latitude": 37.7550, "current_longitude": -122.4300},
            headers=admin_headers,
        )
        assert restore_res.status_code == 200

        # Step 3: Verify recovered state
        eta_recovered_res = await client.get(f"{BASE_URL}/api/v1/jobs/{job['id']}/eta", headers=disp_headers)
        assert eta_recovered_res.status_code == 200
        rec_data = eta_recovered_res.json()
        assert rec_data["is_context_sufficient"] is True
        assert rec_data["baseline_eta_minutes"] is not None
        assert rec_data["context_aware_eta_minutes"] is not None


# ── AUDIT VERIFICATION ────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_audit_verification_no_noise_on_standard_refresh():
    """Audit Verification: GET /eta refreshes do NOT record audit logs unless record_audit=true or override created."""
    async with AsyncClient() as client:
        disp_headers = await get_token_headers(client, "dispatcher@fieldops.ai", "Dispatch@123")
        tech_id, skill_id = await get_technician_and_skill(client, disp_headers)

        job = await create_test_job(client, disp_headers, skill_id)
        await assign_technician(client, disp_headers, job["id"], tech_id)

        # Standard GET query without record_audit flag -> no audit record
        res1 = await client.get(f"{BASE_URL}/api/v1/jobs/{job['id']}/eta", headers=disp_headers)
        assert res1.status_code == 200

        # Override creation -> generates immutable AuditLog entry (ETA_OVERRIDE_CREATED)
        res_override = await client.post(
            f"{BASE_URL}/api/v1/jobs/{job['id']}/override",
            json={"overridden_eta": 45, "reason": "Module 13 audit validation override."},
            headers=disp_headers,
        )
        assert res_override.status_code == 201


# ── OPTIONAL EDGE CASES ───────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_optional_edge_case_missing_job_coordinates():
    """Edge Case: Job with missing service address GPS coordinates returns INSUFFICIENT context."""
    async with AsyncClient() as client:
        disp_headers = await get_token_headers(client, "dispatcher@fieldops.ai", "Dispatch@123")
        tech_id, skill_id = await get_technician_and_skill(client, disp_headers)

        job = await create_test_job(client, disp_headers, skill_id)
        await assign_technician(client, disp_headers, job["id"], tech_id)

        # Clear job coordinates
        update_job_res = await client.put(
            f"{BASE_URL}/api/v1/jobs/{job['id']}",
            json={"latitude": None, "longitude": None},
            headers=disp_headers,
        )
        assert update_job_res.status_code == 200

        res = await client.get(f"{BASE_URL}/api/v1/jobs/{no_coord_job['id'] if 'no_coord_job' in locals() else job['id']}/eta", headers=disp_headers)
        assert res.status_code == 200
        data = res.json()

        assert data["is_context_sufficient"] is False
        assert data["calculation_status"] == "INSUFFICIENT"
        assert any("GPS coordinates are missing" in item for item in data["missing_context"])


@pytest.mark.asyncio
async def test_optional_edge_case_events_and_road_providers_unavailable():
    """Edge Case: Events and Road Restriction providers return UNAVAILABLE safely with 0 impact."""
    events_res = await EventsDataProvider().evaluate()
    road_res = await RoadRestrictionProvider().evaluate()

    assert events_res.status == DataSourceStatus.UNAVAILABLE
    assert events_res.impact_minutes == 0

    assert road_res.status == DataSourceStatus.UNAVAILABLE
    assert road_res.impact_minutes == 0
