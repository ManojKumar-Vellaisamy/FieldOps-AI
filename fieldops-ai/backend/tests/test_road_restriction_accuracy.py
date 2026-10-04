"""
Automated Test Suite for Road Restriction Evidence Semantics & Accuracy.

Verifies:
1. TEST 1: Closure with valid alternate route: detour_seconds=420, incident_delay_seconds=None,
   alternate_route_available=True, impact=7, 'detour delay' in desc.
2. TEST 2: Non-closure incident with reported delay: detour_seconds=None, incident_delay_seconds=107,
   alternate_route_available=False, impact=2, 'incident delay' in desc, 'Derived from alternate route comparison' NOT in desc.
3. TEST 3: Closure with alternate route same duration: detour_seconds=0, alternate_route_available=True,
   impact=0, causal_status='RELEVANT_NO_ADDITIONAL_DETOUR'.
4. TEST 4: Closure with no valid alternate route: detour_seconds=None, alternate_route_available=False,
   causal_status='UNAVAILABLE', impact=0.
5. TEST 5: Non-closure with 0 reported delay: detour_seconds=None, incident_delay_seconds=0 or None, impact=0.
6. TEST 6: Non-closure already accounted for in live route traffic: impact=0, description mentions already accounted for.
7. TEST 7: Road restriction data source serialization: includes both detour_seconds and incident_delay_seconds with correct None vs int values.
8. TEST 8: WebSocket ETA update payload: verifies road data source and factor correctly distinguish detour vs incident delay.
9. TEST 9: Cross-provider aggregation: verifies road incident delay does not double-count with live traffic delay.
10. TEST 10: Stale road restriction: sets impact=0, freshness='STALE', no detour or incident delay applied.
11. TEST 11: Example 2 alternate route difference (43m orig vs 48m alt -> +5m detour).
12. TEST 12: Intersecting alternate route rejected -> UNAVAILABLE, detour_seconds=None.
13. TEST 13: Duplicate overlapping closure records along same corridor -> no summed penalty.
"""

from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch
import uuid

import httpx
import pytest

from app.core.config import settings
from app.models.assignment import Assignment
from app.models.job import Job
from app.models.technician import Technician
from app.models.user import User
from app.schemas.eta import ContextFactor, DataSource
from app.services.context_aggregation import ContextAggregationService
from app.services.context_providers import (
    ContextProviderResult,
    DataSourceStatus,
    RoadRestrictionProvider,
)
from app.services.eta_service import ETAService


# Sample corridor: Market St corridor, San Francisco
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

CLOSURE_COORDS = [
    [-122.4090, 37.7830],
    [-122.4070, 37.7870],
]


def _build_closure_incident(
    inc_id="INC-ACC-001",
    road_from="Market St",
    road_to="4th St",
    coords=None,
    geom_type="LineString",
    delay=None,
    alternate_route_time_seconds=None,
    is_closed=True,
    is_avoided_by_live_route=False,
    causal_status=None,
):
    now = datetime.now(timezone.utc)
    if coords is None:
        coords = CLOSURE_COORDS

    item = {
        "type": "Feature",
        "geometry": {
            "type": geom_type,
            "coordinates": coords,
        },
        "properties": {
            "id": inc_id,
            "iconCategory": 8,
            "magnitudeOfDelay": 4,
            "delay": delay,
            "events": [{"code": 108, "description": "Road closed due to major utility repair"}],
            "startTime": (now - timedelta(hours=1)).isoformat(),
            "endTime": (now + timedelta(hours=6)).isoformat(),
            "from": road_from,
            "to": road_to,
            "road_name": f"{road_from} to {road_to}",
            "is_closed": is_closed,
            "length": 450.0,
        },
    }
    if alternate_route_time_seconds is not None:
        item["alternate_route_time_seconds"] = alternate_route_time_seconds
    if is_avoided_by_live_route:
        item["is_avoided_by_live_route"] = True
    if causal_status:
        item["causal_status"] = causal_status
    return item


def _build_non_closure_incident(
    inc_id="INC-SLOW-001",
    road_from="Market St",
    road_to="4th St",
    delay_sec=107,
    icon_category=1,
    description="Slow traffic",
):
    now = datetime.now(timezone.utc)
    return {
        "type": "Feature",
        "geometry": {
            "type": "Point",
            "coordinates": [-122.4080, 37.7850],
        },
        "properties": {
            "id": inc_id,
            "iconCategory": icon_category,
            "magnitudeOfDelay": 2,
            "delay": delay_sec,
            "events": [{"code": 1, "description": description}],
            "startTime": (now - timedelta(hours=1)).isoformat(),
            "endTime": (now + timedelta(hours=2)).isoformat(),
            "from": road_from,
            "to": road_to,
            "road_name": f"{road_from} to {road_to}",
            "is_closed": False,
        },
    }


# =============================================================================
# TEST 1: Closure with valid alternate route: detour_seconds=420, incident_delay_seconds=None
# =============================================================================
@pytest.mark.asyncio
async def test_road_restriction_closure_with_valid_alternate_route(monkeypatch):
    """
    Original = 41 min (2460s), Alternate = 48 min (2880s) -> detour = 420s (+7 min).
    Must set detour_seconds=420, incident_delay_seconds=None, alternate_route_available=True,
    impact_minutes=7, description with 'detour delay' and alternate route comparison.
    """
    monkeypatch.setattr(settings, "ROAD_RESTRICTION_API_KEY", "test-key-road")

    orig_sec = 41 * 60
    alt_sec = 48 * 60

    incident = _build_closure_incident(
        inc_id="INC-EX1",
        road_from="Market St",
        road_to="4th St",
        alternate_route_time_seconds=alt_sec,
    )
    mock_payload = {"incidents": [incident]}

    provider = RoadRestrictionProvider()
    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = httpx.Response(200, json=mock_payload)
        res = await provider.evaluate(
            origin_lat=ORIGIN_LAT,
            origin_lon=ORIGIN_LON,
            dest_lat=DEST_LAT,
            dest_lon=DEST_LON,
            route_geometry=SAMPLE_ROUTE_GEOMETRY,
            original_route_time_seconds=orig_sec,
        )

    assert res.status == DataSourceStatus.AVAILABLE
    assert res.provenance == "REAL"
    assert res.impact_minutes == 7
    assert res.detour_seconds == 420
    assert res.incident_delay_seconds is None
    assert res.alternate_route_available is True
    assert res.alternate_route_valid is True
    assert res.original_route_time_seconds == 2460
    assert res.alternate_route_time_seconds == 2880
    assert res.causal_status in ("RELEVANT_INCREMENTAL_DETOUR", "CAUSES_DETOUR")
    assert "detour delay" in res.description
    assert "Derived from alternate route comparison" in res.description
    assert "Alternate route: 48 min vs original 41 min (+7 min)" in res.description
    assert res.applied_to_eta is True


# =============================================================================
# TEST 2: Non-closure incident with reported delay: detour_seconds=None, incident_delay_seconds=107
# =============================================================================
@pytest.mark.asyncio
async def test_road_restriction_non_closure_reported_incident_delay(monkeypatch):
    """
    Non-closure traffic incident with reported delay of 107 seconds:
    Must set detour_seconds=None, incident_delay_seconds=107, alternate_route_available=False,
    impact_minutes=2 (round(107/60)), description citing TomTom reported delay,
    and description must NEVER state 'detour delay' or 'Derived from alternate route comparison'.
    """
    monkeypatch.setattr(settings, "ROAD_RESTRICTION_API_KEY", "test-key-road")

    incident = _build_non_closure_incident(
        inc_id="INC-SLOW-107",
        delay_sec=107,
        description="Slow traffic",
    )
    mock_payload = {"incidents": [incident]}

    provider = RoadRestrictionProvider()
    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = httpx.Response(200, json=mock_payload)
        res = await provider.evaluate(
            origin_lat=ORIGIN_LAT,
            origin_lon=ORIGIN_LON,
            dest_lat=DEST_LAT,
            dest_lon=DEST_LON,
            route_geometry=SAMPLE_ROUTE_GEOMETRY,
            original_route_time_seconds=2460,
        )

    assert res.status == DataSourceStatus.AVAILABLE
    assert res.impact_minutes == 2
    assert res.detour_seconds is None
    assert res.incident_delay_seconds == 107
    assert res.alternate_route_available is False
    assert res.causal_status == "RELEVANT_INCIDENT_DELAY"
    assert res.impact_classification == "RELEVANT_INCIDENT_DELAY"
    assert res.applied_to_eta is True

    # Semantic description verification:
    assert "incident delay" in res.description
    assert "TomTom reported incident delay: +107 sec (+2 min)" in res.description
    assert "Derived from alternate route comparison" not in res.description
    assert "detour delay" not in res.description


# =============================================================================
# TEST 3: Closure with alternate route same duration -> detour = 0, RELEVANT_NO_ADDITIONAL_DETOUR
# =============================================================================
@pytest.mark.asyncio
async def test_road_restriction_closure_alternate_route_same_duration(monkeypatch):
    """
    When alternate route has identical duration to original (e.g., 41 min vs 41 min),
    detour is 0 min, alternate_route_available=True, impact=0, and causal_status is RELEVANT_NO_ADDITIONAL_DETOUR.
    """
    monkeypatch.setattr(settings, "ROAD_RESTRICTION_API_KEY", "test-key-road")

    orig_sec = 41 * 60
    alt_sec = 41 * 60

    incident = _build_closure_incident(
        inc_id="INC-SAME-01",
        alternate_route_time_seconds=alt_sec,
    )
    mock_payload = {"incidents": [incident]}

    provider = RoadRestrictionProvider()
    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = httpx.Response(200, json=mock_payload)
        res = await provider.evaluate(
            origin_lat=ORIGIN_LAT,
            origin_lon=ORIGIN_LON,
            dest_lat=DEST_LAT,
            dest_lon=DEST_LON,
            route_geometry=SAMPLE_ROUTE_GEOMETRY,
            original_route_time_seconds=orig_sec,
        )

    assert res.impact_minutes == 0
    assert res.detour_seconds == 0
    assert res.incident_delay_seconds is None
    assert res.alternate_route_available is True
    assert res.causal_status == "RELEVANT_NO_ADDITIONAL_DETOUR"
    assert res.applied_to_eta is False


# =============================================================================
# TEST 4: Closure with no valid alternate route -> UNAVAILABLE, detour = None, impact = 0
# =============================================================================
@pytest.mark.asyncio
async def test_road_restriction_closure_no_valid_alternate_route_unavailable(monkeypatch):
    """
    When no alternate route can be computed for a closure (e.g. routing returns 400),
    status degrades to UNAVAILABLE with detour_seconds=None, alternate_route_available=False,
    strictly 0 min delay applied (no invented +15/+25).
    """
    monkeypatch.setattr(settings, "ROAD_RESTRICTION_API_KEY", "test-key-road")

    incident = _build_closure_incident(
        inc_id="INC-NO-ALT-01",
        coords=CLOSURE_COORDS,
        delay=None,
    )
    mock_payload = {"incidents": [incident]}

    provider = RoadRestrictionProvider()
    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get, \
         patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_get.return_value = httpx.Response(200, json=mock_payload)
        mock_post.return_value = httpx.Response(400, json={"error": "NO_ROUTE_FOUND"})

        res = await provider.evaluate(
            origin_lat=ORIGIN_LAT,
            origin_lon=ORIGIN_LON,
            dest_lat=DEST_LAT,
            dest_lon=DEST_LON,
            route_geometry=SAMPLE_ROUTE_GEOMETRY,
            original_route_time_seconds=2460,
        )

    assert res.impact_minutes == 0
    assert res.detour_seconds is None
    assert res.incident_delay_seconds is None
    assert res.causal_status == "UNAVAILABLE"
    assert res.alternate_route_available is False
    assert res.applied_to_eta is False


# =============================================================================
# TEST 5: Non-closure with 0 reported delay -> detour = None, impact = 0
# =============================================================================
@pytest.mark.asyncio
async def test_road_restriction_non_closure_zero_reported_delay(monkeypatch):
    """
    When a non-closure incident on route has 0 or null reported delay:
    detour_seconds=None, incident_delay_seconds in (0, None), impact_minutes=0,
    applied_to_eta=False.
    """
    monkeypatch.setattr(settings, "ROAD_RESTRICTION_API_KEY", "test-key-road")

    incident = _build_non_closure_incident(
        inc_id="INC-ZERO-01",
        delay_sec=0,
        description="Minor road hazard",
    )
    mock_payload = {"incidents": [incident]}

    provider = RoadRestrictionProvider()
    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = httpx.Response(200, json=mock_payload)
        res = await provider.evaluate(
            origin_lat=ORIGIN_LAT,
            origin_lon=ORIGIN_LON,
            dest_lat=DEST_LAT,
            dest_lon=DEST_LON,
            route_geometry=SAMPLE_ROUTE_GEOMETRY,
            original_route_time_seconds=2460,
        )

    assert res.impact_minutes == 0
    assert res.detour_seconds is None
    assert res.applied_to_eta is False
    assert "0 min delay applied" in res.description


# =============================================================================
# TEST 6: Non-closure already accounted for in live route traffic -> no double counting
# =============================================================================
@pytest.mark.asyncio
async def test_road_restriction_non_closure_already_accounted_for_in_live_traffic(monkeypatch):
    """
    When traffic slowdown is already captured in the authoritative live route
    (traffic_delay_seconds > 0), non-closure road restriction delay is not double counted.
    """
    monkeypatch.setattr(settings, "ROAD_RESTRICTION_API_KEY", "test-key-road")

    incident = _build_non_closure_incident(
        inc_id="INC-SLOWDOWN-01",
        delay_sec=300,
        description="Accident causing slowdown",
    )
    mock_payload = {"incidents": [incident]}

    provider = RoadRestrictionProvider()
    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = httpx.Response(200, json=mock_payload)
        res = await provider.evaluate(
            origin_lat=ORIGIN_LAT,
            origin_lon=ORIGIN_LON,
            dest_lat=DEST_LAT,
            dest_lon=DEST_LON,
            route_geometry=SAMPLE_ROUTE_GEOMETRY,
            original_route_time_seconds=2460,
            traffic_delay_seconds=300,  # Live route already includes 5 min traffic delay!
        )

    assert res.impact_minutes == 0
    assert res.detour_seconds is None
    assert res.applied_to_eta is False
    assert (
        "already accounted for in live route traffic" in res.description
        or "no double-counting" in res.description
    )


# =============================================================================
# TEST 7: Road restriction data source & factor serialization distinction
# =============================================================================
@pytest.mark.asyncio
async def test_road_restriction_data_source_and_factor_serialization():
    """
    Verify DataSource and ContextFactor serialization correctly distinguishes
    detour_seconds vs incident_delay_seconds with exact values and None semantics.
    """
    now = datetime.now(timezone.utc)

    # Scenario A: Closure Detour
    closure_result = ContextProviderResult(
        source_name="Road Restrictions",
        status=DataSourceStatus.AVAILABLE,
        impact_minutes=7,
        description="Route-relevant road restriction adds +7 min detour delay. Derived from alternate route comparison.",
        sampled_at=now,
        category="ROAD",
        provenance="REAL",
        freshness="FRESH",
        impact_classification="INCREMENTAL_DETOUR",
        causal_status="RELEVANT_INCREMENTAL_DETOUR",
        alternate_route_available=True,
        alternate_route_valid=True,
        original_route_time_seconds=2460,
        alternate_route_time_seconds=2880,
        detour_seconds=420,
        incident_delay_seconds=None,
        detour_display="+7 min (+420s)",
    )

    closure_factor_dict = closure_result.to_factor_dict()
    closure_ds_dict = closure_result.to_data_source_dict()

    closure_factor = ContextFactor(**closure_factor_dict)
    closure_ds = DataSource(**closure_ds_dict)

    assert closure_factor.detour_seconds == 420
    assert closure_factor.incident_delay_seconds is None
    assert closure_factor.alternate_route_available is True
    assert closure_ds.detour_seconds == 420
    assert closure_ds.incident_delay_seconds is None
    assert closure_ds.alternate_route_available is True

    # Scenario B: Non-Closure Incident Delay
    incident_result = ContextProviderResult(
        source_name="Road Restrictions",
        status=DataSourceStatus.AVAILABLE,
        impact_minutes=2,
        description="Route-relevant road restriction adds +2 min incident delay. TomTom reported incident delay: +107 sec (+2 min).",
        sampled_at=now,
        category="ROAD",
        provenance="REAL",
        freshness="FRESH",
        impact_classification="RELEVANT_INCIDENT_DELAY",
        causal_status="RELEVANT_INCIDENT_DELAY",
        alternate_route_available=False,
        alternate_route_valid=False,
        original_route_time_seconds=2460,
        alternate_route_time_seconds=None,
        detour_seconds=None,
        incident_delay_seconds=107,
        detour_display=None,
    )

    inc_factor_dict = incident_result.to_factor_dict()
    inc_ds_dict = incident_result.to_data_source_dict()

    inc_factor = ContextFactor(**inc_factor_dict)
    inc_ds = DataSource(**inc_ds_dict)

    assert inc_factor.detour_seconds is None
    assert inc_factor.incident_delay_seconds == 107
    assert inc_factor.alternate_route_available is False
    assert inc_ds.detour_seconds is None
    assert inc_ds.incident_delay_seconds == 107
    assert inc_ds.alternate_route_available is False


# =============================================================================
# TEST 8: WebSocket ETA update payload distinguishes detour vs incident delay
# =============================================================================
@pytest.mark.asyncio
async def test_road_restriction_websocket_eta_update_distinguishes_detour_vs_incident(monkeypatch):
    """
    Verify full ETAService calculation and WebSocket ETA_UPDATED serialization
    accurately reflects detour_seconds vs incident_delay_seconds in both data_sources and factors.
    """
    monkeypatch.setattr(settings, "ROAD_RESTRICTION_API_KEY", "test-key-road")

    orig_sec = 41 * 60  # 2460s (41 min baseline)
    alt_sec = 48 * 60   # 2880s (48 min alternate)

    incident = _build_closure_incident(
        inc_id="INC-WS-ACC-01",
        road_from="Market St",
        road_to="4th St",
        alternate_route_time_seconds=alt_sec,
    )
    mock_payload = {"incidents": [incident]}

    job_id = uuid.uuid4()
    tech_id = uuid.uuid4()

    mock_job = MagicMock(spec=Job)
    mock_job.id = job_id
    mock_job.job_number = "JOB-ACC-001"
    mock_job.latitude = DEST_LAT
    mock_job.longitude = DEST_LON
    mock_job.eta_overrides = []

    mock_tech = MagicMock(spec=Technician)
    mock_tech.id = tech_id
    mock_tech.employee_code = "TECH-ACC-01"
    mock_tech.full_name = "Alex Rivera"
    mock_tech.current_latitude = ORIGIN_LAT
    mock_tech.current_longitude = ORIGIN_LON
    mock_tech.availability_status = "AVAILABLE"
    mock_tech.updated_at = datetime.now(timezone.utc)
    mock_tech.user = MagicMock(spec=User)
    mock_tech.user.full_name = "Alex Rivera"

    mock_assign = MagicMock(spec=Assignment)
    mock_assign.id = uuid.uuid4()
    mock_assign.job_id = job_id
    mock_assign.technician_id = tech_id
    mock_assign.technician = mock_tech
    mock_assign.status = "DISPATCHED"
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
                "lengthInMeters": 18000,
                "travelTimeInSeconds": orig_sec,
                "noTrafficTravelTimeInSeconds": orig_sec,
                "trafficDelayInSeconds": 0,
            },
            "legs": [{
                "points": [{"latitude": pt[1], "longitude": pt[0]} for pt in SAMPLE_ROUTE_GEOMETRY]
            }],
        }]
    }

    async def mock_http_get(url, *args, **kwargs):
        url_str = str(url)
        if "calculateRoute" in url_str:
            return httpx.Response(200, json=route_payload)
        elif "incidentDetails" in url_str:
            return httpx.Response(200, json=mock_payload)
        return httpx.Response(200, json={})

    eta_service = ETAService()
    with patch("app.services.eta_service.AsyncSessionLocal", side_effect=mock_session_ctx), \
         patch("httpx.AsyncClient.get", new_callable=AsyncMock, side_effect=mock_http_get):
        eta_resp = await eta_service.calculate_job_eta(job_id)

    assert eta_resp is not None
    ws_payload = eta_resp.model_dump(mode="json")
    ws_road_ds = next(ds for ds in ws_payload["data_sources"] if ds["category"] == "ROAD")
    assert ws_road_ds["impact_minutes"] == 7
    assert ws_road_ds["detour_seconds"] == 420
    assert ws_road_ds["incident_delay_seconds"] is None

    ws_road_factor = next((f for f in ws_payload["factors"] if f["category"] == "ROAD"), None)
    assert ws_road_factor is not None
    assert ws_road_factor["impact_minutes"] == 7
    assert ws_road_factor["detour_seconds"] == 420
    assert ws_road_factor["incident_delay_seconds"] is None


# =============================================================================
# TEST 9: Cross-provider aggregation deduplicates incident delay against traffic
# =============================================================================
def test_road_restriction_cross_provider_deduplication_incident_delay():
    """
    Verify ContextAggregationService deduplicates RELEVANT_INCIDENT_DELAY against
    live traffic delay, avoiding double counting while preserving closure detours.
    """
    now = datetime.now(timezone.utc)
    agg_service = ContextAggregationService()

    # Case A: Live traffic has 3 min delay, road incident delay is 5 min
    # Road adjusted should be max(0, 5 - 3) = 2 min
    traffic_res = ContextProviderResult(
        source_name="Traffic Telemetry",
        status=DataSourceStatus.AVAILABLE,
        impact_minutes=3,
        description="Live route traffic delay +3m",
        sampled_at=now,
        category="TRAFFIC",
        provenance="REAL",
        freshness="FRESH",
    )
    road_res = ContextProviderResult(
        source_name="Road Restrictions",
        status=DataSourceStatus.AVAILABLE,
        impact_minutes=5,
        description="Route incident delay +5m",
        sampled_at=now,
        category="ROAD",
        provenance="REAL",
        freshness="FRESH",
        impact_classification="RELEVANT_INCIDENT_DELAY",
        causal_status="RELEVANT_INCIDENT_DELAY",
        detour_seconds=None,
        incident_delay_seconds=300,
    )

    summary = agg_service.aggregate(
        provider_results=[traffic_res, road_res],
        baseline_eta_minutes=40,
        distance_km=25.0,
        distance_miles=15.5,
    )

    road_factor = next(f for f in summary.factors if f.category == "ROAD")
    # Road factor adjusted to 2 min (5 - 3) to prevent double counting
    assert road_factor.impact_minutes == 2
    assert "avoid double-counting" in road_factor.description

    # Case B: Measured closure detour (INCREMENTAL_DETOUR) is not subtracted by traffic
    road_closure_res = ContextProviderResult(
        source_name="Road Restrictions",
        status=DataSourceStatus.AVAILABLE,
        impact_minutes=7,
        description="Alternate route detour +7m",
        sampled_at=now,
        category="ROAD",
        provenance="REAL",
        freshness="FRESH",
        impact_classification="INCREMENTAL_DETOUR",
        causal_status="RELEVANT_INCREMENTAL_DETOUR",
        detour_seconds=420,
        incident_delay_seconds=None,
        alternate_route_available=True,
    )

    summary_closure = agg_service.aggregate(
        provider_results=[traffic_res, road_closure_res],
        baseline_eta_minutes=40,
        distance_km=25.0,
        distance_miles=15.5,
    )

    road_closure_factor = next(f for f in summary_closure.factors if f.category == "ROAD")
    assert road_closure_factor.impact_minutes == 7


# =============================================================================
# TEST 10: Stale road restriction -> impact=0, freshness='STALE'
# =============================================================================
@pytest.mark.asyncio
async def test_road_restriction_stale_data_zero_impact(monkeypatch):
    """
    When road restriction data is stale (> 30 min old):
    impact_minutes=0, freshness='STALE', applied_to_eta=False, 0 min delay applied.
    """
    monkeypatch.setattr(settings, "ROAD_RESTRICTION_API_KEY", "test-key-road")

    now = datetime.now(timezone.utc)
    incident = _build_closure_incident(
        inc_id="INC-STALE-01",
        road_from="Market St",
        road_to="4th St",
        alternate_route_time_seconds=2880,
    )
    # Stale / expired incident
    incident["properties"]["startTime"] = (now - timedelta(hours=3)).isoformat()
    incident["properties"]["endTime"] = (now - timedelta(hours=1)).isoformat()
    incident["properties"]["freshness"] = "STALE"
    incident["properties"]["is_stale"] = True
    mock_payload = {"incidents": [incident]}

    provider = RoadRestrictionProvider()
    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = httpx.Response(200, json=mock_payload)
        res = await provider.evaluate(
            origin_lat=ORIGIN_LAT,
            origin_lon=ORIGIN_LON,
            dest_lat=DEST_LAT,
            dest_lon=DEST_LON,
            route_geometry=SAMPLE_ROUTE_GEOMETRY,
            original_route_time_seconds=2460,
        )

    assert res.freshness == "STALE"
    assert res.impact_minutes == 0
    assert res.applied_to_eta is False
    assert "data is stale" in res.description or "0 min delay applied" in res.description


# =============================================================================
# TEST 11: Example 2 alternate route difference (43m orig vs 48m alt -> +5m detour)
# =============================================================================
@pytest.mark.asyncio
async def test_road_restriction_accuracy_example_2_5min_detour(monkeypatch):
    monkeypatch.setattr(settings, "ROAD_RESTRICTION_API_KEY", "test-key-road")

    orig_sec = 43 * 60  # 2580 seconds
    alt_sec = 48 * 60   # 2880 seconds

    incident = _build_closure_incident(
        inc_id="INC-EX2",
        road_from="Market St",
        road_to="4th St",
        alternate_route_time_seconds=alt_sec,
    )
    mock_payload = {"incidents": [incident]}

    provider = RoadRestrictionProvider()
    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = httpx.Response(200, json=mock_payload)
        res = await provider.evaluate(
            origin_lat=ORIGIN_LAT,
            origin_lon=ORIGIN_LON,
            dest_lat=DEST_LAT,
            dest_lon=DEST_LON,
            route_geometry=SAMPLE_ROUTE_GEOMETRY,
            original_route_time_seconds=orig_sec,
        )

    assert res.status == DataSourceStatus.AVAILABLE
    assert res.provenance == "REAL"
    assert res.impact_minutes == 5
    assert res.detour_seconds == 300
    assert res.original_route_time_seconds == 2580
    assert res.alternate_route_time_seconds == 2880
    assert res.causal_status in ("RELEVANT_INCREMENTAL_DETOUR", "CAUSES_DETOUR")
    assert "Alternate route: 48 min vs original 43 min (+5 min)" in res.description
    assert res.applied_to_eta is True


# =============================================================================
# TEST 12: Intersecting alternate route rejected -> UNAVAILABLE, detour_seconds=None
# =============================================================================
@pytest.mark.asyncio
async def test_road_restriction_alternate_route_intersects_closure_rejected(monkeypatch):
    monkeypatch.setattr(settings, "ROAD_RESTRICTION_API_KEY", "test-key-road")

    incident = _build_closure_incident(
        inc_id="INC-INTERSECT-01",
        coords=CLOSURE_COORDS,
        delay=None,
    )
    mock_payload = {"incidents": [incident]}

    intersecting_alt_route = {
        "routes": [{
            "summary": {
                "lengthInMeters": 19000,
                "travelTimeInSeconds": 2880,
            },
            "legs": [{
                "points": [{"latitude": pt[1], "longitude": pt[0]} for pt in SAMPLE_ROUTE_GEOMETRY]
            }],
        }]
    }

    provider = RoadRestrictionProvider()
    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get, \
         patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_get.return_value = httpx.Response(200, json=mock_payload)
        mock_post.return_value = httpx.Response(200, json=intersecting_alt_route)

        res = await provider.evaluate(
            origin_lat=ORIGIN_LAT,
            origin_lon=ORIGIN_LON,
            dest_lat=DEST_LAT,
            dest_lon=DEST_LON,
            route_geometry=SAMPLE_ROUTE_GEOMETRY,
            original_route_time_seconds=2460,
        )

    assert res.impact_minutes == 0
    assert res.detour_seconds is None
    assert res.causal_status == "UNAVAILABLE"
    assert res.alternate_route_valid is False
    assert res.applied_to_eta is False


# =============================================================================
# TEST 13: Duplicate overlapping closure records along same corridor -> no summed penalty
# =============================================================================
@pytest.mark.asyncio
async def test_road_restriction_duplicate_overlapping_records_no_summed_penalty(monkeypatch):
    monkeypatch.setattr(settings, "ROAD_RESTRICTION_API_KEY", "test-key-road")

    orig_sec = 41 * 60  # 2460 seconds
    alt_sec = 48 * 60   # 2880 seconds (detour = 7 min)

    incident_eastbound = _build_closure_incident(
        inc_id="INC-JFK-EB",
        road_from="John F Kennedy Dr (EB)",
        road_to="Conservatory Dr",
        coords=CLOSURE_COORDS,
        alternate_route_time_seconds=alt_sec,
    )
    incident_westbound = _build_closure_incident(
        inc_id="INC-JFK-WB",
        road_from="John F Kennedy Dr (WB)",
        road_to="Conservatory Dr",
        coords=CLOSURE_COORDS,
        alternate_route_time_seconds=alt_sec,
    )
    mock_payload = {"incidents": [incident_eastbound, incident_westbound]}

    provider = RoadRestrictionProvider()
    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = httpx.Response(200, json=mock_payload)
        res = await provider.evaluate(
            origin_lat=ORIGIN_LAT,
            origin_lon=ORIGIN_LON,
            dest_lat=DEST_LAT,
            dest_lon=DEST_LON,
            route_geometry=SAMPLE_ROUTE_GEOMETRY,
            original_route_time_seconds=orig_sec,
        )

    # Must be exactly 7 min, NOT 14 min (7 + 7)
    assert res.impact_minutes == 7
    assert res.detour_seconds == 420
    assert "Alternate route: 48 min vs original 41 min (+7 min)" in res.description
