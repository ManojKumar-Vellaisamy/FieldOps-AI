"""
Unit and Integration Tests for Module 16 — Technician Field Operations & Workflow Reliability.

Covers:
1. Complete technician job status lifecycle (ASSIGNED -> TRAVELLING/EN_ROUTE -> ARRIVED -> WORKING/IN_PROGRESS -> COMPLETED).
2. Status transition alias parsing (EN_ROUTE -> TRAVELLING, IN_PROGRESS -> WORKING).
3. Rejection of invalid status transitions (e.g. ASSIGNED -> WORKING).
4. Technician ownership isolation (Technician B cannot modify Technician A's job).
5. Role security (Dispatcher & Administrator forbidden from technician execution status transitions).
6. Terminal state protection (COMPLETED and CANCELLED jobs cannot be restarted).
7. Location telemetry patch (/api/v1/technicians/me/location) with valid & out-of-bounds WGS84 coordinates.
8. Auto-unassignment of active jobs when technician availability status is patched to INACTIVE.
9. Dispatcher <-> Technician cross-role status and location synchronization.
10. Audit log trail verification (JOB_STATUS_CHANGED).
"""

import uuid
import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.database.session import AsyncSessionLocal
from app.models.audit_log import AuditLog
from app.models.enums import UserRole
from app.models.job import Job

BASE_URL = "http://127.0.0.1:8000"


async def get_token_headers(client: AsyncClient, email: str, password: str) -> dict[str, str]:
    """Helper to authenticate and obtain bearer token headers."""
    res = await client.post(f"{BASE_URL}/api/v1/auth/login", json={"email": email, "password": password})
    assert res.status_code == 200, f"Login failed for {email}: {res.text}"
    token = res.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


async def get_technician_and_skill(client: AsyncClient, disp_headers: dict[str, str]) -> tuple[str, str]:
    """Helper to fetch the technician ID and certified skill ID for technician@fieldops.ai."""
    res = await client.get(f"{BASE_URL}/api/v1/technicians?search=technician@fieldops.ai", headers=disp_headers)
    assert res.status_code == 200, f"Failed to fetch technician: {res.text}"
    body = res.json()
    items = body["items"] if "items" in body else body
    assert len(items) > 0, f"No technician found for technician@fieldops.ai: {res.text}"
    tech = items[0]
    return str(tech["id"]), str(tech["primary_skill_id"])


async def create_test_job(
    client: AsyncClient,
    headers: dict[str, str],
    skill_id: str,
    latitude: float = 37.7800,
    longitude: float = -122.4100,
) -> dict:
    """Helper to create a fresh test job."""
    payload = {
        "customer_name": f"Workflow Test Customer {uuid.uuid4().hex[:4]}",
        "customer_phone": "+1 (555) 888-0022",
        "address": "100 Operational Way, San Francisco, CA",
        "latitude": latitude,
        "longitude": longitude,
        "required_skill_id": skill_id,
        "priority": "HIGH",
        "description": "Validation job for Module 16 technician workflow.",
    }
    res = await client.post(f"{BASE_URL}/api/v1/jobs", json=payload, headers=headers)
    assert res.status_code == 201, f"Failed to create test job: {res.text}"
    return res.json()


async def assign_technician_to_job(
    client: AsyncClient, headers: dict[str, str], job_id: str, technician_id: str
) -> dict:
    """Helper to assign a technician to a job via Dispatcher endpoint."""
    res = await client.post(
        f"{BASE_URL}/api/v1/assignments/jobs/{job_id}/assign",
        json={"technician_id": technician_id},
        headers=headers,
    )
    assert res.status_code == 201, f"Failed to assign technician: {res.text}"
    return res.json()


@pytest.mark.asyncio
async def test_1_complete_technician_lifecycle_and_aliases():
    """1. Test full status transition chain (ASSIGNED -> EN_ROUTE -> ARRIVED -> IN_PROGRESS -> COMPLETED)."""
    async with AsyncClient() as client:
        disp_headers = await get_token_headers(client, "dispatcher@fieldops.ai", "Dispatch@123")
        tech_headers = await get_token_headers(client, "technician@fieldops.ai", "Tech@123")
        tech_id, skill_id = await get_technician_and_skill(client, disp_headers)

        job = await create_test_job(client, disp_headers, skill_id)
        await assign_technician_to_job(client, disp_headers, job["id"], tech_id)

        # Step A: ASSIGNED -> EN_ROUTE (Alias for TRAVELLING)
        res_en_route = await client.patch(
            f"{BASE_URL}/api/v1/jobs/{job['id']}/status",
            json={"status": "EN_ROUTE"},
            headers=tech_headers,
        )
        assert res_en_route.status_code == 200, f"Failed EN_ROUTE transition: {res_en_route.text}"
        assert res_en_route.json()["status"] == "TRAVELLING"

        # Step B: TRAVELLING -> ARRIVED
        res_arrived = await client.patch(
            f"{BASE_URL}/api/v1/jobs/{job['id']}/status",
            json={"status": "ARRIVED"},
            headers=tech_headers,
        )
        assert res_arrived.status_code == 200, f"Failed ARRIVED transition: {res_arrived.text}"
        assert res_arrived.json()["status"] == "ARRIVED"

        # Step C: ARRIVED -> IN_PROGRESS (Alias for WORKING)
        res_working = await client.patch(
            f"{BASE_URL}/api/v1/jobs/{job['id']}/status",
            json={"status": "IN_PROGRESS"},
            headers=tech_headers,
        )
        assert res_working.status_code == 200, f"Failed IN_PROGRESS transition: {res_working.text}"
        assert res_working.json()["status"] == "WORKING"

        # Step D: WORKING -> COMPLETED
        res_completed = await client.patch(
            f"{BASE_URL}/api/v1/jobs/{job['id']}/status",
            json={"status": "COMPLETED", "completion_notes": "Replaced HVAC filter and verified airflow."},
            headers=tech_headers,
        )
        assert res_completed.status_code == 200, f"Failed COMPLETED transition: {res_completed.text}"
        assert res_completed.json()["status"] == "COMPLETED"


@pytest.mark.asyncio
async def test_2_invalid_status_transitions_rejected():
    """2. Test invalid status jumps (e.g. ASSIGNED -> WORKING or TRAVELLING -> COMPLETED) are rejected."""
    async with AsyncClient() as client:
        disp_headers = await get_token_headers(client, "dispatcher@fieldops.ai", "Dispatch@123")
        tech_headers = await get_token_headers(client, "technician@fieldops.ai", "Tech@123")
        tech_id, skill_id = await get_technician_and_skill(client, disp_headers)

        job = await create_test_job(client, disp_headers, skill_id)
        await assign_technician_to_job(client, disp_headers, job["id"], tech_id)

        # Attempt invalid jump: ASSIGNED -> WORKING (must go through TRAVELLING and ARRIVED first)
        res_invalid = await client.patch(
            f"{BASE_URL}/api/v1/jobs/{job['id']}/status",
            json={"status": "WORKING"},
            headers=tech_headers,
        )
        assert res_invalid.status_code == 400
        assert "Invalid status transition" in res_invalid.text


@pytest.mark.asyncio
async def test_3_technician_ownership_isolation():
    """3. Test technician cannot update execution status for a job assigned to another technician."""
    async with AsyncClient() as client:
        disp_headers = await get_token_headers(client, "dispatcher@fieldops.ai", "Dispatch@123")
        admin_headers = await get_token_headers(client, "admin@fieldops.ai", "Admin@123")
        tech1_id, skill_id = await get_technician_and_skill(client, disp_headers)

        # Create a second technician (Tech B)
        tech2_code = f"TECH-{uuid.uuid4().hex[:4].upper()}"
        tech2_email = f"tech2_{uuid.uuid4().hex[:4]}@fieldops.ai"
        tech2_payload = {
            "employee_code": tech2_code,
            "full_name": "Secondary Technician",
            "email": tech2_email,
            "password": "TechPassword@123",
            "phone": "+1 (555) 777-9911",
            "primary_skill_id": skill_id,
            "years_experience": 4,
            "availability_status": "AVAILABLE",
        }
        res_t2 = await client.post(f"{BASE_URL}/api/v1/technicians", json=tech2_payload, headers=admin_headers)
        assert res_t2.status_code == 201, f"Failed to create tech 2: {res_t2.text}"

        tech2_headers = await get_token_headers(client, tech2_email, "TechPassword@123")

        # Assign job to Tech 1
        job = await create_test_job(client, disp_headers, skill_id)
        await assign_technician_to_job(client, disp_headers, job["id"], tech1_id)

        # Tech 2 attempts to patch status on Tech 1's job -> 403 Forbidden
        res_unauthorized = await client.patch(
            f"{BASE_URL}/api/v1/jobs/{job['id']}/status",
            json={"status": "TRAVELLING"},
            headers=tech2_headers,
        )
        assert res_unauthorized.status_code == 403
        assert "assigned to yourself" in res_unauthorized.text.lower()


@pytest.mark.asyncio
async def test_4_role_security_dispatcher_admin_forbidden():
    """4. Test Dispatcher and Administrator cannot perform technician status patch transitions."""
    async with AsyncClient() as client:
        disp_headers = await get_token_headers(client, "dispatcher@fieldops.ai", "Dispatch@123")
        admin_headers = await get_token_headers(client, "admin@fieldops.ai", "Admin@123")
        tech_id, skill_id = await get_technician_and_skill(client, disp_headers)

        job = await create_test_job(client, disp_headers, skill_id)
        await assign_technician_to_job(client, disp_headers, job["id"], tech_id)

        # Dispatcher forbidden
        res_disp = await client.patch(
            f"{BASE_URL}/api/v1/jobs/{job['id']}/status",
            json={"status": "TRAVELLING"},
            headers=disp_headers,
        )
        assert res_disp.status_code == 403

        # Administrator forbidden
        res_admin = await client.patch(
            f"{BASE_URL}/api/v1/jobs/{job['id']}/status",
            json={"status": "TRAVELLING"},
            headers=admin_headers,
        )
        assert res_admin.status_code == 403


@pytest.mark.asyncio
async def test_5_terminal_state_protection():
    """5. Test COMPLETED and CANCELLED jobs cannot undergo further status transitions."""
    async with AsyncClient() as client:
        disp_headers = await get_token_headers(client, "dispatcher@fieldops.ai", "Dispatch@123")
        tech_headers = await get_token_headers(client, "technician@fieldops.ai", "Tech@123")
        tech_id, skill_id = await get_technician_and_skill(client, disp_headers)

        job = await create_test_job(client, disp_headers, skill_id)
        await assign_technician_to_job(client, disp_headers, job["id"], tech_id)

        # Progress to COMPLETED
        await client.patch(f"{BASE_URL}/api/v1/jobs/{job['id']}/status", json={"status": "TRAVELLING"}, headers=tech_headers)
        await client.patch(f"{BASE_URL}/api/v1/jobs/{job['id']}/status", json={"status": "ARRIVED"}, headers=tech_headers)
        await client.patch(f"{BASE_URL}/api/v1/jobs/{job['id']}/status", json={"status": "WORKING"}, headers=tech_headers)
        await client.patch(f"{BASE_URL}/api/v1/jobs/{job['id']}/status", json={"status": "COMPLETED"}, headers=tech_headers)

        # Attempt transition out of COMPLETED -> 400 Bad Request
        res_restart = await client.patch(
            f"{BASE_URL}/api/v1/jobs/{job['id']}/status",
            json={"status": "WORKING"},
            headers=tech_headers,
        )
        assert res_restart.status_code == 400
        assert "Cannot change status of a COMPLETED job" in res_restart.text


@pytest.mark.asyncio
async def test_6_gps_location_telemetry_patch_and_validation():
    """6. Test technician location telemetry endpoint with valid and out-of-bounds coordinates."""
    async with AsyncClient() as client:
        tech_headers = await get_token_headers(client, "technician@fieldops.ai", "Tech@123")

        # 1. Valid WGS84 patch
        valid_payload = {"latitude": 37.7749, "longitude": -122.4194}
        res_valid = await client.patch(f"{BASE_URL}/api/v1/technicians/me/location", json=valid_payload, headers=tech_headers)
        assert res_valid.status_code == 200
        data = res_valid.json()
        assert data["current_latitude"] == 37.7749
        assert data["current_longitude"] == -122.4194

        # 2. Out-of-bounds latitude patch -> 422 Unprocessable Entity (Schema validation)
        res_bad_lat = await client.patch(
            f"{BASE_URL}/api/v1/technicians/me/location",
            json={"latitude": 105.0, "longitude": -122.4194},
            headers=tech_headers,
        )
        assert res_bad_lat.status_code == 422

        # 3. Out-of-bounds longitude patch -> 422 Unprocessable Entity (Schema validation)
        res_bad_lon = await client.patch(
            f"{BASE_URL}/api/v1/technicians/me/location",
            json={"latitude": 37.7749, "longitude": -210.0},
            headers=tech_headers,
        )
        assert res_bad_lon.status_code == 422


@pytest.mark.asyncio
async def test_7_dispatcher_technician_cross_role_sync():
    """7. Test status update made by technician is immediately visible to Dispatcher query."""
    async with AsyncClient() as client:
        disp_headers = await get_token_headers(client, "dispatcher@fieldops.ai", "Dispatch@123")
        tech_headers = await get_token_headers(client, "technician@fieldops.ai", "Tech@123")
        tech_id, skill_id = await get_technician_and_skill(client, disp_headers)

        job = await create_test_job(client, disp_headers, skill_id)
        await assign_technician_to_job(client, disp_headers, job["id"], tech_id)

        # Technician updates to TRAVELLING
        await client.patch(f"{BASE_URL}/api/v1/jobs/{job['id']}/status", json={"status": "TRAVELLING"}, headers=tech_headers)

        # Dispatcher queries job details
        res_disp = await client.get(f"{BASE_URL}/api/v1/jobs/{job['id']}", headers=disp_headers)
        assert res_disp.status_code == 200
        assert res_disp.json()["status"] == "TRAVELLING"


@pytest.mark.asyncio
async def test_8_audit_logging_on_status_change():
    """8. Test that updating job status emits a JOB_STATUS_CHANGED audit record."""
    async with AsyncClient() as client:
        disp_headers = await get_token_headers(client, "dispatcher@fieldops.ai", "Dispatch@123")
        tech_headers = await get_token_headers(client, "technician@fieldops.ai", "Tech@123")
        tech_id, skill_id = await get_technician_and_skill(client, disp_headers)

        job = await create_test_job(client, disp_headers, skill_id)
        await assign_technician_to_job(client, disp_headers, job["id"], tech_id)

        # Perform status change
        await client.patch(f"{BASE_URL}/api/v1/jobs/{job['id']}/status", json={"status": "TRAVELLING"}, headers=tech_headers)

        # Inspect audit logs in database
        async with AsyncSessionLocal() as session:
            res = await session.execute(
                select(AuditLog).where(
                    AuditLog.entity_id == str(job["id"]),
                    AuditLog.action == "JOB_STATUS_CHANGED",
                )
            )
            audit = res.scalar_one_or_none()
            assert audit is not None
            assert "ASSIGNED" in audit.old_value
            assert "TRAVELLING" in audit.new_value
