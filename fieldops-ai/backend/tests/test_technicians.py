"""
Unit and Integration tests for Technician Management end-to-end module.
Covers RBAC, CRUD operations, validation errors, security authorization, and audit logging.
"""

import uuid
import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from app.core.config import settings
from app.models.audit_log import AuditLog

BASE_URL = "http://127.0.0.1:8000"


async def get_token_headers(client: AsyncClient, email: str, password: str) -> dict[str, str]:
    """Helper to authenticate and get Bearer token headers."""
    res = await client.post(f"{BASE_URL}/api/v1/auth/login", json={"email": email, "password": password})
    assert res.status_code == 200, f"Login failed for {email}: {res.text}"
    token = res.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_1_admin_can_create_technician():
    """1. Test Administrator can create a new technician."""
    async with AsyncClient() as client:
        admin_headers = await get_token_headers(client, "admin@fieldops.ai", "Admin@123")

        # Get primary skill ID from list
        tech_list = await client.get(f"{BASE_URL}/api/v1/technicians", headers=admin_headers)
        assert tech_list.status_code == 200
        items = tech_list.json()["items"]
        assert len(items) > 0
        skill_id = items[0]["primary_skill_id"]

        unique_code = f"T-TEST-{str(uuid.uuid4())[:6].upper()}"
        unique_email = f"tech_{str(uuid.uuid4())[:6]}@fieldops.ai"

        payload = {
            "employee_code": unique_code,
            "full_name": "Test Technician User",
            "email": unique_email,
            "password": "Password@123",
            "phone": "+15551234567",
            "primary_skill_id": skill_id,
            "years_experience": 4,
            "availability_status": "AVAILABLE",
        }

        res = await client.post(f"{BASE_URL}/api/v1/technicians", json=payload, headers=admin_headers)
        assert res.status_code == 201
        data = res.json()
        assert data["employee_code"] == unique_code
        assert data["user"]["email"] == unique_email
        assert data["years_experience"] == 4


@pytest.mark.asyncio
async def test_2_admin_can_update_technician():
    """2. Test Administrator can update technician details."""
    async with AsyncClient() as client:
        admin_headers = await get_token_headers(client, "admin@fieldops.ai", "Admin@123")

        # Get skill id
        res_list = await client.get(f"{BASE_URL}/api/v1/technicians", headers=admin_headers)
        assert res_list.status_code == 200
        skill_id = res_list.json()["items"][0]["primary_skill_id"]

        # Create temporary technician for updating
        temp_code = f"T-UPD-{str(uuid.uuid4())[:6].upper()}"
        temp_email = f"upd_{str(uuid.uuid4())[:6]}@fieldops.ai"

        create_res = await client.post(
            f"{BASE_URL}/api/v1/technicians",
            json={
                "employee_code": temp_code,
                "full_name": "Pre-Update Tech Name",
                "email": temp_email,
                "password": "Password@123",
                "phone": "+15550001111",
                "primary_skill_id": skill_id,
                "years_experience": 2,
                "availability_status": "AVAILABLE",
            },
            headers=admin_headers,
        )
        assert create_res.status_code == 201
        tech_id = create_res.json()["id"]

        update_payload = {
            "full_name": "Updated Technician Name",
            "years_experience": 7,
        }

        res = await client.put(f"{BASE_URL}/api/v1/technicians/{tech_id}", json=update_payload, headers=admin_headers)
        assert res.status_code == 200
        data = res.json()
        assert data["user"]["full_name"] == "Updated Technician Name"
        assert data["years_experience"] == 7

        # Clean up temporary technician
        await client.delete(f"{BASE_URL}/api/v1/technicians/{tech_id}", headers=admin_headers)


@pytest.mark.asyncio
async def test_3_admin_can_deactivate_technician():
    """3. Test Administrator can deactivate technician."""
    async with AsyncClient() as client:
        admin_headers = await get_token_headers(client, "admin@fieldops.ai", "Admin@123")

        # First create a temporary technician to deactivate
        res_list = await client.get(f"{BASE_URL}/api/v1/technicians", headers=admin_headers)
        skill_id = res_list.json()["items"][0]["primary_skill_id"]

        temp_code = f"T-DEL-{str(uuid.uuid4())[:6].upper()}"
        temp_email = f"del_{str(uuid.uuid4())[:6]}@fieldops.ai"

        create_res = await client.post(
            f"{BASE_URL}/api/v1/technicians",
            json={
                "employee_code": temp_code,
                "full_name": "Deactivate Me",
                "email": temp_email,
                "password": "Password@123",
                "primary_skill_id": skill_id,
                "years_experience": 2,
            },
            headers=admin_headers,
        )
        assert create_res.status_code == 201
        temp_id = create_res.json()["id"]

        # Deactivate
        del_res = await client.delete(f"{BASE_URL}/api/v1/technicians/{temp_id}", headers=admin_headers)
        assert del_res.status_code == 204


@pytest.mark.asyncio
async def test_4_dispatcher_can_view_technicians():
    """4. Test Dispatcher can view technician directory."""
    async with AsyncClient() as client:
        disp_headers = await get_token_headers(client, "dispatcher@fieldops.ai", "Dispatch@123")

        res = await client.get(f"{BASE_URL}/api/v1/technicians", headers=disp_headers)
        assert res.status_code == 200
        data = res.json()
        assert "items" in data
        assert data["total"] > 0


@pytest.mark.asyncio
async def test_5_dispatcher_cannot_modify_technicians():
    """5. Test Dispatcher cannot create, update, deactivate, or patch status (403 Forbidden)."""
    async with AsyncClient() as client:
        disp_headers = await get_token_headers(client, "dispatcher@fieldops.ai", "Dispatch@123")

        fake_id = str(uuid.uuid4())

        # POST
        post_res = await client.post(
            f"{BASE_URL}/api/v1/technicians",
            json={
                "employee_code": "DISP-HACK",
                "full_name": "Hack",
                "email": "hack@fieldops.ai",
                "password": "Password@123",
                "primary_skill_id": fake_id,
            },
            headers=disp_headers,
        )
        assert post_res.status_code == 403

        # PUT
        put_res = await client.put(f"{BASE_URL}/api/v1/technicians/{fake_id}", json={"full_name": "Hack"}, headers=disp_headers)
        assert put_res.status_code == 403

        # PATCH status
        patch_res = await client.patch(f"{BASE_URL}/api/v1/technicians/{fake_id}/status", json={"availability_status": "OFF_DUTY"}, headers=disp_headers)
        assert patch_res.status_code == 403

        # DELETE
        del_res = await client.delete(f"{BASE_URL}/api/v1/technicians/{fake_id}", headers=disp_headers)
        assert del_res.status_code == 403


@pytest.mark.asyncio
async def test_6_technician_can_view_own_profile():
    """6. Test Technician can view own profile via /me."""
    async with AsyncClient() as client:
        tech_headers = await get_token_headers(client, "technician@fieldops.ai", "Tech@123")

        res = await client.get(f"{BASE_URL}/api/v1/technicians/me", headers=tech_headers)
        assert res.status_code == 200
        data = res.json()
        assert data["user"]["email"] == "technician@fieldops.ai"


@pytest.mark.asyncio
async def test_7_technician_cannot_access_another_technician():
    """7. Test Technician cannot access another technician's profile by ID (403 Forbidden)."""
    async with AsyncClient() as client:
        tech_headers = await get_token_headers(client, "technician@fieldops.ai", "Tech@123")
        other_tech_id = str(uuid.uuid4())

        res = await client.get(f"{BASE_URL}/api/v1/technicians/{other_tech_id}", headers=tech_headers)
        assert res.status_code == 403


@pytest.mark.asyncio
async def test_8_duplicate_employee_code_rejected():
    """8. Test duplicate employee code is rejected with 409 Conflict."""
    async with AsyncClient() as client:
        admin_headers = await get_token_headers(client, "admin@fieldops.ai", "Admin@123")

        res_list = await client.get(f"{BASE_URL}/api/v1/technicians", headers=admin_headers)
        existing_code = res_list.json()["items"][0]["employee_code"]
        skill_id = res_list.json()["items"][0]["primary_skill_id"]

        dup_payload = {
            "employee_code": existing_code,
            "full_name": "Duplicate Code Tech",
            "email": f"dup_{str(uuid.uuid4())[:6]}@fieldops.ai",
            "password": "Password@123",
            "primary_skill_id": skill_id,
        }

        res = await client.post(f"{BASE_URL}/api/v1/technicians", json=dup_payload, headers=admin_headers)
        assert res.status_code == 409


@pytest.mark.asyncio
async def test_9_invalid_experience_rejected():
    """9. Test negative experience is rejected with 422/400 validation error."""
    async with AsyncClient() as client:
        admin_headers = await get_token_headers(client, "admin@fieldops.ai", "Admin@123")

        res_list = await client.get(f"{BASE_URL}/api/v1/technicians", headers=admin_headers)
        skill_id = res_list.json()["items"][0]["primary_skill_id"]

        invalid_payload = {
            "employee_code": f"NEG-{str(uuid.uuid4())[:4]}",
            "full_name": "Negative Experience",
            "email": f"neg_{str(uuid.uuid4())[:6]}@fieldops.ai",
            "password": "Password@123",
            "primary_skill_id": skill_id,
            "years_experience": -5,
        }

        res = await client.post(f"{BASE_URL}/api/v1/technicians", json=invalid_payload, headers=admin_headers)
        assert res.status_code in (400, 422)


@pytest.mark.asyncio
async def test_10_audit_log_created_after_mutation():
    """10. Test audit log is created after technician mutation."""
    async with AsyncClient() as client:
        admin_headers = await get_token_headers(client, "admin@fieldops.ai", "Admin@123")

        res_list = await client.get(f"{BASE_URL}/api/v1/technicians", headers=admin_headers)
        skill_id = res_list.json()["items"][0]["primary_skill_id"]

        audit_code = f"AUD-{str(uuid.uuid4())[:6].upper()}"
        audit_email = f"audit_{str(uuid.uuid4())[:6]}@fieldops.ai"

        create_res = await client.post(
            f"{BASE_URL}/api/v1/technicians",
            json={
                "employee_code": audit_code,
                "full_name": "Audit Test Tech",
                "email": audit_email,
                "password": "Password@123",
                "primary_skill_id": skill_id,
            },
            headers=admin_headers,
        )
        assert create_res.status_code == 201
        created_tech_id = create_res.json()["id"]

        # Verify audit record created in database
        local_engine = create_async_engine(settings.DATABASE_URL)
        async with AsyncSession(local_engine) as session:
            stmt = select(AuditLog).where(AuditLog.entity_id == created_tech_id)
            audit_entry = (await session.execute(stmt)).scalar_one_or_none()
            assert audit_entry is not None
            assert audit_entry.action == "TECHNICIAN_CREATED"
            assert audit_entry.entity == "Technician"
        await local_engine.dispose()
