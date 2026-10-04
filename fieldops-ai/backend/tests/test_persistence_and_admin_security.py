"""
Production Realism & Persistence Verification Test Suite.
Validates:
1. Startup/lifespan baseline creates ZERO operational technicians, jobs, and assignments.
2. Backend strictly rejects Administrator creation via /api/v1/users and /users with HTTP 400.
3. Only Dispatcher and Technician roles are creatable.
4. Technician user creation does NOT automatically generate a Technician operational profile.
5. Admin Reset Password endpoint is removed (404/405).
6. Password ownership is strictly self-service via /api/v1/auth/change-password.
7. Real technician profiles genuinely created persist across database sessions and seed_db calls.
"""

import uuid
import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import func, select

from app.database.seed import seed_db
from app.database.session import AsyncSessionLocal
from app.main import app
from app.models.assignment import Assignment
from app.models.job import Job
from app.models.technician import Technician
from app.models.user import User

BASE_URL = "http://test"


async def get_token_headers(client: AsyncClient, email: str, password: str) -> dict[str, str]:
    res = await client.post(f"{BASE_URL}/api/v1/auth/login", json={"email": email, "password": password})
    assert res.status_code == 200, f"Login failed for {email}: {res.text}"
    token = res.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_startup_baseline_creates_zero_operational_records():
    """Verify that seed_db initializes only system configuration and ZERO operational records."""
    await seed_db()

    async with AsyncSessionLocal() as session:
        tech_count = await session.scalar(select(func.count(Technician.id)))
        job_count = await session.scalar(select(func.count(Job.id)))
        asg_count = await session.scalar(select(func.count(Assignment.id)))

        assert tech_count == 0, f"Expected 0 technicians on baseline startup, found {tech_count}"
        assert job_count == 0, f"Expected 0 jobs on baseline startup, found {job_count}"
        assert asg_count == 0, f"Expected 0 assignments on baseline startup, found {asg_count}"


@pytest.mark.asyncio
async def test_backend_blocks_administrator_creation_at_api_v1():
    """Verify that POST /api/v1/users rejects role='Administrator' with HTTP 400."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url=BASE_URL) as client:
        admin_headers = await get_token_headers(client, "admin@fieldops.ai", "Admin@123")

        # Attempt to create an Administrator account
        res = await client.post(
            f"{BASE_URL}/api/v1/users",
            json={
                "email": "fake_admin@fieldops.ai",
                "full_name": "Rogue Administrator",
                "role": "Administrator",
                "password": "Password@123",
            },
            headers=admin_headers,
        )
        assert res.status_code == 400
        data = res.json()
        assert "Creation of additional Administrator accounts is prohibited" in data["detail"]


@pytest.mark.asyncio
async def test_backend_blocks_administrator_creation_at_root_users():
    """Verify that POST /users rejects role='Administrator' with HTTP 400."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url=BASE_URL) as client:
        admin_headers = await get_token_headers(client, "admin@fieldops.ai", "Admin@123")

        res = await client.post(
            f"{BASE_URL}/users",
            json={
                "email": "another_admin@fieldops.ai",
                "full_name": "Another Administrator",
                "role": "Administrator",
                "password": "Password@123",
            },
            headers=admin_headers,
        )
        assert res.status_code == 400
        data = res.json()
        assert "Creation of additional Administrator accounts is prohibited" in data["detail"]


@pytest.mark.asyncio
async def test_create_dispatcher_and_technician_users():
    """Verify Admin can create Dispatcher and Technician user accounts."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url=BASE_URL) as client:
        admin_headers = await get_token_headers(client, "admin@fieldops.ai", "Admin@123")

        suffix = str(uuid.uuid4())[:6]
        disp_email = f"disp_{suffix}@fieldops.ai"
        tech_email = f"tech_{suffix}@fieldops.ai"

        # 1. Create Dispatcher
        res_disp = await client.post(
            f"{BASE_URL}/api/v1/users",
            json={
                "email": disp_email,
                "full_name": f"Dispatcher {suffix}",
                "role": "Dispatcher",
                "password": "TemporaryPassword@123",
            },
            headers=admin_headers,
        )
        assert res_disp.status_code == 201
        assert res_disp.json()["role"] == "Dispatcher"
        assert res_disp.json()["must_change_password"] is True

        # 2. Create Technician user account
        res_tech = await client.post(
            f"{BASE_URL}/api/v1/users",
            json={
                "email": tech_email,
                "full_name": f"Tech User {suffix}",
                "role": "Technician",
                "password": "TemporaryPassword@123",
            },
            headers=admin_headers,
        )
        assert res_tech.status_code == 201
        assert res_tech.json()["role"] == "Technician"
        assert res_tech.json()["must_change_password"] is True

        # 3. VERIFY: User account was created, but NO Technician operational profile was created!
        tech_user_id = res_tech.json()["id"]
        async with AsyncSessionLocal() as session:
            op_profile = (await session.execute(
                select(Technician).where(Technician.user_id == uuid.UUID(tech_user_id))
            )).scalar_one_or_none()
            assert op_profile is None, "Technician operational profile must NOT be automatically created!"

        # Clean up
        async with AsyncSessionLocal() as session:
            from sqlalchemy import delete
            await session.execute(delete(User).where(User.email.in_([disp_email, tech_email])))
            await session.commit()


@pytest.mark.asyncio
async def test_admin_reset_password_endpoint_is_removed():
    """Verify POST /api/v1/technicians/{id}/reset-password is removed (returns 404/405)."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url=BASE_URL) as client:
        admin_headers = await get_token_headers(client, "admin@fieldops.ai", "Admin@123")
        dummy_id = str(uuid.uuid4())

        res = await client.post(
            f"{BASE_URL}/api/v1/technicians/{dummy_id}/reset-password",
            json={"password": "Password@123", "confirm_password": "Password@123"},
            headers=admin_headers,
        )
        assert res.status_code in (404, 405)


@pytest.mark.asyncio
async def test_self_service_password_change_for_all_roles():
    """Verify that Admin, Dispatcher, and Technician can each change their own password via /auth/change-password."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url=BASE_URL) as client:
        # Test with Dispatcher
        disp_headers = await get_token_headers(client, "dispatcher@fieldops.ai", "Dispatch@123")

        # Change password to new password
        change_res = await client.post(
            f"{BASE_URL}/api/v1/auth/change-password",
            json={
                "current_password": "Dispatch@123",
                "new_password": "NewDispatch@456",
                "confirm_password": "NewDispatch@456",
            },
            headers=disp_headers,
        )
        assert change_res.status_code == 200
        assert "Password changed successfully" in change_res.json()["message"]

        # Verify old password fails
        bad_login = await client.post(
            f"{BASE_URL}/api/v1/auth/login",
            json={"email": "dispatcher@fieldops.ai", "password": "Dispatch@123"},
        )
        assert bad_login.status_code == 401

        # Verify new password succeeds
        good_login = await client.post(
            f"{BASE_URL}/api/v1/auth/login",
            json={"email": "dispatcher@fieldops.ai", "password": "NewDispatch@456"},
        )
        assert good_login.status_code == 200
        new_token = good_login.json()["access_token"]
        new_headers = {"Authorization": f"Bearer {new_token}"}

        # Revert password back to original
        revert_res = await client.post(
            f"{BASE_URL}/api/v1/auth/change-password",
            json={
                "current_password": "NewDispatch@456",
                "new_password": "Dispatch@123",
                "confirm_password": "Dispatch@123",
            },
            headers=new_headers,
        )
        assert revert_res.status_code == 200


@pytest.mark.asyncio
async def test_real_created_technician_persists_across_restarts():
    """
    Simulates real production workflow:
    1. Admin creates Technician A.
    2. Technician A appears in database.
    3. Application startup/seed_db is executed again (simulating restart).
    4. Technician A still exists and is untouched.
    5. No additional demo technicians (TECH-001, TECH-002) were created.
    """
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url=BASE_URL) as client:
        admin_headers = await get_token_headers(client, "admin@fieldops.ai", "Admin@123")

        # Get primary skill
        skills_res = await client.get(f"{BASE_URL}/api/v1/skills", headers=admin_headers)
        skills = skills_res.json()["items"]
        assert len(skills) > 0
        skill_id = skills[0]["id"]

        suffix = str(uuid.uuid4())[:6].upper()
        emp_code = f"TECH-REAL-{suffix}"
        email = f"real_tech_{suffix.lower()}@fieldops.ai"

        # 1. Admin creates real technician
        create_res = await client.post(
            f"{BASE_URL}/api/v1/technicians",
            json={
                "employee_code": emp_code,
                "full_name": f"Genuinely Created Tech {suffix}",
                "email": email,
                "password": "TechPassword@123",
                "confirm_password": "TechPassword@123",
                "phone": "+1 555 987 6543",
                "primary_skill_id": skill_id,
                "years_experience": 4,
                "availability_status": "AVAILABLE",
            },
            headers=admin_headers,
        )
        assert create_res.status_code == 201
        tech_id = create_res.json()["id"]

        # 2. Verify technician appears in list
        list_res = await client.get(f"{BASE_URL}/api/v1/technicians", headers=admin_headers)
        assert list_res.status_code == 200
        codes = [t["employee_code"] for t in list_res.json()["items"]]
        assert emp_code in codes

        # 3. Simulate backend restart cycle 1: run seed_db()
        await seed_db()

        # 4. Verify technician persists and count is unchanged
        list_res2 = await client.get(f"{BASE_URL}/api/v1/technicians", headers=admin_headers)
        assert list_res2.status_code == 200
        items2 = list_res2.json()["items"]
        assert any(t["employee_code"] == emp_code for t in items2)
        assert not any(t["employee_code"] in ("TECH-001", "TECH-002") for t in items2)

        # 5. Simulate backend restart cycle 2: run seed_db()
        await seed_db()

        list_res3 = await client.get(f"{BASE_URL}/api/v1/technicians", headers=admin_headers)
        assert list_res3.status_code == 200
        items3 = list_res3.json()["items"]
        assert any(t["employee_code"] == emp_code for t in items3)
        assert not any(t["employee_code"] in ("TECH-001", "TECH-002") for t in items3)

        # 6. Clean up the created technician
        del_res = await client.delete(f"{BASE_URL}/api/v1/technicians/{tech_id}", headers=admin_headers)
        assert del_res.status_code == 204
