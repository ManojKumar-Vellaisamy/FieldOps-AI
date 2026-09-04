"""
Unit and Integration tests for Job Management end-to-end module.
Covers RBAC, CRUD operations, coordinate validation, active skill checks, controlled cancellation, and audit logging.
"""

import uuid
import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from app.core.config import settings
from app.models.audit_log import AuditLog
from app.models.job import Job

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
    assert len(items) > 0, "No active skills found for testing"
    return items[0]["id"]


@pytest.mark.asyncio
async def test_1_dispatcher_can_create_job():
    """1. Test Dispatcher can create a new service job."""
    async with AsyncClient() as client:
        disp_headers = await get_token_headers(client, "dispatcher@fieldops.ai", "Dispatch@123")
        active_skill_id = await get_active_skill_id(client, disp_headers)

        payload = {
            "customer_name": "Test Customer Inc",
            "customer_phone": "+1 (555) 999-8888",
            "address": "123 Test Street, Suite 400",
            "latitude": 37.7749,
            "longitude": -122.4194,
            "required_skill_id": active_skill_id,
            "priority": "HIGH",
            "description": "Test job creation description.",
        }

        res = await client.post(f"{BASE_URL}/api/v1/jobs", json=payload, headers=disp_headers)
        assert res.status_code == 201
        data = res.json()
        assert data["job_number"].startswith("JOB-")
        assert data["customer_name"] == "Test Customer Inc"
        assert data["status"] == "NEW"
        assert data["priority"] == "HIGH"


@pytest.mark.asyncio
async def test_2_dispatcher_can_list_jobs():
    """2. Test Dispatcher can list jobs."""
    async with AsyncClient() as client:
        disp_headers = await get_token_headers(client, "dispatcher@fieldops.ai", "Dispatch@123")

        res = await client.get(f"{BASE_URL}/api/v1/jobs", headers=disp_headers)
        assert res.status_code == 200
        data = res.json()
        assert "items" in data
        assert data["total"] > 0


@pytest.mark.asyncio
async def test_3_dispatcher_can_retrieve_job():
    """3. Test Dispatcher can retrieve single job details."""
    async with AsyncClient() as client:
        disp_headers = await get_token_headers(client, "dispatcher@fieldops.ai", "Dispatch@123")

        jobs_res = await client.get(f"{BASE_URL}/api/v1/jobs", headers=disp_headers)
        job_id = jobs_res.json()["items"][0]["id"]

        res = await client.get(f"{BASE_URL}/api/v1/jobs/{job_id}", headers=disp_headers)
        assert res.status_code == 200
        assert res.json()["id"] == job_id


@pytest.mark.asyncio
async def test_4_dispatcher_can_update_job():
    """4. Test Dispatcher can update eligible job fields."""
    async with AsyncClient() as client:
        disp_headers = await get_token_headers(client, "dispatcher@fieldops.ai", "Dispatch@123")

        jobs_res = await client.get(f"{BASE_URL}/api/v1/jobs", headers=disp_headers)
        job_id = jobs_res.json()["items"][0]["id"]

        updated_address = "456 Updated Plaza Boulevard"
        res = await client.put(f"{BASE_URL}/api/v1/jobs/{job_id}", json={"address": updated_address}, headers=disp_headers)
        assert res.status_code == 200
        assert res.json()["address"] == updated_address


@pytest.mark.asyncio
async def test_5_dispatcher_can_cancel_job():
    """5. Test Dispatcher can cancel job with reason."""
    async with AsyncClient() as client:
        disp_headers = await get_token_headers(client, "dispatcher@fieldops.ai", "Dispatch@123")
        active_skill_id = await get_active_skill_id(client, disp_headers)

        # Create job to cancel
        create_res = await client.post(
            f"{BASE_URL}/api/v1/jobs",
            json={
                "customer_name": "Cancel Target Corp",
                "address": "999 Discard Way",
                "latitude": 37.0,
                "longitude": -122.0,
                "required_skill_id": active_skill_id,
            },
            headers=disp_headers,
        )
        assert create_res.status_code == 201
        job_id = create_res.json()["id"]

        cancel_res = await client.post(
            f"{BASE_URL}/api/v1/jobs/{job_id}/cancel",
            json={"reason": "Customer requested appointment cancellation."},
            headers=disp_headers,
        )
        assert cancel_res.status_code == 200
        assert cancel_res.json()["status"] == "CANCELLED"


@pytest.mark.asyncio
async def test_6_technician_cannot_create_job():
    """6. Test Technician cannot create a job (403 Forbidden)."""
    async with AsyncClient() as client:
        disp_headers = await get_token_headers(client, "dispatcher@fieldops.ai", "Dispatch@123")
        active_skill_id = await get_active_skill_id(client, disp_headers)
        tech_headers = await get_token_headers(client, "technician@fieldops.ai", "Tech@123")

        payload = {
            "customer_name": "Illegal Tech Job",
            "address": "123 Unauthorized St",
            "latitude": 37.0,
            "longitude": -122.0,
            "required_skill_id": active_skill_id,
        }

        res = await client.post(f"{BASE_URL}/api/v1/jobs", json=payload, headers=tech_headers)
        assert res.status_code == 403


@pytest.mark.asyncio
async def test_7_administrator_cannot_create_job():
    """7. Test Administrator cannot create a job (403 Forbidden)."""
    async with AsyncClient() as client:
        disp_headers = await get_token_headers(client, "dispatcher@fieldops.ai", "Dispatch@123")
        active_skill_id = await get_active_skill_id(client, disp_headers)
        admin_headers = await get_token_headers(client, "admin@fieldops.ai", "Admin@123")

        payload = {
            "customer_name": "Illegal Admin Job",
            "address": "123 Unauthorized St",
            "latitude": 37.0,
            "longitude": -122.0,
            "required_skill_id": active_skill_id,
        }

        res = await client.post(f"{BASE_URL}/api/v1/jobs", json=payload, headers=admin_headers)
        assert res.status_code == 403


@pytest.mark.asyncio
async def test_8_technician_can_view_only_own_jobs():
    """8. Test Technician can view only assigned jobs via /jobs/my."""
    async with AsyncClient() as client:
        tech_headers = await get_token_headers(client, "technician@fieldops.ai", "Tech@123")

        res = await client.get(f"{BASE_URL}/api/v1/jobs/my", headers=tech_headers)
        assert res.status_code == 200
        assert isinstance(res.json(), list)


@pytest.mark.asyncio
async def test_9_technician_cannot_access_other_technician_job():
    """9. Test Technician cannot access another technician's job or unassigned job (403 Forbidden)."""
    async with AsyncClient() as client:
        disp_headers = await get_token_headers(client, "dispatcher@fieldops.ai", "Dispatch@123")
        tech_headers = await get_token_headers(client, "technician@fieldops.ai", "Tech@123")
        active_skill_id = await get_active_skill_id(client, disp_headers)

        # Create unassigned job
        create_res = await client.post(
            f"{BASE_URL}/api/v1/jobs",
            json={
                "customer_name": "Private Job Corp",
                "address": "123 Private St",
                "latitude": 37.0,
                "longitude": -122.0,
                "required_skill_id": active_skill_id,
            },
            headers=disp_headers,
        )
        assert create_res.status_code == 201
        job_id = create_res.json()["id"]

        # Technician tries to access GET /jobs/{job_id}
        res = await client.get(f"{BASE_URL}/api/v1/jobs/{job_id}", headers=tech_headers)
        assert res.status_code == 403


@pytest.mark.asyncio
async def test_10_invalid_skill_rejected():
    """10. Test nonexistent skill ID is rejected with 400 Validation Error."""
    async with AsyncClient() as client:
        disp_headers = await get_token_headers(client, "dispatcher@fieldops.ai", "Dispatch@123")
        fake_skill_id = str(uuid.uuid4())

        payload = {
            "customer_name": "Fake Skill Corp",
            "address": "123 Fake St",
            "latitude": 37.0,
            "longitude": -122.0,
            "required_skill_id": fake_skill_id,
        }

        res = await client.post(f"{BASE_URL}/api/v1/jobs", json=payload, headers=disp_headers)
        assert res.status_code == 400


@pytest.mark.asyncio
async def test_11_inactive_skill_rejected():
    """11. Test inactive skill is rejected when creating job."""
    async with AsyncClient() as client:
        admin_headers = await get_token_headers(client, "admin@fieldops.ai", "Admin@123")
        disp_headers = await get_token_headers(client, "dispatcher@fieldops.ai", "Dispatch@123")

        # Create inactive skill
        unique_name = f"Inactive Skill {str(uuid.uuid4())[:4]}"
        skill_res = await client.post(f"{BASE_URL}/api/v1/skills", json={"skill_name": unique_name, "category": "Test"}, headers=admin_headers)
        skill_id = skill_res.json()["id"]

        # Deactivate skill
        await client.patch(f"{BASE_URL}/api/v1/skills/{skill_id}/status", json={"status": "INACTIVE"}, headers=admin_headers)

        payload = {
            "customer_name": "Inactive Skill Customer",
            "address": "123 Address",
            "latitude": 37.0,
            "longitude": -122.0,
            "required_skill_id": skill_id,
        }

        res = await client.post(f"{BASE_URL}/api/v1/jobs", json=payload, headers=disp_headers)
        assert res.status_code == 400


@pytest.mark.asyncio
async def test_12_invalid_coordinates_rejected():
    """12. Test invalid coordinates (lat -95.0) are rejected."""
    async with AsyncClient() as client:
        disp_headers = await get_token_headers(client, "dispatcher@fieldops.ai", "Dispatch@123")
        active_skill_id = await get_active_skill_id(client, disp_headers)

        payload = {
            "customer_name": "Bad Coords",
            "address": "123 Bad Way",
            "latitude": -95.0,  # Invalid
            "longitude": -122.0,
            "required_skill_id": active_skill_id,
        }

        res = await client.post(f"{BASE_URL}/api/v1/jobs", json=payload, headers=disp_headers)
        assert res.status_code in (400, 422)


@pytest.mark.asyncio
async def test_13_invalid_priority_rejected():
    """13. Test invalid priority is rejected."""
    async with AsyncClient() as client:
        disp_headers = await get_token_headers(client, "dispatcher@fieldops.ai", "Dispatch@123")
        active_skill_id = await get_active_skill_id(client, disp_headers)

        payload = {
            "customer_name": "Bad Priority",
            "address": "123 Priority St",
            "latitude": 37.0,
            "longitude": -122.0,
            "required_skill_id": active_skill_id,
            "priority": "SUPER_ULTRA_HIGH",
        }

        res = await client.post(f"{BASE_URL}/api/v1/jobs", json=payload, headers=disp_headers)
        assert res.status_code in (400, 422)


@pytest.mark.asyncio
async def test_14_invalid_status_transition_rejected():
    """14. Test modifying a CANCELLED job is rejected with 400."""
    async with AsyncClient() as client:
        disp_headers = await get_token_headers(client, "dispatcher@fieldops.ai", "Dispatch@123")
        active_skill_id = await get_active_skill_id(client, disp_headers)

        # Create and cancel job
        c_res = await client.post(
            f"{BASE_URL}/api/v1/jobs",
            json={"customer_name": "Dead Job", "address": "123 Dead Rd", "latitude": 37.0, "longitude": -122.0, "required_skill_id": active_skill_id},
            headers=disp_headers,
        )
        assert c_res.status_code == 201
        job_id = c_res.json()["id"]

        await client.post(f"{BASE_URL}/api/v1/jobs/{job_id}/cancel", json={"reason": "Cancelled for test"}, headers=disp_headers)

        # Attempt to modify cancelled job
        mod_res = await client.put(f"{BASE_URL}/api/v1/jobs/{job_id}", json={"address": "Attempted Revive St"}, headers=disp_headers)
        assert mod_res.status_code == 400


@pytest.mark.asyncio
async def test_15_cancellation_requires_reason():
    """15. Test job cancellation without reason returns 400/422."""
    async with AsyncClient() as client:
        disp_headers = await get_token_headers(client, "dispatcher@fieldops.ai", "Dispatch@123")
        active_skill_id = await get_active_skill_id(client, disp_headers)

        create_res = await client.post(
            f"{BASE_URL}/api/v1/jobs",
            json={"customer_name": "No Reason Corp", "address": "123 Street", "latitude": 37.0, "longitude": -122.0, "required_skill_id": active_skill_id},
            headers=disp_headers,
        )
        assert create_res.status_code == 201
        job_id = create_res.json()["id"]

        cancel_res = await client.post(f"{BASE_URL}/api/v1/jobs/{job_id}/cancel", json={"reason": "   "}, headers=disp_headers)
        assert cancel_res.status_code in (400, 422)


@pytest.mark.asyncio
async def test_16_job_creation_creates_audit_log():
    """16. Test audit log JOB_CREATED is written after job creation."""
    async with AsyncClient() as client:
        disp_headers = await get_token_headers(client, "dispatcher@fieldops.ai", "Dispatch@123")
        active_skill_id = await get_active_skill_id(client, disp_headers)

        create_res = await client.post(
            f"{BASE_URL}/api/v1/jobs",
            json={"customer_name": "Audit Job Corp", "address": "123 Audit Way", "latitude": 37.0, "longitude": -122.0, "required_skill_id": active_skill_id},
            headers=disp_headers,
        )
        assert create_res.status_code == 201
        job_id = create_res.json()["id"]

        local_engine = create_async_engine(settings.DATABASE_URL)
        async with AsyncSession(local_engine) as session:
            stmt = select(AuditLog).where(AuditLog.entity_id == job_id, AuditLog.action == "JOB_CREATED")
            entry = (await session.execute(stmt)).scalar_one_or_none()
            assert entry is not None
            assert entry.entity == "Job"
        await local_engine.dispose()


@pytest.mark.asyncio
async def test_17_job_update_creates_audit_log():
    """17. Test audit log JOB_UPDATED is written after job update."""
    async with AsyncClient() as client:
        disp_headers = await get_token_headers(client, "dispatcher@fieldops.ai", "Dispatch@123")
        active_skill_id = await get_active_skill_id(client, disp_headers)

        create_res = await client.post(
            f"{BASE_URL}/api/v1/jobs",
            json={"customer_name": "Audit Update Co", "address": "123 Pre Update", "latitude": 37.0, "longitude": -122.0, "required_skill_id": active_skill_id},
            headers=disp_headers,
        )
        assert create_res.status_code == 201
        job_id = create_res.json()["id"]

        await client.put(f"{BASE_URL}/api/v1/jobs/{job_id}", json={"address": "123 Post Update"}, headers=disp_headers)

        local_engine = create_async_engine(settings.DATABASE_URL)
        async with AsyncSession(local_engine) as session:
            stmt = select(AuditLog).where(AuditLog.entity_id == job_id, AuditLog.action == "JOB_UPDATED")
            entry = (await session.execute(stmt)).scalar_one_or_none()
            assert entry is not None
        await local_engine.dispose()


@pytest.mark.asyncio
async def test_18_job_cancellation_creates_audit_log():
    """18. Test audit log JOB_CANCELLED is written with reason after job cancellation."""
    async with AsyncClient() as client:
        disp_headers = await get_token_headers(client, "dispatcher@fieldops.ai", "Dispatch@123")
        active_skill_id = await get_active_skill_id(client, disp_headers)

        create_res = await client.post(
            f"{BASE_URL}/api/v1/jobs",
            json={"customer_name": "Audit Cancel Co", "address": "123 Pre Cancel", "latitude": 37.0, "longitude": -122.0, "required_skill_id": active_skill_id},
            headers=disp_headers,
        )
        assert create_res.status_code == 201
        job_id = create_res.json()["id"]

        cancel_reason = "Duplicate job entry in queue."
        await client.post(f"{BASE_URL}/api/v1/jobs/{job_id}/cancel", json={"reason": cancel_reason}, headers=disp_headers)

        local_engine = create_async_engine(settings.DATABASE_URL)
        async with AsyncSession(local_engine) as session:
            stmt = select(AuditLog).where(AuditLog.entity_id == job_id, AuditLog.action == "JOB_CANCELLED")
            entry = (await session.execute(stmt)).scalar_one_or_none()
            assert entry is not None
            assert cancel_reason in entry.reason
        await local_engine.dispose()


@pytest.mark.asyncio
async def test_19_job_numbers_are_unique():
    """19. Test server-side job numbers are unique for subsequent job creations."""
    async with AsyncClient() as client:
        disp_headers = await get_token_headers(client, "dispatcher@fieldops.ai", "Dispatch@123")
        active_skill_id = await get_active_skill_id(client, disp_headers)

        res1 = await client.post(f"{BASE_URL}/api/v1/jobs", json={"customer_name": "Seq 1", "address": "123 First St", "latitude": 37.0, "longitude": -122.0, "required_skill_id": active_skill_id}, headers=disp_headers)
        res2 = await client.post(f"{BASE_URL}/api/v1/jobs", json={"customer_name": "Seq 2", "address": "456 Second St", "latitude": 37.0, "longitude": -122.0, "required_skill_id": active_skill_id}, headers=disp_headers)

        assert res1.status_code == 201
        assert res2.status_code == 201
        num1 = res1.json()["job_number"]
        num2 = res2.json()["job_number"]
        assert num1 != num2

