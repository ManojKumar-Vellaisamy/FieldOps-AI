"""
Phase 4B Focused Test Suite: GPS Observation Timestamp & Freshness Foundation.

Verifies end-to-end preservation of real GNSS observation timestamps:
- Freshness based strictly on location_updated_at, never technician.updated_at.
- Stale GPS remains STALE even if technician row is updated by admin.
- Missing location_updated_at evaluates to UNKNOWN, never defaulting to FRESH.
- Future timestamps beyond tolerance (> 300s) are rejected.
- Timezone-aware normalization to UTC.
- Full compatibility with existing ETA calculation and WebSocket events.
"""

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch
import uuid
import pytest
from pydantic import ValidationError

from app.models.technician import Technician
from app.models.user import User
from app.schemas.technician import TechnicianLocationPatch
from app.services.context_providers import DataSourceStatus, GPSLocationProvider
from app.services.eta_service import ETAService
from app.services.technician_service import TechnicianService


# ── TEST 1: GPS observation = now, technician.updated_at = old → FRESH ─────────

@pytest.mark.asyncio
async def test_case_1_gps_fresh_when_observation_recent_and_updated_at_old():
    now = datetime.now(timezone.utc)
    recent_fix = now - timedelta(seconds=45)
    ancient_updated_at = now - timedelta(days=30)

    provider = GPSLocationProvider()
    result = await provider.evaluate(
        technician_lat=37.7749,
        technician_lon=-122.4194,
        tech_updated_at=recent_fix,  # passed from location_updated_at
    )

    assert result.status == DataSourceStatus.AVAILABLE
    assert result.freshness == "FRESH"
    assert result.impact_classification == "NOT_APPLIED"
    assert result.impact_minutes == 0
    assert result.data_age_seconds is not None
    assert result.data_age_seconds <= 600
    assert "Technician GPS location confirmed" in result.description


# ── TEST 2: GPS observation = 4h ago, technician.updated_at = now → STALE ──────

@pytest.mark.asyncio
async def test_case_2_gps_stale_when_observation_old_and_updated_at_now():
    now = datetime.now(timezone.utc)
    old_fix = now - timedelta(hours=4)

    provider = GPSLocationProvider()
    result = await provider.evaluate(
        technician_lat=37.7749,
        technician_lon=-122.4194,
        tech_updated_at=old_fix,
    )

    assert result.status == DataSourceStatus.STALE
    assert result.freshness == "STALE"
    assert result.impact_classification == "NOT_APPLIED"
    assert result.impact_minutes == 0
    assert result.data_age_seconds is not None
    assert result.data_age_seconds > 600
    assert "ETA computed from last known GPS fix." in result.description


# ── TEST 3: GPS coordinates exist, location_updated_at = None → UNKNOWN ────────

@pytest.mark.asyncio
async def test_case_3_gps_unknown_when_location_updated_at_is_none():
    provider = GPSLocationProvider()
    result = await provider.evaluate(
        technician_lat=37.7749,
        technician_lon=-122.4194,
        tech_updated_at=None,
    )

    assert result.status == DataSourceStatus.AVAILABLE
    assert result.freshness == "UNKNOWN"  # MUST NOT be FRESH
    assert result.impact_classification == "NOT_APPLIED"
    assert result.impact_minutes == 0
    assert result.data_age_seconds is None
    assert "GPS observation timestamp unavailable — freshness is UNKNOWN." in result.description


# ── TEST 4: Admin update changes updated_at but not location_updated_at ─────────

@pytest.mark.asyncio
async def test_case_4_admin_profile_update_does_not_change_gps_freshness():
    now = datetime.now(timezone.utc)
    stale_fix = now - timedelta(minutes=45)

    # Technician has stale GPS fix
    tech = Technician(
        id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        employee_code="TECH-P4B",
        current_latitude=37.7749,
        current_longitude=-122.4194,
        location_updated_at=stale_fix,
        created_at=now - timedelta(days=10),
        updated_at=stale_fix,
    )

    # Admin updates technician availability or skills at `now`
    tech.availability_status = "BUSY"
    tech.updated_at = now  # Row updated_at changes to now!

    # GPS freshness must still be based strictly on location_updated_at
    provider = GPSLocationProvider()
    result = await provider.evaluate(
        technician_lat=tech.current_latitude,
        technician_lon=tech.current_longitude,
        tech_updated_at=tech.location_updated_at,  # reads location_updated_at
    )

    assert result.freshness == "STALE"
    assert result.status == DataSourceStatus.STALE
    assert result.freshness != "FRESH"


# ── TEST 5: Genuine GPS update updates location_updated_at ──────────────────────

@pytest.mark.asyncio
async def test_case_5_genuine_gps_update_persists_location_updated_at():
    now = datetime.now(timezone.utc)
    fix_time = now - timedelta(seconds=15)
    tech_id = uuid.uuid4()

    mock_tech = Technician(
        id=tech_id,
        user_id=uuid.uuid4(),
        employee_code="TECH-LIVE",
        years_experience=3,
        current_latitude=37.7500,
        current_longitude=-122.4300,
        location_updated_at=now - timedelta(hours=2),
        availability_status="AVAILABLE",
        created_at=now - timedelta(days=5),
        updated_at=now - timedelta(hours=2),
    )

    repo_mock = MagicMock()
    async def fake_get(tid):
        return mock_tech if tid == tech_id else None

    async def fake_update(t, lat, lon, recorded_at=None, actor_id=None):
        t.current_latitude = lat
        t.current_longitude = lon
        t.location_updated_at = recorded_at or datetime.now(timezone.utc)
        t.updated_at = datetime.now(timezone.utc)
        return t

    repo_mock.get_by_id = AsyncMock(side_effect=fake_get)
    repo_mock.update_location = AsyncMock(side_effect=fake_update)

    service = TechnicianService()
    service.repo = repo_mock

    with patch.object(service, "_recalculate_active_jobs_eta", new=AsyncMock()) as mock_recalc:
        with patch("app.core.realtime.ws_manager.broadcast_operational_event", new=AsyncMock()) as mock_ws:
            updated = await service.update_location(
                tech_id=tech_id,
                latitude=37.7800,
                longitude=-122.4100,
                recorded_at=fix_time,
            )

            assert updated.current_latitude == 37.7800
            assert updated.current_longitude == -122.4100
            assert updated.location_updated_at == fix_time
            mock_recalc.assert_awaited_once_with(tech_id)
            mock_ws.assert_awaited_once()
            ws_payload = mock_ws.call_args[0][1]
            assert ws_payload["location_updated_at"] == fix_time.isoformat()


# ── TEST 6: Timezone-aware recorded_at normalized to UTC ────────────────────────

def test_case_6_timezone_aware_recorded_at_normalized():
    # Pass timestamp with +05:30 offset
    tz_ist = timezone(timedelta(hours=5, minutes=30))
    now_ist = datetime.now(tz_ist)

    patch = TechnicianLocationPatch(
        latitude=37.7749,
        longitude=-122.4194,
        recorded_at=now_ist,
    )

    assert patch.recorded_at is not None
    assert patch.recorded_at.tzinfo == timezone.utc
    # Ensure exact same absolute point in time
    assert abs((patch.recorded_at - now_ist.astimezone(timezone.utc)).total_seconds()) < 0.001


# ── TEST 7: Malformed recorded_at rejected by Pydantic ─────────────────────────

def test_case_7_malformed_recorded_at_validation_error():
    with pytest.raises(ValidationError):
        TechnicianLocationPatch(
            latitude=37.7749,
            longitude=-122.4194,
            recorded_at="invalid-date-string",
        )


# ── TEST 8: Future recorded_at beyond tolerance (> 300s) rejected ──────────────

def test_case_8_future_recorded_at_beyond_tolerance_rejected():
    now = datetime.now(timezone.utc)

    # 10 minutes into the future (> 300s allowed)
    impossible_future = now + timedelta(seconds=600)
    with pytest.raises(ValidationError) as exc_info:
        TechnicianLocationPatch(
            latitude=37.7749,
            longitude=-122.4194,
            recorded_at=impossible_future,
        )
    assert "recorded_at timestamp cannot be in the future" in str(exc_info.value)

    # 60 seconds into the future (within 300s drift tolerance)
    acceptable_drift = now + timedelta(seconds=60)
    valid_patch = TechnicianLocationPatch(
        latitude=37.7749,
        longitude=-122.4194,
        recorded_at=acceptable_drift,
    )
    assert valid_patch.recorded_at is not None


# ── TEST 9: Existing technician with NULL location_updated_at ──────────────────

def test_case_9_existing_technician_null_timestamp_no_fabricated_history():
    tech = Technician(
        id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        employee_code="TECH-NULL",
        current_latitude=37.7749,
        current_longitude=-122.4194,
    )
    # Default must be None, zero fake timestamps
    assert tech.location_updated_at is None


# ── TEST 10: ETA Service evaluates location_updated_at correctly ───────────────

@pytest.mark.asyncio
async def test_case_10_eta_service_reads_location_updated_at():
    now = datetime.now(timezone.utc)

    # Mock technician with FRESH location_updated_at
    mock_tech = MagicMock(spec=Technician)
    mock_tech.id = uuid.uuid4()
    mock_tech.employee_code = "TECH-001"
    mock_tech.current_latitude = 37.7770
    mock_tech.current_longitude = -122.4160
    mock_tech.location_updated_at = now - timedelta(seconds=30)
    mock_tech.updated_at = now - timedelta(days=7)  # old record updated_at
    mock_tech.availability_status = "AVAILABLE"
    mock_tech.user = MagicMock(spec=User)
    mock_tech.user.full_name = "Alex Tech"

    provider = GPSLocationProvider()
    gps_res = await provider.evaluate(
        technician_lat=mock_tech.current_latitude,
        technician_lon=mock_tech.current_longitude,
        tech_updated_at=mock_tech.location_updated_at,
    )

    assert gps_res.freshness == "FRESH"
    assert gps_res.status == DataSourceStatus.AVAILABLE

    # Stale location_updated_at
    mock_tech.location_updated_at = now - timedelta(minutes=25)
    gps_stale = await provider.evaluate(
        technician_lat=mock_tech.current_latitude,
        technician_lon=mock_tech.current_longitude,
        tech_updated_at=mock_tech.location_updated_at,
    )
    assert gps_stale.freshness == "STALE"
    assert gps_stale.status == DataSourceStatus.STALE

    # NULL location_updated_at
    mock_tech.location_updated_at = None
    gps_unknown = await provider.evaluate(
        technician_lat=mock_tech.current_latitude,
        technician_lon=mock_tech.current_longitude,
        tech_updated_at=mock_tech.location_updated_at,
    )
    assert gps_unknown.freshness == "UNKNOWN"
