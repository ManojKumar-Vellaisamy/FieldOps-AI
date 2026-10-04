"""
Phase 4D Automated Test Suite:
Real Route-Aware Road Closure + Detour Accuracy.

Verifies:
1. Off-route closure (2 km away) -> 0 impact, NOT_RELEVANT.
2. Near-destination but off-route closure (1.5 km from dest) -> 0 impact, NOT_RELEVANT.
3. Route-intersecting closure -> RELEVANT.
4. Relevant closure + alternate route same duration -> 0 detour, RELEVANT_NO_ADDITIONAL_DETOUR.
5. Relevant closure + alternate route 12 min slower -> +12 min detour, RELEVANT_INCREMENTAL_DETOUR.
6. Alternate route still intersects closure -> reject alternate route as invalid, 0 detour, UNAVAILABLE.
7. Long closure geometry -> derive bounding box around entire affected segment, not just center.
8. Alternate route unavailable -> 0 fake delay, honest UNAVAILABLE state.
9. Live traffic already includes incident slowdown -> no double counting.
10. OSRM route geometry works for route-corridor checking when TomTom routing is unavailable.
11. Point-only incident fallback works with strict 50m metric threshold.
12. No old arbitrary +15/+30 closure heuristic remains active.
"""

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch
import httpx
import pytest

from app.core.config import settings
from app.services.context_providers import (
    ContextProviderResult,
    DataSourceStatus,
    RoadRestrictionProvider,
    STRICT_ROAD_CORRIDOR_BUFFER_METERS,
    _calculate_closure_detour,
)

# -----------------------------------------------------------------------------
# Common Test Fixtures: Market Street Corridor (San Francisco)
# Origin: Market & 8th St (37.7770, -122.4160)
# Destination: Market & 2nd St (37.7890, -122.4010)
# Route length approx 1.8 km along Market St
# -----------------------------------------------------------------------------
ORIGIN_LAT = 37.7770
ORIGIN_LON = -122.4160
DEST_LAT = 37.7890
DEST_LON = -122.4010

SAMPLE_ROUTE_GEOMETRY = [
    [-122.4160, 37.7770],
    [-122.4120, 37.7810],
    [-122.4080, 37.7850],
    [-122.4040, 37.7875],
    [-122.4010, 37.7890],
]


def _build_incident_feature(
    inc_id="INC-001",
    coords=None,
    geom_type="Point",
    icon_category=8,
    magnitude=4,
    delay=None,
    road_from="Market St",
    road_to="4th St",
    is_closed=True,
    start_time=None,
    end_time=None,
):
    if coords is None:
        coords = [-122.4080, 37.7850]
    now = datetime.now(timezone.utc)
    if start_time is None:
        start_time = (now - timedelta(hours=1)).isoformat()
    if end_time is None:
        end_time = (now + timedelta(hours=5)).isoformat()

    desc = "Road closure due to emergency water main repair" if is_closed else "Traffic slowdown due to road incident"
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
            "events": [{"code": 108 if is_closed else 1, "description": desc}],
            "startTime": start_time,
            "endTime": end_time,
            "from": road_from,
            "to": road_to,
            "is_closed": is_closed,
            "length": 400.0,
        },
    }


# =============================================================================
# 1. Off-route closure -> 0 impact, NOT_RELEVANT
# =============================================================================
@pytest.mark.asyncio
async def test_case_1_off_route_closure(monkeypatch):
    """Closure is 2 km away from route -> NOT_RELEVANT, 0 additional ETA impact."""
    monkeypatch.setattr(settings, "ROAD_RESTRICTION_API_KEY", "test-key-road")

    # Coordinates in Mission District (~2 km away from Market St route)
    incident = _build_incident_feature(
        inc_id="INC-OFF-ROUTE-01",
        coords=[-122.4185, 37.7590],  # ~2 km south
        road_from="Mission St",
        road_to="20th St",
    )
    mock_payload = {"incidents": [incident]}

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
    assert res.causal_status == "NOT_RELEVANT"
    assert res.applied_to_eta is False
    assert res.distance_to_route_meters > 1500
    assert "outside selected route corridor" in res.relevance_reason


# =============================================================================
# 2. Near-destination but off-route closure -> 0 impact, NOT_RELEVANT
# =============================================================================
@pytest.mark.asyncio
async def test_case_2_near_destination_off_route_closure(monkeypatch):
    """Closure is 1.5 km from destination but does NOT intersect the route -> 0 impact."""
    monkeypatch.setattr(settings, "ROAD_RESTRICTION_API_KEY", "test-key-road")

    # Destination is at (37.7890, -122.4010).
    # Incident on Nob Hill / Bush St is ~1.5 km away from destination and off-corridor.
    incident = _build_incident_feature(
        inc_id="INC-DEST-OFF-02",
        coords=[-122.4080, 37.7990],  # ~1.5 km north of corridor
        road_from="Bush St",
        road_to="Taylor St",
    )
    mock_payload = {"incidents": [incident]}

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
    assert res.causal_status == "NOT_RELEVANT"
    assert res.applied_to_eta is False
    assert "not affecting this route" in res.description


# =============================================================================
# 3. Route-intersecting closure -> RELEVANT
# =============================================================================
@pytest.mark.asyncio
async def test_case_3_route_intersecting_closure(monkeypatch):
    """Closure intersects the selected route -> RELEVANT."""
    monkeypatch.setattr(settings, "ROAD_RESTRICTION_API_KEY", "test-key-road")

    cross_street_closure = [
        [-122.4090, 37.7830],
        [-122.4070, 37.7870],
    ]
    incident = _build_incident_feature(
        inc_id="INC-INTERSECT-03",
        coords=cross_street_closure,
        geom_type="LineString",
        road_from="Market St",
        road_to="4th St",
        is_closed=True,
    )
    mock_payload = {"incidents": [incident]}

    provider = RoadRestrictionProvider()
    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get, \
         patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_get.return_value = httpx.Response(200, json=mock_payload)
        # Alternate route with +5 min detour
        mock_post.return_value = httpx.Response(200, json={
            "routes": [{
                "summary": {"travelTimeInSeconds": 900, "lengthInMeters": 2400},
                "legs": [{"points": [
                    {"latitude": 37.7770, "longitude": -122.4160},
                    {"latitude": 37.7740, "longitude": -122.4100},  # Mission St detour
                    {"latitude": 37.7890, "longitude": -122.4010},
                ]}]
            }]
        })

        res = await provider.evaluate(
            origin_lat=ORIGIN_LAT, origin_lon=ORIGIN_LON,
            dest_lat=DEST_LAT, dest_lon=DEST_LON,
            route_geometry=SAMPLE_ROUTE_GEOMETRY,
            original_route_time_seconds=600,
        )

    assert res.is_route_relevant is True
    assert res.relevance_status == "RELEVANT"
    assert res.affected_geometry_available is True
    assert res.alternate_route_valid is True
    assert res.impact_minutes == 5  # (900 - 600) / 60 = 5
    assert res.causal_status == "RELEVANT_INCREMENTAL_DETOUR"


# =============================================================================
# 4. Relevant closure + alternate route same duration -> 0 detour
# =============================================================================
@pytest.mark.asyncio
async def test_case_4_relevant_closure_same_duration_detour_zero(monkeypatch):
    """Closure intersects route, but alternate route takes the SAME travel time -> 0 detour."""
    monkeypatch.setattr(settings, "ROAD_RESTRICTION_API_KEY", "test-key-road")

    incident = _build_incident_feature(
        inc_id="INC-SAME-TIME-04",
        coords=[-122.4080, 37.7850],
        road_from="Market St",
        road_to="5th St",
        is_closed=True,
    )
    mock_payload = {"incidents": [incident]}

    # Alternate route has duration 600s, identical to original_route_time_seconds (600s)
    alt_route_response = {
        "routes": [{
            "summary": {"travelTimeInSeconds": 600, "lengthInMeters": 2100},
            "legs": [{"points": [
                {"latitude": 37.7770, "longitude": -122.4160},
                {"latitude": 37.7800, "longitude": -122.4200},  # parallel street
                {"latitude": 37.7890, "longitude": -122.4010},
            ]}]
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

    assert res.is_route_relevant is True
    assert res.relevance_status == "RELEVANT"
    assert res.impact_minutes == 0
    assert res.detour_seconds == 0
    assert res.applied_to_eta is False
    assert res.causal_status == "RELEVANT_NO_ADDITIONAL_DETOUR"
    assert "no additional detour time measured" in res.relevance_reason


# =============================================================================
# 5. Relevant closure + alternate route 12 min slower -> +12 min detour
# =============================================================================
@pytest.mark.asyncio
async def test_case_5_relevant_closure_incremental_detour_12min(monkeypatch):
    """Closure intersects route, alternate route is 12 minutes slower -> +12 min."""
    monkeypatch.setattr(settings, "ROAD_RESTRICTION_API_KEY", "test-key-road")

    incident = _build_incident_feature(
        inc_id="INC-DETOUR-12M-05",
        coords=[-122.4080, 37.7850],
        road_from="Market St",
        road_to="4th St",
        is_closed=True,
    )
    mock_payload = {"incidents": [incident]}

    # Original time: 600s (10 min). Alternate route: 1320s (22 min) -> detour: 720s (12 min)
    alt_route_response = {
        "routes": [{
            "summary": {"travelTimeInSeconds": 1320, "lengthInMeters": 4200},
            "legs": [{"points": [
                {"latitude": 37.7770, "longitude": -122.4160},
                {"latitude": 37.7700, "longitude": -122.4100},  # Folsom St detour
                {"latitude": 37.7890, "longitude": -122.4010},
            ]}]
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

    assert res.is_route_relevant is True
    assert res.impact_minutes == 12
    assert res.detour_seconds == 720
    assert res.applied_to_eta is True
    assert res.causal_status == "RELEVANT_INCREMENTAL_DETOUR"
    assert res.alternate_route_valid is True
    assert "adds 12 min" in res.relevance_reason or "alternate route adds 12 min" in res.relevance_reason


# =============================================================================
# 6. Alternate route still intersects closure -> reject alternate
# =============================================================================
@pytest.mark.asyncio
async def test_case_6_alternate_route_still_intersects_closure_rejected(monkeypatch):
    """Alternate route returned by provider still passes through closure segment -> rejected, 0 detour."""
    monkeypatch.setattr(settings, "ROAD_RESTRICTION_API_KEY", "test-key-road")

    # Closure at Market & 4th (-122.4080, 37.7850)
    incident = _build_incident_feature(
        inc_id="INC-REINTERSECT-06",
        coords=[-122.4080, 37.7850],
        road_from="Market St",
        road_to="4th St",
        is_closed=True,
    )
    mock_payload = {"incidents": [incident]}

    # Alternate route erroneously still passes through Market & 4th (-122.4080, 37.7850)
    alt_route_response = {
        "routes": [{
            "summary": {"travelTimeInSeconds": 1500, "lengthInMeters": 3500},
            "legs": [{"points": [
                {"latitude": 37.7770, "longitude": -122.4160},
                {"latitude": 37.7850, "longitude": -122.4080},  # Directly hits the closure!
                {"latitude": 37.7890, "longitude": -122.4010},
            ]}]
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

    assert res.is_route_relevant is True
    assert res.alternate_route_valid is False
    assert res.impact_minutes == 0  # Rejection guarantees 0 fake delay
    assert res.applied_to_eta is False
    assert res.causal_status == "UNAVAILABLE"
    assert "still intersects the closed road segment" in res.relevance_reason


# =============================================================================
# 7. Long closure geometry -> avoid affected segment, not only incident center
# =============================================================================
@pytest.mark.asyncio
async def test_case_7_long_closure_geometry_bounding_box_avoidance(monkeypatch):
    """LineString closure bounding box spans all coordinates of the segment with buffer."""
    long_segment = [
        [-122.4150, 37.7780],
        [-122.4110, 37.7820],
        [-122.4070, 37.7860],
    ]

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = httpx.Response(200, json={
            "routes": [{
                "summary": {"travelTimeInSeconds": 800, "lengthInMeters": 2500},
                "legs": [{"points": [
                    {"latitude": 37.7770, "longitude": -122.4160},
                    {"latitude": 37.7890, "longitude": -122.4010},
                ]}]
            }]
        })

        res = await _calculate_closure_detour(
            origin_lat=ORIGIN_LAT,
            origin_lon=ORIGIN_LON,
            dest_lat=DEST_LAT,
            dest_lon=DEST_LON,
            closure_lat=37.7820,
            closure_lon=-122.4110,
            original_route_time_seconds=600,
            api_key="test-key",
            closure_coords=long_segment,
        )

        assert mock_post.called
        call_kwargs = mock_post.call_args[1]
        body = call_kwargs.get("json", {})
        rect = body["avoidAreas"]["rectangles"][0]
        sw = rect["southWestCorner"]
        ne = rect["northEastCorner"]

        # Bounding box must enclose min/max of the entire long segment
        # Long segment lats: [37.7780, 37.7860], lons: [-122.4150, -122.4070]
        assert sw["latitude"] <= 37.7780
        assert ne["latitude"] >= 37.7860
        assert sw["longitude"] <= -122.4150
        assert ne["longitude"] >= -122.4070


# =============================================================================
# 8. Alternate route unavailable -> 0 fake delay / honest unavailable state
# =============================================================================
@pytest.mark.asyncio
async def test_case_8_alternate_route_unavailable_honest_zero(monkeypatch):
    """When alternate route returns 400, 503, or no routes, return strictly 0 min delay."""
    monkeypatch.setattr(settings, "ROAD_RESTRICTION_API_KEY", "test-key-road")

    incident = _build_incident_feature(
        inc_id="INC-NOALT-08",
        coords=[-122.4080, 37.7850],
        is_closed=True,
    )
    mock_payload = {"incidents": [incident]}

    provider = RoadRestrictionProvider()
    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get, \
         patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_get.return_value = httpx.Response(200, json=mock_payload)
        # Alternate route service fails with 503
        mock_post.return_value = httpx.Response(503, text="Routing unavailable")

        res = await provider.evaluate(
            origin_lat=ORIGIN_LAT, origin_lon=ORIGIN_LON,
            dest_lat=DEST_LAT, dest_lon=DEST_LON,
            route_geometry=SAMPLE_ROUTE_GEOMETRY,
            original_route_time_seconds=600,
        )

    assert res.is_route_relevant is True
    assert res.impact_minutes == 0  # Zero fake data!
    assert res.applied_to_eta is False
    assert res.causal_status == "UNAVAILABLE"
    assert "no verified alternate-route detour could be calculated" in res.relevance_reason


# =============================================================================
# 9. Live traffic already includes incident -> no double counting
# =============================================================================
@pytest.mark.asyncio
async def test_case_9_live_traffic_already_includes_incident_no_double_counting(monkeypatch):
    """Non-closed incident slowdown already accounted for in authoritative live route traffic delay."""
    monkeypatch.setattr(settings, "ROAD_RESTRICTION_API_KEY", "test-key-road")

    # Accident on route (iconCategory 1), delay 300s (5m)
    incident = _build_incident_feature(
        inc_id="INC-ACCIDENT-09",
        coords=[-122.4080, 37.7850],
        icon_category=1,
        delay=300,
        is_closed=False,
    )
    mock_payload = {"incidents": [incident]}

    provider = RoadRestrictionProvider()
    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = httpx.Response(200, json=mock_payload)

        # live route already reports 300s traffic delay
        res = await provider.evaluate(
            origin_lat=ORIGIN_LAT, origin_lon=ORIGIN_LON,
            dest_lat=DEST_LAT, dest_lon=DEST_LON,
            route_geometry=SAMPLE_ROUTE_GEOMETRY,
            original_route_time_seconds=600,
            traffic_delay_seconds=300,
        )

    assert res.is_route_relevant is True
    assert res.impact_minutes == 0  # Deduplicated against live traffic delay
    assert res.applied_to_eta is False
    assert res.impact_classification == "INCLUDED_IN_LIVE_ROUTE"
    assert res.causal_status == "RELEVANT_NO_ADDITIONAL_DETOUR"
    assert "already accounted for in authoritative live route traffic delay" in res.relevance_reason


# =============================================================================
# 10. OSRM route geometry works for route-corridor checking
# =============================================================================
@pytest.mark.asyncio
async def test_case_10_osrm_route_geometry_works_for_corridor_checking(monkeypatch):
    """When TomTom is down, OSRM derived route geometry accurately detects corridor relevance."""
    monkeypatch.setattr(settings, "ROAD_RESTRICTION_API_KEY", "test-key-road")

    # OSRM derived route polyline
    osrm_route_geometry = [
        [-122.4160, 37.7770],
        [-122.4110, 37.7820],
        [-122.4060, 37.7870],
        [-122.4010, 37.7890],
    ]

    # Incident right on OSRM route segment (-122.4110, 37.7820)
    incident_on_osrm = _build_incident_feature(
        inc_id="INC-OSRM-ON-10",
        coords=[-122.4110, 37.7820],
        is_closed=False,
        delay=240,
    )
    mock_payload = {"incidents": [incident_on_osrm]}

    provider = RoadRestrictionProvider()
    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = httpx.Response(200, json=mock_payload)

        res = await provider.evaluate(
            origin_lat=ORIGIN_LAT, origin_lon=ORIGIN_LON,
            dest_lat=DEST_LAT, dest_lon=DEST_LON,
            route_geometry=osrm_route_geometry,
            original_route_time_seconds=700,
            traffic_delay_seconds=0,
        )

    assert res.is_route_relevant is True
    assert res.relevance_status == "RELEVANT"
    assert res.distance_to_route_meters <= STRICT_ROAD_CORRIDOR_BUFFER_METERS
    assert res.impact_minutes == 4


# =============================================================================
# 11. Point-only incident fallback works with controlled metric threshold
# =============================================================================
@pytest.mark.asyncio
async def test_case_11_point_only_incident_fallback_controlled_metric_threshold(monkeypatch):
    """Point incident within 50m is RELEVANT; point incident at 100m is NOT_RELEVANT."""
    monkeypatch.setattr(settings, "ROAD_RESTRICTION_API_KEY", "test-key-road")

    # Point 1: ~17m from route segment -> RELEVANT
    incident_near = _build_incident_feature(
        inc_id="INC-POINT-NEAR-11",
        coords=[-122.4080, 37.78515],
        is_closed=False,
        delay=180,
    )
    # Point 2: ~165m from route segment -> NOT_RELEVANT
    incident_far = _build_incident_feature(
        inc_id="INC-POINT-FAR-11",
        coords=[-122.4080, 37.7865],
        is_closed=False,
        delay=180,
    )

    provider = RoadRestrictionProvider()

    # Test Near
    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = httpx.Response(200, json={"incidents": [incident_near]})
        res_near = await provider.evaluate(
            origin_lat=ORIGIN_LAT, origin_lon=ORIGIN_LON,
            dest_lat=DEST_LAT, dest_lon=DEST_LON,
            route_geometry=SAMPLE_ROUTE_GEOMETRY,
            original_route_time_seconds=600,
            traffic_delay_seconds=0,
        )
    assert res_near.is_route_relevant is True
    assert res_near.distance_to_route_meters <= 50.0

    # Test Far
    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = httpx.Response(200, json={"incidents": [incident_far]})
        res_far = await provider.evaluate(
            origin_lat=ORIGIN_LAT, origin_lon=ORIGIN_LON,
            dest_lat=DEST_LAT, dest_lon=DEST_LON,
            route_geometry=SAMPLE_ROUTE_GEOMETRY,
            original_route_time_seconds=600,
            traffic_delay_seconds=0,
        )
    assert res_far.is_route_relevant is False
    assert res_far.distance_to_route_meters > 50.0
    assert res_far.impact_minutes == 0


# =============================================================================
# 12. No old arbitrary +15/+30 closure heuristic remains active
# =============================================================================
@pytest.mark.asyncio
async def test_case_12_no_old_arbitrary_heuristics_active(monkeypatch):
    """Verify that no fixed +5, +8, +10, +15, +30 minute penalties ever trigger for unmeasured closures."""
    monkeypatch.setattr(settings, "ROAD_RESTRICTION_API_KEY", "test-key-road")

    # Road closure on route, no alternate route available, no reported delay
    incident = _build_incident_feature(
        inc_id="INC-NO-HEURISTIC-12",
        coords=[-122.4080, 37.7850],
        icon_category=8,  # Road Closed
        magnitude=4,      # Severe / Blocking
        delay=None,
        is_closed=True,
    )

    provider = RoadRestrictionProvider()
    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get, \
         patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_get.return_value = httpx.Response(200, json={"incidents": [incident]})
        mock_post.return_value = httpx.Response(404, text="No route")

        res = await provider.evaluate(
            origin_lat=ORIGIN_LAT, origin_lon=ORIGIN_LON,
            dest_lat=DEST_LAT, dest_lon=DEST_LON,
            route_geometry=SAMPLE_ROUTE_GEOMETRY,
            original_route_time_seconds=600,
        )

    # Must be 0, never arbitrary +15 or +30
    assert res.impact_minutes == 0
    assert res.impact_minutes not in (5, 8, 10, 15, 30)
    assert res.applied_to_eta is False
    assert res.causal_status == "UNAVAILABLE"
