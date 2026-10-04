"""
Phase 4C Automated Test Suite: Fix OSRM Routed Fallback.

Validates the 3-tier routing hierarchy:
1. TomTom authoritative live routing (REAL)
2. OSRM road routing baseline (DERIVED, not live traffic flow)
3. Haversine straight-line fallback (FALLBACK, only when both TomTom and OSRM fail)

Tests:
TEST 1: TomTom available + OSRM available -> TomTom selected (REAL).
TEST 2: TomTom unavailable + OSRM available -> OSRM selected (DERIVED, duration, distance, geometry, Haversine not used).
TEST 3: TomTom timeout + OSRM available -> OSRM selected.
TEST 4: TomTom malformed + OSRM available -> OSRM selected.
TEST 5: TomTom NO_ROUTE_FOUND (HTTP 400) + OSRM available -> OSRM selected.
TEST 6: TomTom unavailable + OSRM unavailable -> Haversine fallback.
TEST 7: TomTom available + OSRM unavailable -> TomTom remains authoritative.
TEST 8: OSRM route distance differs significantly from Haversine -> uses OSRM distance.
TEST 9: OSRM route geometry exists -> geometry is preserved.
TEST 10: OSRM active -> no fake live traffic delay is generated (traffic_delay = 0, impact = 0).
"""

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch
import pytest
import httpx

from app.core.config import settings
from app.models.job import Job
from app.models.technician import Technician
from app.models.user import User
from app.services.context_providers import (
    ContextProviderResult,
    DataSourceStatus,
    TrafficDataProvider,
)
from app.services.eta_service import ETAService, _haversine_miles


# Standard test coordinates (San Francisco)
TECH_LAT = 37.7749
TECH_LON = -122.4194
JOB_LAT = 37.7949
JOB_LON = -122.4094

# Mock TomTom payload
MOCK_TOMTOM_PAYLOAD = {
    "routes": [
        {
            "summary": {
                "lengthInMeters": 15000,
                "travelTimeInSeconds": 1320,  # 22 min
                "noTrafficTravelTimeInSeconds": 1080,  # 18 min
                "trafficDelayInSeconds": 240,  # 4 min delay
            },
            "legs": [
                {
                    "points": [
                        {"latitude": TECH_LAT, "longitude": TECH_LON},
                        {"latitude": 37.7849, "longitude": -122.4144},
                        {"latitude": JOB_LAT, "longitude": JOB_LON},
                    ]
                }
            ],
        }
    ]
}

# Mock OSRM payload
MOCK_OSRM_PAYLOAD = {
    "code": "Ok",
    "routes": [
        {
            "duration": 1200.0,  # 20 min
            "distance": 14000.0,  # 14 km (8.7 mi)
            "geometry": {
                "type": "LineString",
                "coordinates": [
                    [TECH_LON, TECH_LAT],
                    [-122.4144, 37.7849],
                    [JOB_LON, JOB_LAT],
                ],
            },
        }
    ],
}


def _create_mock_job_and_tech(location_updated_at=None):
    job_id = uuid.uuid4()
    tech_id = uuid.uuid4()

    mock_job = MagicMock(spec=Job)
    mock_job.id = job_id
    mock_job.job_number = "JOB-4C-001"
    mock_job.latitude = JOB_LAT
    mock_job.longitude = JOB_LON
    mock_job.assignments = []
    mock_job.eta_overrides = []

    mock_tech = MagicMock(spec=Technician)
    mock_tech.id = tech_id
    mock_tech.employee_code = "TECH-101"
    mock_tech.current_latitude = TECH_LAT
    mock_tech.current_longitude = TECH_LON
    mock_tech.availability_status = "AVAILABLE"
    mock_tech.location_updated_at = location_updated_at or datetime.now(timezone.utc)
    mock_tech.updated_at = datetime.now(timezone.utc)
    mock_tech.user = MagicMock(spec=User)
    mock_tech.user.full_name = "Alex Rivera"

    return mock_job, mock_tech


# ── TEST 1: TomTom Available + OSRM Available -> TomTom Selected (REAL) ────────

@pytest.mark.asyncio
async def test_1_tomtom_available_osrm_available_tomtom_wins():
    """Case A: Both TomTom and OSRM are reachable; TomTom wins as authoritative live router."""
    provider = TrafficDataProvider()

    with patch.object(settings, "TRAFFIC_PROVIDER", "tomtom"), \
         patch.object(settings, "TRAFFIC_API_KEY", "mock-tomtom-key"), \
         patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:

        mock_get.return_value = httpx.Response(200, json=MOCK_TOMTOM_PAYLOAD)

        result = await provider.evaluate(
            origin_lat=TECH_LAT,
            origin_lon=TECH_LON,
            dest_lat=JOB_LAT,
            dest_lon=JOB_LON,
        )

        assert result.status == DataSourceStatus.AVAILABLE
        assert result.provenance == "REAL"
        assert "TomTom" in result.source_name
        assert result.live_travel_time_seconds == 1320
        assert result.free_flow_travel_time_seconds == 1080
        assert result.routed_distance_meters == 15000.0


# ── TEST 2: TomTom Unavailable + OSRM Available -> OSRM Selected (DERIVED) ─────

@pytest.mark.asyncio
async def test_2_tomtom_unavailable_osrm_available_osrm_selected():
    """Case B: TomTom returns HTTP 503; OSRM succeeds. OSRM duration, distance, geometry used; Haversine not used."""
    provider = TrafficDataProvider()

    # Route request: TomTom fails with 503, OSRM succeeds with 200
    async def mock_router(url, *args, **kwargs):
        if "api.tomtom.com" in str(url):
            return httpx.Response(503, text="Service Unavailable")
        elif "router.project-osrm.org" in str(url):
            return httpx.Response(200, json=MOCK_OSRM_PAYLOAD)
        return httpx.Response(404)

    with patch.object(settings, "TRAFFIC_PROVIDER", "tomtom"), \
         patch.object(settings, "TRAFFIC_API_KEY", "mock-tomtom-key"), \
         patch("httpx.AsyncClient.get", side_effect=mock_router):

        result = await provider.evaluate(
            origin_lat=TECH_LAT,
            origin_lon=TECH_LON,
            dest_lat=JOB_LAT,
            dest_lon=JOB_LON,
        )

        assert result.status == DataSourceStatus.AVAILABLE
        assert result.provenance == "DERIVED"
        assert result.provenance != "REAL"
        assert "Route Baseline (OSRM)" in result.source_name
        assert "does not provide live traffic flow" in result.description
        assert result.routed_distance_meters == 14000.0
        assert result.free_flow_travel_time_seconds == 1200
        assert result.live_travel_time_seconds == 1200
        assert result.impact_minutes == 0
        assert result.traffic_delay_seconds == 0
        assert result.route_geometry is not None


# ── TEST 3: TomTom Timeout + OSRM Available -> OSRM Selected ─────────────────

@pytest.mark.asyncio
async def test_3_tomtom_timeout_osrm_available():
    """Case C: TomTom times out; OSRM succeeds and is selected."""
    provider = TrafficDataProvider()

    async def mock_router(url, *args, **kwargs):
        if "api.tomtom.com" in str(url):
            raise httpx.TimeoutException("TomTom gateway timed out")
        elif "router.project-osrm.org" in str(url):
            return httpx.Response(200, json=MOCK_OSRM_PAYLOAD)
        return httpx.Response(404)

    with patch.object(settings, "TRAFFIC_PROVIDER", "tomtom"), \
         patch.object(settings, "TRAFFIC_API_KEY", "mock-tomtom-key"), \
         patch("httpx.AsyncClient.get", side_effect=mock_router):

        result = await provider.evaluate(
            origin_lat=TECH_LAT,
            origin_lon=TECH_LON,
            dest_lat=JOB_LAT,
            dest_lon=JOB_LON,
        )

        assert result.status == DataSourceStatus.AVAILABLE
        assert result.provenance == "DERIVED"
        assert "Route Baseline (OSRM)" in result.source_name
        assert result.routed_distance_meters == 14000.0


# ── TEST 4: TomTom Malformed + OSRM Available -> OSRM Selected ───────────────

@pytest.mark.asyncio
async def test_4_tomtom_malformed_osrm_available():
    """Case D: TomTom returns malformed payload (empty routes); OSRM succeeds and is selected."""
    provider = TrafficDataProvider()

    async def mock_router(url, *args, **kwargs):
        if "api.tomtom.com" in str(url):
            return httpx.Response(200, json={"routes": []})
        elif "router.project-osrm.org" in str(url):
            return httpx.Response(200, json=MOCK_OSRM_PAYLOAD)
        return httpx.Response(404)

    with patch.object(settings, "TRAFFIC_PROVIDER", "tomtom"), \
         patch.object(settings, "TRAFFIC_API_KEY", "mock-tomtom-key"), \
         patch("httpx.AsyncClient.get", side_effect=mock_router):

        result = await provider.evaluate(
            origin_lat=TECH_LAT,
            origin_lon=TECH_LON,
            dest_lat=JOB_LAT,
            dest_lon=JOB_LON,
        )

        assert result.status == DataSourceStatus.AVAILABLE
        assert result.provenance == "DERIVED"
        assert "Route Baseline (OSRM)" in result.source_name
        assert result.routed_distance_meters == 14000.0


# ── TEST 5: TomTom NO_ROUTE_FOUND (HTTP 400) + OSRM Available -> OSRM Selected ─

@pytest.mark.asyncio
async def test_5_tomtom_no_route_found_osrm_available():
    """Case E: TomTom returns HTTP 400 (unrouteable corridor); OSRM succeeds and is selected."""
    provider = TrafficDataProvider()

    async def mock_router(url, *args, **kwargs):
        if "api.tomtom.com" in str(url):
            return httpx.Response(400, json={"detailedError": {"message": "No route found"}})
        elif "router.project-osrm.org" in str(url):
            return httpx.Response(200, json=MOCK_OSRM_PAYLOAD)
        return httpx.Response(404)

    with patch.object(settings, "TRAFFIC_PROVIDER", "tomtom"), \
         patch.object(settings, "TRAFFIC_API_KEY", "mock-tomtom-key"), \
         patch("httpx.AsyncClient.get", side_effect=mock_router):

        result = await provider.evaluate(
            origin_lat=TECH_LAT,
            origin_lon=TECH_LON,
            dest_lat=JOB_LAT,
            dest_lon=JOB_LON,
        )

        assert result.status == DataSourceStatus.AVAILABLE
        assert result.provenance == "DERIVED"
        assert "Route Baseline (OSRM)" in result.source_name
        assert result.routed_distance_meters == 14000.0


from contextlib import asynccontextmanager

def _mock_session_ctx(job, tech):
    @asynccontextmanager
    async def _ctx():
        mock_session = AsyncMock()
        job_result = MagicMock()
        job_result.scalar_one_or_none.return_value = job
        tech_result = MagicMock()
        tech_result.scalar_one_or_none.return_value = tech
        mock_session.execute = AsyncMock(side_effect=[job_result, tech_result])
        yield mock_session
    return _ctx


# ── TEST 6: TomTom Unavailable + OSRM Unavailable -> Haversine Fallback ────────

@pytest.mark.asyncio
async def test_6_tomtom_unavailable_osrm_unavailable_haversine_fallback():
    """Case F: Both TomTom and OSRM fail; ETAService falls back to straight-line Haversine."""
    provider = TrafficDataProvider()

    async def mock_router(url, *args, **kwargs):
        return httpx.Response(503, text="Service Unavailable")

    with patch.object(settings, "TRAFFIC_PROVIDER", "tomtom"), \
         patch.object(settings, "TRAFFIC_API_KEY", "mock-tomtom-key"), \
         patch("httpx.AsyncClient.get", side_effect=mock_router):

        result = await provider.evaluate(
            origin_lat=TECH_LAT,
            origin_lon=TECH_LON,
            dest_lat=JOB_LAT,
            dest_lon=JOB_LON,
        )

        assert result.status == DataSourceStatus.UNAVAILABLE
        assert result.provenance == "UNAVAILABLE"

    # Now verify ETAService end-to-end fallback
    job, tech = _create_mock_job_and_tech()
    eta_service = ETAService()

    with patch.object(settings, "TRAFFIC_PROVIDER", "tomtom"), \
         patch.object(settings, "TRAFFIC_API_KEY", "mock-tomtom-key"), \
         patch("app.services.eta_service.AsyncSessionLocal", side_effect=_mock_session_ctx(job, tech)), \
         patch("httpx.AsyncClient.get", side_effect=mock_router):

        eta_resp = await eta_service.calculate_job_eta(
            job_id=job.id,
            technician_id=tech.id,
            record_audit=False,
        )

        haversine_mi = _haversine_miles(TECH_LAT, TECH_LON, JOB_LAT, JOB_LON)
        assert eta_resp.route_provenance == "DERIVED"
        assert eta_resp.route_geometry is None
        assert eta_resp.routed_distance_meters is None
        assert abs(eta_resp.distance_miles - haversine_mi) < 0.05
        assert "Clear transit conditions" in eta_resp.reason


# ── TEST 7: TomTom Available + OSRM Unavailable -> TomTom Remains Authoritative

@pytest.mark.asyncio
async def test_7_tomtom_available_osrm_unavailable_tomtom_wins():
    """Case G: TomTom succeeds; OSRM is not even needed and TomTom remains authoritative."""
    provider = TrafficDataProvider()

    async def mock_router(url, *args, **kwargs):
        if "api.tomtom.com" in str(url):
            return httpx.Response(200, json=MOCK_TOMTOM_PAYLOAD)
        raise RuntimeError("OSRM should not be queried when TomTom succeeds!")

    with patch.object(settings, "TRAFFIC_PROVIDER", "tomtom"), \
         patch.object(settings, "TRAFFIC_API_KEY", "mock-tomtom-key"), \
         patch("httpx.AsyncClient.get", side_effect=mock_router):

        result = await provider.evaluate(
            origin_lat=TECH_LAT,
            origin_lon=TECH_LON,
            dest_lat=JOB_LAT,
            dest_lon=JOB_LON,
        )

        assert result.status == DataSourceStatus.AVAILABLE
        assert result.provenance == "REAL"
        assert "TomTom" in result.source_name
        assert result.routed_distance_meters == 15000.0


# ── TEST 8: OSRM Route Distance Differs from Haversine -> Uses OSRM Distance ──

@pytest.mark.asyncio
async def test_8_osrm_route_distance_differs_from_haversine():
    """Case H / Metric Distance: OSRM road distance is used instead of Haversine in ETAService."""
    job, tech = _create_mock_job_and_tech()
    eta_service = ETAService()

    async def mock_router(url, *args, **kwargs):
        if "api.tomtom.com" in str(url):
            return httpx.Response(500, text="Internal Server Error")
        elif "router.project-osrm.org" in str(url):
            return httpx.Response(200, json=MOCK_OSRM_PAYLOAD)
        return httpx.Response(404)

    with patch.object(settings, "TRAFFIC_PROVIDER", "tomtom"), \
         patch.object(settings, "TRAFFIC_API_KEY", "mock-tomtom-key"), \
         patch("app.services.eta_service.AsyncSessionLocal", side_effect=_mock_session_ctx(job, tech)), \
         patch("httpx.AsyncClient.get", side_effect=mock_router):

        eta_resp = await eta_service.calculate_job_eta(
            job_id=job.id,
            technician_id=tech.id,
            record_audit=False,
        )

        haversine_mi = _haversine_miles(TECH_LAT, TECH_LON, JOB_LAT, JOB_LON)
        osrm_mi = round(14000.0 / 1000.0 / 1.60934, 2)

        # Haversine straight line is ~1.48 miles, OSRM road distance is 8.7 miles
        assert haversine_mi < 2.0
        assert eta_resp.distance_miles == osrm_mi
        assert eta_resp.distance_miles > 8.0
        assert eta_resp.routed_distance_meters == 14000.0
        assert eta_resp.routed_distance_km == 14.0
        assert eta_resp.routed_distance_miles == osrm_mi
        assert eta_resp.haversine_distance_miles == round(haversine_mi, 2)


# ── TEST 9: OSRM Route Geometry Exists -> Preserved for Downstream ─────────────

@pytest.mark.asyncio
async def test_9_osrm_route_geometry_preserved():
    """Verify OSRM route geometry is preserved in ETAService response."""
    job, tech = _create_mock_job_and_tech()
    eta_service = ETAService()

    async def mock_router(url, *args, **kwargs):
        if "api.tomtom.com" in str(url):
            return httpx.Response(500, text="Internal Server Error")
        elif "router.project-osrm.org" in str(url):
            return httpx.Response(200, json=MOCK_OSRM_PAYLOAD)
        return httpx.Response(404)

    with patch.object(settings, "TRAFFIC_PROVIDER", "tomtom"), \
         patch.object(settings, "TRAFFIC_API_KEY", "mock-tomtom-key"), \
         patch("app.services.eta_service.AsyncSessionLocal", side_effect=_mock_session_ctx(job, tech)), \
         patch("httpx.AsyncClient.get", side_effect=mock_router):

        eta_resp = await eta_service.calculate_job_eta(
            job_id=job.id,
            technician_id=tech.id,
            record_audit=False,
        )

        expected_coords = [
            [TECH_LON, TECH_LAT],
            [-122.4144, 37.7849],
            [JOB_LON, JOB_LAT],
        ]
        assert eta_resp.route_geometry == expected_coords
        assert eta_resp.route_provenance == "DERIVED"


# ── TEST 10: OSRM Active -> No Fake Live Traffic Delay Generated ───────────────

@pytest.mark.asyncio
async def test_10_osrm_active_no_fake_live_traffic_delay():
    """Verify OSRM active road routing does not manufacture fake live traffic delay."""
    job, tech = _create_mock_job_and_tech()
    eta_service = ETAService()

    async def mock_router(url, *args, **kwargs):
        if "api.tomtom.com" in str(url):
            return httpx.Response(500, text="Internal Server Error")
        elif "router.project-osrm.org" in str(url):
            return httpx.Response(200, json=MOCK_OSRM_PAYLOAD)
        return httpx.Response(404)

    with patch.object(settings, "TRAFFIC_PROVIDER", "tomtom"), \
         patch.object(settings, "TRAFFIC_API_KEY", "mock-tomtom-key"), \
         patch("app.services.eta_service.AsyncSessionLocal", side_effect=_mock_session_ctx(job, tech)), \
         patch("httpx.AsyncClient.get", side_effect=mock_router):

        eta_resp = await eta_service.calculate_job_eta(
            job_id=job.id,
            technician_id=tech.id,
            record_audit=False,
        )

        # 1200 seconds = 20 minutes duration
        assert eta_resp.baseline_eta_minutes == 20
        assert eta_resp.free_flow_eta_minutes == 20
        assert eta_resp.live_route_eta_minutes == 20
        assert eta_resp.traffic_delay_minutes == 0
        assert eta_resp.context_aware_eta_minutes == 20
        assert "OSRM road baseline" in eta_resp.reason
        assert "DERIVED" in eta_resp.reason
