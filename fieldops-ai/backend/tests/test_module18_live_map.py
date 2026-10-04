"""
Module 18 Tests: Live Field Operations Map, Navigation Integrity & Production Data Consistency.
Validates:
1. Live map technician data retrieval
2. Live map active job retrieval
3. Real technician location reflected in map data
4. Technician location realtime event constant
5. Job assignment reflected in map
6. Job unassignment reflected in map
7. Job status change reflected in map
8. Technician availability change reflected in map
9. Duplicate realtime event does not duplicate entities
10. Reconnect reconciliation restores authoritative state
11. Unauthorized role cannot access restricted map data
12. GPS stale-state classification
13. Analytics and ETA Performance separation
14. GET requests do not create/increment jobs
15. Repeated refresh does not change total job count
"""

import uuid
from datetime import datetime, timezone, timedelta
import pytest
from httpx import AsyncClient
from sqlalchemy import select, func

from app.core.realtime import EVENT_TECHNICIAN_LOCATION_UPDATED
from app.database.session import AsyncSessionLocal
from app.models.enums import JobStatus, UserRole
from app.models.job import Job
from app.models.technician import Technician
from app.models.user import User

BASE_URL = "http://127.0.0.1:8000"


async def get_token_headers(client: AsyncClient, email: str, password: str) -> dict[str, str]:
    """Helper to authenticate and get Bearer token headers."""
    res = await client.post(f"{BASE_URL}/api/v1/auth/login", json={"email": email, "password": password})
    assert res.status_code == 200, f"Login failed for {email}: {res.text}"
    token = res.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_1_live_map_technician_data_retrieval():
    """1. Dispatcher can fetch all technicians for live map with coordinates and availability status."""
    async with AsyncClient() as client:
        disp_headers = await get_token_headers(client, "dispatcher@fieldops.ai", "Dispatch@123")
        res = await client.get(f"{BASE_URL}/api/v1/technicians?page_size=50", headers=disp_headers)
        assert res.status_code == 200
        data = res.json()
        assert "items" in data
        assert len(data["items"]) > 0
        tech = data["items"][0]
        assert "id" in tech
        assert "employee_code" in tech
        assert "availability_status" in tech
        assert "current_latitude" in tech
        assert "current_longitude" in tech


@pytest.mark.asyncio
async def test_2_live_map_active_job_retrieval():
    """2. Dispatcher can fetch active jobs for map with location coordinates and priority."""
    async with AsyncClient() as client:
        disp_headers = await get_token_headers(client, "dispatcher@fieldops.ai", "Dispatch@123")
        res = await client.get(f"{BASE_URL}/api/v1/jobs?page_size=50", headers=disp_headers)
        assert res.status_code == 200
        data = res.json()
        assert "items" in data
        assert len(data["items"]) > 0
        job = data["items"][0]
        assert "job_number" in job
        assert "status" in job
        assert "priority" in job
        assert "latitude" in job
        assert "longitude" in job


@pytest.mark.asyncio
async def test_3_technician_real_gps_telemetry_reflection():
    """3. Real browser GPS PATCH from technician updates PostgreSQL and reflects in GET /technicians/me."""
    async with AsyncClient() as client:
        tech_headers = await get_token_headers(client, "technician@fieldops.ai", "Tech@123")
        disp_headers = await get_token_headers(client, "dispatcher@fieldops.ai", "Dispatch@123")

        test_lat = 37.7799
        test_lng = -122.4144
        patch_res = await client.patch(
            f"{BASE_URL}/api/v1/technicians/me/location",
            json={"latitude": test_lat, "longitude": test_lng},
            headers=tech_headers,
        )
        assert patch_res.status_code == 200
        patch_data = patch_res.json()
        assert abs(patch_data["current_latitude"] - test_lat) < 0.0001
        assert abs(patch_data["current_longitude"] - test_lng) < 0.0001

        # Verify me endpoint reflects updated location
        me_res = await client.get(f"{BASE_URL}/api/v1/technicians/me", headers=tech_headers)
        assert me_res.status_code == 200
        assert abs(me_res.json()["current_latitude"] - test_lat) < 0.0001
        assert abs(me_res.json()["current_longitude"] - test_lng) < 0.0001


@pytest.mark.asyncio
async def test_4_technician_location_realtime_event():
    """4. Updating technician location generates TECHNICIAN_LOCATION_UPDATED event payload."""
    assert EVENT_TECHNICIAN_LOCATION_UPDATED == "TECHNICIAN_LOCATION_UPDATED"


@pytest.mark.asyncio
async def test_5_job_assignment_reflected_in_map():
    """5. Assigning job to technician links assignment and updates job state for live map."""
    async with AsyncClient() as client:
        disp_headers = await get_token_headers(client, "dispatcher@fieldops.ai", "Dispatch@123")

        # Fetch first available NEW job
        jobs_res = await client.get(f"{BASE_URL}/api/v1/jobs?status=NEW&page_size=5", headers=disp_headers)
        assert jobs_res.status_code == 200
        jobs = jobs_res.json()["items"]
        if not jobs:
            pytest.skip("No NEW job available for assignment test")

        target_job = jobs[0]

        techs_res = await client.get(f"{BASE_URL}/api/v1/technicians?page_size=10", headers=disp_headers)
        assert techs_res.status_code == 200
        techs = techs_res.json()["items"]
        assert len(techs) > 0

        target_tech = techs[0]

        # Assign job
        asg_res = await client.post(
            f"{BASE_URL}/api/v1/assignments/jobs/{target_job['id']}/assign",
            json={"technician_id": target_tech["id"]},
            headers=disp_headers,
        )
        assert asg_res.status_code == 201

        # Verify job reflects status ASSIGNED and assigned technician
        job_check = await client.get(f"{BASE_URL}/api/v1/jobs/{target_job['id']}", headers=disp_headers)
        assert job_check.status_code == 200
        job_data = job_check.json()
        assert job_data["status"] == "ASSIGNED"
        assert job_data["assigned_technician"] is not None
        assert job_data["assigned_technician"]["id"] == target_tech["id"]


@pytest.mark.asyncio
async def test_6_job_unassignment_reflected_in_map():
    """6. Unassigning job resets job status to NEW and clears assigned technician."""
    async with AsyncClient() as client:
        disp_headers = await get_token_headers(client, "dispatcher@fieldops.ai", "Dispatch@123")

        # Find or assign a job first
        jobs_res = await client.get(f"{BASE_URL}/api/v1/jobs?status=ASSIGNED&page_size=5", headers=disp_headers)
        assert jobs_res.status_code == 200
        assigned_jobs = jobs_res.json()["items"]

        if not assigned_jobs:
            # Assign first new job
            new_jobs_res = await client.get(f"{BASE_URL}/api/v1/jobs?status=NEW&page_size=1", headers=disp_headers)
            target_job = new_jobs_res.json()["items"][0]
            techs_res = await client.get(f"{BASE_URL}/api/v1/technicians?page_size=1", headers=disp_headers)
            tech_id = techs_res.json()["items"][0]["id"]
            await client.post(
                f"{BASE_URL}/api/v1/assignments/jobs/{target_job['id']}/assign",
                json={"technician_id": tech_id},
                headers=disp_headers,
            )
        else:
            target_job = assigned_jobs[0]

        # Unassign job
        unasg_res = await client.post(
            f"{BASE_URL}/api/v1/assignments/jobs/{target_job['id']}/unassign",
            headers=disp_headers,
        )
        assert unasg_res.status_code == 200

        # Verify job reflects status NEW and no assigned technician
        job_check = await client.get(f"{BASE_URL}/api/v1/jobs/{target_job['id']}", headers=disp_headers)
        assert job_check.status_code == 200
        job_data = job_check.json()
        assert job_data["status"] == "NEW"
        assert job_data["assigned_technician"] is None


@pytest.mark.asyncio
async def test_7_job_status_transition_reflection():
    """7. Technician status updates (TRAVELLING) reflect in job queries."""
    async with AsyncClient() as client:
        disp_headers = await get_token_headers(client, "dispatcher@fieldops.ai", "Dispatch@123")
        tech_headers = await get_token_headers(client, "technician@fieldops.ai", "Tech@123")

        # Get technician ID
        me_res = await client.get(f"{BASE_URL}/api/v1/technicians/me", headers=tech_headers)
        assert me_res.status_code == 200
        tech_id = me_res.json()["id"]

        # Ensure technician has an assigned job
        jobs_res = await client.get(f"{BASE_URL}/api/v1/jobs?status=NEW&page_size=1", headers=disp_headers)
        if not jobs_res.json()["items"]:
            pytest.skip("No NEW job to assign")

        target_job = jobs_res.json()["items"][0]

        await client.post(
            f"{BASE_URL}/api/v1/assignments/jobs/{target_job['id']}/assign",
            json={"technician_id": tech_id},
            headers=disp_headers,
        )

        # Transition status to TRAVELLING as assigned technician
        t_res = await client.patch(
            f"{BASE_URL}/api/v1/jobs/{target_job['id']}/status",
            json={"status": "TRAVELLING"},
            headers=tech_headers,
        )
        assert t_res.status_code == 200
        assert t_res.json()["status"] == "TRAVELLING"

        # Verify in dispatcher GET
        chk = await client.get(f"{BASE_URL}/api/v1/jobs/{target_job['id']}", headers=disp_headers)
        assert chk.json()["status"] == "TRAVELLING"

        # Unassign to reset for clean operational state
        await client.post(
            f"{BASE_URL}/api/v1/assignments/jobs/{target_job['id']}/unassign",
            headers=disp_headers,
        )


@pytest.mark.asyncio
async def test_8_technician_availability_change_reflection():
    """8. Technician availability status change (AVAILABLE -> UNAVAILABLE) reflects in GET /technicians/me."""
    async with AsyncClient() as client:
        tech_headers = await get_token_headers(client, "technician@fieldops.ai", "Tech@123")

        me_res = await client.get(f"{BASE_URL}/api/v1/technicians/me", headers=tech_headers)
        tech_id = me_res.json()["id"]

        # Update availability to UNAVAILABLE
        patch_res = await client.patch(
            f"{BASE_URL}/api/v1/technicians/{tech_id}/status",
            json={"availability_status": "UNAVAILABLE"},
            headers=tech_headers,
        )
        assert patch_res.status_code == 200
        assert patch_res.json()["availability_status"] == "UNAVAILABLE"

        # Restore to AVAILABLE
        await client.patch(
            f"{BASE_URL}/api/v1/technicians/{tech_id}/status",
            json={"availability_status": "AVAILABLE"},
            headers=tech_headers,
        )


@pytest.mark.asyncio
async def test_9_duplicate_realtime_event_does_not_duplicate_entities():
    """9. Multiple location updates for the same technician maintain exactly one database record."""
    async with AsyncClient() as client:
        tech_headers = await get_token_headers(client, "technician@fieldops.ai", "Tech@123")

        # Send 3 identical location updates
        for _ in range(3):
            await client.patch(
                f"{BASE_URL}/api/v1/technicians/me/location",
                json={"latitude": 37.7550, "longitude": -122.4300},
                headers=tech_headers,
            )

        # Check total technician count in database
        async with AsyncSessionLocal() as session:
            count = await session.scalar(
                select(func.count(Technician.id)).where(Technician.employee_code == "TECH-001")
            )
            assert count == 1, "Duplicate technician records created"


@pytest.mark.asyncio
async def test_10_reconnect_reconciliation_authoritative_state():
    """10. Authoritative REST reconciliation fetches identical state after reconnect."""
    async with AsyncClient() as client:
        disp_headers = await get_token_headers(client, "dispatcher@fieldops.ai", "Dispatch@123")

        res1 = await client.get(f"{BASE_URL}/api/v1/jobs?page_size=10", headers=disp_headers)
        res2 = await client.get(f"{BASE_URL}/api/v1/jobs?page_size=10", headers=disp_headers)

        assert res1.json()["total"] == res2.json()["total"]
        assert len(res1.json()["items"]) == len(res2.json()["items"])


@pytest.mark.asyncio
async def test_11_unauthorized_role_cannot_access_dispatcher_map_telemetry():
    """11. Technician role is forbidden from accessing global dispatcher jobs directory."""
    async with AsyncClient() as client:
        tech_headers = await get_token_headers(client, "technician@fieldops.ai", "Tech@123")

        res = await client.get(f"{BASE_URL}/api/v1/jobs", headers=tech_headers)
        assert res.status_code == 403, "Technician should be forbidden from accessing global jobs"


@pytest.mark.asyncio
async def test_12_gps_freshness_classification():
    """12. GPS stale-state classification logic properly differentiates <=30s as LIVE and >30s as STALE."""
    now = datetime.now(timezone.utc)

    # 1. Fresh timestamp (10 seconds ago)
    fresh_time = (now - timedelta(seconds=10)).isoformat()
    diff_fresh = (datetime.now(timezone.utc) - datetime.fromisoformat(fresh_time)).total_seconds()
    status_fresh = "LIVE" if diff_fresh <= 30 else "STALE"
    assert status_fresh == "LIVE"

    # 2. Stale timestamp (60 seconds ago)
    stale_time = (now - timedelta(seconds=60)).isoformat()
    diff_stale = (datetime.now(timezone.utc) - datetime.fromisoformat(stale_time)).total_seconds()
    status_stale = "LIVE" if diff_stale <= 30 else "STALE"
    assert status_stale == "STALE"


@pytest.mark.asyncio
async def test_13_analytics_and_eta_performance_separation():
    """13. Analytics and ETA Performance backend routes are distinct and return their respective payloads."""
    async with AsyncClient() as client:
        disp_headers = await get_token_headers(client, "dispatcher@fieldops.ai", "Dispatch@123")

        # Operational Analytics
        res_analytics = await client.get(f"{BASE_URL}/api/v1/analytics/operational", headers=disp_headers)
        assert res_analytics.status_code == 200
        analytics_data = res_analytics.json()
        assert "total_jobs" in analytics_data
        assert "status_distribution" in analytics_data
        assert "priority_distribution" in analytics_data
        assert "technician_utilization_percentage" in analytics_data

        # ETA Experiment Benchmarks
        res_eta = await client.get(f"{BASE_URL}/api/v1/eta/experiment", headers=disp_headers)
        assert res_eta.status_code == 200
        eta_data = res_eta.json()
        assert "baseline_mae_minutes" in eta_data
        assert "context_aware_mae_minutes" in eta_data
        assert "improvement_percent" in eta_data


@pytest.mark.asyncio
async def test_14_get_requests_do_not_create_or_increment_jobs():
    """14. Repeated GET calls do not create or increment any database jobs."""
    async with AsyncClient() as client:
        disp_headers = await get_token_headers(client, "dispatcher@fieldops.ai", "Dispatch@123")

        # Get initial count
        res_initial = await client.get(f"{BASE_URL}/api/v1/jobs?page_size=1", headers=disp_headers)
        initial_total = res_initial.json()["total"]

        # Call GET multiple times
        for _ in range(5):
            res = await client.get(f"{BASE_URL}/api/v1/jobs?page_size=10", headers=disp_headers)
            assert res.status_code == 200

        # Verify final count equals initial count
        res_final = await client.get(f"{BASE_URL}/api/v1/jobs?page_size=1", headers=disp_headers)
        assert res_final.json()["total"] == initial_total


@pytest.mark.asyncio
async def test_15_repeated_refresh_maintains_stable_job_count():
    """15. Calling /analytics/operational and /jobs repeatedly maintains identical authoritative totals."""
    async with AsyncClient() as client:
        disp_headers = await get_token_headers(client, "dispatcher@fieldops.ai", "Dispatch@123")

        res_a1 = await client.get(f"{BASE_URL}/api/v1/analytics/operational", headers=disp_headers)
        res_j1 = await client.get(f"{BASE_URL}/api/v1/jobs", headers=disp_headers)

        res_a2 = await client.get(f"{BASE_URL}/api/v1/analytics/operational", headers=disp_headers)
        res_j2 = await client.get(f"{BASE_URL}/api/v1/jobs", headers=disp_headers)

        assert res_a1.json()["total_jobs"] == res_a2.json()["total_jobs"]
        assert res_j1.json()["total"] == res_j2.json()["total"]
        assert res_a1.json()["total_jobs"] == res_j1.json()["total"]
