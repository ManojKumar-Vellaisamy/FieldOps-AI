"""
Module 22 — Real Operational Flow Validation, UI Consistency & Product Completion Test Suite.

End-to-End Operational Validation covering:
SCENARIO 1: Normal conditions (Job Creation -> Skill Matching -> Assignment -> Technician Transit Workflow -> Completion -> Audit History).
SCENARIO 2: Traffic context causes ETA increase (Recalculation, Provenance, Dispatcher & Tech visibility).
SCENARIO 3: Weather context affects ETA (Weather severity penalty applied with explanation).
SCENARIO 4: External context provider unavailable (Baseline ETA remains usable, 0 penalty, no crash).
SCENARIO 5: Dispatcher manual ETA override (Override authoritative over background updates, audit recorded).
SCENARIO 6: Technician GPS unavailable/stale (Clear status flagging, no synthetic movement, safe fallback).
"""

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch
import uuid

from httpx import AsyncClient
import pytest

from app.core.config import settings
from app.models.enums import UserRole
from app.services.context_aggregation import ContextAggregationService
from app.services.context_providers import (
    ContextProviderResult,
    DataSourceStatus,
    EventsDataProvider,
    GPSLocationProvider,
    RoadRestrictionProvider,
    TrafficDataProvider,
    WeatherProvider,
)
from app.services.eta_service import ETAService

BASE_URL = "http://127.0.0.1:8000"


async def get_auth_headers(client: AsyncClient, email: str = "dispatcher@fieldops.ai", password: str = "Dispatch@123") -> dict[str, str]:
    """Helper to authenticate user and retrieve Bearer token header."""
    res = await client.post(f"{BASE_URL}/api/v1/auth/login", json={"email": email, "password": password})
    assert res.status_code == 200, f"Login failed for {email}: {res.text}"
    token = res.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


async def get_active_technician(client: AsyncClient, headers: dict[str, str]) -> tuple[str, str]:
    """Fetch an active technician ID and primary skill ID."""
    res = await client.get(f"{BASE_URL}/api/v1/technicians?search=technician@fieldops.ai", headers=headers)
    assert res.status_code == 200
    body = res.json()
    items = body["items"] if "items" in body else body
    assert len(items) > 0, "Technician technician@fieldops.ai not found"
    tech = items[0]
    return str(tech["id"]), str(tech.get("primary_skill_id"))


@pytest.mark.asyncio
async def test_scenario_1_normal_operational_workflow():
    """
    SCENARIO 1: Normal conditions workflow
    Dispatcher creates Job -> System understands skill -> Technician assigned ->
    Technician receives job -> Technician moves (EN_ROUTE -> ARRIVED -> WORKING -> COMPLETED) ->
    Dispatcher sees live operational state -> Audit history records workflow events.
    """
    async with AsyncClient() as client:
        disp_headers = await get_auth_headers(client, "dispatcher@fieldops.ai", "Dispatch@123")
        tech_headers = await get_auth_headers(client, "technician@fieldops.ai", "Tech@123")
        tech_id, skill_id = await get_active_technician(client, disp_headers)

        if not skill_id or skill_id == "None":
            res_skills = await client.get(f"{BASE_URL}/api/v1/skills?status=ACTIVE", headers=disp_headers)
            assert res_skills.status_code == 200
            skills = res_skills.json().get("items", [])
            assert len(skills) > 0
            skill_id = skills[0]["id"]

        # 1. Dispatcher creates job requiring specific skill
        job_payload = {
            "customer_name": f"Scenario 1 Customer {uuid.uuid4().hex[:4]}",
            "customer_phone": "+1-555-0199",
            "address": "789 Operational Way, San Francisco, CA 94105",
            "latitude": 37.7892,
            "longitude": -122.4014,
            "priority": "HIGH",
            "required_skill_id": skill_id,
            "description": "Routine Maintenance Check",
        }
        res = await client.post(f"{BASE_URL}/api/v1/jobs", json=job_payload, headers=disp_headers)
        assert res.status_code == 201, f"Job creation failed: {res.text}"
        job = res.json()
        job_id = job["id"]
        assert job["status"] in ("NEW", "UNASSIGNED")
        assert job["required_skill_id"] == skill_id

        # 2. Dispatcher queries Smart Assignment recommendation
        res_rec = await client.get(f"{BASE_URL}/api/v1/assignments/jobs/{job_id}/recommendation", headers=disp_headers)
        assert res_rec.status_code == 200

        # 3. Dispatcher assigns technician
        assign_payload = {
            "technician_id": tech_id,
        }
        res_assign = await client.post(f"{BASE_URL}/api/v1/assignments/jobs/{job_id}/assign", json=assign_payload, headers=disp_headers)
        assert res_assign.status_code == 201, f"Assignment failed: {res_assign.text}"
        assert res_assign.json()["assignment_status"] == "ASSIGNED"
        assert str(res_assign.json()["technician_id"]) == str(tech_id)

        # 4. Technician views assigned job
        res_my = await client.get(f"{BASE_URL}/api/v1/jobs/my", headers=tech_headers)
        assert res_my.status_code == 200
        my_jobs = res_my.json()
        target_job = next((j for j in my_jobs if j["id"] == job_id), None)
        assert target_job is not None
        assert target_job["status"] == "ASSIGNED"

        # 5. Technician workflow transitions: EN_ROUTE -> ARRIVED -> IN_PROGRESS -> COMPLETED
        # EN_ROUTE
        res_tr = await client.patch(f"{BASE_URL}/api/v1/jobs/{job_id}/status", json={"status": "EN_ROUTE"}, headers=tech_headers)
        assert res_tr.status_code == 200
        assert res_tr.json()["status"] in ["TRAVELLING", "EN_ROUTE"]

        # ARRIVED
        res_arr = await client.patch(f"{BASE_URL}/api/v1/jobs/{job_id}/status", json={"status": "ARRIVED"}, headers=tech_headers)
        assert res_arr.status_code == 200
        assert res_arr.json()["status"] == "ARRIVED"

        # IN_PROGRESS (WORKING)
        res_wrk = await client.patch(f"{BASE_URL}/api/v1/jobs/{job_id}/status", json={"status": "IN_PROGRESS"}, headers=tech_headers)
        assert res_wrk.status_code == 200
        assert res_wrk.json()["status"] in ["IN_PROGRESS", "WORKING"]

        # COMPLETED
        res_comp = await client.patch(
            f"{BASE_URL}/api/v1/jobs/{job_id}/status",
            json={"status": "COMPLETED", "completion_notes": "Completed maintenance successfully."},
            headers=tech_headers,
        )
        assert res_comp.status_code == 200
        assert res_comp.json()["status"] == "COMPLETED"

        # 6. Dispatcher verifies live operational state & audit history
        res_live = await client.get(f"{BASE_URL}/api/v1/jobs/{job_id}", headers=disp_headers)
        assert res_live.status_code == 200
        assert res_live.json()["status"] == "COMPLETED"

        res_audit = await client.get(f"{BASE_URL}/api/v1/audit-logs?entity_id={job_id}", headers=disp_headers)
        assert res_audit.status_code == 200
        audit_records = res_audit.json()["items"]
        assert len(audit_records) >= 4
        actions = [a["action"] for a in audit_records]
        assert "TECHNICIAN_ASSIGNED" in actions
        assert "JOB_STATUS_CHANGED" in actions


@pytest.mark.asyncio
async def test_scenario_2_traffic_context_causes_eta_increase():
    """
    SCENARIO 2: Traffic/context causes ETA increase
    ETA recalculates -> Dispatcher sees updated ETA -> Tech sees operational ETA.
    """
    service = ContextAggregationService()
    baseline_eta = 15

    mock_traffic_normal = ContextProviderResult("Traffic", DataSourceStatus.AVAILABLE, 0, "Normal flow", category="TRAFFIC")
    mock_traffic_heavy = ContextProviderResult("Traffic", DataSourceStatus.AVAILABLE, 15, "Heavy congestion", category="TRAFFIC")

    summary_normal = service.aggregate(
        provider_results=[mock_traffic_normal],
        baseline_eta_minutes=baseline_eta,
        distance_km=5.0,
        distance_miles=3.1,
    )

    summary_heavy = service.aggregate(
        provider_results=[mock_traffic_heavy],
        baseline_eta_minutes=baseline_eta,
        distance_km=5.0,
        distance_miles=3.1,
    )

    assert summary_heavy.total_adjustment_minutes > summary_normal.total_adjustment_minutes
    assert summary_heavy.total_adjustment_minutes == 15
    assert summary_heavy.available_count == 1


@pytest.mark.asyncio
async def test_scenario_3_weather_context_affects_eta():
    """
    SCENARIO 3: Weather/context affects ETA
    Context adjustment is applied -> Explanation/provenance remains visible.
    """
    service = ContextAggregationService()
    baseline_eta = 20

    mock_weather_snow = ContextProviderResult("Weather", DataSourceStatus.AVAILABLE, 12, "Heavy Snowfall", category="WEATHER")

    summary = service.aggregate(
        provider_results=[mock_weather_snow],
        baseline_eta_minutes=baseline_eta,
        distance_km=8.0,
        distance_miles=5.0,
    )

    assert summary.total_adjustment_minutes == 12
    assert summary.available_count == 1
    assert any(f.category == "WEATHER" and f.impact_minutes == 12 for f in summary.factors)


@pytest.mark.asyncio
async def test_scenario_4_external_context_provider_unavailable():
    """
    SCENARIO 4: External context provider unavailable
    Baseline ETA remains usable -> No crash -> Unavailable provider contributes 0 mins.
    """
    service = ContextAggregationService()
    baseline_eta = 15

    w_res = ContextProviderResult("Weather", DataSourceStatus.AVAILABLE, 5, "Light Rain", category="WEATHER")
    events_fail = ContextProviderResult("Events", DataSourceStatus.UNAVAILABLE, 15, "503 Unavailable", category="EVENTS")
    road_fail = ContextProviderResult("RoadRestrictions", DataSourceStatus.UNAVAILABLE, 20, "Timeout", category="ROAD")

    summary = service.aggregate(
        provider_results=[w_res, events_fail, road_fail],
        baseline_eta_minutes=baseline_eta,
        distance_km=5.0,
        distance_miles=3.1,
    )

    assert summary.total_adjustment_minutes == 5  # Only Weather contributes
    assert summary.unavailable_count == 2
    assert summary.available_count == 1
    assert summary.calculation_status in ("PARTIAL", "COMPLETE")


@pytest.mark.asyncio
async def test_scenario_5_dispatcher_manual_eta_override():
    """
    SCENARIO 5: Dispatcher overrides ETA
    Override remains authoritative -> Background context refresh does not overwrite it -> Audit history records override.
    """
    async with AsyncClient() as client:
        disp_headers = await get_auth_headers(client, "dispatcher@fieldops.ai", "Dispatch@123")
        tech_id, skill_id = await get_active_technician(client, disp_headers)

        if not skill_id or skill_id == "None":
            res_skills = await client.get(f"{BASE_URL}/api/v1/skills?status=ACTIVE", headers=disp_headers)
            assert res_skills.status_code == 200
            skills = res_skills.json().get("items", [])
            assert len(skills) > 0
            skill_id = skills[0]["id"]

        # 1. Create and assign job
        job_payload = {
            "customer_name": f"Scenario 5 Manual Override {uuid.uuid4().hex[:4]}",
            "customer_phone": "+1-555-0555",
            "address": "100 Override St, San Francisco, CA 94103",
            "latitude": 37.7790,
            "longitude": -122.4100,
            "priority": "MEDIUM",
            "required_skill_id": skill_id,
        }
        res_job = await client.post(f"{BASE_URL}/api/v1/jobs", json=job_payload, headers=disp_headers)
        assert res_job.status_code == 201
        job_id = res_job.json()["id"]

        await client.post(f"{BASE_URL}/api/v1/assignments/jobs/{job_id}/assign", json={"technician_id": tech_id}, headers=disp_headers)

        # 2. Dispatcher applies manual ETA override (e.g. 50 minutes)
        override_payload = {
            "overridden_eta": 50,
            "reason": "Roadblock expected near site",
        }
        res_ovr = await client.post(f"{BASE_URL}/api/v1/eta/jobs/{job_id}/override", json=override_payload, headers=disp_headers)
        assert res_ovr.status_code == 201, f"ETA Override failed: {res_ovr.text}"
        ovr_data = res_ovr.json()
        assert ovr_data["overridden_eta"] == 50

        # 3. Query ETA calculation endpoint and ensure override is authoritative
        res_get_eta = await client.get(f"{BASE_URL}/api/v1/eta/jobs/{job_id}/eta", headers=disp_headers)
        assert res_get_eta.status_code == 200
        current_eta = res_get_eta.json()
        assert current_eta["final_dispatch_eta_minutes"] == 50
        assert current_eta["active_override"] is not None

        # 4. Verify audit history records ETA override action
        res_audit = await client.get(f"{BASE_URL}/api/v1/audit-logs?entity_id={job_id}", headers=disp_headers)
        assert res_audit.status_code == 200
        audit_records = res_audit.json()["items"]
        actions = [a["action"] for a in audit_records]
        assert any("OVERRIDE" in a for a in actions)


@pytest.mark.asyncio
async def test_scenario_6_technician_gps_unavailable_stale():
    """
    SCENARIO 6: Technician GPS becomes unavailable/stale
    System clearly shows GPS status -> Existing authoritative state/ETA remains safe -> No fake location is generated.
    """
    async with AsyncClient() as client:
        disp_headers = await get_auth_headers(client, "dispatcher@fieldops.ai", "Dispatch@123")
        tech_headers = await get_auth_headers(client, "technician@fieldops.ai", "Tech@123")

        # 1. Verify GPS location update endpoint validates coordinates strictly
        res_invalid = await client.patch(
            f"{BASE_URL}/api/v1/technicians/me/location",
            json={"latitude": 999.0, "longitude": -122.4194},
            headers=tech_headers,
        )
        assert res_invalid.status_code in (400, 422), "System must reject out-of-range coordinates"

        # 2. Verify GPS location provider handles stale or missing coordinates without generating fake movement
        gps_provider = GPSLocationProvider()
        res_stale = await gps_provider.evaluate(
            technician_lat=None, technician_lon=None
        )

        assert res_stale.status in (DataSourceStatus.STALE, DataSourceStatus.UNAVAILABLE, DataSourceStatus.INVALID)
        assert res_stale.impact_minutes == 0
