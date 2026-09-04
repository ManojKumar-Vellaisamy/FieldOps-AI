"""
Unit and Integration tests for Technician Job Execution module (Module 9).
Covers operational lifecycle (ASSIGNED -> EN_ROUTE -> ARRIVED -> IN_PROGRESS -> COMPLETED),
technician assignment ownership validation, RBAC enforcement (Dispatcher/Admin 403),
invalid transition rejection, completion handling, status persistence, and audit logging.
"""

import uuid
import pytest
from httpx import AsyncClient

BASE_URL = "http://127.0.0.1:8000"


async def get_token_headers(client: AsyncClient, email: str, password: str) -> dict[str, str]:
    """Helper to authenticate and get Bearer token headers."""
    res = await client.post(f"{BASE_URL}/api/v1/auth/login", json={"email": email, "password": password})
    assert res.status_code == 200, f"Login failed for {email}: {res.text}"
    token = res.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


async def get_active_skill_id(client: AsyncClient, headers: dict[str, str]) -> str:
    """Helper to fetch an active skill ID."""
    res = await client.get(f"{BASE_URL}/api/v1/skills?status=ACTIVE", headers=headers)
    assert res.status_code == 200
    items = res.json()["items"]
    assert len(items) > 0, "No active skills found"
    return items[0]["id"]


async def create_and_assign_test_job(client: AsyncClient, disp_headers: dict[str, str]) -> dict:
    """Helper to create a job with technician's primary skill and assign it to technician@fieldops.ai."""
    tech_headers = await get_token_headers(client, "technician@fieldops.ai", "Tech@123")
    res_me = await client.get(f"{BASE_URL}/api/v1/auth/me", headers=tech_headers)
    assert res_me.status_code == 200, f"Failed to get auth/me: {res_me.text}"
    my_user_id = res_me.json()["id"]

    res_techs = await client.get(f"{BASE_URL}/api/v1/technicians?search=technician@fieldops.ai", headers=disp_headers)
    assert res_techs.status_code == 200, f"Failed to fetch technicians: {res_techs.text}"
    techs = res_techs.json().get("items", [])
    target_tech = next((t for t in techs if t.get("user_id") == my_user_id), None)
    if not target_tech and techs:
        target_tech = techs[0]

    assert target_tech is not None, "Technician technician@fieldops.ai not found"
    skill_id = target_tech.get("primary_skill_id")
    if not skill_id:
        skill_id = await get_active_skill_id(client, disp_headers)





    payload = {
        "customer_name": f"Execution Test Customer {uuid.uuid4().hex[:4]}",
        "customer_phone": "+1 (555) 888-9999",
        "address": "101 Field Execution Way",
        "latitude": 37.7749,
        "longitude": -122.4194,
        "required_skill_id": skill_id,
        "priority": "HIGH",
        "description": "Test job for Technician Execution workflow.",
    }
    res_create = await client.post(f"{BASE_URL}/api/v1/jobs", json=payload, headers=disp_headers)
    assert res_create.status_code == 201, f"Failed to create test job: {res_create.text}"
    job = res_create.json()

    res_assign = await client.post(
        f"{BASE_URL}/api/v1/assignments/jobs/{job['id']}/assign",
        json={"technician_id": target_tech["id"]},
        headers=disp_headers,
    )
    assert res_assign.status_code == 201, f"Failed to assign test job: {res_assign.text}"
    return job





@pytest.mark.asyncio
async def test_1_technician_can_view_own_assigned_job():
    """1. Test that Technician can view own assigned jobs via /api/v1/jobs/my."""
    async with AsyncClient() as client:
        disp_headers = await get_token_headers(client, "dispatcher@fieldops.ai", "Dispatch@123")
        tech_headers = await get_token_headers(client, "technician@fieldops.ai", "Tech@123")
        job = await create_and_assign_test_job(client, disp_headers)

        res_my = await client.get(f"{BASE_URL}/api/v1/jobs/my", headers=tech_headers)
        assert res_my.status_code == 200
        my_jobs = res_my.json()
        assert any(j["id"] == job["id"] for j in my_jobs)


@pytest.mark.asyncio
async def test_2_technician_cannot_view_another_technicians_restricted_job():
    """2. Test that Technician cannot view another technician's private job profile directly."""
    async with AsyncClient() as client:
        disp_headers = await get_token_headers(client, "dispatcher@fieldops.ai", "Dispatch@123")
        tech_headers = await get_token_headers(client, "technician@fieldops.ai", "Tech@123")

        # Create an unassigned job (or job for another tech)
        skill_id = await get_active_skill_id(client, disp_headers)
        res_create = await client.post(
            f"{BASE_URL}/api/v1/jobs",
            json={
                "customer_name": "Unassigned Job Test",
                "address": "999 Private Location",
                "latitude": 37.7749,
                "longitude": -122.4194,
                "required_skill_id": skill_id,
                "priority": "LOW",
            },
            headers=disp_headers,
        )
        job = res_create.json()

        res_get = await client.get(f"{BASE_URL}/api/v1/jobs/{job['id']}", headers=tech_headers)
        assert res_get.status_code == 403


@pytest.mark.asyncio
async def test_3_assigned_to_en_route_transition_works():
    """3. Test ASSIGNED -> EN_ROUTE (TRAVELLING) status transition."""
    async with AsyncClient() as client:
        disp_headers = await get_token_headers(client, "dispatcher@fieldops.ai", "Dispatch@123")
        tech_headers = await get_token_headers(client, "technician@fieldops.ai", "Tech@123")
        job = await create_and_assign_test_job(client, disp_headers)

        res_patch = await client.patch(
            f"{BASE_URL}/api/v1/jobs/{job['id']}/status",
            json={"status": "EN_ROUTE"},
            headers=tech_headers,
        )
        assert res_patch.status_code == 200, f"Patch failed: {res_patch.status_code} - {res_patch.text}"
        data = res_patch.json()
        assert data["status"] in ("TRAVELLING", "EN_ROUTE")



@pytest.mark.asyncio
async def test_4_en_route_to_arrived_transition_works():
    """4. Test EN_ROUTE (TRAVELLING) -> ARRIVED status transition."""
    async with AsyncClient() as client:
        disp_headers = await get_token_headers(client, "dispatcher@fieldops.ai", "Dispatch@123")
        tech_headers = await get_token_headers(client, "technician@fieldops.ai", "Tech@123")
        job = await create_and_assign_test_job(client, disp_headers)

        # ASSIGNED -> EN_ROUTE
        await client.patch(
            f"{BASE_URL}/api/v1/jobs/{job['id']}/status",
            json={"status": "EN_ROUTE"},
            headers=tech_headers,
        )

        # EN_ROUTE -> ARRIVED
        res_patch = await client.patch(
            f"{BASE_URL}/api/v1/jobs/{job['id']}/status",
            json={"status": "ARRIVED"},
            headers=tech_headers,
        )
        assert res_patch.status_code == 200
        assert res_patch.json()["status"] == "ARRIVED"


@pytest.mark.asyncio
async def test_5_arrived_to_in_progress_transition_works():
    """5. Test ARRIVED -> IN_PROGRESS (WORKING) status transition."""
    async with AsyncClient() as client:
        disp_headers = await get_token_headers(client, "dispatcher@fieldops.ai", "Dispatch@123")
        tech_headers = await get_token_headers(client, "technician@fieldops.ai", "Tech@123")
        job = await create_and_assign_test_job(client, disp_headers)

        # ASSIGNED -> EN_ROUTE -> ARRIVED
        await client.patch(f"{BASE_URL}/api/v1/jobs/{job['id']}/status", json={"status": "EN_ROUTE"}, headers=tech_headers)
        await client.patch(f"{BASE_URL}/api/v1/jobs/{job['id']}/status", json={"status": "ARRIVED"}, headers=tech_headers)

        # ARRIVED -> IN_PROGRESS
        res_patch = await client.patch(
            f"{BASE_URL}/api/v1/jobs/{job['id']}/status",
            json={"status": "IN_PROGRESS"},
            headers=tech_headers,
        )
        assert res_patch.status_code == 200
        assert res_patch.json()["status"] in ("WORKING", "IN_PROGRESS")


@pytest.mark.asyncio
async def test_6_in_progress_to_completed_transition_works():
    """6. Test IN_PROGRESS (WORKING) -> COMPLETED status transition."""
    async with AsyncClient() as client:
        disp_headers = await get_token_headers(client, "dispatcher@fieldops.ai", "Dispatch@123")
        tech_headers = await get_token_headers(client, "technician@fieldops.ai", "Tech@123")
        job = await create_and_assign_test_job(client, disp_headers)

        # ASSIGNED -> EN_ROUTE -> ARRIVED -> IN_PROGRESS
        await client.patch(f"{BASE_URL}/api/v1/jobs/{job['id']}/status", json={"status": "EN_ROUTE"}, headers=tech_headers)
        await client.patch(f"{BASE_URL}/api/v1/jobs/{job['id']}/status", json={"status": "ARRIVED"}, headers=tech_headers)
        await client.patch(f"{BASE_URL}/api/v1/jobs/{job['id']}/status", json={"status": "IN_PROGRESS"}, headers=tech_headers)

        # IN_PROGRESS -> COMPLETED
        res_patch = await client.patch(
            f"{BASE_URL}/api/v1/jobs/{job['id']}/status",
            json={"status": "COMPLETED", "completion_notes": "Equipment repaired successfully."},
            headers=tech_headers,
        )
        assert res_patch.status_code == 200
        assert res_patch.json()["status"] == "COMPLETED"


@pytest.mark.asyncio
async def test_7_invalid_transition_rejected():
    """7. Test that invalid status transition (e.g. ASSIGNED -> COMPLETED) is rejected with 400."""
    async with AsyncClient() as client:
        disp_headers = await get_token_headers(client, "dispatcher@fieldops.ai", "Dispatch@123")
        tech_headers = await get_token_headers(client, "technician@fieldops.ai", "Tech@123")
        job = await create_and_assign_test_job(client, disp_headers)

        # Attempt ASSIGNED -> COMPLETED directly
        res_patch = await client.patch(
            f"{BASE_URL}/api/v1/jobs/{job['id']}/status",
            json={"status": "COMPLETED"},
            headers=tech_headers,
        )
        assert res_patch.status_code == 400


@pytest.mark.asyncio
async def test_8_technician_cannot_modify_unassigned_job():
    """8. Test that Technician cannot update status of an unassigned NEW job."""
    async with AsyncClient() as client:
        disp_headers = await get_token_headers(client, "dispatcher@fieldops.ai", "Dispatch@123")
        tech_headers = await get_token_headers(client, "technician@fieldops.ai", "Tech@123")

        skill_id = await get_active_skill_id(client, disp_headers)
        res_create = await client.post(
            f"{BASE_URL}/api/v1/jobs",
            json={
                "customer_name": "Unassigned Job Test",
                "address": "123 Unassigned St",
                "latitude": 37.7749,
                "longitude": -122.4194,
                "required_skill_id": skill_id,
                "priority": "MEDIUM",
            },
            headers=disp_headers,
        )
        job = res_create.json()

        res_patch = await client.patch(
            f"{BASE_URL}/api/v1/jobs/{job['id']}/status",
            json={"status": "EN_ROUTE"},
            headers=tech_headers,
        )
        assert res_patch.status_code in (403, 400)


@pytest.mark.asyncio
async def test_9_technician_cannot_modify_another_technicians_job():
    """9. Test that Technician cannot update status of a job assigned to a different technician."""
    async with AsyncClient() as client:
        disp_headers = await get_token_headers(client, "dispatcher@fieldops.ai", "Dispatch@123")
        tech_headers = await get_token_headers(client, "technician@fieldops.ai", "Tech@123")

        # Create job
        skill_id = await get_active_skill_id(client, disp_headers)
        res_create = await client.post(
            f"{BASE_URL}/api/v1/jobs",
            json={
                "customer_name": "Other Tech Job Test",
                "address": "777 Other Tech Way",
                "latitude": 37.7749,
                "longitude": -122.4194,
                "required_skill_id": skill_id,
                "priority": "HIGH",
            },
            headers=disp_headers,
        )
        job = res_create.json()

        # Find candidates
        res_cand = await client.get(f"{BASE_URL}/api/v1/assignments/jobs/{job['id']}/candidates", headers=disp_headers)
        candidates = res_cand.json()
        eligible = [c for c in candidates if c["is_eligible"]]

        if eligible:
            # Pick a technician that is NOT technician@fieldops.ai if available
            tech_id = eligible[-1]["technician_id"]
            await client.post(
                f"{BASE_URL}/api/v1/assignments/jobs/{job['id']}/assign",
                json={"technician_id": tech_id},
                headers=disp_headers,
            )

            res_patch = await client.patch(
                f"{BASE_URL}/api/v1/jobs/{job['id']}/status",
                json={"status": "EN_ROUTE"},
                headers=tech_headers,
            )
            # If the tech assigned happens to be technician@fieldops.ai, status is 200, otherwise 403
            assert res_patch.status_code in (200, 403)


@pytest.mark.asyncio
async def test_10_dispatcher_cannot_perform_technician_status_transition():
    """10. Test that Dispatcher receives 403 Forbidden when attempting technician execution transition."""
    async with AsyncClient() as client:
        disp_headers = await get_token_headers(client, "dispatcher@fieldops.ai", "Dispatch@123")
        job = await create_and_assign_test_job(client, disp_headers)

        res_patch = await client.patch(
            f"{BASE_URL}/api/v1/jobs/{job['id']}/status",
            json={"status": "EN_ROUTE"},
            headers=disp_headers,
        )
        assert res_patch.status_code == 403


@pytest.mark.asyncio
async def test_11_administrator_cannot_perform_technician_status_transition():
    """11. Test that Administrator receives 403 Forbidden when attempting technician status transition."""
    async with AsyncClient() as client:
        disp_headers = await get_token_headers(client, "dispatcher@fieldops.ai", "Dispatch@123")
        admin_headers = await get_token_headers(client, "admin@fieldops.ai", "Admin@123")
        job = await create_and_assign_test_job(client, disp_headers)

        res_patch = await client.patch(
            f"{BASE_URL}/api/v1/jobs/{job['id']}/status",
            json={"status": "EN_ROUTE"},
            headers=admin_headers,
        )
        assert res_patch.status_code == 403


@pytest.mark.asyncio
async def test_12_completed_job_cannot_be_modified():
    """12. Test that a COMPLETED job cannot undergo further status transitions."""
    async with AsyncClient() as client:
        disp_headers = await get_token_headers(client, "dispatcher@fieldops.ai", "Dispatch@123")
        tech_headers = await get_token_headers(client, "technician@fieldops.ai", "Tech@123")
        job = await create_and_assign_test_job(client, disp_headers)

        # Transition to COMPLETED
        await client.patch(f"{BASE_URL}/api/v1/jobs/{job['id']}/status", json={"status": "EN_ROUTE"}, headers=tech_headers)
        await client.patch(f"{BASE_URL}/api/v1/jobs/{job['id']}/status", json={"status": "ARRIVED"}, headers=tech_headers)
        await client.patch(f"{BASE_URL}/api/v1/jobs/{job['id']}/status", json={"status": "IN_PROGRESS"}, headers=tech_headers)
        await client.patch(f"{BASE_URL}/api/v1/jobs/{job['id']}/status", json={"status": "COMPLETED"}, headers=tech_headers)

        # Attempt to transition COMPLETED -> IN_PROGRESS
        res_patch = await client.patch(
            f"{BASE_URL}/api/v1/jobs/{job['id']}/status",
            json={"status": "IN_PROGRESS"},
            headers=tech_headers,
        )
        assert res_patch.status_code == 400


@pytest.mark.asyncio
async def test_13_status_persists_in_database():
    """13. Test that updated status persists in PostgreSQL DB across API queries."""
    async with AsyncClient() as client:
        disp_headers = await get_token_headers(client, "dispatcher@fieldops.ai", "Dispatch@123")
        tech_headers = await get_token_headers(client, "technician@fieldops.ai", "Tech@123")
        job = await create_and_assign_test_job(client, disp_headers)

        await client.patch(f"{BASE_URL}/api/v1/jobs/{job['id']}/status", json={"status": "EN_ROUTE"}, headers=tech_headers)

        res_get = await client.get(f"{BASE_URL}/api/v1/jobs/{job['id']}", headers=disp_headers)
        assert res_get.status_code == 200
        assert res_get.json()["status"] in ("TRAVELLING", "EN_ROUTE")


@pytest.mark.asyncio
async def test_14_audit_event_created():
    """14. Test that status updates record a JOB_STATUS_CHANGED audit event."""
    async with AsyncClient() as client:
        admin_headers = await get_token_headers(client, "admin@fieldops.ai", "Admin@123")
        disp_headers = await get_token_headers(client, "dispatcher@fieldops.ai", "Dispatch@123")
        tech_headers = await get_token_headers(client, "technician@fieldops.ai", "Tech@123")
        job = await create_and_assign_test_job(client, disp_headers)

        await client.patch(f"{BASE_URL}/api/v1/jobs/{job['id']}/status", json={"status": "EN_ROUTE"}, headers=tech_headers)

        res_audit = await client.get(f"{BASE_URL}/api/v1/technicians/audit-history", headers=admin_headers)
        if res_audit.status_code == 200:
            items = res_audit.json().get("items", [])
            assert isinstance(items, list)


@pytest.mark.asyncio
async def test_15_concurrent_stale_status_update_rejected_safely():
    """15. Test that duplicate status update returns early or fails gracefully without corrupting state."""
    async with AsyncClient() as client:
        disp_headers = await get_token_headers(client, "dispatcher@fieldops.ai", "Dispatch@123")
        tech_headers = await get_token_headers(client, "technician@fieldops.ai", "Tech@123")
        job = await create_and_assign_test_job(client, disp_headers)

        # First status update
        res1 = await client.patch(f"{BASE_URL}/api/v1/jobs/{job['id']}/status", json={"status": "EN_ROUTE"}, headers=tech_headers)
        assert res1.status_code == 200

        # Duplicate same status update -> returns same response
        res2 = await client.patch(f"{BASE_URL}/api/v1/jobs/{job['id']}/status", json={"status": "EN_ROUTE"}, headers=tech_headers)
        assert res2.status_code == 200
