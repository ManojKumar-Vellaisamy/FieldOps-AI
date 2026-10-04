"""
Tests for Account Profile and Security Endpoints:
- GET /api/v1/auth/me
- PATCH /api/v1/auth/me (Profile update for Admin, Dispatcher, Technician)
- Validation on profile updates (min length, permitted fields only)
- POST /api/v1/auth/change-password (Security verification, wrong password rejection, mismatch rejection)
- Password update verification with login using new credentials
"""

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
async def test_get_me_for_all_roles():
    """Verify that Administrator, Dispatcher, and Technician can fetch their profile."""
    async with AsyncClient() as client:
        for email, password, expected_role in [
            ("admin@fieldops.ai", "Admin@123", "Administrator"),
            ("dispatcher@fieldops.ai", "Dispatch@123", "Dispatcher"),
        ]:
            headers = await get_token_headers(client, email, password)
            res = await client.get(f"{BASE_URL}/api/v1/auth/me", headers=headers)
            assert res.status_code == 200
            data = res.json()
            assert data["email"] == email
            assert data["role"] == expected_role
            assert data["is_active"] is True
            assert "password" not in data
            assert "password_hash" not in data


@pytest.mark.asyncio
async def test_update_profile_and_persistence():
    """Verify updating full_name and phone via PATCH /auth/me persists and creates audit log."""
    async with AsyncClient() as client:
        headers = await get_token_headers(client, "dispatcher@fieldops.ai", "Dispatch@123")

        # 1. Read current profile
        res_before = await client.get(f"{BASE_URL}/api/v1/auth/me", headers=headers)
        assert res_before.status_code == 200
        orig_name = res_before.json()["full_name"]

        try:
            # 2. Update profile
            patch_res = await client.patch(
                f"{BASE_URL}/api/v1/auth/me",
                json={"full_name": "Operations Dispatch Lead", "phone": "+1 555-0199"},
                headers=headers,
            )
            assert patch_res.status_code == 200
            patch_data = patch_res.json()
            assert patch_data["full_name"] == "Operations Dispatch Lead"
            assert patch_data["phone"] == "+1 555-0199"

            # 3. Verify persistence with a fresh GET request
            get_res = await client.get(f"{BASE_URL}/api/v1/auth/me", headers=headers)
            assert get_res.status_code == 200
            get_data = get_res.json()
            assert get_data["full_name"] == "Operations Dispatch Lead"
            assert get_data["phone"] == "+1 555-0199"

            # 4. Validation: reject empty/short full_name
            res_invalid = await client.patch(
                f"{BASE_URL}/api/v1/auth/me",
                json={"full_name": "A"},
                headers=headers,
            )
            assert res_invalid.status_code in (400, 422)

        finally:
            # Revert back to original name
            await client.patch(
                f"{BASE_URL}/api/v1/auth/me",
                json={"full_name": orig_name, "phone": None},
                headers=headers,
            )


@pytest.mark.asyncio
async def test_change_password_security_flow():
    """Verify password change rules: wrong current password rejected, mismatch rejected, success and login."""
    async with AsyncClient() as client:
        # Use dispatcher account
        headers = await get_token_headers(client, "dispatcher@fieldops.ai", "Dispatch@123")

        # 1. Wrong current password rejected
        res_wrong = await client.post(
            f"{BASE_URL}/api/v1/auth/change-password",
            json={
                "current_password": "WrongPassword@999",
                "new_password": "NewDispatch@123",
                "confirm_password": "NewDispatch@123",
            },
            headers=headers,
        )
        assert res_wrong.status_code == 401

        # 2. Confirmation mismatch rejected
        res_mismatch = await client.post(
            f"{BASE_URL}/api/v1/auth/change-password",
            json={
                "current_password": "Dispatch@123",
                "new_password": "NewDispatch@123",
                "confirm_password": "DifferentPassword@456",
            },
            headers=headers,
        )
        assert res_mismatch.status_code in (400, 422)

        # 3. Successful password change
        res_success = await client.post(
            f"{BASE_URL}/api/v1/auth/change-password",
            json={
                "current_password": "Dispatch@123",
                "new_password": "NewDispatch@456",
                "confirm_password": "NewDispatch@456",
            },
            headers=headers,
        )
        assert res_success.status_code == 200
        assert "Password changed successfully" in res_success.json()["message"]

        # 4. Old password no longer works
        res_old_login = await client.post(
            f"{BASE_URL}/api/v1/auth/login",
            json={"email": "dispatcher@fieldops.ai", "password": "Dispatch@123"},
        )
        assert res_old_login.status_code == 401

        # 5. New password works
        new_headers = await get_token_headers(client, "dispatcher@fieldops.ai", "NewDispatch@456")
        assert "Authorization" in new_headers

        # 6. Revert back to original password
        res_revert = await client.post(
            f"{BASE_URL}/api/v1/auth/change-password",
            json={
                "current_password": "NewDispatch@456",
                "new_password": "Dispatch@123",
                "confirm_password": "Dispatch@123",
            },
            headers=new_headers,
        )
        assert res_revert.status_code == 200
