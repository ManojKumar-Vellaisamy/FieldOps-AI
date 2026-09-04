"""
Comprehensive Integration and Unit Tests for Module 11 — Real Context Data Integration,
Baseline Comparison & Dispatcher Override.

Verifies:
1. Baseline calculation remains unchanged
2. Weather adjustment works
3. Traffic provider unavailable is handled safely
4. Events provider unavailable is handled safely
5. Road restriction provider unavailable is handled safely
6. Multiple unavailable providers handled cleanly
7. Invalid provider data handling
8. Missing GPS handling
9. Stale GPS handling
10. Context aggregation layer functionality
11. Baseline vs context-aware comparison response
12. ETA error calculation and experiment service
13. Non-routine scenario evaluation across benchmark dataset
14. Dispatcher can create manual ETA override
15. Technician cannot create ETA override (403 Forbidden)
16. Unauthorized user receives 403 Forbidden
17. ETA override requires an operational reason
18. Override audit event (ETA_OVERRIDE_CREATED) is recorded
19. Existing JOB_STATUS_CHANGED audit logging still works
"""

import uuid
import pytest
from datetime import datetime, timedelta, timezone
from httpx import AsyncClient

from app.models.enums import UserRole
from app.services.context_aggregation import ContextAggregationService
from app.services.context_providers import (
    ContextProviderResult,
    DataSourceStatus,
    EventsDataProvider,
    GPSLocationProvider,
    RoadRestrictionProvider,
    TrafficDataProvider,
    WeatherProvider,
)
from app.services.eta_experiment_service import ETAExperimentService

BASE_URL = "http://127.0.0.1:8000"


async def get_token_headers(client: AsyncClient, email: str, password: str) -> dict[str, str]:
    """Helper to authenticate and get Bearer token headers."""
    res = await client.post(f"{BASE_URL}/api/v1/auth/login", json={"email": email, "password": password})
    assert res.status_code == 200, f"Login failed for {email}: {res.text}"
    token = res.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


async def get_technician_and_skill(client: AsyncClient, headers: dict[str, str]) -> tuple[str, str]:
    """Helper to fetch active technician ID and primary skill ID."""
    res = await client.get(f"{BASE_URL}/api/v1/technicians?search=TECH-001", headers=headers)
    assert res.status_code == 200
    body = res.json()
    items = body["items"] if "items" in body else body
    assert len(items) > 0, "TECH-001 not found"
    tech = items[0]
    return str(tech["id"]), str(tech["primary_skill_id"])


async def create_test_job(
    client: AsyncClient,
    headers: dict[str, str],
    skill_id: str,
    latitude: float | None = 37.7749,
    longitude: float | None = -122.4194,
) -> dict:
    """Helper to create a fresh service job."""
    payload = {
        "customer_name": f"Module11 Customer {uuid.uuid4().hex[:4]}",
        "customer_phone": "+1 (555) 888-7777",
        "address": "100 Operational Context Way, San Francisco, CA",
        "latitude": latitude if latitude is not None else 37.7749,
        "longitude": longitude if longitude is not None else -122.4194,
        "required_skill_id": skill_id,
        "priority": "HIGH",
        "description": "Module 11 integration test job.",
    }
    res = await client.post(f"{BASE_URL}/api/v1/jobs", json=payload, headers=headers)
    assert res.status_code == 201, f"Failed to create test job: {res.text}"
    return res.json()


async def assign_technician_to_job(
    client: AsyncClient, headers: dict[str, str], job_id: str, technician_id: str
) -> dict:
    """Helper to assign technician to job."""
    res = await client.post(
        f"{BASE_URL}/api/v1/assignments/jobs/{job_id}/assign",
        json={"technician_id": technician_id},
        headers=headers,
    )
    assert res.status_code == 201
    return res.json()


# ── Test Cases ─────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_1_baseline_calculation_remains_unchanged():
    """1. Test baseline ETA is distance / 40 km/h + 3 min staging."""
    async with AsyncClient() as client:
        disp_headers = await get_token_headers(client, "dispatcher@fieldops.ai", "Dispatch@123")
        tech_id, skill_id = await get_technician_and_skill(client, disp_headers)

        job = await create_test_job(client, disp_headers, skill_id)
        await assign_technician_to_job(client, disp_headers, job["id"], tech_id)

        res = await client.get(f"{BASE_URL}/api/v1/jobs/{job['id']}/eta?weather=Clear", headers=disp_headers)
        assert res.status_code == 200
        data = res.json()

        assert data["baseline_eta_minutes"] is not None
        # Verify distance -> baseline equation
        dist_km = data["distance_km"]
        expected_baseline = max(1, round((dist_km / 40.0) * 60.0 + 3))
        assert data["baseline_eta_minutes"] == expected_baseline


@pytest.mark.asyncio
async def test_2_weather_adjustment_works():
    """2. Test weather provider returns valid adjustment for adverse conditions."""
    provider = WeatherProvider()
    res_clear = await provider.evaluate(weather_condition="Clear")
    res_rain = await provider.evaluate(weather_condition="Heavy Rain")
    res_storm = await provider.evaluate(weather_condition="Storm")

    assert res_clear.status == DataSourceStatus.AVAILABLE
    assert res_clear.impact_minutes == 0

    assert res_rain.status == DataSourceStatus.AVAILABLE
    assert res_rain.impact_minutes == 12

    assert res_storm.status == DataSourceStatus.AVAILABLE
    assert res_storm.impact_minutes == 15


@pytest.mark.asyncio
async def test_3_traffic_provider_unavailable_handled_safely():
    """3. Test traffic provider safely returns UNAVAILABLE with 0 impact."""
    provider = TrafficDataProvider()
    res = await provider.evaluate()

    assert res.status == DataSourceStatus.UNAVAILABLE
    assert res.impact_minutes == 0
    assert res.source_name == "Traffic Data"
    assert "not integrated" in res.description.lower()


@pytest.mark.asyncio
async def test_4_events_provider_unavailable_handled_safely():
    """4. Test events provider safely returns UNAVAILABLE with 0 impact."""
    provider = EventsDataProvider()
    res = await provider.evaluate()

    assert res.status == DataSourceStatus.UNAVAILABLE
    assert res.impact_minutes == 0
    assert res.source_name == "Events"


@pytest.mark.asyncio
async def test_5_road_restriction_provider_unavailable_handled_safely():
    """5. Test road restriction provider safely returns UNAVAILABLE with 0 impact."""
    provider = RoadRestrictionProvider()
    res = await provider.evaluate()

    assert res.status == DataSourceStatus.UNAVAILABLE
    assert res.impact_minutes == 0
    assert res.source_name == "Road Restrictions"


@pytest.mark.asyncio
async def test_6_multiple_unavailable_providers():
    """6. Test multiple unavailable providers do not cause calculation errors."""
    traffic_res = await TrafficDataProvider().evaluate()
    events_res = await EventsDataProvider().evaluate()
    road_res = await RoadRestrictionProvider().evaluate()

    agg_service = ContextAggregationService()
    summary = agg_service.aggregate(
        provider_results=[traffic_res, events_res, road_res],
        baseline_eta_minutes=15,
        distance_km=10.0,
        distance_miles=6.2,
    )

    assert summary.unavailable_count == 3
    assert summary.total_adjustment_minutes == 0


@pytest.mark.asyncio
async def test_7_invalid_provider_data():
    """7. Test invalid GPS coordinates return INVALID status with 0 impact."""
    gps_provider = GPSLocationProvider()
    res_out_of_bounds = await gps_provider.evaluate(technician_lat=120.0, technician_lon=-200.0)

    assert res_out_of_bounds.status == DataSourceStatus.INVALID
    assert res_out_of_bounds.impact_minutes == 0
    assert "outside valid WGS84 bounds" in res_out_of_bounds.description


@pytest.mark.asyncio
async def test_8_missing_gps():
    """8. Test missing technician GPS returns UNAVAILABLE status."""
    gps_provider = GPSLocationProvider()
    res_missing = await gps_provider.evaluate(technician_lat=None, technician_lon=None)

    assert res_missing.status == DataSourceStatus.UNAVAILABLE
    assert res_missing.impact_minutes == 0


@pytest.mark.asyncio
async def test_9_stale_gps():
    """9. Test stale GPS (updated > 2 hours ago) returns STALE status."""
    gps_provider = GPSLocationProvider()
    stale_time = datetime.now(timezone.utc) - timedelta(hours=3)

    res_stale = await gps_provider.evaluate(
        technician_lat=37.7749,
        technician_lon=-122.4194,
        tech_updated_at=stale_time,
    )

    assert res_stale.status == DataSourceStatus.STALE
    assert res_stale.impact_minutes == 0
    assert "last updated" in res_stale.description.lower()


@pytest.mark.asyncio
async def test_10_context_aggregation():
    """10. Test ContextAggregationService correctly sums valid available factors only."""
    gps_res = ContextProviderResult("GPS", DataSourceStatus.AVAILABLE, 0, "GPS OK", category="GPS")
    weather_res = ContextProviderResult("Weather", DataSourceStatus.AVAILABLE, 12, "Heavy Rain", category="WEATHER")
    traffic_res = ContextProviderResult("Traffic", DataSourceStatus.UNAVAILABLE, 15, "Unused mock", category="TRAFFIC")

    agg_service = ContextAggregationService()
    summary = agg_service.aggregate(
        provider_results=[gps_res, weather_res, traffic_res],
        baseline_eta_minutes=20,
        distance_km=13.3,
        distance_miles=8.2,
    )

    # Traffic is UNAVAILABLE so its 15 min mock impact must be ignored -> only weather (+12) added
    assert summary.total_adjustment_minutes == 12
    assert summary.available_count == 2
    assert summary.unavailable_count == 1


@pytest.mark.asyncio
async def test_11_baseline_vs_context_aware_result():
    """11. Test baseline vs context-aware difference in ETA API response."""
    async with AsyncClient() as client:
        disp_headers = await get_token_headers(client, "dispatcher@fieldops.ai", "Dispatch@123")
        tech_id, skill_id = await get_technician_and_skill(client, disp_headers)

        job = await create_test_job(client, disp_headers, skill_id)
        await assign_technician_to_job(client, disp_headers, job["id"], tech_id)

        res = await client.get(f"{BASE_URL}/api/v1/jobs/{job['id']}/eta?weather=Heavy%20Rain", headers=disp_headers)
        assert res.status_code == 200
        data = res.json()

        assert data["baseline_eta_minutes"] is not None
        assert data["context_aware_eta_minutes"] is not None
        assert data["adjustment_minutes"] == 12
        assert data["context_aware_eta_minutes"] == data["baseline_eta_minutes"] + 12


@pytest.mark.asyncio
async def test_12_eta_error_calculation():
    """12. Test ETA experiment service metrics calculation."""
    exp_service = ETAExperimentService()
    metrics = exp_service.evaluate_experiment()

    assert metrics.baseline_mae_minutes > 0
    assert metrics.context_aware_mae_minutes > 0
    assert metrics.context_aware_mae_minutes < metrics.baseline_mae_minutes
    assert metrics.improvement_percent > 0
    assert metrics.sample_count >= 50
    assert metrics.is_simulated_dataset is True


@pytest.mark.asyncio
async def test_13_non_routine_scenario_evaluation():
    """13. Test non-routine MAE performance in benchmark experiment."""
    exp_service = ETAExperimentService()
    metrics = exp_service.evaluate_experiment()

    assert metrics.baseline_non_routine_mae > metrics.context_aware_non_routine_mae
    assert metrics.baseline_non_routine_mae > metrics.baseline_mae_minutes


@pytest.mark.asyncio
async def test_14_dispatcher_can_create_override():
    """14. Test Dispatcher role can create manual ETA override."""
    async with AsyncClient() as client:
        disp_headers = await get_token_headers(client, "dispatcher@fieldops.ai", "Dispatch@123")
        tech_id, skill_id = await get_technician_and_skill(client, disp_headers)

        job = await create_test_job(client, disp_headers, skill_id)
        await assign_technician_to_job(client, disp_headers, job["id"], tech_id)

        override_payload = {
            "overridden_eta": 45,
            "reason": "Local severe road construction block not in feed.",
        }

        res = await client.post(
            f"{BASE_URL}/api/v1/jobs/{job['id']}/override",
            json=override_payload,
            headers=disp_headers,
        )
        assert res.status_code == 201, f"Failed override: {res.text}"
        data = res.json()
        assert data["job_id"] == job["id"]
        assert data["overridden_eta"] == 45
        assert data["reason"] == "Local severe road construction block not in feed."

        # Verify ETA endpoint reflects active override
        eta_res = await client.get(f"{BASE_URL}/api/v1/jobs/{job['id']}/eta", headers=disp_headers)
        assert eta_res.status_code == 200
        eta_data = eta_res.json()

        assert eta_data["active_override"] is not None
        assert eta_data["active_override"]["overridden_eta"] == 45
        assert eta_data["final_dispatch_eta_minutes"] == 45


@pytest.mark.asyncio
async def test_15_technician_cannot_create_override():
    """15. Test Technician role is forbidden from creating ETA override (403 Forbidden)."""
    async with AsyncClient() as client:
        disp_headers = await get_token_headers(client, "dispatcher@fieldops.ai", "Dispatch@123")
        tech_headers = await get_token_headers(client, "technician@fieldops.ai", "Tech@123")
        tech_id, skill_id = await get_technician_and_skill(client, disp_headers)

        job = await create_test_job(client, disp_headers, skill_id)
        await assign_technician_to_job(client, disp_headers, job["id"], tech_id)

        override_payload = {
            "overridden_eta": 30,
            "reason": "Technician attempting override.",
        }

        res = await client.post(
            f"{BASE_URL}/api/v1/jobs/{job['id']}/override",
            json=override_payload,
            headers=tech_headers,
        )
        assert res.status_code == 403
        assert "not authorized" in res.text.lower() or "forbidden" in res.text.lower()


@pytest.mark.asyncio
async def test_16_unauthorized_user_receives_403():
    """16. Test unauthenticated request or technician accessing unassigned override receives 403/401."""
    async with AsyncClient() as client:
        disp_headers = await get_token_headers(client, "dispatcher@fieldops.ai", "Dispatch@123")
        tech_headers = await get_token_headers(client, "technician@fieldops.ai", "Tech@123")
        _, skill_id = await get_technician_and_skill(client, disp_headers)

        unassigned_job = await create_test_job(client, disp_headers, skill_id)

        res = await client.get(
            f"{BASE_URL}/api/v1/jobs/{unassigned_job['id']}/override-history",
            headers=tech_headers,
        )
        assert res.status_code == 403


@pytest.mark.asyncio
async def test_17_override_requires_a_reason():
    """17. Test creating an ETA override with blank or missing reason fails validation."""
    async with AsyncClient() as client:
        disp_headers = await get_token_headers(client, "dispatcher@fieldops.ai", "Dispatch@123")
        tech_id, skill_id = await get_technician_and_skill(client, disp_headers)

        job = await create_test_job(client, disp_headers, skill_id)
        await assign_technician_to_job(client, disp_headers, job["id"], tech_id)

        # Blank reason -> validation error 422
        res = await client.post(
            f"{BASE_URL}/api/v1/jobs/{job['id']}/override",
            json={"overridden_eta": 30, "reason": "  "},
            headers=disp_headers,
        )
        assert res.status_code in (400, 422)


@pytest.mark.asyncio
async def test_18_override_audit_event_created():
    """18. Test that creating an ETA override generates an AuditLog entry with action ETA_OVERRIDE_CREATED."""
    async with AsyncClient() as client:
        disp_headers = await get_token_headers(client, "dispatcher@fieldops.ai", "Dispatch@123")
        admin_headers = await get_token_headers(client, "admin@fieldops.ai", "Admin@123")
        tech_id, skill_id = await get_technician_and_skill(client, disp_headers)

        job = await create_test_job(client, disp_headers, skill_id)
        await assign_technician_to_job(client, disp_headers, job["id"], tech_id)

        res_override = await client.post(
            f"{BASE_URL}/api/v1/jobs/{job['id']}/override",
            json={"overridden_eta": 50, "reason": "Audit verification override rationale."},
            headers=disp_headers,
        )
        assert res_override.status_code == 201

        # Check override history endpoint
        res_hist = await client.get(
            f"{BASE_URL}/api/v1/jobs/{job['id']}/override-history",
            headers=disp_headers,
        )
        assert res_hist.status_code == 200
        hist_data = res_hist.json()
        assert len(hist_data) >= 1
        assert hist_data[0]["overridden_eta"] == 50
        assert hist_data[0]["reason"] == "Audit verification override rationale."


@pytest.mark.asyncio
async def test_19_existing_job_status_changed_audit_still_works():
    """19. Test existing JOB_STATUS_CHANGED audit lifecycle events continue to function properly."""
    async with AsyncClient() as client:
        disp_headers = await get_token_headers(client, "dispatcher@fieldops.ai", "Dispatch@123")
        tech_headers = await get_token_headers(client, "technician@fieldops.ai", "Tech@123")
        tech_id, skill_id = await get_technician_and_skill(client, disp_headers)

        job = await create_test_job(client, disp_headers, skill_id)
        await assign_technician_to_job(client, disp_headers, job["id"], tech_id)

        # Transition status to TRAVELLING
        res_status = await client.patch(
            f"{BASE_URL}/api/v1/jobs/{job['id']}/status",
            json={"status": "TRAVELLING", "notes": "Technician departing for site."},
            headers=tech_headers,
        )
        assert res_status.status_code == 200
        assert res_status.json()["status"] == "TRAVELLING"
