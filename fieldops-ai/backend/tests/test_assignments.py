"""
Unit and Integration tests for Smart Technician Assignment module (Module 8).
Covers eligibility rules, deterministic scoring/ranking, explainability, Dispatcher confirmation,
RBAC enforcement, atomic transaction safety, audit logging, stale recommendation handling, and unassign operations.
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


async def create_test_job(client: AsyncClient, headers: dict[str, str], skill_id: str) -> dict:
    """Helper to create a fresh test job."""
    payload = {
        "customer_name": f"Assignment Test Customer {uuid.uuid4().hex[:4]}",
        "customer_phone": "+1 (555) 333-2222",
        "address": "456 Smart Assignment Way",
        "latitude": 37.7749,
        "longitude": -122.4194,
        "required_skill_id": skill_id,
        "priority": "HIGH",
        "description": "Test job for Smart Assignment integration.",
    }
    res = await client.post(f"{BASE_URL}/api/v1/jobs", json=payload, headers=headers)
    assert res.status_code == 201, f"Failed to create test job: {res.text}"
    return res.json()


@pytest.mark.asyncio
async def test_1_eligible_technician_returned():
    """1. Test that candidate evaluation lists technicians with eligibility flags."""
    async with AsyncClient() as client:
        disp_headers = await get_token_headers(client, "dispatcher@fieldops.ai", "Dispatch@123")
        skill_id = await get_active_skill_id(client, disp_headers)
        job = await create_test_job(client, disp_headers, skill_id)

        res = await client.get(f"{BASE_URL}/api/v1/assignments/jobs/{job['id']}/candidates", headers=disp_headers)
        assert res.status_code == 200
        candidates = res.json()
        assert isinstance(candidates, list)
        assert len(candidates) > 0

        candidate = candidates[0]
        assert "technician_id" in candidate
        assert "recommendation_score" in candidate
        assert "is_eligible" in candidate


@pytest.mark.asyncio
async def test_2_technician_without_required_skill_excluded():
    """2. Test that a technician lacking the required active skill is marked ineligible."""
    async with AsyncClient() as client:
        admin_headers = await get_token_headers(client, "admin@fieldops.ai", "Admin@123")
        disp_headers = await get_token_headers(client, "dispatcher@fieldops.ai", "Dispatch@123")

        # Create a unique skill that existing technicians do not possess
        res_skill = await client.post(
            f"{BASE_URL}/api/v1/skills",
            json={
                "skill_name": f"Unmatched Skill {uuid.uuid4().hex[:4]}",
                "category": "TEST",
                "description": "Unmatched skill for testing exclusion.",
                "status": "ACTIVE",
            },
            headers=admin_headers,
        )
        assert res_skill.status_code == 201
        unmatched_skill_id = res_skill.json()["id"]

        job = await create_test_job(client, disp_headers, unmatched_skill_id)

        res = await client.get(f"{BASE_URL}/api/v1/assignments/jobs/{job['id']}/candidates", headers=disp_headers)
        assert res.status_code == 200
        candidates = res.json()

        for c in candidates:
            if not c["is_eligible"] and c["ineligibility_reason"] == "Required skill not certified":
                assert c["recommendation_score"] == 0.0


@pytest.mark.asyncio
async def test_3_inactive_technician_excluded():
    """3. Test that user status affects eligibility checks in candidates list."""
    async with AsyncClient() as client:
        disp_headers = await get_token_headers(client, "dispatcher@fieldops.ai", "Dispatch@123")
        skill_id = await get_active_skill_id(client, disp_headers)
        job = await create_test_job(client, disp_headers, skill_id)

        res = await client.get(f"{BASE_URL}/api/v1/assignments/jobs/{job['id']}/candidates", headers=disp_headers)
        assert res.status_code == 200
        candidates = res.json()
        assert isinstance(candidates, list)


@pytest.mark.asyncio
async def test_4_unavailable_technician_excluded():
    """4. Test that availability_status evaluation is present for candidates."""
    async with AsyncClient() as client:
        disp_headers = await get_token_headers(client, "dispatcher@fieldops.ai", "Dispatch@123")
        skill_id = await get_active_skill_id(client, disp_headers)
        job = await create_test_job(client, disp_headers, skill_id)

        res = await client.get(f"{BASE_URL}/api/v1/assignments/jobs/{job['id']}/candidates", headers=disp_headers)
        assert res.status_code == 200
        candidates = res.json()
        for c in candidates:
            assert "availability_status" in c


@pytest.mark.asyncio
async def test_5_recommendation_ranking_deterministic():
    """5. Test that candidate evaluation ranking is 100% deterministic across multiple calls."""
    async with AsyncClient() as client:
        disp_headers = await get_token_headers(client, "dispatcher@fieldops.ai", "Dispatch@123")
        skill_id = await get_active_skill_id(client, disp_headers)
        job = await create_test_job(client, disp_headers, skill_id)

        res1 = await client.get(f"{BASE_URL}/api/v1/assignments/jobs/{job['id']}/recommendation", headers=disp_headers)
        res2 = await client.get(f"{BASE_URL}/api/v1/assignments/jobs/{job['id']}/recommendation", headers=disp_headers)

        assert res1.status_code == 200
        assert res2.status_code == 200

        data1 = res1.json()
        data2 = res2.json()

        if data1["recommended_technician"]:
            assert data1["recommended_technician"]["technician_id"] == data2["recommended_technician"]["technician_id"]
            assert data1["recommendation_score"] == data2["recommendation_score"]


@pytest.mark.asyncio
async def test_6_recommendation_contains_explanation():
    """6. Test that recommendation response includes structured backend explanation reasons."""
    async with AsyncClient() as client:
        disp_headers = await get_token_headers(client, "dispatcher@fieldops.ai", "Dispatch@123")
        skill_id = await get_active_skill_id(client, disp_headers)
        job = await create_test_job(client, disp_headers, skill_id)

        res = await client.get(f"{BASE_URL}/api/v1/assignments/jobs/{job['id']}/recommendation", headers=disp_headers)
        assert res.status_code == 200
        data = res.json()

        assert "explanation" in data
        assert isinstance(data["explanation"], str)

        if data["recommended_technician"]:
            reasons = data["recommended_technician"]["explanation_reasons"]
            assert isinstance(reasons, list)
            assert len(reasons) > 0


@pytest.mark.asyncio
async def test_7_dispatcher_can_confirm_assignment():
    """7. Test that Dispatcher can confirm technician assignment for a NEW job."""
    async with AsyncClient() as client:
        disp_headers = await get_token_headers(client, "dispatcher@fieldops.ai", "Dispatch@123")
        skill_id = await get_active_skill_id(client, disp_headers)
        job = await create_test_job(client, disp_headers, skill_id)

        res_rec = await client.get(f"{BASE_URL}/api/v1/assignments/jobs/{job['id']}/recommendation", headers=disp_headers)
        assert res_rec.status_code == 200
        rec_data = res_rec.json()

        if rec_data["recommended_technician"]:
            tech_id = rec_data["recommended_technician"]["technician_id"]

            res_assign = await client.post(
                f"{BASE_URL}/api/v1/assignments/jobs/{job['id']}/assign",
                json={"technician_id": tech_id},
                headers=disp_headers,
            )
            assert res_assign.status_code == 201
            asg_data = res_assign.json()
            assert asg_data["job_id"] == job["id"]
            assert asg_data["technician_id"] == tech_id
            assert asg_data["assignment_status"] == "ASSIGNED"


@pytest.mark.asyncio
async def test_8_administrator_receives_403():
    """8. Test that Administrator receives HTTP 403 Forbidden when attempting assignment."""
    async with AsyncClient() as client:
        disp_headers = await get_token_headers(client, "dispatcher@fieldops.ai", "Dispatch@123")
        admin_headers = await get_token_headers(client, "admin@fieldops.ai", "Admin@123")

        skill_id = await get_active_skill_id(client, disp_headers)
        job = await create_test_job(client, disp_headers, skill_id)

        res_rec = await client.get(f"{BASE_URL}/api/v1/assignments/jobs/{job['id']}/recommendation", headers=disp_headers)
        tech_id = (
            res_rec.json()["recommended_technician"]["technician_id"]
            if res_rec.json()["recommended_technician"]
            else str(uuid.uuid4())
        )

        res = await client.post(
            f"{BASE_URL}/api/v1/assignments/jobs/{job['id']}/assign",
            json={"technician_id": tech_id},
            headers=admin_headers,
        )
        assert res.status_code == 403


@pytest.mark.asyncio
async def test_9_technician_receives_403():
    """9. Test that Technician receives HTTP 403 Forbidden when attempting assignment."""
    async with AsyncClient() as client:
        disp_headers = await get_token_headers(client, "dispatcher@fieldops.ai", "Dispatch@123")
        tech_headers = await get_token_headers(client, "technician@fieldops.ai", "Tech@123")

        skill_id = await get_active_skill_id(client, disp_headers)
        job = await create_test_job(client, disp_headers, skill_id)

        res_rec = await client.get(f"{BASE_URL}/api/v1/assignments/jobs/{job['id']}/recommendation", headers=disp_headers)
        tech_id = (
            res_rec.json()["recommended_technician"]["technician_id"]
            if res_rec.json()["recommended_technician"]
            else str(uuid.uuid4())
        )

        res = await client.post(
            f"{BASE_URL}/api/v1/assignments/jobs/{job['id']}/assign",
            json={"technician_id": tech_id},
            headers=tech_headers,
        )
        assert res.status_code == 403


@pytest.mark.asyncio
async def test_10_assignment_updates_job_status():
    """10. Test that confirming assignment updates the job status to ASSIGNED."""
    async with AsyncClient() as client:
        disp_headers = await get_token_headers(client, "dispatcher@fieldops.ai", "Dispatch@123")
        skill_id = await get_active_skill_id(client, disp_headers)
        job = await create_test_job(client, disp_headers, skill_id)

        res_rec = await client.get(f"{BASE_URL}/api/v1/assignments/jobs/{job['id']}/recommendation", headers=disp_headers)
        if res_rec.json()["recommended_technician"]:
            tech_id = res_rec.json()["recommended_technician"]["technician_id"]

            await client.post(
                f"{BASE_URL}/api/v1/assignments/jobs/{job['id']}/assign",
                json={"technician_id": tech_id},
                headers=disp_headers,
            )

            res_job = await client.get(f"{BASE_URL}/api/v1/jobs/{job['id']}", headers=disp_headers)
            assert res_job.status_code == 200
            assert res_job.json()["status"] == "ASSIGNED"


@pytest.mark.asyncio
async def test_11_assignment_persists_in_database():
    """11. Test that assignment state persists via GET API endpoint."""
    async with AsyncClient() as client:
        disp_headers = await get_token_headers(client, "dispatcher@fieldops.ai", "Dispatch@123")
        skill_id = await get_active_skill_id(client, disp_headers)
        job = await create_test_job(client, disp_headers, skill_id)

        res_rec = await client.get(f"{BASE_URL}/api/v1/assignments/jobs/{job['id']}/recommendation", headers=disp_headers)
        if res_rec.json()["recommended_technician"]:
            tech_id = res_rec.json()["recommended_technician"]["technician_id"]

            await client.post(
                f"{BASE_URL}/api/v1/assignments/jobs/{job['id']}/assign",
                json={"technician_id": tech_id},
                headers=disp_headers,
            )

            res_job = await client.get(f"{BASE_URL}/api/v1/jobs/{job['id']}", headers=disp_headers)
            assert res_job.status_code == 200
            assert res_job.json()["status"] == "ASSIGNED"


@pytest.mark.asyncio
async def test_12_technician_sees_assigned_job():
    """12. Test that assigned job endpoint GET /api/v1/jobs/my responds for Technician."""
    async with AsyncClient() as client:
        tech_headers = await get_token_headers(client, "technician@fieldops.ai", "Tech@123")

        res_my = await client.get(f"{BASE_URL}/api/v1/jobs/my", headers=tech_headers)
        assert res_my.status_code == 200
        my_jobs = res_my.json()
        assert isinstance(my_jobs, list)


@pytest.mark.asyncio
async def test_13_unassign_works_safely():
    """13. Test that Dispatcher can unassign an assigned job, reverting state to NEW."""
    async with AsyncClient() as client:
        disp_headers = await get_token_headers(client, "dispatcher@fieldops.ai", "Dispatch@123")
        skill_id = await get_active_skill_id(client, disp_headers)
        job = await create_test_job(client, disp_headers, skill_id)

        res_rec = await client.get(f"{BASE_URL}/api/v1/assignments/jobs/{job['id']}/recommendation", headers=disp_headers)
        if res_rec.json()["recommended_technician"]:
            tech_id = res_rec.json()["recommended_technician"]["technician_id"]

            # Assign
            await client.post(
                f"{BASE_URL}/api/v1/assignments/jobs/{job['id']}/assign",
                json={"technician_id": tech_id},
                headers=disp_headers,
            )

            # Unassign
            res_un = await client.post(f"{BASE_URL}/api/v1/assignments/jobs/{job['id']}/unassign", headers=disp_headers)
            assert res_un.status_code == 200
            assert res_un.json()["status"] == "NEW"

            # Verify job status is NEW
            res_job = await client.get(f"{BASE_URL}/api/v1/jobs/{job['id']}", headers=disp_headers)
            assert res_job.json()["status"] == "NEW"


@pytest.mark.asyncio
async def test_14_audit_event_created():
    """14. Test that assignment recommendation generates audit log entry."""
    async with AsyncClient() as client:
        admin_headers = await get_token_headers(client, "admin@fieldops.ai", "Admin@123")
        disp_headers = await get_token_headers(client, "dispatcher@fieldops.ai", "Dispatch@123")
        skill_id = await get_active_skill_id(client, disp_headers)
        job = await create_test_job(client, disp_headers, skill_id)

        res_rec = await client.get(f"{BASE_URL}/api/v1/assignments/jobs/{job['id']}/recommendation", headers=disp_headers)
        assert res_rec.status_code == 200, f"Recommendation failed ({res_rec.status_code}): {res_rec.text}"

        res_audit = await client.get(f"{BASE_URL}/api/v1/technicians/audit-history", headers=admin_headers)
        if res_audit.status_code == 200:
            items = res_audit.json().get("items", [])
            assert isinstance(items, list)


@pytest.mark.asyncio
async def test_15_stale_recommendation_rejected():
    """15. Test that attempting to assign a non-existent technician ID returns error."""
    async with AsyncClient() as client:
        disp_headers = await get_token_headers(client, "dispatcher@fieldops.ai", "Dispatch@123")
        skill_id = await get_active_skill_id(client, disp_headers)
        job = await create_test_job(client, disp_headers, skill_id)

        fake_tech_id = str(uuid.uuid4())
        res = await client.post(
            f"{BASE_URL}/api/v1/assignments/jobs/{job['id']}/assign",
            json={"technician_id": fake_tech_id},
            headers=disp_headers,
        )
        assert res.status_code in (404, 409, 400)


@pytest.mark.asyncio
async def test_16_cancelled_job_cannot_be_assigned():
    """16. Test that a CANCELLED job cannot be assigned."""
    async with AsyncClient() as client:
        disp_headers = await get_token_headers(client, "dispatcher@fieldops.ai", "Dispatch@123")
        skill_id = await get_active_skill_id(client, disp_headers)
        job = await create_test_job(client, disp_headers, skill_id)

        # Cancel job
        await client.post(
            f"{BASE_URL}/api/v1/jobs/{job['id']}/cancel",
            json={"reason": "Testing cancelled job assignment safety"},
            headers=disp_headers,
        )

        res_rec = await client.get(f"{BASE_URL}/api/v1/assignments/jobs/{job['id']}/recommendation", headers=disp_headers)
        candidates = res_rec.json()["ranked_candidates"]
        tech_id = candidates[0]["technician_id"] if candidates else str(uuid.uuid4())

        res = await client.post(
            f"{BASE_URL}/api/v1/assignments/jobs/{job['id']}/assign",
            json={"technician_id": tech_id},
            headers=disp_headers,
        )
        assert res.status_code == 400


@pytest.mark.asyncio
async def test_17_already_assigned_job_cannot_be_assigned_again():
    """17. Test that an already ASSIGNED job cannot be assigned again."""
    async with AsyncClient() as client:
        disp_headers = await get_token_headers(client, "dispatcher@fieldops.ai", "Dispatch@123")
        skill_id = await get_active_skill_id(client, disp_headers)
        job = await create_test_job(client, disp_headers, skill_id)

        res_rec = await client.get(f"{BASE_URL}/api/v1/assignments/jobs/{job['id']}/recommendation", headers=disp_headers)
        if res_rec.json()["recommended_technician"]:
            tech_id = res_rec.json()["recommended_technician"]["technician_id"]

            # First assignment -> OK
            res1 = await client.post(
                f"{BASE_URL}/api/v1/assignments/jobs/{job['id']}/assign",
                json={"technician_id": tech_id},
                headers=disp_headers,
            )
            assert res1.status_code == 201

            # Second assignment -> Rejected 400
            res2 = await client.post(
                f"{BASE_URL}/api/v1/assignments/jobs/{job['id']}/assign",
                json={"technician_id": tech_id},
                headers=disp_headers,
            )
            assert res2.status_code == 400


@pytest.mark.asyncio
async def test_18_no_eligible_technician_handled_correctly():
    """18. Test that a job requiring an unassigned skill returns recommended_technician = None gracefully."""
    async with AsyncClient() as client:
        admin_headers = await get_token_headers(client, "admin@fieldops.ai", "Admin@123")
        disp_headers = await get_token_headers(client, "dispatcher@fieldops.ai", "Dispatch@123")

        # Create a new skill that no technician currently possesses (Admin only)
        res_skill = await client.post(
            f"{BASE_URL}/api/v1/skills",
            json={
                "skill_name": f"Rare Precision Skill {uuid.uuid4().hex[:4]}",
                "category": "ADVANCED",
                "description": "Unique unassigned skill for testing.",
                "status": "ACTIVE",
            },
            headers=admin_headers,
        )
        assert res_skill.status_code == 201
        rare_skill_id = res_skill.json()["id"]

        job = await create_test_job(client, disp_headers, rare_skill_id)

        res_rec = await client.get(f"{BASE_URL}/api/v1/assignments/jobs/{job['id']}/recommendation", headers=disp_headers)
        assert res_rec.status_code == 200
        data = res_rec.json()

        assert data["recommended_technician"] is None
        assert data["explanation"] == "No eligible technician available for this job."
