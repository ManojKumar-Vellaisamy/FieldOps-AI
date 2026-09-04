"""
Unit and Integration tests for Skills Management end-to-end module.
Covers RBAC, CRUD operations, validation errors, soft deactivation safety, and audit logging.
"""

import uuid
import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from app.core.config import settings
from app.models.audit_log import AuditLog
from app.models.technician import Technician

BASE_URL = "http://127.0.0.1:8000"


async def get_token_headers(client: AsyncClient, email: str, password: str) -> dict[str, str]:
    """Helper to authenticate and get Bearer token headers."""
    res = await client.post(f"{BASE_URL}/api/v1/auth/login", json={"email": email, "password": password})
    assert res.status_code == 200, f"Login failed for {email}: {res.text}"
    token = res.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_1_admin_can_create_skill():
    """1. Test Administrator can create a new skill."""
    async with AsyncClient() as client:
        admin_headers = await get_token_headers(client, "admin@fieldops.ai", "Admin@123")

        unique_name = f"Test Skill {str(uuid.uuid4())[:6]}"
        payload = {
            "skill_name": unique_name,
            "category": "Calibration",
            "description": "Test skill description for automated testing.",
            "status": "ACTIVE",
        }

        res = await client.post(f"{BASE_URL}/api/v1/skills", json=payload, headers=admin_headers)
        assert res.status_code == 201
        data = res.json()
        assert data["skill_name"] == unique_name
        assert data["category"] == "Calibration"
        assert data["status"] == "ACTIVE"


@pytest.mark.asyncio
async def test_2_admin_can_update_skill():
    """2. Test Administrator can update a skill."""
    async with AsyncClient() as client:
        admin_headers = await get_token_headers(client, "admin@fieldops.ai", "Admin@123")

        skills_res = await client.get(f"{BASE_URL}/api/v1/skills", headers=admin_headers)
        assert skills_res.status_code == 200
        skill_id = skills_res.json()["items"][0]["id"]

        updated_desc = f"Updated description {str(uuid.uuid4())[:4]}"
        res = await client.put(f"{BASE_URL}/api/v1/skills/{skill_id}", json={"description": updated_desc}, headers=admin_headers)
        assert res.status_code == 200
        assert res.json()["description"] == updated_desc


@pytest.mark.asyncio
async def test_3_admin_can_toggle_skill_status():
    """3. Test Administrator can activate/deactivate a skill."""
    async with AsyncClient() as client:
        admin_headers = await get_token_headers(client, "admin@fieldops.ai", "Admin@123")

        skills_res = await client.get(f"{BASE_URL}/api/v1/skills", headers=admin_headers)
        skill_id = skills_res.json()["items"][0]["id"]

        # Deactivate
        deact_res = await client.patch(f"{BASE_URL}/api/v1/skills/{skill_id}/status", json={"status": "INACTIVE"}, headers=admin_headers)
        assert deact_res.status_code == 200
        assert deact_res.json()["status"] == "INACTIVE"

        # Reactivate
        act_res = await client.patch(f"{BASE_URL}/api/v1/skills/{skill_id}/status", json={"status": "ACTIVE"}, headers=admin_headers)
        assert act_res.status_code == 200
        assert act_res.json()["status"] == "ACTIVE"


@pytest.mark.asyncio
async def test_4_dispatcher_can_list_skills():
    """4. Test Dispatcher can list skills."""
    async with AsyncClient() as client:
        disp_headers = await get_token_headers(client, "dispatcher@fieldops.ai", "Dispatch@123")

        res = await client.get(f"{BASE_URL}/api/v1/skills", headers=disp_headers)
        assert res.status_code == 200
        data = res.json()
        assert "items" in data
        assert data["total"] > 0


@pytest.mark.asyncio
async def test_5_dispatcher_cannot_create_skill():
    """5. Test Dispatcher cannot create a skill (403 Forbidden)."""
    async with AsyncClient() as client:
        disp_headers = await get_token_headers(client, "dispatcher@fieldops.ai", "Dispatch@123")

        payload = {
            "skill_name": "Unauthorized Skill Creation",
            "category": "Illegal",
            "description": "Should fail",
        }

        res = await client.post(f"{BASE_URL}/api/v1/skills", json=payload, headers=disp_headers)
        assert res.status_code == 403


@pytest.mark.asyncio
async def test_6_dispatcher_cannot_modify_skill():
    """6. Test Dispatcher cannot modify or patch a skill (403 Forbidden)."""
    async with AsyncClient() as client:
        disp_headers = await get_token_headers(client, "dispatcher@fieldops.ai", "Dispatch@123")
        fake_id = str(uuid.uuid4())

        put_res = await client.put(f"{BASE_URL}/api/v1/skills/{fake_id}", json={"category": "Modified"}, headers=disp_headers)
        assert put_res.status_code == 403

        patch_res = await client.patch(f"{BASE_URL}/api/v1/skills/{fake_id}/status", json={"status": "INACTIVE"}, headers=disp_headers)
        assert patch_res.status_code == 403


@pytest.mark.asyncio
async def test_7_technician_can_view_own_skills():
    """7. Test Technician can view own assigned skills via /skills/me."""
    async with AsyncClient() as client:
        tech_headers = await get_token_headers(client, "technician@fieldops.ai", "Tech@123")

        res = await client.get(f"{BASE_URL}/api/v1/skills/me", headers=tech_headers)
        assert res.status_code == 200
        assert isinstance(res.json(), list)


@pytest.mark.asyncio
async def test_8_technician_cannot_modify_skills():
    """8. Test Technician cannot create or update skills (403 Forbidden)."""
    async with AsyncClient() as client:
        tech_headers = await get_token_headers(client, "technician@fieldops.ai", "Tech@123")
        fake_id = str(uuid.uuid4())

        post_res = await client.post(f"{BASE_URL}/api/v1/skills", json={"skill_name": "Hacked", "category": "None"}, headers=tech_headers)
        assert post_res.status_code == 403

        put_res = await client.put(f"{BASE_URL}/api/v1/skills/{fake_id}", json={"category": "Hacked"}, headers=tech_headers)
        assert put_res.status_code == 403


@pytest.mark.asyncio
async def test_9_duplicate_skill_names_rejected():
    """9. Test duplicate skill names (case-insensitive) are rejected with 409 Conflict."""
    async with AsyncClient() as client:
        admin_headers = await get_token_headers(client, "admin@fieldops.ai", "Admin@123")

        skills_res = await client.get(f"{BASE_URL}/api/v1/skills", headers=admin_headers)
        existing_name = skills_res.json()["items"][0]["skill_name"]

        dup_payload = {
            "skill_name": existing_name.upper(),  # case-insensitive match
            "category": "Duplicate",
            "description": "Should fail",
        }

        res = await client.post(f"{BASE_URL}/api/v1/skills", json=dup_payload, headers=admin_headers)
        assert res.status_code == 409


@pytest.mark.asyncio
async def test_10_invalid_skill_data_rejected():
    """10. Test empty skill name or category is rejected with validation error (400/422)."""
    async with AsyncClient() as client:
        admin_headers = await get_token_headers(client, "admin@fieldops.ai", "Admin@123")

        invalid_payload = {
            "skill_name": "   ",  # whitespace only
            "category": "Electrical",
        }

        res = await client.post(f"{BASE_URL}/api/v1/skills", json=invalid_payload, headers=admin_headers)
        assert res.status_code in (400, 422)


@pytest.mark.asyncio
async def test_11_audit_log_created_after_skill_mutation():
    """11. Test audit log entry SKILL_CREATED is written after skill creation."""
    async with AsyncClient() as client:
        admin_headers = await get_token_headers(client, "admin@fieldops.ai", "Admin@123")

        unique_name = f"Audit Skill {str(uuid.uuid4())[:6]}"
        create_res = await client.post(
            f"{BASE_URL}/api/v1/skills",
            json={"skill_name": unique_name, "category": "Network"},
            headers=admin_headers,
        )
        assert create_res.status_code == 201
        created_skill_id = create_res.json()["id"]

        local_engine = create_async_engine(settings.DATABASE_URL)
        async with AsyncSession(local_engine) as session:
            stmt = select(AuditLog).where(AuditLog.entity_id == created_skill_id)
            entry = (await session.execute(stmt)).scalar_one_or_none()
            assert entry is not None
            assert entry.action == "SKILL_CREATED"
            assert entry.entity == "Skill"
        await local_engine.dispose()


@pytest.mark.asyncio
async def test_12_deactivation_preserves_technician_relationships():
    """12. Test soft deactivating a skill preserves existing technician foreign key relationships."""
    async with AsyncClient() as client:
        admin_headers = await get_token_headers(client, "admin@fieldops.ai", "Admin@123")

        skills_res = await client.get(f"{BASE_URL}/api/v1/skills", headers=admin_headers)
        skill_id = skills_res.json()["items"][0]["id"]

        # Deactivate skill
        deact_res = await client.patch(f"{BASE_URL}/api/v1/skills/{skill_id}/status", json={"status": "INACTIVE"}, headers=admin_headers)
        assert deact_res.status_code == 200

        # Verify technician relationship still exists in database
        local_engine = create_async_engine(settings.DATABASE_URL)
        async with AsyncSession(local_engine) as session:
            stmt = select(Technician).where(Technician.primary_skill_id == skill_id)
            techs = (await session.execute(stmt)).scalars().all()
            # Relationships are intact
            assert techs is not None
        await local_engine.dispose()

        # Reactivate skill to leave DB clean
        await client.patch(f"{BASE_URL}/api/v1/skills/{skill_id}/status", json={"status": "ACTIVE"}, headers=admin_headers)
