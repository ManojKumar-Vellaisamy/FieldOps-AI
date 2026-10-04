"""
Phase 4E Test Suite: Short-Route Traffic Sanity + Sub-Minute Detour Evidence.

Verifies:
1. TomTom authoritative live routing traffic delay is NEVER clamped or reduced on short routes.
2. Verified road closure alternate-route detour is NEVER clamped as fake traffic.
3. Sub-minute detour (e.g. 13s) maintains RELEVANT_INCREMENTAL_DETOUR with truthful evidence
   "13 sec additional (<1 min)" rather than misleadingly displaying "+0 min".
4. Multi-minute + seconds detour (e.g. 72s) displays "1 min 12 sec additional".
5. Zero detour displays "No additional detour measured." with RELEVANT_NO_ADDITIONAL_DETOUR.
6. Long route live traffic delay behavior is preserved.
7. OSRM fallback remains honest DERIVED without fake traffic delay.
8. Haversine last-resort fallback remains intact when TomTom and OSRM are unavailable.
9. Route-relevant closure with 13s detour preserves exact seconds evidence throughout ETAService.
10. Off-route closure remains NOT_RELEVANT with 0 impact.
"""

import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, patch, MagicMock
import httpx

from app.core.config import settings
from app.services.context_providers import (
    DataSourceStatus,
    RoadRestrictionProvider,
    TrafficDataProvider,
    _format_detour_evidence,
    DetourCalculationResult,
)
from app.services.context_aggregation import ContextAggregationService, ContextAggregationSummary
from app.schemas.eta import ContextFactor, DataSource

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
):
    if coords is None:
        coords = [-122.4080, 37.7850]
    now = datetime.now(timezone.utc)
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
            "startTime": (now - timedelta(hours=1)).isoformat(),
            "endTime": (now + timedelta(hours=5)).isoformat(),
            "from": road_from,
            "to": road_to,
            "is_closed": is_closed,
            "length": 400.0,
        },
    }


# =============================================================================
# CASE 1: Short route + TomTom free-flow 300 sec + live 420 sec -> delay 120s
# =============================================================================
def test_case_1_short_route_traffic_delay_not_clamped():
    """Short route (<3 mi / 5 km): measured TomTom live traffic delay must NOT be clamped."""
    agg = ContextAggregationService()

    # Free flow = 300s (5m), live route = 420s (7m) -> traffic delay = 120s (2m)
    now = datetime.now(timezone.utc)
    traffic_res = MagicMock()
    traffic_res.category = "TRAFFIC"
    traffic_res.source_name = "Traffic Data (TomTom API)"
    traffic_res.status = DataSourceStatus.AVAILABLE
    traffic_res.provenance = "REAL"
    traffic_res.freshness = "FRESH"
    traffic_res.impact_minutes = 2  # 120s / 60
    traffic_res.impact_classification = "INCLUDED_IN_LIVE_ROUTE"
    traffic_res.free_flow_travel_time_seconds = 300
    traffic_res.live_travel_time_seconds = 420
    traffic_res.traffic_delay_seconds = 120
    traffic_res.to_data_source_dict.return_value = {
        "name": "Traffic Data (TomTom API)", "status": "AVAILABLE", "description": "Traffic (+2 min)",
        "impact_minutes": 2, "sampled_at": now.isoformat(), "category": "TRAFFIC",
        "provenance": "REAL", "freshness": "FRESH", "impact_classification": "INCLUDED_IN_LIVE_ROUTE",
    }
    traffic_res.to_factor_dict.return_value = {
        "category": "TRAFFIC", "factor": "Traffic Data (TomTom API)", "impact_minutes": 2,
        "description": "Traffic (+2 min)", "provenance": "REAL", "freshness": "FRESH",
        "impact_classification": "INCLUDED_IN_LIVE_ROUTE",
    }

    # Short route parameters: 2.5 km (1.5 mi), baseline_eta_minutes = 5
    summary = agg.aggregate(
        provider_results=[traffic_res],
        baseline_eta_minutes=5,
        distance_km=2.5,
        distance_miles=1.5,
        technician_status="AVAILABLE",
    )

    # Traffic delay of 2 min must NOT be clamped to 0 or reduced!
    assert summary.total_adjustment_minutes == 2
    traffic_factor = next(f for f in summary.factors if f.category == "TRAFFIC")
    assert traffic_factor.impact_minutes == 2


# =============================================================================
# CASE 2: Short route + TomTom free-flow 600 sec + live 660 sec -> delay 60s
# =============================================================================
def test_case_2_short_route_large_traffic_delay_preserved():
    """Short route: 600s free-flow vs 660s live route -> 60s (1m) delay preserved in full."""
    agg = ContextAggregationService()

    now = datetime.now(timezone.utc)
    traffic_res = MagicMock()
    traffic_res.category = "TRAFFIC"
    traffic_res.source_name = "Traffic Data (TomTom API)"
    traffic_res.status = DataSourceStatus.AVAILABLE
    traffic_res.provenance = "REAL"
    traffic_res.freshness = "FRESH"
    traffic_res.impact_minutes = 1  # 60s
    traffic_res.impact_classification = "INCLUDED_IN_LIVE_ROUTE"
    traffic_res.free_flow_travel_time_seconds = 600
    traffic_res.live_travel_time_seconds = 660
    traffic_res.traffic_delay_seconds = 60
    traffic_res.to_data_source_dict.return_value = {
        "name": "Traffic Data (TomTom API)", "status": "AVAILABLE", "description": "Traffic (+1 min)",
        "impact_minutes": 1, "sampled_at": now.isoformat(), "category": "TRAFFIC",
        "provenance": "REAL", "freshness": "FRESH", "impact_classification": "INCLUDED_IN_LIVE_ROUTE",
    }
    traffic_res.to_factor_dict.return_value = {
        "category": "TRAFFIC", "factor": "Traffic Data (TomTom API)", "impact_minutes": 1,
        "description": "Traffic (+1 min)", "provenance": "REAL", "freshness": "FRESH",
        "impact_classification": "INCLUDED_IN_LIVE_ROUTE",
    }

    summary = agg.aggregate(
        provider_results=[traffic_res],
        baseline_eta_minutes=10,
        distance_km=4.0,
        distance_miles=2.5,
        technician_status="AVAILABLE",
    )

    assert summary.total_adjustment_minutes == 1
    traffic_factor = next(f for f in summary.factors if f.category == "TRAFFIC")
    assert traffic_factor.impact_minutes == 1


# =============================================================================
# CASE 3: Short route + verified road detour 13 sec -> RELEVANT_INCREMENTAL_DETOUR
# =============================================================================
@pytest.mark.asyncio
async def test_case_3_subminute_road_detour_13sec(monkeypatch):
    """Sub-minute detour (13s): impact_minutes=0, causal_status=RELEVANT_INCREMENTAL_DETOUR, truthful evidence."""
    monkeypatch.setattr(settings, "ROAD_RESTRICTION_API_KEY", "test-key-road")

    incident = _build_incident_feature(
        inc_id="INC-SUBMIN-13",
        coords=[-122.4080, 37.7850],
        road_from="Forest Rd",
        road_to="Hillcrest Rd",
        is_closed=True,
    )
    mock_payload = {"incidents": [incident]}

    # Original route = 962s, Alternate route = 975s -> Detour = 13s
    alt_route_response = {
        "routes": [{
            "summary": {"travelTimeInSeconds": 975, "lengthInMeters": 4200},
            "legs": [{"points": [
                {"latitude": 37.7770, "longitude": -122.4160},
                {"latitude": 37.7830, "longitude": -122.4100},
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
            original_route_time_seconds=962,
        )

    assert res.is_route_relevant is True
    assert res.detour_seconds == 13
    assert res.impact_minutes == 0  # Rounded ETA addition remains 0
    assert res.causal_status == "RELEVANT_INCREMENTAL_DETOUR"
    assert res.impact_classification == "INCREMENTAL_DETOUR"
    assert res.detour_display == "13 sec additional (<1 min)"
    assert "13 sec additional (<1 min)" in res.description
    assert "+0 min" not in res.description


# =============================================================================
# CASE 4: Short route + verified road detour 72 sec -> "1 min 12 sec additional"
# =============================================================================
def test_case_4_detour_72sec_formatted_display():
    """Verified road detour 72s displays '1 min 12 sec additional'."""
    formatted = _format_detour_evidence(72)
    assert formatted == "1 min 12 sec additional"

    formatted_720 = _format_detour_evidence(720)
    assert formatted_720 == "12 min additional"


# =============================================================================
# CASE 5: Short route + detour 0 sec -> "No additional detour measured."
# =============================================================================
@pytest.mark.asyncio
async def test_case_5_zero_detour_representation(monkeypatch):
    """Zero detour (alternate route time == original route time) -> RELEVANT_NO_ADDITIONAL_DETOUR."""
    monkeypatch.setattr(settings, "ROAD_RESTRICTION_API_KEY", "test-key-road")

    incident = _build_incident_feature(
        inc_id="INC-ZERO-DETOUR",
        coords=[-122.4080, 37.7850],
        road_from="Market St",
        road_to="4th St",
        is_closed=True,
    )
    mock_payload = {"incidents": [incident]}

    # Original = 600s, Alternate = 600s -> 0 detour
    alt_route_response = {
        "routes": [{
            "summary": {"travelTimeInSeconds": 600, "lengthInMeters": 3000},
            "legs": [{"points": [
                {"latitude": 37.7770, "longitude": -122.4160},
                {"latitude": 37.7830, "longitude": -122.4100},
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
    assert res.detour_seconds == 0
    assert res.impact_minutes == 0
    assert res.causal_status == "RELEVANT_NO_ADDITIONAL_DETOUR"
    assert res.impact_classification == "INCLUDED_IN_LIVE_ROUTE"
    assert res.detour_display == "No additional detour measured."


# =============================================================================
# CASE 6: Long route + existing traffic delay -> Behavior unchanged
# =============================================================================
def test_case_6_long_route_traffic_delay_preserved():
    """Long route (e.g. 25 km, 30m baseline): live traffic delay preserved in full."""
    agg = ContextAggregationService()

    now = datetime.now(timezone.utc)
    traffic_res = MagicMock()
    traffic_res.category = "TRAFFIC"
    traffic_res.source_name = "Traffic Data (TomTom API)"
    traffic_res.status = DataSourceStatus.AVAILABLE
    traffic_res.provenance = "REAL"
    traffic_res.freshness = "FRESH"
    traffic_res.impact_minutes = 12
    traffic_res.impact_classification = "INCLUDED_IN_LIVE_ROUTE"
    traffic_res.free_flow_travel_time_seconds = 1800
    traffic_res.live_travel_time_seconds = 2520
    traffic_res.traffic_delay_seconds = 720
    traffic_res.to_data_source_dict.return_value = {
        "name": "Traffic Data (TomTom API)", "status": "AVAILABLE", "description": "Traffic (+12 min)",
        "impact_minutes": 12, "sampled_at": now.isoformat(), "category": "TRAFFIC",
        "provenance": "REAL", "freshness": "FRESH", "impact_classification": "INCLUDED_IN_LIVE_ROUTE",
    }
    traffic_res.to_factor_dict.return_value = {
        "category": "TRAFFIC", "factor": "Traffic Data (TomTom API)", "impact_minutes": 12,
        "description": "Traffic (+12 min)", "provenance": "REAL", "freshness": "FRESH",
        "impact_classification": "INCLUDED_IN_LIVE_ROUTE",
    }

    summary = agg.aggregate(
        provider_results=[traffic_res],
        baseline_eta_minutes=30,
        distance_km=25.0,
        distance_miles=15.5,
        technician_status="AVAILABLE",
    )

    assert summary.total_adjustment_minutes == 12


# =============================================================================
# CASE 7: TomTom unavailable + OSRM active -> DERIVED, no fake traffic delay
# =============================================================================
@pytest.mark.asyncio
async def test_case_7_osrm_active_derived_no_fake_traffic(monkeypatch):
    """When TomTom is unavailable and OSRM is active, route is DERIVED with 0 traffic delay."""
    monkeypatch.setattr(settings, "TRAFFIC_PROVIDER", "tomtom")
    monkeypatch.setattr(settings, "TRAFFIC_API_KEY", "test-key-tomtom")

    osrm_response = {
        "code": "Ok",
        "routes": [{
            "duration": 780.0,
            "distance": 8500.0,
            "geometry": {
                "coordinates": [
                    [-122.4194, 37.7749],
                    [-122.4150, 37.7800],
                    [-122.4010, 37.7890],
                ]
            }
        }]
    }

    provider = TrafficDataProvider()
    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        # TomTom fails with 503, OSRM succeeds with 200
        mock_get.side_effect = [
            httpx.Response(503, text="TomTom Outage"),
            httpx.Response(200, json=osrm_response),
        ]

        res = await provider.evaluate(
            origin_lat=37.7749, origin_lon=-122.4194,
            dest_lat=37.7890, dest_lon=-122.4010,
        )

    assert res.status == DataSourceStatus.AVAILABLE
    assert res.provenance == "DERIVED"
    assert res.traffic_delay_seconds == 0
    assert res.impact_minutes == 0
    assert "Route Baseline (OSRM)" in res.source_name


# =============================================================================
# CASE 8: TomTom + OSRM unavailable -> Haversine fallback preserved
# =============================================================================
@pytest.mark.asyncio
async def test_case_8_haversine_last_resort_unchanged(monkeypatch):
    """When both TomTom and OSRM fail, routing returns UNAVAILABLE (drops to Haversine)."""
    monkeypatch.setattr(settings, "TRAFFIC_PROVIDER", "tomtom")
    monkeypatch.setattr(settings, "TRAFFIC_API_KEY", "test-key-tomtom")

    provider = TrafficDataProvider()
    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        # Both fail
        mock_get.side_effect = [
            httpx.Response(500, text="TomTom Error"),
            httpx.Response(500, text="OSRM Error"),
        ]

        res = await provider.evaluate(
            origin_lat=37.7749, origin_lon=-122.4194,
            dest_lat=37.7890, dest_lon=-122.4010,
        )

    assert res.status == DataSourceStatus.UNAVAILABLE
    assert res.provenance == "UNAVAILABLE"
    assert res.impact_minutes == 0


# =============================================================================
# CASE 9: Phase 4D route-relevant closure with 13 sec detour integration
# =============================================================================
def test_case_9_phase4d_13sec_detour_integration():
    """Context aggregation preserves 13s detour without converting to fake +1m or discarding."""
    agg = ContextAggregationService()

    now = datetime.now(timezone.utc)
    road_res = MagicMock()
    road_res.category = "ROAD"
    road_res.source_name = "Road Restrictions"
    road_res.status = DataSourceStatus.AVAILABLE
    road_res.provenance = "REAL"
    road_res.freshness = "FRESH"
    road_res.impact_minutes = 0  # 13s rounds to 0 for ETA
    road_res.detour_seconds = 13
    road_res.detour_display = "13 sec additional (<1 min)"
    road_res.causal_status = "RELEVANT_INCREMENTAL_DETOUR"
    road_res.impact_classification = "INCREMENTAL_DETOUR"
    road_res.is_road_closed = True
    road_res.is_route_relevant = True
    road_res.to_data_source_dict.return_value = {
        "name": "Road Restrictions", "status": "AVAILABLE", "description": "Road closure adds 13 sec additional (<1 min).",
        "impact_minutes": 0, "sampled_at": now.isoformat(), "category": "ROAD",
        "provenance": "REAL", "freshness": "FRESH", "impact_classification": "INCREMENTAL_DETOUR",
        "detour_seconds": 13, "detour_display": "13 sec additional (<1 min)", "causal_status": "RELEVANT_INCREMENTAL_DETOUR",
    }
    road_res.to_factor_dict.return_value = {
        "category": "ROAD", "factor": "Road Restrictions", "impact_minutes": 0,
        "description": "Road closure adds 13 sec additional (<1 min).", "provenance": "DERIVED", "freshness": "FRESH",
        "impact_classification": "INCREMENTAL_DETOUR", "detour_seconds": 13,
        "detour_display": "13 sec additional (<1 min)", "causal_status": "RELEVANT_INCREMENTAL_DETOUR",
    }

    summary = agg.aggregate(
        provider_results=[road_res],
        baseline_eta_minutes=15,
        distance_km=8.0,
        distance_miles=5.0,
        technician_status="AVAILABLE",
    )

    road_factor = next(f for f in summary.factors if f.category == "ROAD")
    assert road_factor.detour_seconds == 13
    assert road_factor.detour_display == "13 sec additional (<1 min)"
    assert road_factor.causal_status == "RELEVANT_INCREMENTAL_DETOUR"
    assert road_factor.impact_minutes == 0


# =============================================================================
# CASE 10: Phase 4D off-route closure -> NOT_RELEVANT, 0 impact, no detour
# =============================================================================
@pytest.mark.asyncio
async def test_case_10_phase4d_off_route_closure(monkeypatch):
    """Off-route closure remains NOT_RELEVANT, 0 impact, and no detour."""
    monkeypatch.setattr(settings, "ROAD_RESTRICTION_API_KEY", "test-key-road")

    # Incident > 1 km away from route corridor
    incident = _build_incident_feature(
        inc_id="INC-OFFROUTE-10",
        coords=[-122.4080, 37.7990],
        road_from="Bush St",
        road_to="Taylor St",
        is_closed=True,
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

    assert res.is_route_relevant is False
    assert res.impact_minutes == 0
    assert res.detour_seconds is None or res.detour_seconds == 0
    assert res.causal_status == "NOT_RELEVANT"
    assert res.impact_classification == "NOT_APPLIED"
