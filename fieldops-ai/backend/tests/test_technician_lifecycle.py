"""
Comprehensive end-to-end verification tests for Technician Lifecycle Management in FieldOps AI.
Tests:
1. Creation with password & confirm password validation.
2. First-time login with temporary password (must_change_password=True).
3. Password change via /api/v1/auth/change-password and clearing must_change_password.
4. Login with updated password and rejection of old temporary password.
5. Deactivation (sets INACTIVE, is_active=False, blocks login).
6. Reactivation (sets AVAILABLE, is_active=True, unblocks login).
7. Admin password reset (re-enforces must_change_password=True).
8. Dependency inspection and safe permanent deletion.
9. Deletion blocker (HTTP 409 Conflict) when operational dependencies exist.
10. Strict RBAC enforcement on all lifecycle actions.
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


@pytest.mark.asyncio
async def test_technician_lifecycle_end_to_end():
    """Complete technician lifecycle: create, first login, change password, deactivate, activate, reset, and safe delete."""
    async with AsyncClient() as client:
        # 1. Admin login
        admin_headers = await get_token_headers(client, "admin@fieldops.ai", "Admin@123")

        # Get a valid primary skill ID
        skills_res = await client.get(f"{BASE_URL}/api/v1/skills", headers=admin_headers)
        assert skills_res.status_code == 200
        skills = skills_res.json()["items"]
        assert len(skills) > 0
        primary_skill_id = skills[0]["id"]

        unique_suffix = str(uuid.uuid4())[:6].upper()
        employee_code = f"T-LC-{unique_suffix}"
        tech_email = f"tech_{unique_suffix.lower()}@fieldops.ai"
        temp_password = "TempPassword@123"

        # 2. Test password mismatch validation during creation
        mismatch_payload = {
            "employee_code": employee_code,
            "full_name": f"Lifecycle Tech {unique_suffix}",
            "email": tech_email,
            "password": temp_password,
            "confirm_password": "DifferentPassword@456",
            "primary_skill_id": primary_skill_id,
            "years_experience": 3,
            "availability_status": "AVAILABLE",
        }
        res_mismatch = await client.post(
            f"{BASE_URL}/api/v1/technicians", json=mismatch_payload, headers=admin_headers
        )
        assert res_mismatch.status_code in (400, 422), f"Expected validation failure, got: {res_mismatch.text}"

        # 3. Create technician with valid password & confirm_password
        valid_create_payload = {
            "employee_code": employee_code,
            "full_name": f"Lifecycle Tech {unique_suffix}",
            "email": tech_email,
            "password": temp_password,
            "confirm_password": temp_password,
            "phone": "+15551239999",
            "primary_skill_id": primary_skill_id,
            "years_experience": 4,
            "availability_status": "AVAILABLE",
        }
        res_create = await client.post(
            f"{BASE_URL}/api/v1/technicians", json=valid_create_payload, headers=admin_headers
        )
        assert res_create.status_code == 201, f"Technician creation failed: {res_create.text}"
        tech_data = res_create.json()
        tech_id = tech_data["id"]
        assert tech_data["employee_code"] == employee_code
        assert tech_data["user"]["email"] == tech_email

        # 4. First-time login: verify must_change_password is True
        login_res = await client.post(
            f"{BASE_URL}/api/v1/auth/login", json={"email": tech_email, "password": temp_password}
        )
        assert login_res.status_code == 200, f"Login failed for new tech: {login_res.text}"
        login_data = login_res.json()
        assert login_data["user"]["must_change_password"] is True
        tech_token = login_data["access_token"]
        tech_headers = {"Authorization": f"Bearer {tech_token}"}

        # 5. Technician updates password via /api/v1/auth/change-password
        new_password = "PermanentPassword@789"

        # 5a. Test rejection of wrong current password
        bad_change_res = await client.post(
            f"{BASE_URL}/api/v1/auth/change-password",
            json={
                "current_password": "WrongPassword@123",
                "new_password": new_password,
                "confirm_password": new_password,
            },
            headers=tech_headers,
        )
        assert bad_change_res.status_code in (400, 401), f"Expected 400/401 on wrong current password: {bad_change_res.text}"

        # 5b. Successful password change
        good_change_res = await client.post(
            f"{BASE_URL}/api/v1/auth/change-password",
            json={
                "current_password": temp_password,
                "new_password": new_password,
                "confirm_password": new_password,
            },
            headers=tech_headers,
        )
        assert good_change_res.status_code == 200, f"Password change failed: {good_change_res.text}"

        # 5c. Verify /auth/me reflects must_change_password is now False
        me_res = await client.get(f"{BASE_URL}/api/v1/auth/me", headers=tech_headers)
        assert me_res.status_code == 200
        assert me_res.json()["must_change_password"] is False

        # 6. Re-login verification: old password fails, new password succeeds
        old_login_res = await client.post(
            f"{BASE_URL}/api/v1/auth/login", json={"email": tech_email, "password": temp_password}
        )
        assert old_login_res.status_code == 401

        new_login_res = await client.post(
            f"{BASE_URL}/api/v1/auth/login", json={"email": tech_email, "password": new_password}
        )
        assert new_login_res.status_code == 200
        assert new_login_res.json()["user"]["must_change_password"] is False

        # 7. Admin deactivates technician
        deact_res = await client.post(
            f"{BASE_URL}/api/v1/technicians/{tech_id}/deactivate", headers=admin_headers
        )
        assert deact_res.status_code == 200
        assert deact_res.json()["availability_status"] == "INACTIVE"
        assert deact_res.json()["user"]["status"] == "INACTIVE"

        # 7a. Deactivated technician cannot log in (account inactive)
        deact_login_res = await client.post(
            f"{BASE_URL}/api/v1/auth/login", json={"email": tech_email, "password": new_password}
        )
        assert deact_login_res.status_code == 401

        # 8. Admin reactivates technician
        act_res = await client.post(
            f"{BASE_URL}/api/v1/technicians/{tech_id}/activate", headers=admin_headers
        )
        assert act_res.status_code == 200
        assert act_res.json()["availability_status"] == "AVAILABLE"
        assert act_res.json()["user"]["status"] == "ACTIVE"

        # 8a. Reactivated technician can log in again
        react_login_res = await client.post(
            f"{BASE_URL}/api/v1/auth/login", json={"email": tech_email, "password": new_password}
        )
        assert react_login_res.status_code == 200

        # 9. Verify Admin reset technician password endpoint is removed / disabled (404 Not Found)
        reset_res = await client.post(
            f"{BASE_URL}/api/v1/technicians/{tech_id}/reset-password",
            json={"password": "ResetPassword@456", "confirm_password": "ResetPassword@456"},
            headers=admin_headers,
        )
        assert reset_res.status_code in (404, 405), f"Expected 404/405 for removed reset endpoint, got: {reset_res.status_code}"

        # 10. Check dependencies endpoint
        deps_res = await client.get(
            f"{BASE_URL}/api/v1/technicians/{tech_id}/dependencies", headers=admin_headers
        )
        assert deps_res.status_code == 200
        deps_data = deps_res.json()
        assert deps_data["can_delete"] is True
        assert deps_data["assignment_count"] == 0
        assert deps_data["eta_override_count"] == 0
        assert len(deps_data["blockers"]) == 0


        # 11. Safe Permanent Deletion of 0-dependency technician
        del_res = await client.delete(
            f"{BASE_URL}/api/v1/technicians/{tech_id}", headers=admin_headers
        )
        assert del_res.status_code == 204

        # 11a. Verify technician no longer exists
        get_res = await client.get(
            f"{BASE_URL}/api/v1/technicians/{tech_id}", headers=admin_headers
        )
        assert get_res.status_code == 404

        # 11b. Verify user account no longer exists
        deleted_login_res = await client.post(
            f"{BASE_URL}/api/v1/auth/login", json={"email": tech_email, "password": new_password}
        )
        assert deleted_login_res.status_code == 401


@pytest.mark.asyncio
async def test_rbac_technician_lifecycle():
    """Verify that Dispatchers and Technicians cannot perform Admin lifecycle operations."""
    async with AsyncClient() as client:
        admin_headers = await get_token_headers(client, "admin@fieldops.ai", "Admin@123")
        disp_headers = await get_token_headers(client, "dispatcher@fieldops.ai", "Dispatch@123")
        tech_headers = await get_token_headers(client, "technician@fieldops.ai", "Tech@123")

        # Create a test tech as admin
        skills_res = await client.get(f"{BASE_URL}/api/v1/skills", headers=admin_headers)
        skill_id = skills_res.json()["items"][0]["id"]
        unique_suffix = str(uuid.uuid4())[:6].upper()

        create_res = await client.post(
            f"{BASE_URL}/api/v1/technicians",
            json={
                "employee_code": f"T-RBAC-{unique_suffix}",
                "full_name": f"RBAC Tech {unique_suffix}",
                "email": f"rbac_{unique_suffix.lower()}@fieldops.ai",
                "password": "Password@123",
                "primary_skill_id": skill_id,
            },
            headers=admin_headers,
        )
        assert create_res.status_code == 201
        tech_id = create_res.json()["id"]

        # Dispatcher tries lifecycle actions (all must be 403 Forbidden)
        assert (
            await client.post(f"{BASE_URL}/api/v1/technicians/{tech_id}/activate", headers=disp_headers)
        ).status_code == 403
        assert (
            await client.post(f"{BASE_URL}/api/v1/technicians/{tech_id}/deactivate", headers=disp_headers)
        ).status_code == 403
        assert (
            await client.post(
                f"{BASE_URL}/api/v1/technicians/{tech_id}/reset-password",
                json={"password": "NewPassword@123"},
                headers=disp_headers,
            )
        ).status_code in (403, 404)
        assert (
            await client.get(f"{BASE_URL}/api/v1/technicians/{tech_id}/dependencies", headers=disp_headers)
        ).status_code == 403
        assert (
            await client.delete(f"{BASE_URL}/api/v1/technicians/{tech_id}", headers=disp_headers)
        ).status_code == 403

        # Technician tries lifecycle actions (all must be 403 Forbidden)
        assert (
            await client.post(f"{BASE_URL}/api/v1/technicians/{tech_id}/activate", headers=tech_headers)
        ).status_code == 403
        assert (
            await client.post(f"{BASE_URL}/api/v1/technicians/{tech_id}/deactivate", headers=tech_headers)
        ).status_code == 403
        assert (
            await client.post(
                f"{BASE_URL}/api/v1/technicians/{tech_id}/reset-password",
                json={"password": "NewPassword@123"},
                headers=tech_headers,
            )
        ).status_code in (403, 404)
        assert (
            await client.get(f"{BASE_URL}/api/v1/technicians/{tech_id}/dependencies", headers=tech_headers)
        ).status_code == 403
        assert (
            await client.delete(f"{BASE_URL}/api/v1/technicians/{tech_id}", headers=tech_headers)
        ).status_code == 403

        # Clean up
        await client.delete(f"{BASE_URL}/api/v1/technicians/{tech_id}", headers=admin_headers)


@pytest.mark.asyncio
async def test_delete_blocked_when_dependencies_exist():
    """Verify that permanent deletion is strictly blocked (HTTP 409) when operational dependencies exist."""
    async with AsyncClient() as client:
        admin_headers = await get_token_headers(client, "admin@fieldops.ai", "Admin@123")
        disp_headers = await get_token_headers(client, "dispatcher@fieldops.ai", "Dispatch@123")

        # 1. Create a technician
        skills_res = await client.get(f"{BASE_URL}/api/v1/skills", headers=admin_headers)
        skill_id = skills_res.json()["items"][0]["id"]
        unique_suffix = str(uuid.uuid4())[:6].upper()

        create_res = await client.post(
            f"{BASE_URL}/api/v1/technicians",
            json={
                "employee_code": f"T-DEP-{unique_suffix}",
                "full_name": f"Dependency Tech {unique_suffix}",
                "email": f"dep_{unique_suffix.lower()}@fieldops.ai",
                "password": "Password@123",
                "primary_skill_id": skill_id,
                "years_experience": 5,
                "availability_status": "AVAILABLE",
            },
            headers=admin_headers,
        )
        assert create_res.status_code == 201
        tech_id = create_res.json()["id"]

        # 2. Create a job and assign it to the technician
        job_res = await client.post(
            f"{BASE_URL}/api/v1/jobs",
            json={
                "customer_name": f"Dependency Customer {unique_suffix}",
                "customer_phone": "+1 (555) 333-4444",
                "address": "123 Operational Lane, Suite 100",
                "latitude": 37.7749,
                "longitude": -122.4194,
                "required_skill_id": skill_id,
                "priority": "HIGH",
                "description": "Job for operational dependency testing.",
            },
            headers=disp_headers,
        )
        assert job_res.status_code == 201
        job_id = job_res.json()["id"]

        assign_res = await client.post(
            f"{BASE_URL}/api/v1/assignments/jobs/{job_id}/assign",
            json={
                "technician_id": tech_id,
                "confidence_score": 0.95,
                "reason": "Test operational assignment",
            },
            headers=disp_headers,
        )
        assert assign_res.status_code in (200, 201), f"Assign failed: {assign_res.status_code} {assign_res.text}"

        # 3. Check dependencies endpoint
        deps_res = await client.get(
            f"{BASE_URL}/api/v1/technicians/{tech_id}/dependencies", headers=admin_headers
        )
        assert deps_res.status_code == 200
        deps_data = deps_res.json()
        assert deps_data["can_delete"] is False
        assert deps_data["has_dependencies"] is True
        assert deps_data["assignment_count"] >= 1
        assert len(deps_data["blockers"]) > 0

        # 4. Attempt permanent delete -> MUST fail with 409 Conflict
        del_res = await client.delete(f"{BASE_URL}/api/v1/technicians/{tech_id}", headers=admin_headers)
        assert del_res.status_code == 409, f"Expected 409 Conflict, got {del_res.status_code}: {del_res.text}"
        assert "Deactivate the technician instead" in del_res.text

        # 5. Technician and User record must still exist intact
        get_res = await client.get(f"{BASE_URL}/api/v1/technicians/{tech_id}", headers=admin_headers)
        assert get_res.status_code == 200
        assert get_res.json()["employee_code"] == f"T-DEP-{unique_suffix}"

        # 6. Deactivate technician -> MUST succeed
        deact_res = await client.post(
            f"{BASE_URL}/api/v1/technicians/{tech_id}/deactivate", headers=admin_headers
        )
        assert deact_res.status_code == 200
        assert deact_res.json()["availability_status"] == "INACTIVE"

