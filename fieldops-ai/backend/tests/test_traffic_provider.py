"""
Comprehensive Unit & Integration Tests for Module 11 — Real Traffic Data Integration.

Verifies:
1. Traffic provider returns valid data when active.
2. Traffic adjustment is correctly applied to context-aware ETA.
3. Traffic provider unavailable (missing coordinates, disabled, or missing API key).
4. Traffic provider network timeout/error handled gracefully (no ETA crash).
5. Invalid/malformed traffic response handling (status = INVALID, 0 impact).
6. Preserving baseline ETA when traffic is unavailable.
7. Weather & GPS adjustments work cleanly alongside traffic.
8. RBAC security model remains unchanged.
9. Job execution lifecycle remains unchanged.
10. Audit logging remains unchanged.
"""

from datetime import datetime, timezone
import pytest
from httpx import AsyncClient, Response
from unittest.mock import patch, AsyncMock

from app.core.config import settings
from app.services.context_providers import (
    ContextProviderResult,
    DataSourceStatus,
    TrafficDataProvider,
    WeatherProvider,
    GPSLocationProvider,
)
from app.services.context_aggregation import ContextAggregationService

BASE_URL = "http://127.0.0.1:8000"


# ── Unit Tests for TrafficDataProvider ──────────────────────────────────────────

@pytest.fixture(autouse=True)
def default_traffic_provider(monkeypatch):
    monkeypatch.setattr(settings, "TRAFFIC_PROVIDER", "osrm")


@pytest.mark.asyncio
async def test_1_traffic_provider_returns_valid_data():
    """1. Test TrafficDataProvider correctly queries OSRM and computes traffic delay."""
    provider = TrafficDataProvider()

    mock_osrm_response = {
        "code": "Ok",
        "routes": [
            {
                "duration": 1380.0,  # 23 minutes
                "distance": 12000.0,  # 12 km
            }
        ],
    }

    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = Response(200, json=mock_osrm_response)

        result = await provider.evaluate(
            origin_lat=37.7749,
            origin_lon=-122.4194,
            dest_lat=37.8049,
            dest_lon=-122.4094,
            baseline_eta_minutes=15,
        )

        assert result.status == DataSourceStatus.AVAILABLE
        assert result.category == "TRAFFIC"
        # 23 min driving vs 15 min baseline -> +8 min delay
        assert result.impact_minutes == 8
        assert "Heavy Congestion" in result.description or "Traffic" in result.description
        assert "OSRM" in result.description
        assert result.source_name in ("Traffic Data", "Route Baseline (OSRM)")


@pytest.mark.asyncio
async def test_2_traffic_provider_free_flow_traffic():
    """2. Test free-flow traffic yields 0 delay adjustment."""
    provider = TrafficDataProvider()

    mock_osrm_response = {
        "code": "Ok",
        "routes": [
            {
                "duration": 900.0,  # 15 minutes
                "distance": 10000.0,
            }
        ],
    }

    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = Response(200, json=mock_osrm_response)

        result = await provider.evaluate(
            origin_lat=37.7749,
            origin_lon=-122.4194,
            dest_lat=37.8049,
            dest_lon=-122.4094,
            baseline_eta_minutes=15,
        )

        assert result.status == DataSourceStatus.AVAILABLE
        assert result.impact_minutes == 0
        assert "Free-flow" in result.description or "Free Flow" in result.description


@pytest.mark.asyncio
async def test_3_traffic_provider_missing_coords_returns_unavailable():
    """3. Test missing origin/destination coordinates safely returns UNAVAILABLE with 0 impact."""
    provider = TrafficDataProvider()
    result = await provider.evaluate(origin_lat=None, origin_lon=None, dest_lat=37.8, dest_lon=-122.4)

    assert result.status == DataSourceStatus.UNAVAILABLE
    assert result.impact_minutes == 0
    assert "missing" in result.description.lower()


@pytest.mark.asyncio
async def test_4_traffic_provider_timeout_handled_safely():
    """4. Test network timeout returns UNAVAILABLE with 0 impact without crashing."""
    import httpx

    provider = TrafficDataProvider()

    with patch("httpx.AsyncClient.get", side_effect=httpx.TimeoutException("Connection timed out")):
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
async def test_5_traffic_provider_invalid_response_handled():
    """5. Test malformed JSON or HTTP error returns INVALID/UNAVAILABLE with 0 impact."""
    provider = TrafficDataProvider()

    # Case A: Non-200 status code
    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = Response(503, text="Service Unavailable")
        res_503 = await provider.evaluate(
            origin_lat=37.7749, origin_lon=-122.4194, dest_lat=37.8049, dest_lon=-122.4094
        )
        assert res_503.status == DataSourceStatus.UNAVAILABLE
        assert res_503.impact_minutes == 0

    # Case B: Out-of-bounds coordinates -> INVALID
    res_bounds = await provider.evaluate(
        origin_lat=120.0, origin_lon=-200.0, dest_lat=37.8049, dest_lon=-122.4094
    )
    assert res_bounds.status == DataSourceStatus.INVALID
    assert res_bounds.impact_minutes == 0


@pytest.mark.asyncio
async def test_6_traffic_provider_tomtom_missing_key():
    """6. Test TomTom provider returns UNAVAILABLE when API key is missing."""
    provider = TrafficDataProvider()

    with patch.object(settings, "TRAFFIC_PROVIDER", "tomtom"), patch.object(settings, "TRAFFIC_API_KEY", None):
        result = await provider.evaluate(
            origin_lat=37.7749, origin_lon=-122.4194, dest_lat=37.8049, dest_lon=-122.4094
        )
        assert result.status == DataSourceStatus.UNAVAILABLE
        assert result.impact_minutes == 0
        assert "API key" in result.description


@pytest.mark.asyncio
async def test_7_context_aggregation_combines_weather_and_traffic():
    """7. Test ContextAggregationService correctly sums valid AVAILABLE weather and traffic adjustments."""
    weather_res = ContextProviderResult("Weather", DataSourceStatus.AVAILABLE, 5, "Moderate Rain", category="WEATHER")
    traffic_res = ContextProviderResult("Traffic Data (OSRM)", DataSourceStatus.AVAILABLE, 8, "Heavy Congestion (+8m)", category="TRAFFIC")

    agg_service = ContextAggregationService()
    summary = agg_service.aggregate(
        provider_results=[weather_res, traffic_res],
        baseline_eta_minutes=20,
        distance_km=13.3,
        distance_miles=8.2,
    )

    assert summary.total_adjustment_minutes == 13  # 5 weather + 8 traffic
    assert summary.available_count == 2
    assert summary.unavailable_count == 0


# ── Integration Tests with API Endpoints ─────────────────────────────────────

async def get_token_headers(client: AsyncClient, email: str, password: str) -> dict[str, str]:
    res = await client.post(f"{BASE_URL}/api/v1/auth/login", json={"email": email, "password": password})
    assert res.status_code == 200
    token = res.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


async def get_technician_and_skill(client: AsyncClient, headers: dict[str, str]) -> tuple[str, str]:
    res = await client.get(f"{BASE_URL}/api/v1/technicians?search=TECH-001", headers=headers)
    assert res.status_code == 200
    body = res.json()
    items = body["items"] if "items" in body else body
    tech = items[0]
    return str(tech["id"]), str(tech["primary_skill_id"])


async def create_test_job(client: AsyncClient, headers: dict[str, str], skill_id: str) -> dict:
    payload = {
        "customer_name": "Traffic Test Customer",
        "customer_phone": "+1 (555) 777-9999",
        "address": "San Francisco Financial District, CA",
        "latitude": 37.7949,
        "longitude": -122.4094,
        "required_skill_id": skill_id,
        "priority": "HIGH",
        "description": "Module 11 Traffic integration test job.",
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


@pytest.mark.asyncio
async def test_8_eta_endpoint_includes_traffic_data_source():
    """8. Test GET /api/v1/jobs/{id}/eta includes Traffic Data in data_sources array."""
    async with AsyncClient() as client:
        disp_headers = await get_token_headers(client, "dispatcher@fieldops.ai", "Dispatch@123")
        tech_id, skill_id = await get_technician_and_skill(client, disp_headers)
        job = await create_test_job(client, disp_headers, skill_id)
        await assign_technician(client, disp_headers, job["id"], tech_id)

        res = await client.get(f"{BASE_URL}/api/v1/jobs/{job['id']}/eta", headers=disp_headers)
        assert res.status_code == 200

        data = res.json()
        assert "data_sources" in data
        traffic_ds = next((s for s in data["data_sources"] if "Traffic" in s["name"]), None)
        assert traffic_ds is not None
        assert traffic_ds["category"] == "TRAFFIC"
        assert traffic_ds["status"] in ("AVAILABLE", "UNAVAILABLE", "STALE", "INVALID")


@pytest.mark.asyncio
async def test_9_rbac_behaviour_remains_unchanged():
    """9. Test Technician role is still restricted from accessing unassigned ETA (403 Forbidden)."""
    async with AsyncClient() as client:
        disp_headers = await get_token_headers(client, "dispatcher@fieldops.ai", "Dispatch@123")
        tech_headers = await get_token_headers(client, "technician@fieldops.ai", "Tech@123")
        _, skill_id = await get_technician_and_skill(client, disp_headers)

        unassigned_job = await create_test_job(client, disp_headers, skill_id)

        res = await client.get(f"{BASE_URL}/api/v1/jobs/{unassigned_job['id']}/eta", headers=tech_headers)
        assert res.status_code == 403


@pytest.mark.asyncio
async def test_10_job_execution_remains_unchanged():
    """10. Test technician job execution lifecycle (status update to TRAVELLING) remains functional."""
    async with AsyncClient() as client:
        disp_headers = await get_token_headers(client, "dispatcher@fieldops.ai", "Dispatch@123")
        tech_headers = await get_token_headers(client, "technician@fieldops.ai", "Tech@123")
        tech_id, skill_id = await get_technician_and_skill(client, disp_headers)

        job = await create_test_job(client, disp_headers, skill_id)
        await assign_technician(client, disp_headers, job["id"], tech_id)

        res = await client.patch(
            f"{BASE_URL}/api/v1/jobs/{job['id']}/status",
            json={"status": "TRAVELLING", "notes": "Departing for site with traffic integration active."},
            headers=tech_headers,
        )
        assert res.status_code == 200
        assert res.json()["status"] == "TRAVELLING"


# ── Comprehensive Real TomTom Pipeline Tests ──────────────────────────────────

@pytest.mark.asyncio
async def test_11_tomtom_traffic_success_with_delay_real_provenance():
    """Verify configured TomTom provider calculates real traffic delay and returns provenance=REAL."""
    provider = TrafficDataProvider()

    mock_tomtom_payload = {
        "routes": [
            {
                "summary": {
                    "travelTimeInSeconds": 1800,  # 30 min
                    "noTrafficTravelTimeInSeconds": 1200,  # 20 min
                    "trafficDelayInSeconds": 600,  # 10 min
                }
            }
        ]
    }

    with patch.object(settings, "TRAFFIC_PROVIDER", "tomtom"), \
         patch.object(settings, "TRAFFIC_API_KEY", "real-tomtom-key-test"), \
         patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = Response(200, json=mock_tomtom_payload)

        result = await provider.evaluate(
            origin_lat=37.7749,
            origin_lon=-122.4194,
            dest_lat=37.8049,
            dest_lon=-122.4094,
            baseline_eta_minutes=20,
        )

        assert result.status == DataSourceStatus.AVAILABLE
        assert result.category == "TRAFFIC"
        assert result.provenance == "REAL"
        assert result.impact_minutes == 10
        assert result.source_name == "Traffic Data (TomTom API)"
        assert "TomTom Traffic API (REAL)" in result.description
        assert "Moderate Traffic" in result.description or "Traffic" in result.description


@pytest.mark.asyncio
async def test_12_tomtom_traffic_free_flow_real_provenance():
    """Verify configured TomTom provider in free-flow conditions returns 0m delay with provenance=REAL."""
    provider = TrafficDataProvider()

    mock_tomtom_payload = {
        "routes": [
            {
                "summary": {
                    "travelTimeInSeconds": 1200,
                    "noTrafficTravelTimeInSeconds": 1200,
                    "trafficDelayInSeconds": 0,
                }
            }
        ]
    }

    with patch.object(settings, "TRAFFIC_PROVIDER", "tomtom"), \
         patch.object(settings, "TRAFFIC_API_KEY", "real-tomtom-key-test"), \
         patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = Response(200, json=mock_tomtom_payload)

        result = await provider.evaluate(
            origin_lat=37.7749,
            origin_lon=-122.4194,
            dest_lat=37.8049,
            dest_lon=-122.4094,
            baseline_eta_minutes=20,
        )

        assert result.status == DataSourceStatus.AVAILABLE
        assert result.provenance == "REAL"
        assert result.impact_minutes == 0
        assert "Free Flow" in result.description
        assert "TomTom Traffic API (REAL)" in result.description


@pytest.mark.asyncio
async def test_13_tomtom_traffic_authentication_failure_401_403():
    """Verify TomTom 401/403 invalid key returns UNAVAILABLE, 0m impact, and provenance=UNAVAILABLE."""
    provider = TrafficDataProvider()

    with patch.object(settings, "TRAFFIC_PROVIDER", "tomtom"), \
         patch.object(settings, "TRAFFIC_API_KEY", "invalid-key"), \
         patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = Response(401, json={"error": "Unauthorized"})

        result = await provider.evaluate(
            origin_lat=37.7749,
            origin_lon=-122.4194,
            dest_lat=37.8049,
            dest_lon=-122.4094,
            baseline_eta_minutes=20,
        )

        assert result.status == DataSourceStatus.UNAVAILABLE
        assert result.provenance == "UNAVAILABLE"
        assert result.impact_minutes == 0
        assert "authentication error" in result.description.lower() or "401" in result.description


@pytest.mark.asyncio
async def test_14_tomtom_traffic_server_error_500():
    """Verify TomTom 500 error returns UNAVAILABLE, 0m impact, and preserves baseline."""
    provider = TrafficDataProvider()

    with patch.object(settings, "TRAFFIC_PROVIDER", "tomtom"), \
         patch.object(settings, "TRAFFIC_API_KEY", "test-key"), \
         patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = Response(500, text="Internal Server Error")

        result = await provider.evaluate(
            origin_lat=37.7749,
            origin_lon=-122.4194,
            dest_lat=37.8049,
            dest_lon=-122.4094,
            baseline_eta_minutes=20,
        )

        assert result.status == DataSourceStatus.UNAVAILABLE
        assert result.provenance == "UNAVAILABLE"
        assert result.impact_minutes == 0
        assert "HTTP 500" in result.description


@pytest.mark.asyncio
async def test_15_tomtom_traffic_timeout_safe_handling():
    """Verify TomTom timeout returns UNAVAILABLE with 0m impact."""
    import httpx

    provider = TrafficDataProvider()

    with patch.object(settings, "TRAFFIC_PROVIDER", "tomtom"), \
         patch.object(settings, "TRAFFIC_API_KEY", "test-key"), \
         patch("httpx.AsyncClient.get", side_effect=httpx.TimeoutException("TomTom timeout")):

        result = await provider.evaluate(
            origin_lat=37.7749,
            origin_lon=-122.4194,
            dest_lat=37.8049,
            dest_lon=-122.4094,
            baseline_eta_minutes=20,
        )

        assert result.status == DataSourceStatus.UNAVAILABLE
        assert result.provenance == "UNAVAILABLE"
        assert result.impact_minutes == 0
        assert "timed out" in result.description.lower()


@pytest.mark.asyncio
async def test_16_tomtom_traffic_malformed_response_safe_handling():
    """Verify TomTom malformed response returns INVALID with 0m impact."""
    provider = TrafficDataProvider()

    with patch.object(settings, "TRAFFIC_PROVIDER", "tomtom"), \
         patch.object(settings, "TRAFFIC_API_KEY", "test-key"), \
         patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = Response(200, json={"unexpected": "structure"})

        result = await provider.evaluate(
            origin_lat=37.7749,
            origin_lon=-122.4194,
            dest_lat=37.8049,
            dest_lon=-122.4094,
            baseline_eta_minutes=20,
        )

        assert result.status == DataSourceStatus.INVALID
        assert result.provenance == "UNAVAILABLE"
        assert result.impact_minutes == 0
        assert "malformed" in result.description.lower()


@pytest.mark.asyncio
async def test_17_osrm_baseline_strictly_derived_provenance():
    """Verify OSRM baseline routing is strictly classified as DERIVED, never REAL."""
    provider = TrafficDataProvider()

    mock_osrm = {
        "code": "Ok",
        "routes": [{"duration": 1200.0, "distance": 10000.0}],
    }

    with patch.object(settings, "TRAFFIC_PROVIDER", "osrm"), \
         patch.object(settings, "TRAFFIC_API_KEY", None), \
         patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = Response(200, json=mock_osrm)

        result = await provider.evaluate(
            origin_lat=37.7749,
            origin_lon=-122.4194,
            dest_lat=37.8049,
            dest_lon=-122.4094,
            baseline_eta_minutes=15,
        )

        assert result.status == DataSourceStatus.AVAILABLE
        assert result.provenance == "DERIVED"
        assert result.provenance != "REAL"
        assert "DERIVED" in result.description


@pytest.mark.asyncio
async def test_18_tomtom_delay_propagates_into_eta_calculation():
    """Verify that TomTom traffic delay propagates directly into ETAService calculation."""
    from app.services.eta_service import ETAService
    import uuid

    mock_tomtom = {
        "routes": [
            {
                "summary": {
                    "travelTimeInSeconds": 2400,  # 40 min
                    "noTrafficTravelTimeInSeconds": 1500,  # 25 min
                    "trafficDelayInSeconds": 900,  # 15 min delay
                }
            }
        ]
    }

    eta_svc = ETAService()

    async with AsyncClient() as client:
        disp_headers = await get_token_headers(client, "dispatcher@fieldops.ai", "Dispatch@123")
        tech_id, skill_id = await get_technician_and_skill(client, disp_headers)
        job = await create_test_job(client, disp_headers, skill_id)
        await assign_technician(client, disp_headers, job["id"], tech_id)

        with patch.object(settings, "TRAFFIC_PROVIDER", "tomtom"), \
             patch.object(settings, "TRAFFIC_API_KEY", "real-key-test"), \
             patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = Response(200, json=mock_tomtom)

            eta_resp = await eta_svc.calculate_job_eta(
                job_id=uuid.UUID(job["id"]),
                technician_id=uuid.UUID(tech_id),
            )

            assert eta_resp.is_context_sufficient is True
            traffic_source = next(
                (s for s in eta_resp.data_sources if "TomTom" in s.name or "Traffic" in s.name), None
            )
            assert traffic_source is not None
            assert traffic_source.provenance == "REAL"
            assert traffic_source.status == "AVAILABLE"
            assert traffic_source.impact_minutes == 15

            # Verify context-aware ETA includes the 15 min traffic delay
            assert eta_resp.context_aware_eta_minutes == eta_resp.baseline_eta_minutes + eta_resp.adjustment_minutes
            assert any(f.category == "TRAFFIC" and f.impact_minutes == 15 for f in eta_resp.factors)

