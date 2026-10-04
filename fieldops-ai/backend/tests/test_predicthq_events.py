"""
Unit and integration tests for Real PredictHQ Events Integration (Module 25).
"""

import uuid
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, patch, MagicMock

import httpx
import pytest

from sqlalchemy import select
from app.core.config import settings
from app.database.session import AsyncSessionLocal
from app.services.context_providers import DataSourceStatus, EventsDataProvider, ContextProviderResult
from app.services.eta_service import ETAService
from app.models.job import Job, JobStatus
from app.models.technician import Technician
from app.models.user import User, UserRole


@pytest.fixture(autouse=True)
def ensure_default_settings(monkeypatch):
    """Ensure baseline settings for predictable tests."""
    monkeypatch.setattr(settings, "EVENTS_API_KEY", "test-predicthq-token-xyz")
    monkeypatch.setattr(settings, "EVENTS_API_URL", "https://api.predicthq.com/v1/events/")
    monkeypatch.setattr(settings, "EVENTS_TIMEOUT_SECONDS", 2.0)
    monkeypatch.setattr(settings, "TRAFFIC_PROVIDER", "osrm")


# ── 1. Missing API Key ──────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_predicthq_missing_api_key(monkeypatch):
    """When EVENTS_API_KEY is None or empty, returns UNAVAILABLE with 0 delay."""
    monkeypatch.setattr(settings, "EVENTS_API_KEY", None)
    provider = EventsDataProvider()
    res = await provider.evaluate(dest_lat=37.7749, dest_lon=-122.4194)

    assert res.status == DataSourceStatus.UNAVAILABLE
    assert res.provenance == "UNAVAILABLE"
    assert res.impact_minutes == 0
    assert "key missing" in res.description.lower() or "not configured" in res.description.lower() or "not integrated" in res.description.lower()


# ── 2. Successful Response — Major Gathering (+10m) ────────────────────────────

@pytest.mark.asyncio
async def test_predicthq_successful_major_gathering():
    """Major stadium game (attendance > 20,000, rank > 75) adds +10 min staging delay."""
    now = datetime.now(timezone.utc)
    mock_payload = {
        "count": 1,
        "results": [
            {
                "id": "EVT-GIANTS-GAME",
                "title": "SF Giants vs SD Padres",
                "category": "sports",
                "rank": 82,
                "phq_attendance": 38500,
                "start": (now + timedelta(minutes=30)).isoformat(),
                "end": (now + timedelta(hours=3)).isoformat(),
                "location": [-122.3892, 37.7785],  # [lon, lat] at Oracle Park
            }
        ],
    }

    mock_resp = MagicMock(spec=httpx.Response)
    mock_resp.status_code = 200
    mock_resp.json.return_value = mock_payload

    with patch("httpx.AsyncClient.get", new_callable=AsyncMock, return_value=mock_resp):
        provider = EventsDataProvider()
        res = await provider.evaluate(dest_lat=37.7749, dest_lon=-122.4194)

    assert res.status == DataSourceStatus.AVAILABLE
    assert res.provenance == "REAL"
    assert res.impact_minutes == 10
    assert res.event_count == 1
    assert res.active_event_name == "SF Giants vs SD Padres"
    assert res.event_category == "sports"
    assert res.event_attendance == 38500
    assert res.event_rank == 82
    assert "+10 min staging delay" in res.description


# ── 3. Successful Response — Moderate Gathering (+3m) ─────────────────────────

@pytest.mark.asyncio
async def test_predicthq_successful_moderate_gathering():
    """Moderate gathering (attendance 2,500, rank 45) adds +3 min delay."""
    now = datetime.now(timezone.utc)
    mock_payload = {
        "count": 1,
        "results": [
            {
                "id": "EVT-TECH-CONF",
                "title": "Cloud Computing Summit",
                "category": "conferences",
                "rank": 45,
                "phq_attendance": 2500,
                "start": (now - timedelta(hours=1)).isoformat(),
                "end": (now + timedelta(hours=4)).isoformat(),
                "location": [-122.4018, 37.7842],
            }
        ],
    }

    mock_resp = MagicMock(spec=httpx.Response)
    mock_resp.status_code = 200
    mock_resp.json.return_value = mock_payload

    with patch("httpx.AsyncClient.get", new_callable=AsyncMock, return_value=mock_resp):
        provider = EventsDataProvider()
        res = await provider.evaluate(dest_lat=37.7749, dest_lon=-122.4194)

    assert res.status == DataSourceStatus.AVAILABLE
    assert res.provenance == "REAL"
    assert res.impact_minutes == 3
    assert res.event_attendance == 2500


# ── 4. Successful Response — Minor / Informational Gathering (0m) ─────────────

@pytest.mark.asyncio
async def test_predicthq_successful_minor_gathering_zero_delay():
    """Minor gathering (rank < 30, attendance < 1,000) results in 0 min delay (informational)."""
    now = datetime.now(timezone.utc)
    mock_payload = {
        "count": 1,
        "results": [
            {
                "id": "EVT-LOCAL-RECITAL",
                "title": "Sunday Afternoon Recital",
                "category": "performing-arts",
                "rank": 18,
                "phq_attendance": 120,
                "start": (now - timedelta(minutes=15)).isoformat(),
                "end": (now + timedelta(hours=1)).isoformat(),
                "location": [-122.4200, 37.7750],
            }
        ],
    }

    mock_resp = MagicMock(spec=httpx.Response)
    mock_resp.status_code = 200
    mock_resp.json.return_value = mock_payload

    with patch("httpx.AsyncClient.get", new_callable=AsyncMock, return_value=mock_resp):
        provider = EventsDataProvider()
        res = await provider.evaluate(dest_lat=37.7749, dest_lon=-122.4194)

    assert res.status == DataSourceStatus.AVAILABLE
    assert res.provenance == "REAL"
    assert res.impact_minutes == 0
    assert "informational impact" in res.description.lower() or "0 min" in res.description


# ── 5. Zero Events Nearby (0m, provenance=REAL) ───────────────────────────────

@pytest.mark.asyncio
async def test_predicthq_zero_events_provenance_is_real():
    """PredictHQ returns 200 OK with empty results: status=AVAILABLE, provenance=REAL, impact=0."""
    mock_resp = MagicMock(spec=httpx.Response)
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"count": 0, "results": []}

    with patch("httpx.AsyncClient.get", new_callable=AsyncMock, return_value=mock_resp):
        provider = EventsDataProvider()
        res = await provider.evaluate(dest_lat=37.7749, dest_lon=-122.4194)

    assert res.status == DataSourceStatus.AVAILABLE
    assert res.provenance == "REAL"
    assert res.impact_minutes == 0
    assert res.event_count == 0
    assert "no active public events" in res.description.lower()


# ── 6. Non-Congestion Category (Observance / Holiday) ─────────────────────────

@pytest.mark.asyncio
async def test_predicthq_non_congestion_category_zero_delay():
    """Non-traffic/non-congestion categories (e.g. observances, holidays) contribute 0 min delay."""
    now = datetime.now(timezone.utc)
    mock_payload = {
        "count": 1,
        "results": [
            {
                "id": "EVT-HUMAN-RIGHTS",
                "title": "Human Rights Observance Day",
                "category": "observances",
                "rank": 40,
                "phq_attendance": None,
                "start": (now - timedelta(hours=2)).isoformat(),
                "end": (now + timedelta(hours=10)).isoformat(),
                "location": [-122.4194, 37.7749],
            }
        ],
    }

    mock_resp = MagicMock(spec=httpx.Response)
    mock_resp.status_code = 200
    mock_resp.json.return_value = mock_payload

    with patch("httpx.AsyncClient.get", new_callable=AsyncMock, return_value=mock_resp):
        provider = EventsDataProvider()
        res = await provider.evaluate(dest_lat=37.7749, dest_lon=-122.4194)

    assert res.status == DataSourceStatus.AVAILABLE
    assert res.provenance == "REAL"
    assert res.impact_minutes == 0


# ── 7. HTTP Authentication Failure (401/403) ──────────────────────────────────

@pytest.mark.asyncio
async def test_predicthq_auth_failure_401():
    """HTTP 401 returns UNAVAILABLE with 0 delay and no crash."""
    mock_resp = MagicMock(spec=httpx.Response)
    mock_resp.status_code = 401
    mock_resp.text = '{"error": "Unauthorized"}'

    with patch("httpx.AsyncClient.get", new_callable=AsyncMock, return_value=mock_resp):
        provider = EventsDataProvider()
        res = await provider.evaluate(dest_lat=37.7749, dest_lon=-122.4194)

    assert res.status == DataSourceStatus.UNAVAILABLE
    assert res.provenance == "UNAVAILABLE"
    assert res.impact_minutes == 0
    assert "authentication failed" in res.description.lower()


# ── 8. Rate Limit Reached (429) ───────────────────────────────────────────────

@pytest.mark.asyncio
async def test_predicthq_rate_limit_429():
    """HTTP 429 returns UNAVAILABLE with 0 delay."""
    mock_resp = MagicMock(spec=httpx.Response)
    mock_resp.status_code = 429
    mock_resp.text = '{"error": "Rate limit exceeded"}'

    with patch("httpx.AsyncClient.get", new_callable=AsyncMock, return_value=mock_resp):
        provider = EventsDataProvider()
        res = await provider.evaluate(dest_lat=37.7749, dest_lon=-122.4194)

    assert res.status == DataSourceStatus.UNAVAILABLE
    assert res.provenance == "UNAVAILABLE"
    assert res.impact_minutes == 0
    assert "rate limit" in res.description.lower()


# ── 9. Server Error (500) ─────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_predicthq_server_error_500():
    """HTTP 500 returns UNAVAILABLE with 0 delay."""
    mock_resp = MagicMock(spec=httpx.Response)
    mock_resp.status_code = 500
    mock_resp.text = '{"error": "Internal Server Error"}'

    with patch("httpx.AsyncClient.get", new_callable=AsyncMock, return_value=mock_resp):
        provider = EventsDataProvider()
        res = await provider.evaluate(dest_lat=37.7749, dest_lon=-122.4194)

    assert res.status == DataSourceStatus.UNAVAILABLE
    assert res.provenance == "UNAVAILABLE"
    assert res.impact_minutes == 0
    assert "http 500" in res.description.lower()


# ── 10. Timeout Handling ──────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_predicthq_timeout():
    """httpx.TimeoutException returns UNAVAILABLE with 0 delay."""
    with patch("httpx.AsyncClient.get", new_callable=AsyncMock, side_effect=httpx.TimeoutException("Timeout")):
        provider = EventsDataProvider()
        res = await provider.evaluate(dest_lat=37.7749, dest_lon=-122.4194)

    assert res.status == DataSourceStatus.UNAVAILABLE
    assert res.provenance == "UNAVAILABLE"
    assert res.impact_minutes == 0
    assert "timed out" in res.description.lower()


# ── 11. Malformed JSON Response ───────────────────────────────────────────────

@pytest.mark.asyncio
async def test_predicthq_malformed_json():
    """Non-JSON response returns INVALID with 0 delay."""
    mock_resp = MagicMock(spec=httpx.Response)
    mock_resp.status_code = 200
    mock_resp.json.side_effect = ValueError("Invalid JSON")

    with patch("httpx.AsyncClient.get", new_callable=AsyncMock, return_value=mock_resp):
        provider = EventsDataProvider()
        res = await provider.evaluate(dest_lat=37.7749, dest_lon=-122.4194)

    assert res.status == DataSourceStatus.INVALID
    assert res.provenance == "UNAVAILABLE"
    assert res.impact_minutes == 0
    assert "malformed" in res.description.lower()


# ── 12. Expired Event Filtering ───────────────────────────────────────────────

@pytest.mark.asyncio
async def test_predicthq_expired_event_filtering():
    """Events with end < now are filtered out."""
    now = datetime.now(timezone.utc)
    mock_payload = {
        "count": 1,
        "results": [
            {
                "id": "EVT-PAST-MARATHON",
                "title": "Yesterday's Marathon",
                "category": "sports",
                "rank": 90,
                "phq_attendance": 40000,
                "start": (now - timedelta(days=1, hours=4)).isoformat(),
                "end": (now - timedelta(hours=2)).isoformat(),  # Expired
                "location": [-122.4194, 37.7749],
            }
        ],
    }

    mock_resp = MagicMock(spec=httpx.Response)
    mock_resp.status_code = 200
    mock_resp.json.return_value = mock_payload

    with patch("httpx.AsyncClient.get", new_callable=AsyncMock, return_value=mock_resp):
        provider = EventsDataProvider()
        res = await provider.evaluate(dest_lat=37.7749, dest_lon=-122.4194)

    assert res.status == DataSourceStatus.AVAILABLE
    assert res.provenance == "REAL"
    assert res.impact_minutes == 0
    assert res.event_count == 0


# ── 13. Geographically Irrelevant Filtering (> 5 miles) ───────────────────────

@pytest.mark.asyncio
async def test_predicthq_geographically_irrelevant_filtering():
    """Events outside 5 miles from destination are ignored."""
    now = datetime.now(timezone.utc)
    mock_payload = {
        "count": 1,
        "results": [
            {
                "id": "EVT-OAKLAND-ARENA",
                "title": "Oakland Arena Concert",
                "category": "concerts",
                "rank": 85,
                "phq_attendance": 18000,
                "start": (now + timedelta(hours=1)).isoformat(),
                "end": (now + timedelta(hours=4)).isoformat(),
                "location": [-122.2030, 37.7503],  # Oakland Arena: ~12 miles from SF downtown
            }
        ],
    }

    mock_resp = MagicMock(spec=httpx.Response)
    mock_resp.status_code = 200
    mock_resp.json.return_value = mock_payload

    with patch("httpx.AsyncClient.get", new_callable=AsyncMock, return_value=mock_resp):
        provider = EventsDataProvider()
        res = await provider.evaluate(dest_lat=37.7749, dest_lon=-122.4194)

    assert res.status == DataSourceStatus.AVAILABLE
    assert res.provenance == "REAL"
    assert res.impact_minutes == 0
    assert res.event_count == 0


# ── 14. Duplicate Event ID Filtering ──────────────────────────────────────────

@pytest.mark.asyncio
async def test_predicthq_duplicate_event_filtering():
    """Duplicate event IDs are deduplicated."""
    now = datetime.now(timezone.utc)
    mock_payload = {
        "count": 2,
        "results": [
            {
                "id": "EVT-DUP-1",
                "title": "Downtown Street Fair",
                "category": "festivals",
                "rank": 60,
                "phq_attendance": 6000,
                "start": (now + timedelta(minutes=10)).isoformat(),
                "end": (now + timedelta(hours=3)).isoformat(),
                "location": [-122.4194, 37.7749],
            },
            {
                "id": "EVT-DUP-1",  # Same ID
                "title": "Downtown Street Fair (Duplicate)",
                "category": "festivals",
                "rank": 60,
                "phq_attendance": 6000,
                "start": (now + timedelta(minutes=10)).isoformat(),
                "end": (now + timedelta(hours=3)).isoformat(),
                "location": [-122.4194, 37.7749],
            },
        ],
    }

    mock_resp = MagicMock(spec=httpx.Response)
    mock_resp.status_code = 200
    mock_resp.json.return_value = mock_payload

    with patch("httpx.AsyncClient.get", new_callable=AsyncMock, return_value=mock_resp):
        provider = EventsDataProvider()
        res = await provider.evaluate(dest_lat=37.7749, dest_lon=-122.4194)

    assert res.status == DataSourceStatus.AVAILABLE
    assert res.provenance == "REAL"
    assert res.event_count == 1
    assert res.impact_minutes == 5  # Single festival impact, not doubled


# ── 15. Cumulative Delay Cap (15m) ────────────────────────────────────────────

@pytest.mark.asyncio
async def test_predicthq_cumulative_delay_cap_15m():
    """Multiple large events sum their delay but are capped at maximum 15 minutes."""
    now = datetime.now(timezone.utc)
    mock_payload = {
        "count": 2,
        "results": [
            {
                "id": "EVT-STADIUM-1",
                "title": "Stadium Football Game",
                "category": "sports",
                "rank": 80,
                "phq_attendance": 30000,
                "start": (now + timedelta(minutes=10)).isoformat(),
                "end": (now + timedelta(hours=3)).isoformat(),
                "location": [-122.3892, 37.7785],
            },
            {
                "id": "EVT-STADIUM-2",
                "title": "Arena Music Festival",
                "category": "festivals",
                "rank": 78,
                "phq_attendance": 25000,
                "start": (now + timedelta(minutes=15)).isoformat(),
                "end": (now + timedelta(hours=4)).isoformat(),
                "location": [-122.3900, 37.7790],
            },
        ],
    }

    mock_resp = MagicMock(spec=httpx.Response)
    mock_resp.status_code = 200
    mock_resp.json.return_value = mock_payload

    with patch("httpx.AsyncClient.get", new_callable=AsyncMock, return_value=mock_resp):
        provider = EventsDataProvider()
        res = await provider.evaluate(dest_lat=37.7749, dest_lon=-122.4194)

    assert res.status == DataSourceStatus.AVAILABLE
    assert res.provenance == "REAL"
    assert res.impact_minutes == 15  # 10 + 10 = 20, capped at 15
    assert res.event_count == 2


# ── 16. ETAService Integration & WebSocket Propagation ────────────────────────

@pytest.mark.asyncio
async def test_predicthq_etaservice_propagation():
    """Real PredictHQ event impact propagates through ETAService into data_sources and factors."""
    now = datetime.now(timezone.utc)
    eta_service = ETAService()

    async with AsyncSessionLocal() as session:
        tech = (await session.execute(select(Technician).where(Technician.employee_code == "TECH-002"))).scalar_one_or_none()
        job = (await session.execute(select(Job).where(Job.job_number == "JOB-10002"))).scalar_one_or_none()
        if not tech or not job:
            tech = (await session.execute(select(Technician).where(Technician.current_latitude.isnot(None)))).scalars().first()
            job = (await session.execute(select(Job).where(Job.latitude.isnot(None)))).scalars().first()

        assert tech is not None and job is not None

        mock_payload = {
            "count": 1,
            "results": [
                {
                    "id": "EVT-MARATHON-INTEG",
                    "title": "Bay Area Marathon",
                    "category": "sports",
                    "rank": 85,
                    "phq_attendance": 32000,
                    "start": now.isoformat(),
                    "end": (now + timedelta(hours=4)).isoformat(),
                    "location": [float(job.longitude), float(job.latitude)],
                    "geo": {
                        "address": {
                            "formatted_address": "Embarcadero, San Francisco, CA",
                        }
                    },
                }
            ],
        }

        mock_resp = MagicMock(spec=httpx.Response)
        mock_resp.status_code = 200
        mock_resp.json.return_value = mock_payload

        with patch("httpx.AsyncClient.get", new_callable=AsyncMock, return_value=mock_resp):
            eta_resp = await eta_service.calculate_job_eta(job_id=job.id, technician_id=tech.id)

    # Locate Events data source
    events_ds = next((ds for ds in eta_resp.data_sources if ds.category == "EVENTS"), None)
    assert events_ds is not None
    assert events_ds.status == "AVAILABLE"
    assert events_ds.provenance == "REAL"
    assert events_ds.impact_minutes == 10
    assert events_ds.active_event_name == "Bay Area Marathon"
    assert events_ds.event_attendance == 32000
    assert events_ds.event_rank == 85
    assert events_ds.event_id == "EVT-MARATHON-INTEG"
    assert events_ds.event_start is not None
    assert events_ds.event_end is not None

    # Locate Events factor
    events_factor = next((f for f in eta_resp.factors if f.category == "EVENTS"), None)
    assert events_factor is not None
    assert events_factor.impact_minutes == 10
    assert "Bay Area Marathon" in events_factor.description


# ── 17. HTTP 400 Bad Request ───────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_predicthq_http_400_bad_request():
    """HTTP 400 returns UNAVAILABLE with 0 delay and clear description."""
    mock_resp = MagicMock(spec=httpx.Response)
    mock_resp.status_code = 400
    mock_resp.text = '{"error": "Invalid query parameter"}'

    with patch("httpx.AsyncClient.get", new_callable=AsyncMock, return_value=mock_resp):
        provider = EventsDataProvider()
        res = await provider.evaluate(dest_lat=37.7749, dest_lon=-122.4194)

    assert res.status == DataSourceStatus.UNAVAILABLE
    assert res.provenance == "UNAVAILABLE"
    assert res.impact_minutes == 0
    assert "http 400" in res.description.lower()


# ── 18. WebSocket Broadcast Full Payload Propagation ──────────────────────────

@pytest.mark.asyncio
async def test_predicthq_websocket_broadcast_propagation():
    """PredictHQ event details correctly serialize into WebSocket broadcast payloads."""
    from app.services.technician_service import TechnicianService
    from app.core.realtime import ws_manager, EVENT_ETA_UPDATED
    from app.models.assignment import Assignment

    now = datetime.now(timezone.utc)
    mock_payload = {
        "count": 1,
        "results": [
            {
                "id": "EVT-STADIUM-WS",
                "title": "Oracle Park Baseball Championship",
                "category": "sports",
                "rank": 88,
                "phq_attendance": 41000,
                "start": now.isoformat(),
                "end": (now + timedelta(hours=3)).isoformat(),
                "location": [-122.3892, 37.7785],
            }
        ],
    }

    mock_resp = MagicMock(spec=httpx.Response)
    mock_resp.status_code = 200
    mock_resp.json.return_value = mock_payload

    broadcast_events = []

    async def mock_broadcast(event_name, data, technician_user_id=None):
        broadcast_events.append((event_name, data))

    async with AsyncSessionLocal() as session:
        tech = (await session.execute(select(Technician).where(Technician.employee_code == "TECH-002"))).scalar_one_or_none()
        job = (await session.execute(select(Job).where(Job.job_number == "JOB-10002"))).scalar_one_or_none()
        if not tech or not job:
            tech = (await session.execute(select(Technician).where(Technician.current_latitude.isnot(None)))).scalars().first()
            job = (await session.execute(select(Job).where(Job.latitude.isnot(None)))).scalars().first()

        assert tech is not None and job is not None

        # Ensure active assignment exists for this tech and job
        existing_asgn = (await session.execute(
            select(Assignment).where(Assignment.job_id == job.id, Assignment.technician_id == tech.id)
        )).scalar_one_or_none()
        if not existing_asgn:
            new_asgn = Assignment(
                job_id=job.id,
                technician_id=tech.id,
                assignment_status="ASSIGNED",
                assignment_type="MANUAL",
            )
            session.add(new_asgn)
            await session.commit()
        elif existing_asgn.assignment_status not in ("ASSIGNED", "TRAVELLING", "ARRIVED", "WORKING"):
            existing_asgn.assignment_status = "ASSIGNED"
            await session.commit()

        tech_service = TechnicianService()
        with patch("httpx.AsyncClient.get", new_callable=AsyncMock, return_value=mock_resp), \
             patch.object(ws_manager, "broadcast_operational_event", side_effect=mock_broadcast):
            await tech_service._recalculate_active_jobs_eta(tech.id)

    target_event = next((ev for ev in broadcast_events if ev[1].get("job_id") == str(job.id)), None)
    assert target_event is not None
    event_name, event_data = target_event
    assert event_name == EVENT_ETA_UPDATED
    assert event_data["job_id"] == str(job.id)

    # Validate data_sources in WebSocket payload
    ds_list = event_data.get("data_sources", [])
    events_ds = next((ds for ds in ds_list if ds.get("category") == "EVENTS"), None)
    assert events_ds is not None
    assert events_ds["status"] == "AVAILABLE"
    assert events_ds["provenance"] == "REAL"
    assert events_ds["impact_minutes"] == 10
    assert events_ds["active_event_name"] == "Oracle Park Baseball Championship"
    assert events_ds["event_id"] == "EVT-STADIUM-WS"

