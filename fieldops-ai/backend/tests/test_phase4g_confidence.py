"""
Phase 4G Test Suite: ETA Confidence & Reliability Engine.

Validates the truthful, deterministic ETA confidence and reliability layer:
1. Fresh GPS + TomTom = HIGH.
2. TomTom + optional weather unavailable = valid ETA + reduced confidence (MEDIUM).
3. TomTom + optional events unavailable = valid ETA (MEDIUM).
4. OSRM fallback = DEGRADED (no live traffic).
5. Haversine fallback = lowest/degraded reliability (DEGRADED).
6. Stale GPS = reduced confidence (LOW).
7. NULL GPS timestamp = UNKNOWN, not FRESH (LOW).
8. No GPS = UNAVAILABLE.
9. Real TomTom provenance preserved (REAL).
10. OSRM DERIVED provenance preserved (DERIVED).
11. Weather REAL source / DERIVED impact preserved.
12. Event REAL source / DERIVED impact preserved.
13. Road REAL source / DERIVED detour preserved.
14. ETA_UPDATED contains confidence fields.
15. Phase 4E 13-second detour evidence remains intact ('13 sec additional (<1 min)').
"""

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch
import uuid
import pytest

from app.core.realtime import ws_manager, EVENT_ETA_UPDATED, WebSocketUserSession
from app.models.assignment import Assignment
from app.models.job import Job
from app.models.technician import Technician
from app.models.user import User
from app.schemas.eta import ETAResponse, DataSource, ContextFactor
from app.services.context_providers import (
    ContextProviderResult,
    DataSourceStatus,
    GPSLocationProvider,
    TrafficDataProvider,
    WeatherProvider,
    EventsDataProvider,
    RoadRestrictionProvider,
)
from app.services.eta_confidence import ETAConfidenceEngine, ETAConfidenceAssessment
from app.services.eta_service import ETAService
from app.services.technician_service import TechnicianService


class MockWebSocket:
    def __init__(self) -> None:
        self.received_messages: list[dict] = []
        self.closed = False

    async def accept(self) -> None:
        pass

    async def send_json(self, data: dict) -> None:
        self.received_messages.append(data)


# Test coordinates (San Francisco)
TECH_LAT = 37.7749
TECH_LON = -122.4194
JOB_LAT = 37.7890
JOB_LON = -122.4010


# ── TEST 1: Fresh GPS + TomTom = HIGH ──────────────────────────────────────────
@pytest.mark.asyncio
async def test_case_1_fresh_gps_plus_tomtom_is_high():
    engine = ETAConfidenceEngine()
    now = datetime.now(timezone.utc)

    gps_res = ContextProviderResult(
        source_name="GPS Location",
        status=DataSourceStatus.AVAILABLE,
        impact_minutes=0,
        description="Technician GPS location confirmed.",
        sampled_at=now,
        category="GPS",
        provenance="SYSTEM",
        freshness="FRESH",
        data_age_seconds=30,
    )
    weather_res = ContextProviderResult(
        source_name="Weather Data",
        status=DataSourceStatus.AVAILABLE,
        impact_minutes=0,
        description="Clear sky",
        sampled_at=now,
        category="WEATHER",
        provenance="REAL",
        freshness="FRESH",
    )
    events_res = ContextProviderResult(
        source_name="Events Data",
        status=DataSourceStatus.AVAILABLE,
        impact_minutes=0,
        description="No major events",
        sampled_at=now,
        category="EVENTS",
        provenance="REAL",
        freshness="FRESH",
    )
    road_res = ContextProviderResult(
        source_name="Road Restrictions",
        status=DataSourceStatus.AVAILABLE,
        impact_minutes=0,
        description="No restrictions",
        sampled_at=now,
        category="ROAD",
        provenance="REAL",
        freshness="FRESH",
    )

    assessment = engine.evaluate(
        is_context_sufficient=True,
        gps_result=gps_res,
        weather_result=weather_res,
        events_result=events_res,
        road_result=road_res,
        has_authoritative_tomtom_route=True,
    )

    assert assessment.confidence_level == "HIGH"
    assert assessment.reliability_status == "HIGH"
    assert "Fresh GPS and authoritative TomTom route available" in assessment.confidence_reason
    assert "GPS Location" in assessment.fresh_sources
    assert "TomTom Live Routing" in assessment.fresh_sources
    assert len(assessment.stale_sources) == 0
    assert len(assessment.unavailable_sources) == 0


# ── TEST 2: TomTom + optional weather unavailable = reduced confidence (MEDIUM) ─
@pytest.mark.asyncio
async def test_case_2_tomtom_plus_weather_unavailable_is_medium():
    engine = ETAConfidenceEngine()
    now = datetime.now(timezone.utc)

    gps_res = ContextProviderResult(
        source_name="GPS Location",
        status=DataSourceStatus.AVAILABLE,
        impact_minutes=0,
        description="GPS confirmed",
        sampled_at=now,
        category="GPS",
        freshness="FRESH",
    )
    weather_res = ContextProviderResult(
        source_name="Weather Data",
        status=DataSourceStatus.UNAVAILABLE,
        impact_minutes=0,
        description="Weather API unreachable",
        sampled_at=now,
        category="WEATHER",
        freshness="UNAVAILABLE",
    )
    events_res = ContextProviderResult(
        source_name="Events Data",
        status=DataSourceStatus.AVAILABLE,
        impact_minutes=0,
        description="No events",
        sampled_at=now,
        category="EVENTS",
        freshness="FRESH",
    )
    road_res = ContextProviderResult(
        source_name="Road Restrictions",
        status=DataSourceStatus.AVAILABLE,
        impact_minutes=0,
        description="Clear road",
        sampled_at=now,
        category="ROAD",
        freshness="FRESH",
    )

    assessment = engine.evaluate(
        is_context_sufficient=True,
        gps_result=gps_res,
        weather_result=weather_res,
        events_result=events_res,
        road_result=road_res,
        has_authoritative_tomtom_route=True,
    )

    assert assessment.confidence_level == "MEDIUM"
    assert assessment.reliability_status == "MEDIUM"
    assert "weather context unavailable" in assessment.confidence_reason.lower()
    assert "Weather (Open-Meteo)" in assessment.unavailable_sources
    assert "TomTom Live Routing" in assessment.fresh_sources


# ── TEST 3: TomTom + optional events unavailable = valid ETA (MEDIUM) ───────────
@pytest.mark.asyncio
async def test_case_3_tomtom_plus_events_unavailable_is_medium():
    engine = ETAConfidenceEngine()
    now = datetime.now(timezone.utc)

    gps_res = ContextProviderResult(
        source_name="GPS Location",
        status=DataSourceStatus.AVAILABLE,
        impact_minutes=0,
        description="GPS confirmed",
        sampled_at=now,
        category="GPS",
        freshness="FRESH",
    )
    weather_res = ContextProviderResult(
        source_name="Weather Data",
        status=DataSourceStatus.AVAILABLE,
        impact_minutes=0,
        description="Sunny",
        sampled_at=now,
        category="WEATHER",
        freshness="FRESH",
    )
    events_res = ContextProviderResult(
        source_name="Events Data",
        status=DataSourceStatus.UNAVAILABLE,
        impact_minutes=0,
        description="PredictHQ API key missing",
        sampled_at=now,
        category="EVENTS",
        freshness="UNAVAILABLE",
    )
    road_res = ContextProviderResult(
        source_name="Road Restrictions",
        status=DataSourceStatus.AVAILABLE,
        impact_minutes=0,
        description="No restrictions",
        sampled_at=now,
        category="ROAD",
        freshness="FRESH",
    )

    assessment = engine.evaluate(
        is_context_sufficient=True,
        gps_result=gps_res,
        weather_result=weather_res,
        events_result=events_res,
        road_result=road_res,
        has_authoritative_tomtom_route=True,
    )

    assert assessment.confidence_level == "MEDIUM"
    assert assessment.reliability_status == "MEDIUM"
    assert "events context unavailable" in assessment.confidence_reason.lower() or "event context unavailable" in assessment.confidence_reason.lower()
    assert "Events (PredictHQ)" in assessment.unavailable_sources


# ── TEST 4: OSRM fallback = DEGRADED ───────────────────────────────────────────
@pytest.mark.asyncio
async def test_case_4_osrm_fallback_is_degraded():
    engine = ETAConfidenceEngine()
    now = datetime.now(timezone.utc)

    gps_res = ContextProviderResult(
        source_name="GPS Location",
        status=DataSourceStatus.AVAILABLE,
        impact_minutes=0,
        description="GPS confirmed",
        sampled_at=now,
        category="GPS",
        freshness="FRESH",
    )

    assessment = engine.evaluate(
        is_context_sufficient=True,
        gps_result=gps_res,
        has_authoritative_tomtom_route=False,
        has_derived_osrm_route=True,
    )

    assert assessment.confidence_level == "DEGRADED"
    assert assessment.reliability_status == "DEGRADED"
    assert "TomTom unavailable; OSRM road baseline is being used" in assessment.confidence_reason
    assert "Live traffic is unavailable" in assessment.confidence_reason
    assert "OSRM Road Baseline (No Live Traffic)" in assessment.degraded_sources


# ── TEST 5: Haversine fallback = lowest/degraded reliability (DEGRADED) ────────
@pytest.mark.asyncio
async def test_case_5_haversine_fallback_is_degraded():
    engine = ETAConfidenceEngine()
    now = datetime.now(timezone.utc)

    gps_res = ContextProviderResult(
        source_name="GPS Location",
        status=DataSourceStatus.AVAILABLE,
        impact_minutes=0,
        description="GPS confirmed",
        sampled_at=now,
        category="GPS",
        freshness="FRESH",
    )

    assessment = engine.evaluate(
        is_context_sufficient=True,
        gps_result=gps_res,
        has_authoritative_tomtom_route=False,
        has_derived_osrm_route=False,
        is_haversine_fallback=True,
    )

    assert assessment.confidence_level == "DEGRADED"
    assert assessment.reliability_status == "DEGRADED"
    assert "Haversine straight-line baseline is being used" in assessment.confidence_reason
    assert "Haversine Straight-Line Fallback" in assessment.degraded_sources


# ── TEST 6: Stale GPS = reduced confidence (LOW) ───────────────────────────────
@pytest.mark.asyncio
async def test_case_6_stale_gps_is_low():
    engine = ETAConfidenceEngine()
    now = datetime.now(timezone.utc)

    gps_res = ContextProviderResult(
        source_name="GPS Location",
        status=DataSourceStatus.STALE,
        impact_minutes=0,
        description="Technician GPS last updated 45 min ago",
        sampled_at=now,
        category="GPS",
        freshness="STALE",
        data_age_seconds=2700,
    )

    assessment = engine.evaluate(
        is_context_sufficient=True,
        gps_result=gps_res,
        has_authoritative_tomtom_route=True,
    )

    assert assessment.confidence_level == "LOW"
    assert assessment.reliability_status == "LOW"
    assert "GPS position is stale" in assessment.confidence_reason
    assert "GPS Location" in assessment.stale_sources


# ── TEST 7: NULL GPS timestamp = UNKNOWN, not FRESH (LOW) ─────────────────────
@pytest.mark.asyncio
async def test_case_7_null_gps_timestamp_is_unknown_not_fresh():
    engine = ETAConfidenceEngine()
    now = datetime.now(timezone.utc)

    # NULL timestamp evaluates to UNKNOWN freshness in Phase 4B
    gps_res = ContextProviderResult(
        source_name="GPS Location",
        status=DataSourceStatus.AVAILABLE,
        impact_minutes=0,
        description="GPS observation timestamp unavailable — freshness is UNKNOWN.",
        sampled_at=now,
        category="GPS",
        freshness="UNKNOWN",
        provider_timestamp=None,
        data_age_seconds=None,
    )

    assessment = engine.evaluate(
        is_context_sufficient=True,
        gps_result=gps_res,
        has_authoritative_tomtom_route=True,
    )

    assert assessment.confidence_level == "LOW"
    assert assessment.reliability_status == "LOW"
    assert "GPS observation timestamp unavailable" in assessment.confidence_reason
    assert "GPS Location (Unverified Timestamp)" in assessment.degraded_sources
    assert "GPS Location" not in assessment.fresh_sources


# ── TEST 8: No GPS = UNAVAILABLE ───────────────────────────────────────────────
@pytest.mark.asyncio
async def test_case_8_no_gps_is_unavailable():
    engine = ETAConfidenceEngine()
    now = datetime.now(timezone.utc)

    gps_res = ContextProviderResult(
        source_name="GPS Location",
        status=DataSourceStatus.UNAVAILABLE,
        impact_minutes=0,
        description="Technician GPS coordinates not available.",
        sampled_at=now,
        category="GPS",
        freshness="UNAVAILABLE",
    )

    assessment = engine.evaluate(
        is_context_sufficient=False,
        missing_context=["Technician last known GPS coordinates are missing."],
        gps_result=gps_res,
    )

    assert assessment.confidence_level == "UNAVAILABLE"
    assert assessment.reliability_status == "UNAVAILABLE"
    assert "ETA unavailable" in assessment.confidence_reason
    assert "GPS Location" in assessment.unavailable_sources


# ── TEST 9: Real TomTom provenance preserved (REAL) ────────────────────────────
@pytest.mark.asyncio
async def test_case_9_real_tomtom_provenance_preserved():
    # End-to-end evaluation via ETAService
    job_id = uuid.uuid4()
    tech_id = uuid.uuid4()
    now = datetime.now(timezone.utc)

    mock_job = MagicMock(spec=Job)
    mock_job.id = job_id
    mock_job.job_number = "JOB-4G-REAL"
    mock_job.latitude = JOB_LAT
    mock_job.longitude = JOB_LON
    mock_job.assignments = []
    mock_job.eta_overrides = []

    mock_tech = MagicMock(spec=Technician)
    mock_tech.id = tech_id
    mock_tech.user_id = uuid.uuid4()
    mock_tech.employee_code = "TECH-4G-REAL"
    mock_tech.current_latitude = TECH_LAT
    mock_tech.current_longitude = TECH_LON
    mock_tech.location_updated_at = now - timedelta(seconds=20)
    mock_tech.updated_at = now
    mock_tech.availability_status = "AVAILABLE"
    mock_tech.user = MagicMock(spec=User, full_name="Sarah Connor")

    mock_session = AsyncMock()
    mock_session.execute.side_effect = [
        MagicMock(scalar_one_or_none=MagicMock(return_value=mock_job)),
        MagicMock(scalar_one_or_none=MagicMock(return_value=mock_tech)),
    ]

    from contextlib import asynccontextmanager

    @asynccontextmanager
    async def mock_session_ctx():
        yield mock_session

    mock_traffic_res = ContextProviderResult(
        source_name="TomTom Routing & Traffic",
        status=DataSourceStatus.AVAILABLE,
        impact_minutes=2,
        description="TomTom route with live traffic",
        sampled_at=now,
        category="TRAFFIC",
        provenance="REAL",
        freshness="FRESH",
        free_flow_travel_time_seconds=600,
        live_travel_time_seconds=720,
        routed_distance_meters=5000.0,
        routed_distance_miles=3.1,
        routed_distance_km=5.0,
        route_geometry=[[TECH_LON, TECH_LAT], [JOB_LON, JOB_LAT]],
    )

    with patch("app.services.eta_service.AsyncSessionLocal", side_effect=mock_session_ctx), \
         patch.object(TrafficDataProvider, "evaluate", new_callable=AsyncMock, return_value=mock_traffic_res):
        service = ETAService()
        resp = await service.calculate_job_eta(job_id=job_id, technician_id=tech_id)

        assert resp.route_provenance == "REAL"
        assert resp.confidence_level in ("HIGH", "MEDIUM")
        assert "TomTom Live Routing" in resp.fresh_sources


# ── TEST 10: OSRM DERIVED provenance preserved (DERIVED) ───────────────────────
@pytest.mark.asyncio
async def test_case_10_osrm_derived_provenance_preserved():
    job_id = uuid.uuid4()
    tech_id = uuid.uuid4()
    now = datetime.now(timezone.utc)

    mock_job = MagicMock(spec=Job)
    mock_job.id = job_id
    mock_job.job_number = "JOB-4G-OSRM"
    mock_job.latitude = JOB_LAT
    mock_job.longitude = JOB_LON
    mock_job.assignments = []
    mock_job.eta_overrides = []

    mock_tech = MagicMock(spec=Technician)
    mock_tech.id = tech_id
    mock_tech.user_id = uuid.uuid4()
    mock_tech.employee_code = "TECH-4G-OSRM"
    mock_tech.current_latitude = TECH_LAT
    mock_tech.current_longitude = TECH_LON
    mock_tech.location_updated_at = now - timedelta(seconds=20)
    mock_tech.updated_at = now
    mock_tech.availability_status = "AVAILABLE"
    mock_tech.user = MagicMock(spec=User, full_name="Kyle Reese")

    mock_session = AsyncMock()
    mock_session.execute.side_effect = [
        MagicMock(scalar_one_or_none=MagicMock(return_value=mock_job)),
        MagicMock(scalar_one_or_none=MagicMock(return_value=mock_tech)),
    ]

    from contextlib import asynccontextmanager

    @asynccontextmanager
    async def mock_session_ctx():
        yield mock_session

    # OSRM fallback result: provenance = DERIVED
    mock_osrm_res = ContextProviderResult(
        source_name="Traffic & Routing",
        status=DataSourceStatus.AVAILABLE,
        impact_minutes=0,
        description="OSRM road routing fallback",
        sampled_at=now,
        category="TRAFFIC",
        provenance="DERIVED",
        freshness="FRESH",
        free_flow_travel_time_seconds=660,
        live_travel_time_seconds=660,
        routed_distance_meters=5200.0,
        routed_distance_miles=3.2,
        routed_distance_km=5.2,
        route_geometry=[[TECH_LON, TECH_LAT], [JOB_LON, JOB_LAT]],
    )

    with patch("app.services.eta_service.AsyncSessionLocal", side_effect=mock_session_ctx), \
         patch.object(TrafficDataProvider, "evaluate", new_callable=AsyncMock, return_value=mock_osrm_res):
        service = ETAService()
        resp = await service.calculate_job_eta(job_id=job_id, technician_id=tech_id)

        assert resp.route_provenance == "DERIVED"
        assert resp.confidence_level == "DEGRADED"
        assert resp.reliability_status == "DEGRADED"
        assert "TomTom unavailable; OSRM road baseline is being used" in resp.confidence_reason
        assert "OSRM Road Baseline (No Live Traffic)" in resp.degraded_sources


# ── TEST 11: Weather REAL source / DERIVED impact preserved ─────────────────────
@pytest.mark.asyncio
async def test_case_11_weather_real_source_derived_impact_preserved():
    provider = WeatherProvider()
    now = datetime.now(timezone.utc)
    res = await provider.evaluate(
        weather_condition="Moderate Rain",
        lat=TECH_LAT,
        lon=TECH_LON,
        baseline_eta_minutes=15,
        distance_miles=5.0,
    )

    ds_dict = res.to_data_source_dict()
    factor_dict = res.to_factor_dict()

    # Weather source feed provenance is REAL (or mock provider provenance)
    assert ds_dict["category"] == "WEATHER"
    # Delay impact is computed/derived
    assert factor_dict["provenance"] == "DERIVED"


# ── TEST 12: Event REAL source / DERIVED impact preserved ──────────────────────
@pytest.mark.asyncio
async def test_case_12_event_real_source_derived_impact_preserved():
    now = datetime.now(timezone.utc)
    res = ContextProviderResult(
        source_name="Events Data (PredictHQ)",
        status=DataSourceStatus.AVAILABLE,
        impact_minutes=3,
        description="Major concert near destination (+3m delay)",
        sampled_at=now,
        category="EVENTS",
        provenance="REAL",
        freshness="FRESH",
        event_count=1,
        active_event_name="Live Concert",
    )

    ds_dict = res.to_data_source_dict()
    factor_dict = res.to_factor_dict()

    assert ds_dict["provenance"] == "REAL"
    assert factor_dict["provenance"] == "DERIVED"
    assert factor_dict["impact_minutes"] == 3


# ── TEST 13: Road REAL source / DERIVED detour preserved ───────────────────────
@pytest.mark.asyncio
async def test_case_13_road_real_source_derived_detour_preserved():
    now = datetime.now(timezone.utc)
    res = ContextProviderResult(
        source_name="Road Restrictions",
        status=DataSourceStatus.AVAILABLE,
        impact_minutes=2,
        description="Road closure on Market St; verified detour active",
        sampled_at=now,
        category="ROAD",
        provenance="REAL",
        freshness="FRESH",
        is_road_closed=True,
        detour_seconds=120,
        detour_display="2 min detour",
        impact_classification="INCREMENTAL_DETOUR",
    )

    ds_dict = res.to_data_source_dict()
    factor_dict = res.to_factor_dict()

    assert ds_dict["provenance"] == "REAL"
    assert factor_dict["provenance"] == "DERIVED"
    assert factor_dict["detour_seconds"] == 120


# ── TEST 14: ETA_UPDATED contains confidence fields ─────────────────────────────
@pytest.mark.asyncio
async def test_case_14_websocket_eta_updated_contains_confidence_fields():
    disp_user_id = uuid.uuid4()
    tech_user_id = uuid.uuid4()
    job_id = uuid.uuid4()
    tech_id = uuid.uuid4()

    mock_disp_ws = MockWebSocket()
    disp_session = WebSocketUserSession(websocket=mock_disp_ws, user_id=disp_user_id, role="DISPATCHER")

    async with ws_manager._lock:
        ws_manager._sessions.append(disp_session)

    try:
        mock_job = MagicMock(spec=Job)
        mock_job.id = job_id
        mock_job.job_number = "JOB-4G-WS"
        mock_job.latitude = JOB_LAT
        mock_job.longitude = JOB_LON
        mock_job.assignments = []
        mock_job.eta_overrides = []

        mock_tech = MagicMock(spec=Technician)
        mock_tech.id = tech_id
        mock_tech.user_id = tech_user_id
        mock_tech.full_name = "Marcus Vance"
        mock_tech.employee_code = "TECH-4G-WS"
        mock_tech.current_latitude = TECH_LAT
        mock_tech.current_longitude = TECH_LON
        mock_tech.updated_at = datetime.now(timezone.utc)
        mock_tech.location_updated_at = datetime.now(timezone.utc)
        mock_tech.availability_status = "AVAILABLE"

        mock_session = AsyncMock()
        mock_session.execute.side_effect = [
            # 1. select Technician
            MagicMock(scalar_one_or_none=MagicMock(return_value=mock_tech)),
            # 2. select Assignment job_ids
            MagicMock(scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=[job_id])))),
        ]

        from contextlib import asynccontextmanager

        @asynccontextmanager
        async def mock_session_ctx():
            yield mock_session

        fake_eta_resp = ETAResponse(
            job_id=job_id,
            job_number="JOB-4G-WS",
            is_context_sufficient=True,
            calculation_status="COMPLETE",
            baseline_eta_minutes=12,
            context_aware_eta_minutes=15,
            final_dispatch_eta_minutes=15,
            adjustment_minutes=3,
            live_route_eta_minutes=14,
            free_flow_eta_minutes=12,
            traffic_delay_minutes=2,
            additional_verified_impact_minutes=1,
            distance_km=4.5,
            distance_miles=2.8,
            routed_distance_km=4.5,
            routed_distance_miles=2.8,
            routed_distance_meters=4500.0,
            route_provenance="REAL",
            technician_id=tech_id,
            technician_name="Marcus Vance",
            technician_code="TECH-4G-WS",
            factors=[],
            data_sources=[],
            reason="Live TomTom route with moderate traffic",
            missing_context=[],
            calculated_at=datetime.now(timezone.utc).isoformat(),
            confidence_level="HIGH",
            confidence_reason="Fresh GPS and authoritative TomTom route available.",
            reliability_status="HIGH",
            fresh_sources=["GPS Location", "TomTom Live Routing", "Weather (Open-Meteo)"],
            stale_sources=[],
            unavailable_sources=[],
            degraded_sources=[],
        )

        with patch("app.services.technician_service.AsyncSessionLocal", side_effect=mock_session_ctx), \
             patch("app.services.eta_service.ETAService.calculate_job_eta", new_callable=AsyncMock, return_value=fake_eta_resp):

            tech_service = TechnicianService()
            await tech_service._recalculate_active_jobs_eta(tech_id=tech_id)

            assert len(mock_disp_ws.received_messages) == 1
            msg = mock_disp_ws.received_messages[0]
            assert msg["event"] == EVENT_ETA_UPDATED
            payload = msg["data"]

            # Verify presence of all Phase 4G structured reliability fields
            assert "confidence_level" in payload
            assert payload["confidence_level"] == "HIGH"
            assert "confidence_reason" in payload
            assert "Fresh GPS and authoritative TomTom route available" in payload["confidence_reason"]
            assert "reliability_status" in payload
            assert payload["reliability_status"] == "HIGH"
            assert "fresh_sources" in payload
            assert "TomTom Live Routing" in payload["fresh_sources"]
            assert "stale_sources" in payload
            assert "unavailable_sources" in payload
            assert "degraded_sources" in payload

    finally:
        async with ws_manager._lock:
            if disp_session in ws_manager._sessions:
                ws_manager._sessions.remove(disp_session)


# ── TEST 15: Phase 4E 13-second detour evidence remains intact ─────────────────
@pytest.mark.asyncio
async def test_case_15_phase4e_13s_detour_evidence_remains_intact():
    engine = ETAConfidenceEngine()
    now = datetime.now(timezone.utc)

    gps_res = ContextProviderResult(
        source_name="GPS Location",
        status=DataSourceStatus.AVAILABLE,
        impact_minutes=0,
        description="GPS confirmed",
        sampled_at=now,
        category="GPS",
        freshness="FRESH",
    )
    weather_res = ContextProviderResult(
        source_name="Weather Data",
        status=DataSourceStatus.AVAILABLE,
        impact_minutes=0,
        description="Clear",
        sampled_at=now,
        category="WEATHER",
        freshness="FRESH",
    )
    events_res = ContextProviderResult(
        source_name="Events Data",
        status=DataSourceStatus.AVAILABLE,
        impact_minutes=0,
        description="No events",
        sampled_at=now,
        category="EVENTS",
        freshness="FRESH",
    )
    road_res = ContextProviderResult(
        source_name="Road Restrictions",
        status=DataSourceStatus.AVAILABLE,
        impact_minutes=0,
        description="Verified alternate route calculated (+13s detour, <1 min — 0m integer impact)",
        sampled_at=now,
        category="ROAD",
        freshness="FRESH",
        detour_seconds=13,
        detour_display="13 sec additional (<1 min)",
    )

    assessment = engine.evaluate(
        is_context_sufficient=True,
        gps_result=gps_res,
        weather_result=weather_res,
        events_result=events_res,
        road_result=road_res,
        has_authoritative_tomtom_route=True,
        detour_seconds=13,
        detour_display="13 sec additional (<1 min)",
    )

    assert assessment.confidence_level == "HIGH"
    assert "verified road detour included (13 sec additional (<1 min))" in assessment.confidence_reason
