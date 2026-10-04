"""
Phase 3 Automated Test Suite:
Production-Grade ETA Context Fusion, Real-Time Data Freshness, Weather Impact,
Causal Deduplication & Trusted ETA Explanation.

Verifies:
1. Authoritative base: TomTom live route travel time is primary baseline; traffic delay not double-counted.
2. Free-flow route: zero traffic delay, base = live = context ETA.
3. Fallback when unconfigured/unreachable: OSRM/Haversine honest DERIVED / UNAVAILABLE, never fake REAL.
4. Road closure with valid detour: alternate route produces incremental detour, classified INCREMENTAL_DETOUR.
5. Road closure with no detour: detour <= 0 or unavailable produces 0 min, classified INCLUDED_IN_LIVE_ROUTE or NOT_APPLIED.
6. Incident far from route: NOT_RELEVANT, 0 min, classified NOT_APPLIED with metric distance.
7. Incident geometry vs point fallback: geometry intersection takes precedence over point corridor fallback.
8. Event on route with live traffic: classified INCLUDED_IN_LIVE_ROUTE, 0 additional min.
9. Event far from route: NOT_RELEVANT, 0 min, metric distance > 400 m buffer.
10. Event without traffic evidence: 0 min impact, reason documented.
11. Weather clear / mild: 0 min impact, classified NOT_APPLIED.
12. Weather severe: proportional impact, classified INDEPENDENT_CONTEXT, capped by sanity guard.
13. Stale GPS: > 10 min old, status STALE, 0 impact applied.
14. Stale TomTom: > 5 min old, status STALE, fallback to safe baseline.
15. Stale Weather: > 3 hours old, status STALE, 0 impact applied.
16. Causal deduplication: shared corridor congestion between traffic + event + road doesn't stack.
17. Metric unit correctness: all distances in meters / km as primary, miles secondary.
18. End-to-end ETAResponse schema: all Phase 3 fields present, correctly typed, explainable.
"""

from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch
import uuid
import pytest
import httpx

from app.core.config import settings
from app.models.assignment import Assignment
from app.models.job import Job
from app.models.technician import Technician
from app.models.user import User
from app.schemas.eta import ETAResponse
from app.services.context_aggregation import ContextAggregationService
from app.services.context_providers import (
    ContextProviderResult,
    DataSourceStatus,
    EventsDataProvider,
    GPSLocationProvider,
    RoadRestrictionProvider,
    STRICT_EVENT_CORRIDOR_BUFFER_METERS,
    STRICT_ROAD_CORRIDOR_BUFFER_METERS,
    TrafficDataProvider,
    WeatherProvider,
    _format_metric_distance,
    _meters_to_miles,
    _miles_to_meters,
)
from app.services.eta_service import ETAService


# ── Sample Market Street Test Polyline ─────────────────────────────────────────

SAMPLE_ROUTE_GEOMETRY = [
    [-122.4160, 37.7770],
    [-122.4120, 37.7810],
    [-122.4080, 37.7850],
    [-122.4040, 37.7875],
    [-122.4010, 37.7890],
]

ORIGIN_LAT, ORIGIN_LON = 37.7770, -122.4160
DEST_LAT, DEST_LON = 37.7890, -122.4010


# ── Fixtures & Helpers ────────────────────────────────────────────────────────

def _build_incident(
    inc_id="INC-P3-01",
    coords=None,
    geom_type="Point",
    delay=None,
    magnitude=4,
    icon_category=8,
    road_from="Market St",
    road_to="4th St",
    is_stale=False,
):
    if coords is None:
        coords = [-122.4080, 37.7850]
    return {
        "type": "Feature",
        "geometry": {
            "type": geom_type,
            "coordinates": coords,
        },
        "properties": {
            "id": inc_id,
            "iconCategory": icon_category,
            "magnitudeOfDelay": magnitude,
            "delay": delay,
            "events": [{"code": 108, "description": "Road closure construction"}],
            "startTime": (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat(),
            "endTime": (datetime.now(timezone.utc) + timedelta(hours=5)).isoformat(),
            "from": road_from,
            "to": road_to,
            "length": 350.0,
            "is_stale": is_stale,
        },
    }


def _build_event(
    evt_id="EVT-P3-01",
    title="SF Symphony Gala",
    coords=None,
    category="concerts",
    rank=75,
    attendance=3500,
    is_stale=False,
):
    if coords is None:
        coords = [-122.4080, 37.7850]
    return {
        "id": evt_id,
        "title": title,
        "category": category,
        "rank": rank,
        "phq_attendance": attendance,
        "location": coords,
        "start": (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat(),
        "end": (datetime.now(timezone.utc) + timedelta(hours=3)).isoformat(),
        "is_stale": is_stale,
    }


# ── Scenario 1: Authoritative Base (No Double-Counting) ───────────────────────

@pytest.mark.asyncio
async def test_1_authoritative_base_no_double_counting():
    """TomTom live route travel time is primary baseline; traffic delay is not double-counted."""
    provider = TrafficDataProvider()
    mock_payload = {
        "routes": [{
            "summary": {
                "lengthInMeters": 12500,
                "travelTimeInSeconds": 1320,  # 22 min live driving time
                "noTrafficTravelTimeInSeconds": 1080,  # 18 min free-flow
                "trafficDelayInSeconds": 240,  # 4 min delay
            },
            "legs": [{"points": [{"latitude": 37.77, "longitude": -122.41}, {"latitude": 37.79, "longitude": -122.40}]}],
        }]
    }

    with patch.object(settings, "TRAFFIC_PROVIDER", "tomtom"), \
         patch.object(settings, "TRAFFIC_API_KEY", "test-key"), \
         patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = httpx.Response(200, json=mock_payload)
        res = await provider.evaluate(37.77, -122.41, 37.79, -122.40, baseline_eta_minutes=18)

    assert res.status == DataSourceStatus.AVAILABLE
    assert res.provenance == "REAL"
    assert res.freshness == "FRESH"
    assert res.impact_classification == "INCLUDED_IN_LIVE_ROUTE"
    assert res.free_flow_travel_time_seconds == 1080
    assert res.live_travel_time_seconds == 1320
    assert res.impact_minutes == 4
    assert res.routed_distance_meters == 12500.0

    agg = ContextAggregationService()
    summary = agg.aggregate([res], baseline_eta_minutes=18, distance_km=12.5, distance_miles=7.77)
    # Total ETA is baseline (18) + traffic (4) = 22 min = live route driving time
    assert 18 + summary.total_adjustment_minutes == 22
    assert summary.additional_verified_impact_minutes == 0  # No additional detours/weather


# ── Scenario 2: Free-Flow Route ───────────────────────────────────────────────

@pytest.mark.asyncio
async def test_2_free_flow_route_zero_traffic_delay():
    """Zero traffic delay route: base = live = context ETA."""
    provider = TrafficDataProvider()
    mock_payload = {
        "routes": [{
            "summary": {
                "lengthInMeters": 8000,
                "travelTimeInSeconds": 720,  # 12 min
                "noTrafficTravelTimeInSeconds": 720,  # 12 min
                "trafficDelayInSeconds": 0,
            },
            "legs": [{"points": [{"latitude": 37.77, "longitude": -122.41}, {"latitude": 37.78, "longitude": -122.40}]}],
        }]
    }

    with patch.object(settings, "TRAFFIC_PROVIDER", "tomtom"), \
         patch.object(settings, "TRAFFIC_API_KEY", "test-key"), \
         patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = httpx.Response(200, json=mock_payload)
        res = await provider.evaluate(37.77, -122.41, 37.78, -122.40, baseline_eta_minutes=12)

    assert res.impact_minutes == 0
    assert res.live_travel_time_seconds == 720
    assert res.impact_classification == "INCLUDED_IN_LIVE_ROUTE"

    agg = ContextAggregationService()
    summary = agg.aggregate([res], baseline_eta_minutes=12, distance_km=8.0, distance_miles=4.97)
    assert 12 + summary.total_adjustment_minutes == 12
    assert summary.additional_verified_impact_minutes == 0


# ── Scenario 3: Fallback Routing (Honest DERIVED / UNAVAILABLE) ─────────────────

@pytest.mark.asyncio
async def test_3_fallback_routing_honest_derived():
    """When TomTom is unconfigured or unreachable, fallback is honestly DERIVED or UNAVAILABLE."""
    provider = TrafficDataProvider()

    with patch.object(settings, "TRAFFIC_PROVIDER", "tomtom"), \
         patch.object(settings, "TRAFFIC_API_KEY", None), \
         patch.object(settings, "TOMTOM_API_KEY", None):
        res = await provider.evaluate(37.77, -122.41, 37.78, -122.40, baseline_eta_minutes=15)

    assert res.status == DataSourceStatus.UNAVAILABLE
    assert res.provenance == "UNAVAILABLE"
    assert res.impact_minutes == 0


# ── Scenario 4: Road Closure with Valid Detour ────────────────────────────────

@pytest.mark.asyncio
async def test_4_road_closure_incremental_detour():
    """Route-relevant road closure with valid detour derives incremental delay without double-counting."""
    incident = _build_incident(coords=[-122.4080, 37.7850], delay=None)
    mock_payload = {"incidents": [incident]}

    alt_route_response = {
        "routes": [{
            "summary": {
                "travelTimeInSeconds": 1080,  # 18 min detour route
                "lengthInMeters": 4200,
            }
        }]
    }

    provider = RoadRestrictionProvider()
    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get, \
         patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_get.return_value = httpx.Response(200, json=mock_payload)
        mock_post.return_value = httpx.Response(200, json=alt_route_response)

        res = await provider.evaluate(
            origin_lat=ORIGIN_LAT, origin_lon=ORIGIN_LON,
            dest_lat=DEST_LAT, dest_lon=DEST_LON,
            route_geometry=SAMPLE_ROUTE_GEOMETRY,
            original_route_time_seconds=600,  # 10 min original live route
            api_key="mock-key",
        )

    assert res.status == DataSourceStatus.AVAILABLE
    assert res.provenance == "REAL"
    assert res.is_road_closed is True
    assert res.impact_minutes == 8  # round((1080 - 600) / 60) = 8 min
    assert res.impact_classification == "INCREMENTAL_DETOUR"
    assert res.applied_to_eta is True


# ── Scenario 5: Road Closure with No Detour ───────────────────────────────────

@pytest.mark.asyncio
async def test_5_road_closure_detour_not_applied_or_zero():
    """Closure where alternate route calculation is unavailable yields 0 min impact (no fabricated penalty)."""
    incident = _build_incident(coords=[-122.4080, 37.7850], delay=None)
    mock_payload = {"incidents": [incident]}

    provider = RoadRestrictionProvider()
    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get, \
         patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_get.return_value = httpx.Response(200, json=mock_payload)
        mock_post.return_value = httpx.Response(500, text="Internal Error")

        res = await provider.evaluate(
            origin_lat=ORIGIN_LAT, origin_lon=ORIGIN_LON,
            dest_lat=DEST_LAT, dest_lon=DEST_LON,
            route_geometry=SAMPLE_ROUTE_GEOMETRY,
            original_route_time_seconds=600,
            api_key="mock-key",
        )

    assert res.status == DataSourceStatus.AVAILABLE
    assert res.impact_minutes == 0
    assert res.applied_to_eta is False
    assert res.impact_classification in ("INCLUDED_IN_LIVE_ROUTE", "NOT_APPLIED")


# ── Scenario 6: Incident Far from Route (Metric Units) ─────────────────────────

@pytest.mark.asyncio
async def test_6_incident_far_from_route_metric():
    """Incident > 50m corridor buffer is NOT_RELEVANT with 0 min impact and metric distance."""
    # Location ~800m away from Market St
    incident = _build_incident(coords=[-122.4200, 37.7950])
    mock_payload = {"incidents": [incident]}

    provider = RoadRestrictionProvider()
    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = httpx.Response(200, json=mock_payload)
        res = await provider.evaluate(
            origin_lat=ORIGIN_LAT, origin_lon=ORIGIN_LON,
            dest_lat=DEST_LAT, dest_lon=DEST_LON,
            route_geometry=SAMPLE_ROUTE_GEOMETRY,
            api_key="mock-key",
        )

    assert res.is_route_relevant is False
    assert res.relevance_status == "NOT_RELEVANT"
    assert res.impact_minutes == 0
    assert res.impact_classification == "NOT_APPLIED"
    assert res.distance_to_route_meters is not None
    assert res.distance_to_route_meters > STRICT_ROAD_CORRIDOR_BUFFER_METERS
    assert "m" in res.distance_to_route_display or "km" in res.distance_to_route_display


# ── Scenario 7: Incident Geometry vs Point Fallback ───────────────────────────

@pytest.mark.asyncio
async def test_7_incident_geometry_vs_point_fallback():
    """LineString incident geometry takes precedence over point corridor fallback."""
    # LineString crossing the route directly at (-122.4080, 37.7850)
    line_incident = {
        "type": "Feature",
        "geometry": {
            "type": "LineString",
            "coordinates": [
                [-122.4090, 37.7840],
                [-122.4070, 37.7860],
            ],
        },
        "properties": {
            "id": "INC-LINE-01",
            "iconCategory": 9,
            "magnitudeOfDelay": 2,
            "delay": 180,
            "events": [{"code": 101, "description": "Repaving"}],
            "startTime": (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat(),
            "endTime": (datetime.now(timezone.utc) + timedelta(hours=4)).isoformat(),
            "road_name": "Market Street Crossing",
        },
    }
    mock_payload = {"incidents": [line_incident]}

    provider = RoadRestrictionProvider()
    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = httpx.Response(200, json=mock_payload)
        res = await provider.evaluate(
            origin_lat=ORIGIN_LAT, origin_lon=ORIGIN_LON,
            dest_lat=DEST_LAT, dest_lon=DEST_LON,
            route_geometry=SAMPLE_ROUTE_GEOMETRY,
            api_key="mock-key",
        )

    assert res.is_route_relevant is True
    assert res.relevance_status == "RELEVANT"
    assert res.distance_to_route_meters == 0.0
    assert "Affected road geometry" in res.relevance_reason


# ── Scenario 8: Event on Route with Live Traffic Included ─────────────────────

@pytest.mark.asyncio
async def test_8_event_on_route_with_live_traffic_included():
    """Event on route when corridor traffic already measures delay is classified INCLUDED_IN_LIVE_ROUTE."""
    event = _build_event(coords=[-122.4080, 37.7850])
    mock_payload = {"results": [event]}

    provider = EventsDataProvider()
    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = httpx.Response(200, json=mock_payload)
        res = await provider.evaluate(
            dest_lat=DEST_LAT, dest_lon=DEST_LON,
            route_geometry=SAMPLE_ROUTE_GEOMETRY,
            traffic_delay_seconds=240,  # 4 min traffic delay already present
        )

    assert res.status == DataSourceStatus.AVAILABLE
    assert res.is_route_relevant is True
    assert res.impact_minutes == 0
    assert res.impact_classification == "INCLUDED_IN_LIVE_ROUTE"
    assert "already represented in live route travel time" in res.relevance_reason


# ── Scenario 9: Event Far from Route (> 400m Buffer) ──────────────────────────

@pytest.mark.asyncio
async def test_9_event_outside_corridor_buffer_metric():
    """Event at 700m from route exceeds 400m buffer -> NOT_RELEVANT with 0 min impact."""
    # Location ~750m away from Market St route
    event = _build_event(coords=[-122.3950, 37.7940])
    mock_payload = {"results": [event]}

    provider = EventsDataProvider()
    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = httpx.Response(200, json=mock_payload)
        res = await provider.evaluate(
            dest_lat=DEST_LAT, dest_lon=DEST_LON,
            route_geometry=SAMPLE_ROUTE_GEOMETRY,
            traffic_delay_seconds=0,
        )

    assert res.is_route_relevant is False
    assert res.relevance_status == "NOT_RELEVANT"
    assert res.impact_minutes == 0
    assert res.impact_classification == "NOT_APPLIED"
    assert res.distance_to_route_meters is not None
    assert res.distance_to_route_meters > STRICT_EVENT_CORRIDOR_BUFFER_METERS


# ── Scenario 10: Event without Traffic Evidence ───────────────────────────────

@pytest.mark.asyncio
async def test_10_event_without_traffic_evidence_zero_delay():
    """Event near corridor but without measurable route delay yields 0 min impact."""
    event = _build_event(coords=[-122.4082, 37.7852], attendance=1200)
    mock_payload = {"results": [event]}

    provider = EventsDataProvider()
    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = httpx.Response(200, json=mock_payload)
        res = await provider.evaluate(
            dest_lat=DEST_LAT, dest_lon=DEST_LON,
            route_geometry=SAMPLE_ROUTE_GEOMETRY,
            traffic_delay_seconds=0,
        )

    assert res.is_route_relevant is True
    assert res.impact_minutes == 0
    assert res.impact_classification == "NOT_APPLIED"
    assert "No measurable additional route slowdown detected" in res.relevance_reason


# ── Scenario 11: Weather Clear / Mild (0 min Impact) ──────────────────────────

@pytest.mark.asyncio
async def test_11_weather_clear_mild_zero_delay():
    """Clear or mild weather (trace rain <= 0.3mm) yields 0 min impact and NOT_APPLIED."""
    provider = WeatherProvider()
    mock_meteo_payload = {
        "current": {
            "temperature_2m": 16.5,
            "relative_humidity_2m": 65,
            "apparent_temperature": 16.0,
            "precipitation": 0.1,  # Trace drizzle
            "rain": 0.1,
            "weather_code": 51,  # Light drizzle
            "wind_speed_10m": 12.0,  # Gentle breeze
            "wind_direction_10m": 220,
            "time": datetime.now(timezone.utc).isoformat(),
        }
    }

    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = httpx.Response(200, json=mock_meteo_payload)
        res = await provider.evaluate(lat=37.77, lon=-122.41, baseline_eta_minutes=20)

    assert res.status == DataSourceStatus.AVAILABLE
    assert res.provenance == "REAL"
    assert res.freshness == "FRESH"
    assert res.impact_minutes == 0
    assert res.impact_classification == "NOT_APPLIED"


# ── Scenario 12: Weather Severe (Proportional Impact & Sanity Guard) ───────────

@pytest.mark.asyncio
async def test_12_weather_severe_proportional_impact_sanity_guard():
    """Severe weather (heavy rain / storm) produces proportional impact capped by sanity guard."""
    provider = WeatherProvider()
    mock_meteo_payload = {
        "current": {
            "temperature_2m": 12.0,
            "relative_humidity_2m": 95,
            "apparent_temperature": 9.5,
            "precipitation": 12.5,
            "rain": 12.5,
            "weather_code": 95,  # Thunderstorm
            "wind_speed_10m": 45.0,  # Strong wind
            "wind_direction_10m": 190,
            "time": datetime.now(timezone.utc).isoformat(),
        }
    }

    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = httpx.Response(200, json=mock_meteo_payload)
        res = await provider.evaluate(lat=37.77, lon=-122.41, baseline_eta_minutes=30)

    assert res.status == DataSourceStatus.AVAILABLE
    assert res.impact_minutes > 0
    assert res.impact_classification == "INDEPENDENT_CONTEXT"
    # Sanity guard check: capped at 30% of baseline (0.30 * 30 = 9 min)
    assert res.impact_minutes <= 9


# ── Scenario 13: Stale GPS (> 10 min Old) ─────────────────────────────────────

@pytest.mark.asyncio
async def test_13_stale_gps_freshness_zero_impact():
    """GPS location updated > 10 min ago is marked STALE with 0 min impact."""
    provider = GPSLocationProvider()
    stale_timestamp = datetime.now(timezone.utc) - timedelta(minutes=15)

    res = await provider.evaluate(
        technician_lat=37.7749,
        technician_lon=-122.4194,
        tech_updated_at=stale_timestamp,
    )

    assert res.status == DataSourceStatus.STALE
    assert res.freshness == "STALE"
    assert res.impact_minutes == 0
    assert res.impact_classification == "NOT_APPLIED"
    assert res.data_age_seconds is not None
    assert res.data_age_seconds >= 600


# ── Scenario 14: Stale TomTom Traffic ─────────────────────────────────────────

@pytest.mark.asyncio
async def test_14_stale_tomtom_traffic_zero_impact():
    """Traffic data marked STALE yields 0 impact in context aggregation."""
    stale_res = ContextProviderResult(
        source_name="Traffic Data (TomTom API)",
        status=DataSourceStatus.STALE,
        impact_minutes=5,
        description="TomTom data aged > 5 min",
        sampled_at=datetime.now(timezone.utc) - timedelta(minutes=7),
        category="TRAFFIC",
        provenance="REAL",
        freshness="STALE",
        impact_classification="NOT_APPLIED",
        data_age_seconds=420,
    )

    agg = ContextAggregationService()
    summary = agg.aggregate([stale_res], baseline_eta_minutes=20, distance_km=10.0, distance_miles=6.2)

    assert summary.stale_count == 1
    assert summary.total_adjustment_minutes == 0


# ── Scenario 15: Stale Weather (> 3 Hours Old) ────────────────────────────────

@pytest.mark.asyncio
async def test_15_stale_weather_zero_impact():
    """Weather data older than 3 hours is classified STALE with 0 min impact."""
    provider = WeatherProvider()
    stale_time = datetime.now(timezone.utc) - timedelta(hours=4)
    mock_meteo_payload = {
        "current": {
            "temperature_2m": 18.0,
            "relative_humidity_2m": 80,
            "apparent_temperature": 18.0,
            "precipitation": 5.0,
            "rain": 5.0,
            "weather_code": 63,
            "wind_speed_10m": 15.0,
            "wind_direction_10m": 180,
            "time": stale_time.isoformat(),
        }
    }

    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = httpx.Response(200, json=mock_meteo_payload)
        res = await provider.evaluate(lat=37.77, lon=-122.41, baseline_eta_minutes=25)

    assert res.status == DataSourceStatus.STALE
    assert res.freshness == "STALE"
    assert res.impact_minutes == 0
    assert res.impact_classification == "NOT_APPLIED"


# ── Scenario 16: Causal Deduplication across Providers ─────────────────────────

@pytest.mark.asyncio
async def test_16_causal_deduplication_shared_corridor():
    """Traffic congestion + road restriction + event on same corridor do NOT double count."""
    now = datetime.now(timezone.utc)

    # 1. Traffic: 4 min slowdown on route
    traffic_res = ContextProviderResult(
        source_name="Traffic Data",
        status=DataSourceStatus.AVAILABLE,
        impact_minutes=4,
        description="4 min congestion on Market St corridor",
        sampled_at=now,
        category="TRAFFIC",
        provenance="REAL",
        freshness="FRESH",
        impact_classification="INCLUDED_IN_LIVE_ROUTE",
    )

    # 2. Road Restriction: incident reports 5 min delay on same corridor
    # Causal deduplication: only net difference (5 - 4 = 1 min) or alternate detour applied
    road_res = ContextProviderResult(
        source_name="Road Restrictions",
        status=DataSourceStatus.AVAILABLE,
        impact_minutes=5,
        description="Incident on Market St",
        sampled_at=now,
        category="ROAD",
        provenance="REAL",
        freshness="FRESH",
        impact_classification="INCLUDED_IN_LIVE_ROUTE",  # Or adjusted
    )

    # 3. Event: on same corridor, traffic already captures it
    event_res = ContextProviderResult(
        source_name="Events",
        status=DataSourceStatus.AVAILABLE,
        impact_minutes=0,
        description="Event on corridor captured in live traffic",
        sampled_at=now,
        category="EVENTS",
        provenance="REAL",
        freshness="FRESH",
        impact_classification="INCLUDED_IN_LIVE_ROUTE",
    )

    agg = ContextAggregationService()
    summary = agg.aggregate(
        [traffic_res, road_res, event_res],
        baseline_eta_minutes=18,
        distance_km=15.0,
        distance_miles=9.3,
    )

    # Traffic is included in live route (4m delay from free flow)
    # Road restriction classified as INCLUDED_IN_LIVE_ROUTE has 0 net additional
    # Event has 0 net additional
    # Total ETA is 18 + 4 = 22 min, NOT 18 + 4 + 5 = 27 min!
    assert 18 + summary.total_adjustment_minutes == 22
    assert summary.additional_verified_impact_minutes == 0


# ── Scenario 17: Metric Unit Correctness ──────────────────────────────────────

def test_17_metric_unit_correctness():
    """All distance conversions to meters, km, and display strings are mathematically exact."""
    assert _miles_to_meters(1.0) == 1609.3
    assert _miles_to_meters(0.03) == 48.3  # ~50m
    assert _miles_to_meters(0.25) == 402.3  # ~400m
    assert _meters_to_miles(1609.344) == 1.0

    assert _format_metric_distance(50.0) == "50 m"
    assert _format_metric_distance(400.0) == "400 m"
    assert _format_metric_distance(1500.0) == "1.50 km"
    assert _format_metric_distance(12500.0) == "12.50 km"
    assert _format_metric_distance(None) == "—"


# ── Scenario 18: End-to-End ETAResponse Schema & Explainability ────────────────

@pytest.mark.asyncio
async def test_18_end_to_end_eta_response_explainability(monkeypatch):
    """Full calculate_job_eta pipeline populates all Phase 3 fields with trusted explainability."""
    monkeypatch.setattr(settings, "TRAFFIC_PROVIDER", "tomtom")
    monkeypatch.setattr(settings, "TRAFFIC_API_KEY", "test-key")
    monkeypatch.setattr(settings, "ROAD_RESTRICTION_API_KEY", "test-key")

    job_id = uuid.uuid4()
    tech_id = uuid.uuid4()

    mock_job = MagicMock(spec=Job)
    mock_job.id = job_id
    mock_job.job_number = "JOB-P3-100"
    mock_job.latitude = DEST_LAT
    mock_job.longitude = DEST_LON
    mock_job.eta_overrides = []

    mock_tech = MagicMock(spec=Technician)
    mock_tech.id = tech_id
    mock_tech.employee_code = "TECH-P3-01"
    mock_tech.current_latitude = ORIGIN_LAT
    mock_tech.current_longitude = ORIGIN_LON
    mock_tech.availability_status = "AVAILABLE"
    mock_tech.updated_at = datetime.now(timezone.utc)
    mock_tech.user = MagicMock(spec=User)
    mock_tech.user.full_name = "Morgan Lee"

    mock_assign = MagicMock(spec=Assignment)
    mock_assign.id = uuid.uuid4()
    mock_assign.job_id = job_id
    mock_assign.technician_id = tech_id
    mock_assign.technician = mock_tech
    mock_assign.assignment_status = "ASSIGNED"
    mock_job.assignments = [mock_assign]

    mock_session = AsyncMock()
    job_result = MagicMock()
    job_result.scalar_one_or_none.return_value = mock_job
    tech_result = MagicMock()
    tech_result.scalar_one_or_none.return_value = mock_tech
    settings_result = MagicMock()
    settings_result.scalar_one_or_none.return_value = None
    mock_session.execute = AsyncMock(side_effect=[job_result, settings_result, tech_result, tech_result, settings_result])

    @asynccontextmanager
    async def mock_session_ctx():
        yield mock_session

    route_payload = {
        "routes": [{
            "summary": {
                "lengthInMeters": 5400,
                "travelTimeInSeconds": 600,  # 10 min live
                "noTrafficTravelTimeInSeconds": 480,  # 8 min free flow
                "trafficDelayInSeconds": 120,  # 2 min traffic
            },
            "legs": [{
                "points": [
                    {"latitude": 37.7770, "longitude": -122.4160},
                    {"latitude": 37.7810, "longitude": -122.4120},
                    {"latitude": 37.7850, "longitude": -122.4080},
                    {"latitude": 37.7875, "longitude": -122.4040},
                    {"latitude": 37.7890, "longitude": -122.4010},
                ]
            }],
        }]
    }

    incident = _build_incident(coords=[-122.4080, 37.7850])
    alt_route_payload = {
        "routes": [{
            "summary": {
                "travelTimeInSeconds": 840,  # 14 min detour vs 10 min live -> +4 min
                "lengthInMeters": 6800,
            }
        }]
    }

    async def side_effect_get(url, *args, **kwargs):
        url_str = str(url)
        if "calculateRoute" in url_str:
            return httpx.Response(200, json=route_payload)
        elif "incidentDetails" in url_str:
            return httpx.Response(200, json={"incidents": [incident]})
        return httpx.Response(200, json={})

    async def side_effect_post(url, *args, **kwargs):
        return httpx.Response(200, json=alt_route_payload)

    eta_service = ETAService()
    with patch("app.services.eta_service.AsyncSessionLocal", side_effect=mock_session_ctx), \
         patch("httpx.AsyncClient.get", new_callable=AsyncMock, side_effect=side_effect_get), \
         patch("httpx.AsyncClient.post", new_callable=AsyncMock, side_effect=side_effect_post):
        resp: ETAResponse = await eta_service.calculate_job_eta(job_id)

    assert resp.is_context_sufficient is True
    assert resp.baseline_eta_minutes == 8  # Free-flow
    assert resp.live_route_eta_minutes == 10  # Live route
    assert resp.traffic_delay_minutes == 2
    assert resp.routed_distance_meters == 5400.0
    assert resp.routed_distance_km == 5.4
    assert resp.additional_verified_impact_minutes == 4  # Net road detour
    assert resp.context_aware_eta_minutes == 14  # Live (10) + detour (4) = 14 min

    # Verify all factors and data sources have freshness and impact_classification
    for ds in resp.data_sources:
        assert ds.freshness in ("FRESH", "STALE", "UNAVAILABLE", "UNKNOWN")
        assert ds.impact_classification in (
            "INCLUDED_IN_LIVE_ROUTE",
            "INCREMENTAL_DETOUR",
            "INDEPENDENT_CONTEXT",
            "NOT_APPLIED",
            "UNAVAILABLE",
        )
