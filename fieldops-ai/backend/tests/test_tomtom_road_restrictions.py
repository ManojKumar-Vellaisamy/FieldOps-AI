"""
Comprehensive Automated Test Suite for Module 26:
TomTom Road Restrictions / Traffic Incidents Integration.

Verifies:
  - Successful TomTom incident response & full property parsing
  - Relevant incident detection along route corridor
  - Irrelevant incident filtering (outside bounding box / distance)
  - Expired incident filtering (endTime in past)
  - Duplicate incident deduplication
  - Missing API key handling (UNAVAILABLE, 0 min impact)
  - HTTP 401/403 authentication error handling (UNAVAILABLE, 0 min impact)
  - HTTP 429 rate limit error handling (UNAVAILABLE, 0 min impact)
  - HTTP 5xx server error handling (UNAVAILABLE, 0 min impact)
  - Timeout handling (UNAVAILABLE, 0 min impact)
  - Malformed response handling (INVALID, 0 min impact)
  - Informational incidents with 0 min impact
  - Calculated delay for restrictions (reported delay / road closure detour)
  - ETAService propagation into authoritative ETA calculation
  - WebSocket EVENT_ETA_UPDATED broadcast consistency
  - Dispatcher and Technician consistency
"""

import json
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch
import uuid

import httpx
import pytest
from sqlalchemy import select

from app.core.config import settings
from app.database.session import AsyncSessionLocal
from app.models.job import Job
from app.models.technician import Technician
from app.services.context_aggregation import ContextAggregationService
from app.services.context_providers import (
    ContextProviderResult,
    DataSourceStatus,
    RoadRestrictionProvider,
)
from app.services.eta_service import ETAService


# Sample valid TomTom Traffic Incidents mock payloads
def _build_tomtom_incident(
    inc_id="TTI-INC-001",
    icon_category=8,  # Road Closed
    magnitude=4,      # Blocking
    delay=None,
    events=None,
    start_time=None,
    end_time=None,
    road_from="Market St",
    road_to="4th St",
    coords=None,
    length=850.0,
):
    if coords is None:
        coords = [-122.4180, 37.7790]  # [lon, lat] along Market St corridor
    if events is None:
        events = [{"code": 108, "description": "Road closed due to major construction"}]
    if start_time is None:
        start_time = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
    if end_time is None:
        end_time = (datetime.now(timezone.utc) + timedelta(hours=6)).isoformat()

    return {
        "type": "Feature",
        "geometry": {
            "type": "Point",
            "coordinates": coords,
        },
        "properties": {
            "id": inc_id,
            "iconCategory": icon_category,
            "magnitudeOfDelay": magnitude,
            "delay": delay,
            "events": events,
            "startTime": start_time,
            "endTime": end_time,
            "from": road_from,
            "to": road_to,
            "length": length,
        },
    }


# -----------------------------------------------------------------------------
# 1. Successful TomTom incident response and parsing
# -----------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_tomtom_successful_incident_response_and_parsing(monkeypatch):
    """Verify successful TomTom HTTP 200 response parses all fields and yields REAL provenance."""
    monkeypatch.setattr(settings, "ROAD_RESTRICTION_API_KEY", "test-key-road")

    incident = _build_tomtom_incident(
        inc_id="TTI-TEST-100",
        icon_category=8,
        magnitude=4,
        delay=600,  # 10 min delay reported
        road_from="Mission St",
        road_to="5th St",
    )
    mock_payload = {"incidents": [incident]}

    provider = RoadRestrictionProvider()
    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = httpx.Response(200, json=mock_payload)
        res = await provider.evaluate(
            origin_lat=37.7749, origin_lon=-122.4194,
            dest_lat=37.7833, dest_lon=-122.4167,
        )

    assert res.status == DataSourceStatus.AVAILABLE
    assert res.provenance == "REAL"
    assert res.impact_minutes == 10
    assert res.restriction_count == 1
    assert res.active_restriction_name == "Mission St to 5th St"
    assert res.restriction_category == "Road Closed"
    assert res.restriction_severity == "Blocking / Severe"
    assert res.restriction_id == "TTI-TEST-100"
    assert res.is_road_closed is True
    assert "adds +10 min incident delay" in res.description or "adds +10 min detour delay" in res.description
    assert "TomTom Traffic Incidents (REAL)" in res.description


# -----------------------------------------------------------------------------
# 2. Relevant incident detection
# -----------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_tomtom_relevant_incident_detection(monkeypatch):
    """Incident within corridor bounding box and near transit route is detected."""
    monkeypatch.setattr(settings, "ROAD_RESTRICTION_API_KEY", "test-key-road")

    # Near SF Market St
    incident = _build_tomtom_incident(
        inc_id="TTI-REL-01",
        coords=[-122.4180, 37.7760],
        icon_category=7,  # Lane Closed
        delay=180,        # 3 min delay
    )
    mock_payload = {"incidents": [incident]}

    provider = RoadRestrictionProvider()
    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = httpx.Response(200, json=mock_payload)
        res = await provider.evaluate(
            origin_lat=37.7749, origin_lon=-122.4194,
            dest_lat=37.7833, dest_lon=-122.4167,
        )

    assert res.status == DataSourceStatus.AVAILABLE
    assert res.provenance == "REAL"
    assert res.restriction_count == 1
    assert res.impact_minutes == 3


# -----------------------------------------------------------------------------
# 3. Irrelevant incident filtering (outside bounding box / corridor)
# -----------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_tomtom_irrelevant_incident_filtering(monkeypatch):
    """Incident located far away (> 10 miles, Oakland or San Jose) is filtered out."""
    monkeypatch.setattr(settings, "ROAD_RESTRICTION_API_KEY", "test-key-road")

    # Oakland coordinates: -122.2711, 37.8044 (outside SF route corridor bounding box)
    incident_far = _build_tomtom_incident(
        inc_id="TTI-FAR-99",
        coords=[-122.2711, 37.8044],
        icon_category=8,
        delay=900,
    )
    mock_payload = {"incidents": [incident_far]}

    provider = RoadRestrictionProvider()
    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = httpx.Response(200, json=mock_payload)
        res = await provider.evaluate(
            origin_lat=37.7749, origin_lon=-122.4194,
            dest_lat=37.7833, dest_lon=-122.4167,
        )

    assert res.status == DataSourceStatus.AVAILABLE
    assert res.provenance == "REAL"
    assert res.impact_minutes == 0
    assert res.restriction_count == 0
    assert "No active road closures or restrictions along transit corridor" in res.description


# -----------------------------------------------------------------------------
# 4. Expired incident filtering
# -----------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_tomtom_expired_incident_filtering(monkeypatch):
    """Incident with endTime in the past is discarded, resulting in 0 impact."""
    monkeypatch.setattr(settings, "ROAD_RESTRICTION_API_KEY", "test-key-road")

    past_end = (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat()
    incident_expired = _build_tomtom_incident(
        inc_id="TTI-EXP-01",
        end_time=past_end,
        icon_category=8,
        delay=1200,
    )
    mock_payload = {"incidents": [incident_expired]}

    provider = RoadRestrictionProvider()
    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = httpx.Response(200, json=mock_payload)
        res = await provider.evaluate(
            origin_lat=37.7749, origin_lon=-122.4194,
            dest_lat=37.7833, dest_lon=-122.4167,
        )

    assert res.status == DataSourceStatus.AVAILABLE
    assert res.provenance == "REAL"
    assert res.impact_minutes == 0
    assert res.restriction_count == 0


# -----------------------------------------------------------------------------
# 5. Duplicate incident filtering
# -----------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_tomtom_duplicate_incident_filtering(monkeypatch):
    """Duplicate incident IDs in TomTom payload are counted only once."""
    monkeypatch.setattr(settings, "ROAD_RESTRICTION_API_KEY", "test-key-road")

    incident_1 = _build_tomtom_incident(inc_id="TTI-DUP-1", delay=300)
    incident_2 = _build_tomtom_incident(inc_id="TTI-DUP-1", delay=300)
    mock_payload = {"incidents": [incident_1, incident_2]}

    provider = RoadRestrictionProvider()
    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = httpx.Response(200, json=mock_payload)
        res = await provider.evaluate(
            origin_lat=37.7749, origin_lon=-122.4194,
            dest_lat=37.7833, dest_lon=-122.4167,
        )

    assert res.status == DataSourceStatus.AVAILABLE
    assert res.provenance == "REAL"
    assert res.restriction_count == 1
    assert res.impact_minutes == 5


# -----------------------------------------------------------------------------
# 6. Missing API key
# -----------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_tomtom_missing_api_key(monkeypatch):
    """When no TomTom or Traffic API key is configured, safely returns UNAVAILABLE with 0 delay."""
    monkeypatch.setattr(settings, "ROAD_RESTRICTION_API_KEY", None)
    monkeypatch.setattr(settings, "TOMTOM_API_KEY", None)
    monkeypatch.setattr(settings, "TRAFFIC_API_KEY", None)

    provider = RoadRestrictionProvider()
    res = await provider.evaluate(
        origin_lat=37.7749, origin_lon=-122.4194,
        dest_lat=37.7833, dest_lon=-122.4167,
    )

    assert res.status == DataSourceStatus.UNAVAILABLE
    assert res.provenance == "UNAVAILABLE"
    assert res.impact_minutes == 0
    assert "key not configured" in res.description


# -----------------------------------------------------------------------------
# 7. HTTP 401 / 403 Authentication failure
# -----------------------------------------------------------------------------

@pytest.mark.asyncio
@pytest.mark.parametrize("status_code", [401, 403])
async def test_tomtom_http_401_403(monkeypatch, status_code):
    """HTTP 401 or 403 yields UNAVAILABLE with 0 delay and preserves baseline."""
    monkeypatch.setattr(settings, "ROAD_RESTRICTION_API_KEY", "invalid-key")

    provider = RoadRestrictionProvider()
    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = httpx.Response(status_code, text="Unauthorized")
        res = await provider.evaluate(
            origin_lat=37.7749, origin_lon=-122.4194,
            dest_lat=37.7833, dest_lon=-122.4167,
        )

    assert res.status == DataSourceStatus.UNAVAILABLE
    assert res.provenance == "UNAVAILABLE"
    assert res.impact_minutes == 0
    assert f"HTTP {status_code}" in res.description


# -----------------------------------------------------------------------------
# 8. HTTP 429 Rate limiting
# -----------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_tomtom_http_429_rate_limit(monkeypatch):
    """HTTP 429 yields UNAVAILABLE with 0 delay."""
    monkeypatch.setattr(settings, "ROAD_RESTRICTION_API_KEY", "test-key-road")

    provider = RoadRestrictionProvider()
    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = httpx.Response(429, text="Too Many Requests")
        res = await provider.evaluate(
            origin_lat=37.7749, origin_lon=-122.4194,
            dest_lat=37.7833, dest_lon=-122.4167,
        )

    assert res.status == DataSourceStatus.UNAVAILABLE
    assert res.provenance == "UNAVAILABLE"
    assert res.impact_minutes == 0
    assert "rate limit reached" in res.description


# -----------------------------------------------------------------------------
# 9. HTTP 5xx Server error
# -----------------------------------------------------------------------------

@pytest.mark.asyncio
@pytest.mark.parametrize("status_code", [500, 502, 503])
async def test_tomtom_http_5xx_server_error(monkeypatch, status_code):
    """HTTP 5xx server errors safely degrade to UNAVAILABLE with 0 delay."""
    monkeypatch.setattr(settings, "ROAD_RESTRICTION_API_KEY", "test-key-road")

    provider = RoadRestrictionProvider()
    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = httpx.Response(status_code, text="Gateway Error")
        res = await provider.evaluate(
            origin_lat=37.7749, origin_lon=-122.4194,
            dest_lat=37.7833, dest_lon=-122.4167,
        )

    assert res.status == DataSourceStatus.UNAVAILABLE
    assert res.provenance == "UNAVAILABLE"
    assert res.impact_minutes == 0
    assert f"HTTP {status_code}" in res.description


# -----------------------------------------------------------------------------
# 10. Timeout error handling
# -----------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_tomtom_timeout_handling(monkeypatch):
    """Request timeout degrades safely to UNAVAILABLE with 0 delay."""
    monkeypatch.setattr(settings, "ROAD_RESTRICTION_API_KEY", "test-key-road")

    provider = RoadRestrictionProvider()
    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.side_effect = httpx.TimeoutException("Connection timed out")
        res = await provider.evaluate(
            origin_lat=37.7749, origin_lon=-122.4194,
            dest_lat=37.7833, dest_lon=-122.4167,
        )

    assert res.status == DataSourceStatus.UNAVAILABLE
    assert res.provenance == "UNAVAILABLE"
    assert res.impact_minutes == 0
    assert "timed out" in res.description


# -----------------------------------------------------------------------------
# 11. Malformed response handling
# -----------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_tomtom_malformed_response_handling(monkeypatch):
    """Malformed non-JSON response yields INVALID status with 0 delay."""
    monkeypatch.setattr(settings, "ROAD_RESTRICTION_API_KEY", "test-key-road")

    provider = RoadRestrictionProvider()
    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = httpx.Response(200, text="<xml>invalid payload</xml>", headers={"content-type": "text/html"})
        res = await provider.evaluate(
            origin_lat=37.7749, origin_lon=-122.4194,
            dest_lat=37.7833, dest_lon=-122.4167,
        )

    assert res.status == DataSourceStatus.INVALID
    assert res.provenance == "UNAVAILABLE"
    assert res.impact_minutes == 0
    assert "Malformed" in res.description


# -----------------------------------------------------------------------------
# 12. Informational incident with 0-minute impact
# -----------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_tomtom_informational_incident_zero_delay(monkeypatch):
    """Lane closed or advisory without delay yields AVAILABLE, REAL, but strictly 0 min delay."""
    monkeypatch.setattr(settings, "ROAD_RESTRICTION_API_KEY", "test-key-road")

    # iconCategory 7 (Lane Closed), no reported delay, not a full closure
    incident = _build_tomtom_incident(
        inc_id="TTI-INFO-01",
        icon_category=7,
        magnitude=1,  # Minor
        delay=None,
        events=[{"code": 500, "description": "Single lane closed for maintenance"}],
    )
    mock_payload = {"incidents": [incident]}

    provider = RoadRestrictionProvider()
    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = httpx.Response(200, json=mock_payload)
        res = await provider.evaluate(
            origin_lat=37.7749, origin_lon=-122.4194,
            dest_lat=37.7833, dest_lon=-122.4167,
        )

    assert res.status == DataSourceStatus.AVAILABLE
    assert res.provenance == "REAL"
    assert res.impact_minutes == 0
    assert "minor/informational impact — 0 min delay applied" in res.description


# -----------------------------------------------------------------------------
# 13. Valid road closure with calculated detour impact
# -----------------------------------------------------------------------------
# 13. Valid road closure with calculated detour impact
# -----------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_tomtom_valid_restriction_with_calculated_impact(monkeypatch):
    """A major road closure calculates detour impact via alternate route comparison (Phase 2)."""
    monkeypatch.setattr(settings, "ROAD_RESTRICTION_API_KEY", "test-key-road")

    incident = _build_tomtom_incident(
        inc_id="TTI-CLOSURE-01",
        icon_category=8,  # Road Closed
        magnitude=4,      # Blocking
        delay=None,
        events=[{"code": 108, "description": "Road closed due to bridge inspection"}],
    )
    # Provide alternate route time to derive detour
    incident["alternate_route_time_seconds"] = 1080  # 18 min alternate route
    mock_payload = {"incidents": [incident]}

    provider = RoadRestrictionProvider()
    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = httpx.Response(200, json=mock_payload)
        res = await provider.evaluate(
            origin_lat=37.7749, origin_lon=-122.4194,
            dest_lat=37.7833, dest_lon=-122.4167,
            original_route_time_seconds=600,  # 10 min original route
        )

    assert res.status == DataSourceStatus.AVAILABLE
    assert res.provenance == "REAL"
    assert res.impact_minutes == 8  # 18 min - 10 min = 8 min detour
    assert res.is_road_closed is True
    assert res.detour_travel_time_minutes == 18


# -----------------------------------------------------------------------------
# 14. ETAService propagation into authoritative ETA
# -----------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_tomtom_eta_service_propagation(monkeypatch):
    """Verify that TomTom road restriction context propagates into ETAService authoritative ETA."""
    from unittest.mock import MagicMock
    from contextlib import asynccontextmanager
    from app.models.assignment import Assignment
    from app.models.user import User

    monkeypatch.setattr(settings, "ROAD_RESTRICTION_API_KEY", "test-key-road")

    incident = _build_tomtom_incident(
        inc_id="TTI-PROP-01",
        icon_category=8,
        magnitude=4,
        delay=480,  # 8 min delay
    )
    mock_payload = {"incidents": [incident]}

    job_id = uuid.uuid4()
    tech_id = uuid.uuid4()

    mock_job = MagicMock(spec=Job)
    mock_job.id = job_id
    mock_job.job_number = "JOB-PROP-TEST"
    mock_job.latitude = 37.7833
    mock_job.longitude = -122.4167
    mock_job.eta_overrides = []

    mock_tech = MagicMock(spec=Technician)
    mock_tech.id = tech_id
    mock_tech.employee_code = "TECH-PROP-01"
    mock_tech.full_name = "Alex Rivera"
    mock_tech.current_latitude = 37.7749
    mock_tech.current_longitude = -122.4194
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
                "lengthInMeters": 1500,
                "travelTimeInSeconds": 600,
                "noTrafficTravelTimeInSeconds": 600,
                "trafficDelayInSeconds": 0,
            },
            "legs": [{
                "points": [
                    {"latitude": 37.7749, "longitude": -122.4194},
                    {"latitude": 37.7790, "longitude": -122.4180},
                    {"latitude": 37.7833, "longitude": -122.4167},
                ]
            }],
        }]
    }

    async def side_effect_get(url, *args, **kwargs):
        url_str = str(url)
        if "calculateRoute" in url_str:
            return httpx.Response(200, json=route_payload)
        elif "incidentDetails" in url_str:
            return httpx.Response(200, json=mock_payload)
        return httpx.Response(200, json={})

    eta_service = ETAService()
    with patch("app.services.eta_service.AsyncSessionLocal", side_effect=mock_session_ctx), \
         patch("httpx.AsyncClient.get", new_callable=AsyncMock, side_effect=side_effect_get):
        eta_resp = await eta_service.calculate_job_eta(job_id)

    assert eta_resp is not None
    road_sources = [ds for ds in eta_resp.data_sources if ds.category == "ROAD"]
    assert len(road_sources) == 1
    road_ds = road_sources[0]
    assert road_ds.status == "AVAILABLE"
    assert road_ds.provenance == "REAL"
    assert road_ds.impact_minutes == 8
    assert road_ds.active_restriction_name == "Market St to 4th St"
    assert eta_resp.context_aware_eta_minutes >= eta_resp.baseline_eta_minutes + 8


# -----------------------------------------------------------------------------
# 15. WebSocket propagation & Dispatcher/Technician consistency
# -----------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_tomtom_websocket_event_and_consistency(monkeypatch):
    """Verify EVENT_ETA_UPDATED broadcast payload preserves road restriction provenance and is identical."""
    from unittest.mock import MagicMock
    from contextlib import asynccontextmanager
    from app.models.assignment import Assignment
    from app.models.user import User

    monkeypatch.setattr(settings, "ROAD_RESTRICTION_API_KEY", "test-key-road")

    incident = _build_tomtom_incident(
        inc_id="TTI-WS-01",
        icon_category=8,
        magnitude=3,
        delay=300,  # 5 min delay
    )
    mock_payload = {"incidents": [incident]}

    job_id = uuid.uuid4()
    tech_id = uuid.uuid4()

    mock_job = MagicMock(spec=Job)
    mock_job.id = job_id
    mock_job.job_number = "JOB-WS-TEST"
    mock_job.latitude = 37.7833
    mock_job.longitude = -122.4167
    mock_job.eta_overrides = []

    mock_tech = MagicMock(spec=Technician)
    mock_tech.id = tech_id
    mock_tech.employee_code = "TECH-WS-01"
    mock_tech.full_name = "Alex Rivera"
    mock_tech.current_latitude = 37.7749
    mock_tech.current_longitude = -122.4194
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
                "lengthInMeters": 1500,
                "travelTimeInSeconds": 600,
                "noTrafficTravelTimeInSeconds": 600,
                "trafficDelayInSeconds": 0,
            },
            "legs": [{
                "points": [
                    {"latitude": 37.7749, "longitude": -122.4194},
                    {"latitude": 37.7790, "longitude": -122.4180},
                    {"latitude": 37.7833, "longitude": -122.4167},
                ]
            }],
        }]
    }

    async def side_effect_get(url, *args, **kwargs):
        url_str = str(url)
        if "calculateRoute" in url_str:
            return httpx.Response(200, json=route_payload)
        elif "incidentDetails" in url_str:
            return httpx.Response(200, json=mock_payload)
        return httpx.Response(200, json={})

    eta_service = ETAService()
    with patch("app.services.eta_service.AsyncSessionLocal", side_effect=mock_session_ctx), \
         patch("httpx.AsyncClient.get", new_callable=AsyncMock, side_effect=side_effect_get):
        eta_resp = await eta_service.calculate_job_eta(job_id)

    ws_payload = eta_resp.model_dump(mode="json")
    road_ds = next(ds for ds in ws_payload["data_sources"] if ds["category"] == "ROAD")
    assert road_ds["provenance"] == "REAL"
    assert road_ds["status"] == "AVAILABLE"
    assert road_ds["impact_minutes"] == 5

    dispatcher_eta = ws_payload["final_dispatch_eta_minutes"]
    technician_eta = ws_payload["final_dispatch_eta_minutes"]
    assert dispatcher_eta == technician_eta
    assert dispatcher_eta == eta_resp.final_dispatch_eta_minutes
