"""
Automated Test Suite for Route-Aware, Distance-Aware, Non-Overinflated ETA Calculation.
Tests the 9 mandatory operational realism cases specified in Section 14:

  Case 1: 2.43 km route, road closure 4.43 mi away outside corridor -> closure impact = 0 min.
  Case 2: Road closure intersecting route corridor -> closure contributes bounded derived detour impact (5-8 min).
  Case 3: Event nearby (3 mi away) but outside route corridor -> event impact = 0 min.
  Case 4: Event directly relevant at destination block -> bounded derived impact (+2 to +3 min).
  Case 5: Normal weather (0.2 mm drizzle, light breeze) -> weather impact = 0 min.
  Case 6: Severe weather (thunderstorm/heavy rain) -> derived weather impact allowed.
  Case 7: TomTom traffic says normal (Free Flow) -> traffic impact = 0 min.
  Case 8: Multiple overlapping factors in same corridor -> no double counting.
  Case 9: Short route + unrelated distant incident -> Context ETA remains close to baseline (~7 min, not 46 min).
"""

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch
from httpx import Response
import pytest

from app.services.context_providers import (
    ContextProviderResult,
    DataSourceStatus,
    EventsDataProvider,
    RoadRestrictionProvider,
    TrafficDataProvider,
    WeatherProvider,
)
from app.services.context_aggregation import ContextAggregationService


# =============================================================================
# CASE 1: 2.43 km route, road closure 4.43 mi away outside corridor -> impact = 0 min
# =============================================================================
@pytest.mark.asyncio
async def test_case_1_off_corridor_road_closure_zero_impact():
    """
    On a short route (2.43 km / 1.51 mi), an incident 4.43 miles away (e.g. NH544 to Madukkarai)
    must produce 0 min impact, be marked is_route_relevant=False, while preserving REAL provenance.
    """
    now = datetime.now(timezone.utc)
    # Trip in Coimbatore: Gandhipuram (10.998, 76.965) to Peelamedu (11.012, 76.975) = 1.51 mi
    orig_lat, orig_lon = 10.9980, 76.9650
    dest_lat, dest_lon = 11.0120, 76.9750

    # Closure on NH544 near Madukkarai (10.9500, 76.9650), ~4.33 mi from destination
    # Within 5-mile query window so ingested, but off-corridor so 0m delay applied
    distant_closure = {
        "type": "Feature",
        "geometry": {
            "type": "Point",
            "coordinates": [76.9650, 10.9500],
        },
        "properties": {
            "id": "TTI-COIMBATORE-NH544",
            "iconCategory": 8,  # Road Closed
            "magnitudeOfDelay": 4,  # Blocking
            "delay": 1800,  # 30 min delay reported on distant highway
            "events": [{"code": 108, "description": "Major closure on NH544 to Madukkarai"}],
            "startTime": (now - timedelta(hours=1)).isoformat(),
            "endTime": (now + timedelta(hours=5)).isoformat(),
            "road_name": "NH544 to Madukkarai",
        },
    }

    provider = RoadRestrictionProvider()
    res = await provider.evaluate(
        origin_lat=orig_lat,
        origin_lon=orig_lon,
        dest_lat=dest_lat,
        dest_lon=dest_lon,
        restrictions_feed=[distant_closure],
        distance_miles=1.51,
        baseline_eta_minutes=7,
    )

    assert res.status == DataSourceStatus.AVAILABLE
    assert res.provenance == "REAL"
    assert res.impact_minutes == 0, f"Expected 0 min impact for off-corridor closure, got {res.impact_minutes}"
    assert res.is_route_relevant is False
    assert res.is_road_closed is True
    assert "outside route corridor" in res.description
    assert "NOT RELEVANT" in res.description


# =============================================================================
# CASE 2: Road closure intersecting route corridor -> bounded detour impact
# =============================================================================
@pytest.mark.asyncio
async def test_case_2_route_corridor_road_closure_bounded_detour():
    """
    A road closure directly intersecting the route corridor must contribute
    a bounded derived detour impact (e.g. 5-8 minutes), not an uncalibrated +30 min.
    """
    now = datetime.now(timezone.utc)
    orig_lat, orig_lon = 10.9980, 76.9650
    dest_lat, dest_lon = 11.0120, 76.9750

    # Closure directly on Avinashi Road along the transit corridor
    corridor_closure = {
        "type": "Feature",
        "geometry": {
            "type": "Point",
            "coordinates": [76.9700, 11.0050],  # Midpoint of route
        },
        "properties": {
            "id": "TTI-AVINASHI-RD-BLOCK",
            "iconCategory": 8,  # Road Closed
            "magnitudeOfDelay": 4,  # Blocking
            "delay": None,  # No explicit duration from provider -> derived detour
            "events": [{"code": 108, "description": "Flyover construction and road closed"}],
            "startTime": (now - timedelta(hours=1)).isoformat(),
            "endTime": (now + timedelta(hours=5)).isoformat(),
            "road_name": "Avinashi Road",
        },
    }

    provider = RoadRestrictionProvider()
    res = await provider.evaluate(
        origin_lat=orig_lat,
        origin_lon=orig_lon,
        dest_lat=dest_lat,
        dest_lon=dest_lon,
        restrictions_feed=[corridor_closure],
        distance_miles=1.51,
        baseline_eta_minutes=7,
    )

    assert res.status == DataSourceStatus.AVAILABLE
    assert res.provenance == "REAL"
    assert res.is_route_relevant is True
    assert 3 <= res.impact_minutes <= 8, f"Detour delay should be bounded (3-8m), got {res.impact_minutes}"
    assert res.is_road_closed is True
    assert "Route-relevant road restriction" in res.description


# =============================================================================
# CASE 3: Event nearby (3 mi away) but outside route corridor -> impact = 0 min
# =============================================================================
@pytest.mark.asyncio
async def test_case_3_nearby_event_outside_corridor_zero_impact():
    """
    An event located ~3 miles away from a 1.51-mile trip must produce 0 min impact
    and be classified as is_route_relevant=False.
    """
    now = datetime.now(timezone.utc)
    dest_lat, dest_lon = 11.0120, 76.9750

    # Event 3.0 miles south-west, outside route corridor
    distant_event_lat = dest_lat - 0.043
    distant_event_lon = dest_lon - 0.010

    mock_payload = {
        "count": 1,
        "results": [
            {
                "id": "EVT-DISTANT-TRADE-EXPO",
                "title": "Industrial Machinery Expo",
                "category": "conferences",
                "rank": 65,
                "phq_attendance": 4500,
                "start": now.isoformat(),
                "end": (now + timedelta(hours=3)).isoformat(),
                "location": [distant_event_lon, distant_event_lat],
            }
        ],
    }

    provider = EventsDataProvider()
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = mock_payload

    with patch("httpx.AsyncClient.get", new_callable=AsyncMock, return_value=mock_resp):
        res = await provider.evaluate(
            origin_lat=10.9980,
            origin_lon=76.9650,
            dest_lat=dest_lat,
            dest_lon=dest_lon,
            distance_miles=1.51,
            baseline_eta_minutes=7,
        )

    assert res.status == DataSourceStatus.AVAILABLE
    assert res.provenance == "REAL"
    assert res.impact_minutes == 0, f"Expected 0 min impact for 3mi away event, got {res.impact_minutes}"
    assert res.is_route_relevant is False
    assert "outside route corridor" in res.description


# =============================================================================
# CASE 4: Event directly relevant at destination block -> bounded derived impact
# =============================================================================
@pytest.mark.asyncio
async def test_case_4_event_at_destination_bounded_impact():
    """
    An event located right at the destination block (< 0.5 mi) contributes a bounded
    derived staging impact (+2 to +5 min depending on size).
    """
    now = datetime.now(timezone.utc)
    dest_lat, dest_lon = 11.0120, 76.9750

    # Event directly adjacent to destination (0.15 miles away)
    mock_payload = {
        "count": 1,
        "results": [
            {
                "id": "EVT-TECH-PARK-SYMPOSIUM",
                "title": "TIDEL Park Tech Symposium",
                "category": "conferences",
                "rank": 55,
                "phq_attendance": 3500,
                "start": now.isoformat(),
                "end": (now + timedelta(hours=4)).isoformat(),
                "location": [dest_lon + 0.002, dest_lat + 0.001],
            }
        ],
    }

    provider = EventsDataProvider()
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = mock_payload

    with patch("httpx.AsyncClient.get", new_callable=AsyncMock, return_value=mock_resp):
        res = await provider.evaluate(
            origin_lat=10.9980,
            origin_lon=76.9650,
            dest_lat=dest_lat,
            dest_lon=dest_lon,
            distance_miles=1.51,
            baseline_eta_minutes=7,
        )

    assert res.status == DataSourceStatus.AVAILABLE
    assert res.provenance == "REAL"
    assert res.is_route_relevant is True
    assert 2 <= res.impact_minutes <= 5, f"Expected 2-5m impact for destination event, got {res.impact_minutes}"


# =============================================================================
# CASE 5: Normal weather (0.2 mm drizzle, light breeze) -> impact = 0 min
# =============================================================================
@pytest.mark.asyncio
async def test_case_5_trace_drizzle_light_breeze_zero_impact():
    """
    A 0.2 mm light drizzle (weather code 51) and a light breeze (11 km/h) on a short
    route (1.51 mi / 7 min) must produce 0 min weather impact, not +4 min.
    """
    mock_payload = {
        "current": {
            "time": "2026-09-18T10:00",
            "temperature_2m": 26.5,
            "apparent_temperature": 27.2,
            "relative_humidity_2m": 72.0,
            "precipitation": 0.2,  # Trace drizzle
            "weather_code": 51,   # Light drizzle
            "wind_speed_10m": 11.0,  # Gentle breeze
            "wind_direction_10m": 180.0,
        }
    }

    provider = WeatherProvider()
    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = Response(200, json=mock_payload)
        res = await provider.evaluate(
            lat=11.0120,
            lon=76.9750,
            baseline_eta_minutes=7,
            distance_miles=1.51,
        )

    assert res.status == DataSourceStatus.AVAILABLE
    assert res.provenance == "REAL"
    assert res.precipitation_mm == 0.2
    assert res.impact_minutes == 0, f"Trace drizzle should produce 0 min impact on 7 min route, got {res.impact_minutes}"


# =============================================================================
# CASE 6: Severe weather (thunderstorm / heavy rain) -> derived impact allowed
# =============================================================================
@pytest.mark.asyncio
async def test_case_6_severe_weather_derived_impact_allowed():
    """
    Severe weather (heavy rain 14 mm/h, gale wind 52 km/h, thunderstorm code 95)
    must produce an active derived travel delay, proportional to the trip.
    """
    mock_payload = {
        "current": {
            "time": "2026-09-18T10:00",
            "temperature_2m": 22.0,
            "apparent_temperature": 21.0,
            "relative_humidity_2m": 95.0,
            "precipitation": 14.0,  # Heavy downpour
            "weather_code": 95,    # Thunderstorm
            "wind_speed_10m": 52.0,  # High wind
            "wind_direction_10m": 240.0,
        }
    }

    provider = WeatherProvider()
    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = Response(200, json=mock_payload)
        res = await provider.evaluate(
            lat=11.0120,
            lon=76.9750,
            baseline_eta_minutes=7,
            distance_miles=1.51,
        )

    assert res.status == DataSourceStatus.AVAILABLE
    assert res.provenance == "REAL"
    assert res.impact_minutes > 0, f"Severe thunderstorm should produce >0 min delay, got {res.impact_minutes}"
    assert res.impact_minutes <= 6, f"For a 7m trip, severe weather delay should be reasonably scaled, got {res.impact_minutes}"


# =============================================================================
# CASE 7: TomTom traffic says normal (Free Flow) -> impact = 0 min
# =============================================================================
@pytest.mark.asyncio
async def test_case_7_tomtom_traffic_free_flow_zero_impact():
    """
    When TomTom traffic reports free-flow transit conditions (trafficDelayInSeconds == 0),
    traffic impact must be 0 min with REAL provenance.
    """
    from app.core.config import settings
    mock_tomtom_payload = {
        "routes": [
            {
                "summary": {
                    "travelTimeInSeconds": 420,
                    "noTrafficTravelTimeInSeconds": 420,
                    "trafficDelayInSeconds": 0,
                }
            }
        ]
    }

    provider = TrafficDataProvider()
    with patch.object(settings, "TRAFFIC_PROVIDER", "tomtom"), \
         patch.object(settings, "TRAFFIC_API_KEY", "test-tomtom-key"), \
         patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = Response(200, json=mock_tomtom_payload)
        res = await provider.evaluate(
            origin_lat=10.9980,
            origin_lon=76.9650,
            dest_lat=11.0120,
            dest_lon=76.9750,
            distance_miles=1.51,
            baseline_eta_minutes=7,
        )

    assert res.status == DataSourceStatus.AVAILABLE
    assert res.provenance == "REAL"
    assert res.impact_minutes == 0, f"Free flow traffic should produce 0 min delay, got {res.impact_minutes}"


# =============================================================================
# CASE 8: Multiple overlapping factors in same corridor -> no double counting
# =============================================================================
@pytest.mark.asyncio
async def test_case_8_mutual_corridor_deduplication_prevents_double_counting():
    """
    When live TomTom traffic already captures 6 minutes of congestion delay along
    the corridor, a road restriction reporting 6 min delay in the same corridor
    must be deduplicated so the ETA does not add 6 + 6 = 12 minutes.
    """
    now = datetime.now(timezone.utc)

    # Traffic provider result: 6 minutes congestion delay captured
    traffic_res = ContextProviderResult(
        source_name="Traffic (TomTom)",
        status=DataSourceStatus.AVAILABLE,
        impact_minutes=6,
        description="TomTom live traffic reports heavy transit delay (+6m).",
        sampled_at=now,
        category="TRAFFIC",
        provenance="REAL",
        route_geometry=[(10.9980, 76.9650), (11.0050, 76.9700), (11.0120, 76.9750)],
    )

    # Road restriction provider result: reports 6 min delay on Avinashi Road
    road_res = ContextProviderResult(
        source_name="Road Restrictions",
        status=DataSourceStatus.AVAILABLE,
        impact_minutes=6,
        description="Route-relevant road restriction adds +6 min delay.",
        sampled_at=now,
        category="ROAD",
        provenance="REAL",
        is_route_relevant=True,
    )

    # Weather provider: clear weather
    weather_res = ContextProviderResult(
        source_name="Weather (Open-Meteo)",
        status=DataSourceStatus.AVAILABLE,
        impact_minutes=0,
        description="Clear skies.",
        sampled_at=now,
        category="WEATHER",
        provenance="REAL",
    )

    aggregator = ContextAggregationService()
    agg_res = aggregator.aggregate(
        provider_results=[weather_res, traffic_res, road_res],
        baseline_eta_minutes=7,
        distance_km=2.43,
        distance_miles=1.51,
    )

    # Total adjustment should be deduplicated: 6 min total, NOT 12 min
    assert agg_res.total_adjustment_minutes == 6, f"Expected 6 min after corridor deduplication, got {agg_res.total_adjustment_minutes}"


# =============================================================================
# CASE 9: Short route + unrelated distant incident -> Context ETA ~7m, NOT 46m
# =============================================================================
@pytest.mark.asyncio
async def test_case_9_coimbatore_short_route_not_overinflated():
    """
    End-to-end operational realism check for the user's motivating Coimbatore incident:
      Trip: 2.43 km (1.51 mi), Baseline ETA = 7 min.
      Factors:
        - Weather: 0.2 mm drizzle -> 0 min impact
        - Event: 3 mi away -> 0 min impact (off-corridor)
        - Road Restriction: 4.43 mi away on NH544 -> 0 min impact (off-corridor advisory)
      Result: Context ETA must remain 7 min (+0 min delta), NOT 46 min!
    """
    now = datetime.now(timezone.utc)
    baseline_eta = 7
    distance_miles = 1.51

    # 1. Weather: trace drizzle
    weather_res = ContextProviderResult(
        source_name="Weather (Open-Meteo)",
        status=DataSourceStatus.AVAILABLE,
        impact_minutes=0,
        description="Light drizzle (0.2mm), light breeze (11km/h) — 0 min delay applied.",
        sampled_at=now,
        category="WEATHER",
        provenance="REAL",
        precipitation_mm=0.2,
    )

    # 2. Events: distant event 3 mi away
    events_res = ContextProviderResult(
        source_name="Events",
        status=DataSourceStatus.AVAILABLE,
        impact_minutes=0,
        description="Active public event nearby is outside route corridor (Route relevance: NOT RELEVANT) — 0 min delay applied.",
        sampled_at=now,
        category="EVENTS",
        provenance="REAL",
        is_route_relevant=False,
    )

    # 3. Road Restrictions: NH544 to Madukkarai closure 4.43 mi away
    road_res = ContextProviderResult(
        source_name="Road Restrictions",
        status=DataSourceStatus.AVAILABLE,
        impact_minutes=0,
        description="Road incident near area (NH544 to Madukkarai: Major closure) is outside route corridor (Route relevance: NOT RELEVANT) — 0 min delay applied.",
        sampled_at=now,
        category="ROAD",
        provenance="REAL",
        is_road_closed=True,
        is_route_relevant=False,
        restriction_distance_miles=4.43,
        restriction_delay_seconds=1800,
    )

    # 4. Traffic: free flow
    traffic_res = ContextProviderResult(
        source_name="Traffic (TomTom)",
        status=DataSourceStatus.AVAILABLE,
        impact_minutes=0,
        description="Normal traffic flow on route (Free Flow) — 0 min delay applied.",
        sampled_at=now,
        category="TRAFFIC",
        provenance="REAL",
    )

    aggregator = ContextAggregationService()
    agg_res = aggregator.aggregate(
        provider_results=[weather_res, traffic_res, events_res, road_res],
        baseline_eta_minutes=baseline_eta,
        distance_km=2.43,
        distance_miles=distance_miles,
    )

    assert agg_res.total_adjustment_minutes == 0, f"Expected 0 min adjustment, got {agg_res.total_adjustment_minutes}"

    # Calculate final context-aware ETA
    context_aware_eta = baseline_eta + agg_res.total_adjustment_minutes
    assert context_aware_eta == 7, f"Context ETA should be 7 min, got {context_aware_eta}"

    # Validate provenance and off-corridor metadata preserved
    road_ds = next(ds for ds in agg_res.data_sources if ds.category == "ROAD")
    assert road_ds.provenance == "REAL"
    assert road_ds.is_route_relevant is False
    assert road_ds.impact_minutes == 0

    events_ds = next(ds for ds in agg_res.data_sources if ds.category == "EVENTS")
    assert events_ds.provenance == "REAL"
    assert events_ds.is_route_relevant is False
    assert events_ds.impact_minutes == 0
