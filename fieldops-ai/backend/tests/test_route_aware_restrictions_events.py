"""
Phase 2 Comprehensive Test Suite:
Route-Aware Road Restrictions & Event Relevance

Verifies:
1. Incident far from selected route -> NOT_RELEVANT -> 0 ETA impact
2. Incident near destination but on a different road -> NOT_RELEVANT -> 0 ETA impact
3. Incident geometry intersects selected route -> RELEVANT
4. Route-relevant closure with valid alternate route -> derived detour -> no arbitrary +15/+30
5. Route-relevant closure without reliable alternate-route calculation -> 0 min impact, no fabricated delay
6. Event near destination but outside route -> REAL event -> NOT_RELEVANT -> 0 impact
7. Event near route but no measurable traffic effect -> REAL event -> 0 impact, no fabricated penalty
8. Route-relevant event with defensible traffic evidence -> DERIVED impact only
9. Multiple unrelated incidents/events -> none inflate ETA
10. Step 1 TomTom authoritative ETA foundation remains preserved
"""

import json
import math
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch
import uuid

import httpx
import pytest

from app.core.config import settings
from app.services.context_providers import (
    ContextProviderResult,
    DataSourceStatus,
    EventsDataProvider,
    RoadRestrictionProvider,
    STRICT_EVENT_CORRIDOR_BUFFER_MILES,
    STRICT_ROAD_CORRIDOR_BUFFER_MILES,
)
from app.services.eta_service import ETAService, _haversine_miles


# -----------------------------------------------------------------------------
# Common Test Fixtures: Market Street Corridor (San Francisco)
# Origin: Market & 8th St (37.7770, -122.4160)
# Destination: Market & 2nd St (37.7890, -122.4010)
# -----------------------------------------------------------------------------

ORIGIN_LAT = 37.7770
ORIGIN_LON = -122.4160
DEST_LAT = 37.7890
DEST_LON = -122.4010

# GeoJSON coordinates: [[lon, lat], ...]
SAMPLE_ROUTE_GEOMETRY = [
    [-122.4160, 37.7770],
    [-122.4120, 37.7810],
    [-122.4080, 37.7850],
    [-122.4040, 37.7875],
    [-122.4010, 37.7890],
]


def _build_incident(
    inc_id="INC-001",
    coords=None,
    geom_type="Point",
    delay=None,
    magnitude=3,
    icon_category=8,
    road_from="Market St",
    road_to="4th St",
):
    if coords is None:
        coords = [-122.4080, 37.7850]  # Directly on route
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
            "events": [{"code": 108, "description": "Construction road work"}],
            "startTime": (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat(),
            "endTime": (datetime.now(timezone.utc) + timedelta(hours=5)).isoformat(),
            "from": road_from,
            "to": road_to,
            "length": 350.0,
        },
    }


def _build_event(
    evt_id="EVT-001",
    title="City Tech Convention",
    coords=None,
    category="conferences",
    rank=75,
    attendance=5000,
):
    if coords is None:
        coords = [-122.4081, 37.7851]  # Adjacent to route
    return {
        "id": evt_id,
        "title": title,
        "category": category,
        "rank": rank,
        "phq_attendance": attendance,
        "location": coords,  # [lon, lat]
        "start": (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat(),
        "end": (datetime.now(timezone.utc) + timedelta(hours=4)).isoformat(),
        "state": "active",
    }


# =============================================================================
# 1. Incident far from selected route -> NOT_RELEVANT -> 0 ETA impact
# =============================================================================

@pytest.mark.asyncio
async def test_1_incident_far_from_route(monkeypatch):
    monkeypatch.setattr(settings, "ROAD_RESTRICTION_API_KEY", "test-key")
    # Twin Peaks area: ~3 miles southwest of Market St corridor
    far_incident = _build_incident(
        inc_id="INC-FAR-01",
        coords=[-122.4470, 37.7540],
        delay=600,
    )
    mock_payload = {"incidents": [far_incident]}

    provider = RoadRestrictionProvider()
    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = httpx.Response(200, json=mock_payload)
        res = await provider.evaluate(
            origin_lat=ORIGIN_LAT, origin_lon=ORIGIN_LON,
            dest_lat=DEST_LAT, dest_lon=DEST_LON,
            route_geometry=SAMPLE_ROUTE_GEOMETRY,
            original_route_time_seconds=600,
        )

    assert res.status == DataSourceStatus.AVAILABLE
    assert res.provenance == "REAL"
    assert res.impact_minutes == 0
    assert res.is_route_relevant is False
    assert res.relevance_status == "NOT_RELEVANT"
    assert res.applied_to_eta is False
    assert "outside selected route corridor" in res.relevance_reason


# =============================================================================
# 2. Incident near destination but on a different road -> NOT_RELEVANT
# =============================================================================

@pytest.mark.asyncio
async def test_2_incident_near_destination_different_road(monkeypatch):
    monkeypatch.setattr(settings, "ROAD_RESTRICTION_API_KEY", "test-key")
    # Destination is at (37.7890, -122.4010).
    # Bush St / Chinatown incident is ~0.4 miles away, but Market St corridor buffer is 0.03 mi.
    diff_road_incident = _build_incident(
        inc_id="INC-BUSH-01",
        coords=[-122.4050, 37.7940],  # ~0.4 mi north on Bush St
        delay=900,
        road_from="Bush St",
        road_to="Grant Ave",
    )
    mock_payload = {"incidents": [diff_road_incident]}

    provider = RoadRestrictionProvider()
    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = httpx.Response(200, json=mock_payload)
        res = await provider.evaluate(
            origin_lat=ORIGIN_LAT, origin_lon=ORIGIN_LON,
            dest_lat=DEST_LAT, dest_lon=DEST_LON,
            route_geometry=SAMPLE_ROUTE_GEOMETRY,
            original_route_time_seconds=600,
        )

    assert res.impact_minutes == 0
    assert res.is_route_relevant is False
    assert res.relevance_status == "NOT_RELEVANT"
    assert res.applied_to_eta is False
    assert res.distance_to_route > STRICT_ROAD_CORRIDOR_BUFFER_MILES


# =============================================================================
# 3. Incident geometry (LineString) intersects selected route -> RELEVANT
# =============================================================================

@pytest.mark.asyncio
async def test_3_incident_geometry_intersects_route(monkeypatch):
    monkeypatch.setattr(settings, "ROAD_RESTRICTION_API_KEY", "test-key")
    # Cross street closure intersecting Market St between 4th & 5th
    cross_street_segment = [
        [-122.4090, 37.7830],
        [-122.4070, 37.7870],
    ]
    intersecting_incident = _build_incident(
        inc_id="INC-INTERSECT-01",
        coords=cross_street_segment,
        geom_type="LineString",
        delay=360,  # 6 min delay
        icon_category=9,  # Road Works
        road_from="4th St",
        road_to="Mission St",
    )
    mock_payload = {"incidents": [intersecting_incident]}

    provider = RoadRestrictionProvider()
    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = httpx.Response(200, json=mock_payload)
        res = await provider.evaluate(
            origin_lat=ORIGIN_LAT, origin_lon=ORIGIN_LON,
            dest_lat=DEST_LAT, dest_lon=DEST_LON,
            route_geometry=SAMPLE_ROUTE_GEOMETRY,
            original_route_time_seconds=600,
        )

    assert res.status == DataSourceStatus.AVAILABLE
    assert res.provenance == "REAL"
    assert res.is_route_relevant is True
    assert res.relevance_status == "RELEVANT"
    assert res.applied_to_eta is True
    assert res.impact_minutes == 6
    assert "intersects selected route" in res.relevance_reason


# =============================================================================
# 4. Route-relevant closure with valid alternate route -> derived detour
# =============================================================================

@pytest.mark.asyncio
async def test_4_closure_with_valid_alternate_route(monkeypatch):
    monkeypatch.setattr(settings, "ROAD_RESTRICTION_API_KEY", "test-key")
    # Full road closure directly on route segment, no explicit delay reported
    closure_incident = _build_incident(
        inc_id="INC-CLOSE-01",
        coords=[-122.4080, 37.7850],
        icon_category=8,  # Road Closed
        magnitude=4,      # Blocking
        delay=None,
    )
    mock_payload = {"incidents": [closure_incident]}

    # Alternate route via avoidAreas POST returns 1020s (17 min) vs original 600s (10 min) -> +7 min detour
    alt_route_response = {
        "routes": [{
            "summary": {
                "travelTimeInSeconds": 1020,
                "lengthInMeters": 3100,
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
            original_route_time_seconds=600,
        )

    assert res.status == DataSourceStatus.AVAILABLE
    assert res.provenance == "REAL"
    assert res.is_road_closed is True
    assert res.is_route_relevant is True
    assert res.relevance_status == "RELEVANT"
    assert res.applied_to_eta is True
    assert res.impact_minutes == 7  # Derived: round((1020 - 600) / 60) = 7
    assert res.detour_travel_time_minutes == 17
    assert "Detour derived from alternate route" in res.relevance_reason


# =============================================================================
# 5. Route-relevant closure without reliable alternate route -> no fabricated delay
# =============================================================================

@pytest.mark.asyncio
async def test_5_closure_without_reliable_alternate_route(monkeypatch):
    monkeypatch.setattr(settings, "ROAD_RESTRICTION_API_KEY", "test-key")
    closure_incident = _build_incident(
        inc_id="INC-CLOSE-NOALT-01",
        coords=[-122.4080, 37.7850],
        icon_category=8,
        magnitude=4,
        delay=None,
    )
    mock_payload = {"incidents": [closure_incident]}

    provider = RoadRestrictionProvider()
    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get, \
         patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_get.return_value = httpx.Response(200, json=mock_payload)
        # Alternate route service returns HTTP 503 or error
        mock_post.return_value = httpx.Response(503, text="Service Unavailable")

        res = await provider.evaluate(
            origin_lat=ORIGIN_LAT, origin_lon=ORIGIN_LON,
            dest_lat=DEST_LAT, dest_lon=DEST_LON,
            route_geometry=SAMPLE_ROUTE_GEOMETRY,
            original_route_time_seconds=600,
        )

    assert res.status == DataSourceStatus.AVAILABLE
    assert res.provenance == "REAL"
    assert res.is_road_closed is True
    assert res.is_route_relevant is True
    assert res.relevance_status == "RELEVANT"
    assert res.impact_minutes == 0  # Strictly 0 min — zero fake data!
    assert res.applied_to_eta is False
    assert "Alternate route calculation unavailable" in res.relevance_reason


# =============================================================================
# 6. Event near destination but outside route corridor -> NOT_RELEVANT -> 0 impact
# =============================================================================

@pytest.mark.asyncio
async def test_6_event_near_destination_outside_route(monkeypatch):
    monkeypatch.setattr(settings, "EVENTS_API_KEY", "test-key")
    # Event at Embarcadero Center (~0.6 mi east of destination, outside route corridor buffer 0.25 mi)
    far_event = _build_event(
        evt_id="EVT-EMBARCADERO-01",
        title="Fashion & Retail Expo",
        coords=[-122.3950, 37.7940],
        category="festivals",
        rank=80,
    )
    mock_payload = {"results": [far_event]}

    provider = EventsDataProvider()
    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = httpx.Response(200, json=mock_payload)
        res = await provider.evaluate(
            dest_lat=DEST_LAT, dest_lon=DEST_LON,
            route_geometry=SAMPLE_ROUTE_GEOMETRY,
            traffic_delay_seconds=180,
        )

    assert res.status == DataSourceStatus.AVAILABLE
    assert res.provenance == "REAL"
    assert res.impact_minutes == 0
    assert res.is_route_relevant is False
    assert res.relevance_status == "NOT_RELEVANT"
    assert res.applied_to_eta is False
    assert res.distance_to_route > STRICT_EVENT_CORRIDOR_BUFFER_MILES
    assert "outside 0.25 mi corridor buffer" in res.relevance_reason


# =============================================================================
# 7. Event near route but no measurable traffic effect -> 0 impact
# =============================================================================

@pytest.mark.asyncio
async def test_7_event_near_route_no_traffic_slowdown(monkeypatch):
    monkeypatch.setattr(settings, "EVENTS_API_KEY", "test-key")
    # Event adjacent to Market St corridor (distance ~0.05 mi)
    route_event = _build_event(
        evt_id="EVT-MARKET-01",
        title="San Francisco Tech Meetup",
        coords=[-122.4082, 37.7852],
        category="community",
        rank=50,
        attendance=800,
    )
    mock_payload = {"results": [route_event]}

    provider = EventsDataProvider()
    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = httpx.Response(200, json=mock_payload)
        # Live routing reports traffic_delay_seconds = 0
        res = await provider.evaluate(
            dest_lat=DEST_LAT, dest_lon=DEST_LON,
            route_geometry=SAMPLE_ROUTE_GEOMETRY,
            traffic_delay_seconds=0,
        )

    assert res.status == DataSourceStatus.AVAILABLE
    assert res.provenance == "REAL"
    assert res.is_route_relevant is True
    assert res.impact_minutes == 0  # Strictly 0 min delay applied
    assert res.applied_to_eta is False
    assert "measurable ETA impact unavailable" in res.relevance_reason


# =============================================================================
# 8. Route-relevant event with defensible traffic evidence -> derived impact only
# =============================================================================

@pytest.mark.asyncio
async def test_8_event_near_route_with_traffic_evidence(monkeypatch):
    monkeypatch.setattr(settings, "EVENTS_API_KEY", "test-key")
    # Major concert at arena adjacent to route corridor with measured road delay
    route_event = _build_event(
        evt_id="EVT-MAJOR-01",
        title="Arena Major Concert",
        coords=[-122.4082, 37.7852],
        category="concerts",
        rank=85,
        attendance=18000,
    )
    route_event["measured_delay_minutes"] = 4
    mock_payload = {"results": [route_event]}

    provider = EventsDataProvider()
    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = httpx.Response(200, json=mock_payload)
        res = await provider.evaluate(
            dest_lat=DEST_LAT, dest_lon=DEST_LON,
            route_geometry=SAMPLE_ROUTE_GEOMETRY,
            traffic_delay_seconds=0,
        )

    assert res.status == DataSourceStatus.AVAILABLE
    assert res.provenance == "REAL"
    assert res.is_route_relevant is True
    assert res.relevance_status == "RELEVANT"
    assert res.applied_to_eta is True
    assert res.impact_minutes == 4
    assert "Measured traffic delay (+4m)" in res.relevance_reason


# =============================================================================
# 9. Multiple unrelated incidents/events -> none inflate ETA
# =============================================================================

@pytest.mark.asyncio
async def test_9_multiple_unrelated_incidents_events(monkeypatch):
    monkeypatch.setattr(settings, "ROAD_RESTRICTION_API_KEY", "test-key")
    monkeypatch.setattr(settings, "EVENTS_API_KEY", "test-key")

    unrelated_incidents = [
        _build_incident(f"INC-IRR-{i}", coords=[-122.4500 + (i * 0.01), 37.7400 + (i * 0.01)], delay=300)
        for i in range(4)
    ]
    unrelated_events = [
        _build_event(f"EVT-IRR-{i}", title=f"Far Gathering {i}", coords=[-122.4600 + (i * 0.01), 37.7300 + (i * 0.01)])
        for i in range(3)
    ]

    road_provider = RoadRestrictionProvider()
    events_provider = EventsDataProvider()

    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = httpx.Response(200, json={"incidents": unrelated_incidents})
        road_res = await road_provider.evaluate(
            origin_lat=ORIGIN_LAT, origin_lon=ORIGIN_LON,
            dest_lat=DEST_LAT, dest_lon=DEST_LON,
            route_geometry=SAMPLE_ROUTE_GEOMETRY,
            original_route_time_seconds=600,
        )

    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = httpx.Response(200, json={"results": unrelated_events})
        events_res = await events_provider.evaluate(
            dest_lat=DEST_LAT, dest_lon=DEST_LON,
            route_geometry=SAMPLE_ROUTE_GEOMETRY,
            traffic_delay_seconds=0,
        )

    assert road_res.impact_minutes == 0
    assert road_res.applied_to_eta is False
    assert events_res.impact_minutes == 0
    assert events_res.applied_to_eta is False


# =============================================================================
# 10. Step 1 TomTom authoritative ETA foundation preserved
# =============================================================================

@pytest.mark.asyncio
async def test_10_step1_tomtom_authoritative_foundation_preserved(monkeypatch):
    """Verify that TomTom live routing baseline + traffic delay calculations remain untouched."""
    from app.services.context_providers import TrafficDataProvider

    monkeypatch.setattr(settings, "TRAFFIC_API_KEY", "valid-key")
    monkeypatch.setattr(settings, "TRAFFIC_PROVIDER", "tomtom")

    provider = TrafficDataProvider()
    tomtom_response = {
        "routes": [{
            "summary": {
                "lengthInMeters": 4500,
                "travelTimeInSeconds": 720,             # 12 min live
                "trafficDelayInSeconds": 180,           # 3 min delay
                "noTrafficTravelTimeInSeconds": 540,    # 9 min free-flow baseline
            },
            "legs": [{
                "points": [
                    {"latitude": ORIGIN_LAT, "longitude": ORIGIN_LON},
                    {"latitude": DEST_LAT, "longitude": DEST_LON},
                ]
            }],
        }]
    }

    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = httpx.Response(200, json=tomtom_response)
        res = await provider.evaluate(
            origin_lat=ORIGIN_LAT, origin_lon=ORIGIN_LON,
            dest_lat=DEST_LAT, dest_lon=DEST_LON,
        )

    assert res.status == DataSourceStatus.AVAILABLE
    assert res.provenance == "REAL"
    assert res.free_flow_travel_time_seconds == 540     # Authoritative baseline
    assert res.live_travel_time_seconds == 720          # Authoritative live route
    assert res.traffic_delay_seconds == 180             # Authoritative traffic delay
    assert res.impact_minutes == 3                      # 180s / 60
    assert res.route_geometry is not None               # GeoJSON coordinates preserved
