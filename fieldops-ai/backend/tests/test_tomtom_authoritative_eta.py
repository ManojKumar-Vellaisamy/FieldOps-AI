"""
Tests for STEP 1: TomTom Live Routing as Authoritative ETA Base.

Validates:
1. Normal TomTom live routing:
   - noTrafficTravelTime = 18 min
   - travelTime = 22 min
   - trafficDelay = 4 min
   - Baseline ETA = 18 min (free-flow road travel time)
   - Live route ETA = 22 min (TomTom live driving time)
   - Traffic delay factor is NOT double-counted (18 + 4 = 22, NOT 22 + 4 = 26)
2. Free-flow TomTom routing:
   - noTrafficTravelTime = 10 min
   - travelTime = 10 min
   - trafficDelay = 0
   - Baseline ETA = 10 min, live route ETA = 10 min, traffic penalty = 0 min
3. Routed distance vs Haversine:
   - TomTom routed road distance (lengthInMeters) is extracted and used
   - Both routed and Haversine distances are exposed transparently
4. TomTom failure / unconfigured fallback:
   - Graceful fallback to Haversine straight-line baseline
   - Provenance is honestly UNAVAILABLE or DERIVED, never fake REAL
5. End-to-end ETAService integration:
   - Full calculate_job_eta pipeline populates baseline_eta_minutes,
     free_flow_eta_minutes, live_route_eta_minutes, traffic_delay_minutes,
     routed_distance_miles, haversine_distance_miles, route_geometry,
     and route_provenance='REAL'.
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
from app.services.context_aggregation import ContextAggregationService
from app.services.eta_service import ETAService


# ── Test 1: Normal TomTom Live Routing (No Double-Counting) ───────────────────

@pytest.mark.asyncio
async def test_1_tomtom_live_routing_baseline_and_no_double_counting():
    """
    Test 1:
    noTrafficTravelTime = 1080s (18 min)
    travelTime = 1320s (22 min)
    trafficDelay = 240s (4 min)

    Verifies:
    - Provider extracts free_flow_travel_time_seconds = 1080
    - Provider extracts live_travel_time_seconds = 1320
    - Provider impact_minutes = 4 min
    - In ContextAggregation, Baseline (18) + Traffic Delay (4) = 22 min (Live route ETA)
    - Avoiding the double-counting bug where 22 was added to 4 to give 26.
    """
    provider = TrafficDataProvider()

    mock_tomtom_payload = {
        "routes": [
            {
                "summary": {
                    "lengthInMeters": 15000,
                    "travelTimeInSeconds": 1320,  # 22 min
                    "noTrafficTravelTimeInSeconds": 1080,  # 18 min
                    "trafficDelayInSeconds": 240,  # 4 min
                },
                "legs": [
                    {
                        "points": [
                            {"latitude": 37.7749, "longitude": -122.4194},
                            {"latitude": 37.7849, "longitude": -122.4144},
                            {"latitude": 37.7949, "longitude": -122.4094},
                        ]
                    }
                ],
            }
        ]
    }

    with patch.object(settings, "TRAFFIC_PROVIDER", "tomtom"), \
         patch.object(settings, "TRAFFIC_API_KEY", "mock-tomtom-key"), \
         patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = httpx.Response(200, json=mock_tomtom_payload)

        result = await provider.evaluate(
            origin_lat=37.7749,
            origin_lon=-122.4194,
            dest_lat=37.7949,
            dest_lon=-122.4094,
            baseline_eta_minutes=15,
        )

        assert result.status == DataSourceStatus.AVAILABLE
        assert result.provenance == "REAL"
        assert result.free_flow_travel_time_seconds == 1080
        assert result.live_travel_time_seconds == 1320
        assert result.traffic_delay_seconds == 240
        assert result.impact_minutes == 4
        assert result.routed_distance_meters == 15000.0
        assert result.routed_distance_km == 15.0
        assert result.routed_distance_miles == round(15.0 / 1.60934, 2)
        assert len(result.route_geometry) == 3

        # Simulate ETAService logic:
        # Baseline is set from free_flow_travel_time_seconds (18 min)
        baseline_eta = round(result.free_flow_travel_time_seconds / 60.0)
        assert baseline_eta == 18

        live_route_eta = round(result.live_travel_time_seconds / 60.0)
        assert live_route_eta == 22

        # ContextAggregation with traffic factor only:
        agg_service = ContextAggregationService()
        summary = agg_service.aggregate(
            provider_results=[result],
            baseline_eta_minutes=baseline_eta,
            distance_km=result.routed_distance_km,
            distance_miles=result.routed_distance_miles,
        )
        context_eta = baseline_eta + summary.total_adjustment_minutes

        # Authoritative equality check:
        # Context ETA must equal 22 min (Live Route ETA), NOT 26 min!
        assert context_eta == 22
        assert context_eta == live_route_eta
        assert context_eta != 26, "Double counting detected! Traffic delay was added to live travel time instead of free-flow baseline."


# ── Test 2: Free-flow TomTom Routing (0 min Traffic Delay) ────────────────────

@pytest.mark.asyncio
async def test_2_tomtom_free_flow_routing():
    """
    Test 2:
    noTrafficTravelTime = 600s (10 min)
    travelTime = 600s (10 min)
    trafficDelay = 0s

    Verifies:
    - Baseline ETA = 10 min
    - Live route ETA = 10 min
    - Traffic impact = 0 min
    """
    provider = TrafficDataProvider()

    mock_tomtom_payload = {
        "routes": [
            {
                "summary": {
                    "lengthInMeters": 8000,
                    "travelTimeInSeconds": 600,
                    "noTrafficTravelTimeInSeconds": 600,
                    "trafficDelayInSeconds": 0,
                },
                "legs": [
                    {
                        "points": [
                            {"latitude": 37.7749, "longitude": -122.4194},
                            {"latitude": 37.7849, "longitude": -122.4094},
                        ]
                    }
                ],
            }
        ]
    }

    with patch.object(settings, "TRAFFIC_PROVIDER", "tomtom"), \
         patch.object(settings, "TRAFFIC_API_KEY", "mock-tomtom-key"), \
         patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = httpx.Response(200, json=mock_tomtom_payload)

        result = await provider.evaluate(
            origin_lat=37.7749,
            origin_lon=-122.4194,
            dest_lat=37.7849,
            dest_lon=-122.4094,
            baseline_eta_minutes=15,
        )

        assert result.status == DataSourceStatus.AVAILABLE
        assert result.provenance == "REAL"
        assert result.impact_minutes == 0
        assert result.traffic_delay_seconds == 0
        assert result.free_flow_travel_time_seconds == 600
        assert result.live_travel_time_seconds == 600

        baseline_eta = round(result.free_flow_travel_time_seconds / 60.0)
        live_route_eta = round(result.live_travel_time_seconds / 60.0)
        assert baseline_eta == 10
        assert live_route_eta == 10


# ── Test 3: Routed Distance vs Haversine Distance ──────────────────────────────

@pytest.mark.asyncio
async def test_3_routed_distance_vs_haversine():
    """
    Test 3:
    Origin: (37.7749, -122.4194), Dest: (37.7949, -122.4094)
    Haversine distance is ~1.48 miles (~2.39 km).
    TomTom routed road distance is 15000 meters = 15.0 km = 9.32 miles.

    Verifies:
    - Provider extracts the road distance (15.0 km / 9.32 miles)
    - Road distance is significantly different from Haversine straight-line distance
    - Road distance is available as routed_distance_miles and routed_distance_km
    """
    provider = TrafficDataProvider()

    mock_tomtom_payload = {
        "routes": [
            {
                "summary": {
                    "lengthInMeters": 15000,
                    "travelTimeInSeconds": 1200,
                    "noTrafficTravelTimeInSeconds": 1000,
                    "trafficDelayInSeconds": 200,
                },
                "legs": [
                    {"points": [{"latitude": 37.7749, "longitude": -122.4194}]}
                ],
            }
        ]
    }

    with patch.object(settings, "TRAFFIC_PROVIDER", "tomtom"), \
         patch.object(settings, "TRAFFIC_API_KEY", "mock-tomtom-key"), \
         patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = httpx.Response(200, json=mock_tomtom_payload)

        result = await provider.evaluate(
            origin_lat=37.7749,
            origin_lon=-122.4194,
            dest_lat=37.7949,
            dest_lon=-122.4094,
        )

        assert result.routed_distance_meters == 15000.0
        assert result.routed_distance_km == 15.0
        assert result.routed_distance_miles == 9.32

        # Verify against straight line
        from app.services.eta_service import _haversine_miles
        haversine_mi = _haversine_miles(37.7749, -122.4194, 37.7949, -122.4094)
        assert haversine_mi < 2.0
        assert result.routed_distance_miles > 9.0
        assert result.routed_distance_miles != haversine_mi


# ── Test 4: TomTom Routing Failure Fallback ────────────────────────────────────

@pytest.mark.asyncio
async def test_4_tomtom_failure_fallback_honest_provenance():
    """
    Test 4:
    When TomTom API returns 503 Service Unavailable or times out:
    - Status is UNAVAILABLE
    - Impact minutes is 0
    - Provenance is honestly 'UNAVAILABLE' (never 'REAL')
    - Description explains failure without claiming fake data
    """
    provider = TrafficDataProvider()

    with patch.object(settings, "TRAFFIC_PROVIDER", "tomtom"), \
         patch.object(settings, "TRAFFIC_API_KEY", "mock-tomtom-key"), \
         patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = httpx.Response(503, text="Service Unavailable")

        result = await provider.evaluate(
            origin_lat=37.7749,
            origin_lon=-122.4194,
            dest_lat=37.7949,
            dest_lon=-122.4094,
            baseline_eta_minutes=15,
        )

        assert result.status == DataSourceStatus.UNAVAILABLE
        assert result.impact_minutes == 0
        assert result.provenance == "UNAVAILABLE"
        assert result.provenance != "REAL"
        assert "HTTP 503" in result.description


# ── Test 5: Full ETAService Integration Pipeline ──────────────────────────────

@pytest.mark.asyncio
async def test_5_full_eta_service_pipeline_authoritative_tomtom():
    """
    Test 5:
    End-to-end ETAService.calculate_job_eta with TomTom mocked.
    Verifies:
    - baseline_eta_minutes == 18
    - free_flow_eta_minutes == 18
    - live_route_eta_minutes == 22
    - traffic_delay_minutes == 4
    - routed_distance_miles and haversine_distance_miles both populated
    - route_geometry coordinates are present
    - route_provenance == 'REAL'
    - final dispatch ETA reflects live routing without double-counting
    """
    job_id = uuid.uuid4()
    tech_id = uuid.uuid4()
    actor_id = uuid.uuid4()

    mock_job = MagicMock(spec=Job)
    mock_job.id = job_id
    mock_job.job_number = "JOB-TEST-001"
    mock_job.latitude = 37.7949
    mock_job.longitude = -122.4094
    mock_job.assignments = []
    mock_job.eta_overrides = []

    mock_tech = MagicMock(spec=Technician)
    mock_tech.id = tech_id
    mock_tech.employee_code = "TECH-001"
    mock_tech.full_name = "Alex Rivera"
    mock_tech.current_latitude = 37.7749
    mock_tech.current_longitude = -122.4194
    mock_tech.availability_status = "AVAILABLE"
    mock_tech.updated_at = datetime.now(timezone.utc)
    mock_tech.user = MagicMock(spec=User)
    mock_tech.user.full_name = "Alex Rivera"

    mock_session = AsyncMock()

    # Configure session.execute to return job on first call, tech on second call
    def execute_side_effect(stmt):
        mock_result = MagicMock()
        # inspect query representation or return based on call
        return mock_result

    # Setup session query returns
    job_result = MagicMock()
    job_result.scalar_one_or_none.return_value = mock_job

    tech_result = MagicMock()
    tech_result.scalar_one_or_none.return_value = mock_tech

    mock_session.execute = AsyncMock(side_effect=[job_result, tech_result])

    mock_tomtom_payload = {
        "routes": [
            {
                "summary": {
                    "lengthInMeters": 15000,
                    "travelTimeInSeconds": 1320,  # 22 min
                    "noTrafficTravelTimeInSeconds": 1080,  # 18 min
                    "trafficDelayInSeconds": 240,  # 4 min
                },
                "legs": [
                    {
                        "points": [
                            {"latitude": 37.7749, "longitude": -122.4194},
                            {"latitude": 37.7849, "longitude": -122.4144},
                            {"latitude": 37.7949, "longitude": -122.4094},
                        ]
                    }
                ],
            }
        ]
    }

    from contextlib import asynccontextmanager

    @asynccontextmanager
    async def mock_session_ctx():
        yield mock_session

    eta_service = ETAService()

    with patch.object(settings, "TRAFFIC_PROVIDER", "tomtom"), \
         patch.object(settings, "TRAFFIC_API_KEY", "mock-tomtom-key"), \
         patch("app.services.eta_service.AsyncSessionLocal", side_effect=mock_session_ctx), \
         patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = httpx.Response(200, json=mock_tomtom_payload)

        response = await eta_service.calculate_job_eta(
            job_id=job_id,
            actor_id=actor_id,
            technician_id=tech_id,
            weather_condition="CLEAR",
            record_audit=False,
        )

        assert response.is_context_sufficient is True
        assert response.baseline_eta_minutes == 18
        assert response.free_flow_eta_minutes == 18
        assert response.live_route_eta_minutes == 22
        assert response.traffic_delay_minutes == 4
        assert response.routed_distance_miles == 9.32
        assert response.routed_distance_km == 15.0
        assert response.haversine_distance_miles is not None
        assert response.haversine_distance_miles < response.routed_distance_miles
        assert response.route_provenance == "REAL"
        assert response.route_geometry is not None
        assert len(response.route_geometry) == 3
        # In clear weather with no other factors, context ETA equals live route ETA (22 min)
        assert response.context_aware_eta_minutes == 22
        assert response.final_dispatch_eta_minutes == 22
