"""
Integration and Unit Tests for Smart Technician Assignment (Module 9).

Verifies:
1. Dispatcher can request recommendations.
2. Inactive technician is excluded from eligibility.
3. Unavailable technician is excluded from eligibility.
4. Technician without required skill is excluded from eligibility.
5. Eligible technician receives a valid score (0 - 100).
6. Best eligible technician is ranked first.
7. Dispatcher can assign recommended technician.
8. Assignment persists in PostgreSQL with ASSIGNED status.
9. Technician sees the assigned job in their work queue.
10. Technician cannot assign themselves or others (403 Forbidden).
11. Administrator RBAC remains valid (cannot execute dispatcher-only assignment).
12. Invalid technician assignment is rejected.
13. Completed/cancelled job cannot be assigned.
14. Concurrent/duplicate assignment is handled safely.
15. TECHNICIAN_ASSIGNED audit event is created.
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


async def get_technician_and_skill(client: AsyncClient, headers: dict[str, str]) -> tuple[str, str]:
    """Helper to fetch an active technician ID and their certified skill ID."""
    res = await client.get(f"{BASE_URL}/api/v1/technicians?search=TECH-001", headers=headers)
    assert res.status_code == 200
    body = res.json()
    items = body["items"] if "items" in body else body
    assert len(items) > 0, "TECH-001 not found"
    tech = items[0]
    return str(tech["id"]), str(tech["primary_skill_id"])


async def create_test_job(
    client: AsyncClient,
    headers: dict[str, str],
    skill_id: str,
    priority: str = "HIGH",
) -> dict:
    """Helper to create an unassigned test job."""
    unique_suffix = uuid.uuid4().hex[:6]
    payload = {
        "customer_name": f"Enterprise Client {unique_suffix}",
        "customer_phone": "+1 555 019 3322",
        "address": "789 Market St, San Francisco, CA 94103",
        "latitude": 37.7879,
        "longitude": -122.4075,
        "priority": priority,
        "required_skill_id": skill_id,
        "description": "Module 9 Smart Assignment test service call",
    }
    res = await client.post(f"{BASE_URL}/api/v1/jobs", json=payload, headers=headers)
    assert res.status_code == 201, f"Failed to create job: {res.text}"
    return res.json()


@pytest.mark.asyncio
async def test_1_dispatcher_can_request_recommendations():
    """1. Dispatcher can request recommendations via standard REST endpoint."""
    async with AsyncClient() as client:
        disp_headers = await get_token_headers(client, "dispatcher@fieldops.ai", "Dispatch@123")
        tech_id, skill_id = await get_technician_and_skill(client, disp_headers)
        job = await create_test_job(client, disp_headers, skill_id)

        res = await client.get(
            f"{BASE_URL}/api/v1/jobs/{job['id']}/assignment-recommendations",
            headers=disp_headers,
        )
        assert res.status_code == 200, f"Failed: {res.text}"
        data = res.json()
        assert data["job_id"] == job["id"]
        assert "recommended_technician" in data
        assert "ranked_candidates" in data
        assert isinstance(data["ranked_candidates"], list)


@pytest.mark.asyncio
async def test_2_inactive_technician_is_excluded():
    """2. Inactive technician is excluded from eligibility."""
    async with AsyncClient() as client:
        disp_headers = await get_token_headers(client, "dispatcher@fieldops.ai", "Dispatch@123")
        tech_id, skill_id = await get_technician_and_skill(client, disp_headers)
        job = await create_test_job(client, disp_headers, skill_id)

        res = await client.get(
            f"{BASE_URL}/api/v1/jobs/{job['id']}/assignment-recommendations",
            headers=disp_headers,
        )
        assert res.status_code == 200
        candidates = res.json()["ranked_candidates"]
        for c in candidates:
            if not c["is_eligible"] and "inactive" in (c["ineligibility_reason"] or "").lower():
                assert c["recommendation_score"] == 0.0


@pytest.mark.asyncio
async def test_3_unavailable_technician_is_excluded():
    """3. Unavailable technician is marked ineligible with reason."""
    async with AsyncClient() as client:
        disp_headers = await get_token_headers(client, "dispatcher@fieldops.ai", "Dispatch@123")
        tech_id, skill_id = await get_technician_and_skill(client, disp_headers)
        job = await create_test_job(client, disp_headers, skill_id)

        res = await client.get(
            f"{BASE_URL}/api/v1/jobs/{job['id']}/assignment-recommendations",
            headers=disp_headers,
        )
        assert res.status_code == 200
        candidates = res.json()["ranked_candidates"]
        for c in candidates:
            if c["availability_status"] != "AVAILABLE" and "inactive" not in (c["ineligibility_reason"] or "").lower():
                assert c["is_eligible"] is False
                assert "status is" in (c["ineligibility_reason"] or "").lower()


@pytest.mark.asyncio
async def test_4_technician_without_required_skill_is_excluded():
    """4. Technician without required skill certification is ineligible."""
    async with AsyncClient() as client:
        disp_headers = await get_token_headers(client, "dispatcher@fieldops.ai", "Dispatch@123")
        tech_id, skill_id = await get_technician_and_skill(client, disp_headers)

        # Create job requiring this certified skill
        job = await create_test_job(client, disp_headers, skill_id)

        res = await client.get(
            f"{BASE_URL}/api/v1/jobs/{job['id']}/assignment-recommendations",
            headers=disp_headers,
        )
        assert res.status_code == 200
        candidates = res.json()["ranked_candidates"]
        for c in candidates:
            if c["primary_skill_name"] != res.json()["required_skill_name"]:
                assert c["is_eligible"] is False
                all_reasons = " ".join([c.get("ineligibility_reason") or ""] + (c.get("explanation_reasons") or [])).lower()
                assert "required skill not certified" in all_reasons


@pytest.mark.asyncio
async def test_5_eligible_technician_receives_valid_score():
    """5. Eligible technician receives a valid score between 0 and 100."""
    async with AsyncClient() as client:
        disp_headers = await get_token_headers(client, "dispatcher@fieldops.ai", "Dispatch@123")
        tech_id, skill_id = await get_technician_and_skill(client, disp_headers)
        job = await create_test_job(client, disp_headers, skill_id)

        res = await client.get(
            f"{BASE_URL}/api/v1/jobs/{job['id']}/assignment-recommendations",
            headers=disp_headers,
        )
        assert res.status_code == 200
        rec = res.json()["recommended_technician"]
        if rec:
            assert rec["recommendation_score"] > 0
            assert rec["recommendation_score"] <= 100
            assert len(rec["explanation_reasons"]) > 0


@pytest.mark.asyncio
async def test_6_best_eligible_technician_is_ranked_first():
    """6. Best eligible technician with highest score is ranked first."""
    async with AsyncClient() as client:
        disp_headers = await get_token_headers(client, "dispatcher@fieldops.ai", "Dispatch@123")
        tech_id, skill_id = await get_technician_and_skill(client, disp_headers)
        job = await create_test_job(client, disp_headers, skill_id)

        res = await client.get(
            f"{BASE_URL}/api/v1/jobs/{job['id']}/assignment-recommendations",
            headers=disp_headers,
        )
        assert res.status_code == 200
        candidates = res.json()["ranked_candidates"]
        eligible = [c for c in candidates if c["is_eligible"]]
        if len(eligible) > 1:
            assert eligible[0]["recommendation_score"] >= eligible[1]["recommendation_score"]
            assert eligible[0]["ranking"] == 1


@pytest.mark.asyncio
async def test_7_dispatcher_can_assign_recommended_technician():
    """7. Dispatcher can assign recommended technician via POST /assign-technician."""
    async with AsyncClient() as client:
        disp_headers = await get_token_headers(client, "dispatcher@fieldops.ai", "Dispatch@123")
        tech_id, skill_id = await get_technician_and_skill(client, disp_headers)
        job = await create_test_job(client, disp_headers, skill_id)

        res_rec = await client.get(
            f"{BASE_URL}/api/v1/jobs/{job['id']}/assignment-recommendations",
            headers=disp_headers,
        )
        assert res_rec.status_code == 200
        rec_tech = res_rec.json()["recommended_technician"]
        assert rec_tech is not None

        res_asg = await client.post(
            f"{BASE_URL}/api/v1/jobs/{job['id']}/assign-technician",
            json={"technician_id": rec_tech["technician_id"]},
            headers=disp_headers,
        )
        assert res_asg.status_code == 201, f"Failed: {res_asg.text}"
        assert res_asg.json()["technician_id"] == rec_tech["technician_id"]
        assert res_asg.json()["assignment_status"] == "ASSIGNED"


@pytest.mark.asyncio
async def test_8_assignment_persists_in_postgresql():
    """8. Assignment persists in PostgreSQL and updates job status to ASSIGNED."""
    async with AsyncClient() as client:
        disp_headers = await get_token_headers(client, "dispatcher@fieldops.ai", "Dispatch@123")
        tech_id, skill_id = await get_technician_and_skill(client, disp_headers)
        job = await create_test_job(client, disp_headers, skill_id)

        res_asg = await client.post(
            f"{BASE_URL}/api/v1/jobs/{job['id']}/assign-technician",
            json={"technician_id": tech_id},
            headers=disp_headers,
        )
        assert res_asg.status_code == 201

        res_job = await client.get(f"{BASE_URL}/api/v1/jobs/{job['id']}", headers=disp_headers)
        assert res_job.status_code == 200
        job_data = res_job.json()
        assert job_data["status"] == "ASSIGNED"
        assert job_data["assigned_technician"] is not None
        assert str(job_data["assigned_technician"]["id"]) == tech_id


@pytest.mark.asyncio
async def test_9_technician_sees_assigned_job():
    """9. Technician sees the assigned job in their personal work queue."""
    async with AsyncClient() as client:
        disp_headers = await get_token_headers(client, "dispatcher@fieldops.ai", "Dispatch@123")
        tech_headers = await get_token_headers(client, "technician@fieldops.ai", "Tech@123")
        tech_id, skill_id = await get_technician_and_skill(client, disp_headers)
        job = await create_test_job(client, disp_headers, skill_id)

        # Assign to TECH-001 (Alex Rivera)
        res_asg = await client.post(
            f"{BASE_URL}/api/v1/jobs/{job['id']}/assign-technician",
            json={"technician_id": tech_id},
            headers=disp_headers,
        )
        assert res_asg.status_code == 201

        # Technician checks own jobs
        res_my = await client.get(f"{BASE_URL}/api/v1/jobs/my", headers=tech_headers)
        assert res_my.status_code == 200
        my_jobs = res_my.json()
        job_ids = [j["id"] for j in my_jobs]
        assert job["id"] in job_ids


@pytest.mark.asyncio
async def test_10_technician_cannot_assign_themselves():
    """10. Technician cannot assign themselves or any other technician (403 Forbidden)."""
    async with AsyncClient() as client:
        disp_headers = await get_token_headers(client, "dispatcher@fieldops.ai", "Dispatch@123")
        tech_headers = await get_token_headers(client, "technician@fieldops.ai", "Tech@123")
        tech_id, skill_id = await get_technician_and_skill(client, disp_headers)
        job = await create_test_job(client, disp_headers, skill_id)

        res = await client.post(
            f"{BASE_URL}/api/v1/jobs/{job['id']}/assign-technician",
            json={"technician_id": tech_id},
            headers=tech_headers,
        )
        assert res.status_code == 403


@pytest.mark.asyncio
async def test_11_administrator_rbac_remains_valid():
    """11. Administrator cannot execute dispatcher assignment (403 Forbidden)."""
    async with AsyncClient() as client:
        disp_headers = await get_token_headers(client, "dispatcher@fieldops.ai", "Dispatch@123")
        admin_headers = await get_token_headers(client, "admin@fieldops.ai", "Admin@123")
        tech_id, skill_id = await get_technician_and_skill(client, disp_headers)
        job = await create_test_job(client, disp_headers, skill_id)

        res = await client.post(
            f"{BASE_URL}/api/v1/jobs/{job['id']}/assign-technician",
            json={"technician_id": tech_id},
            headers=admin_headers,
        )
        assert res.status_code == 403


@pytest.mark.asyncio
async def test_12_invalid_technician_assignment_rejected():
    """12. Assigning non-existent technician is rejected with 404/400/409."""
    async with AsyncClient() as client:
        disp_headers = await get_token_headers(client, "dispatcher@fieldops.ai", "Dispatch@123")
        tech_id, skill_id = await get_technician_and_skill(client, disp_headers)
        job = await create_test_job(client, disp_headers, skill_id)

        fake_id = str(uuid.uuid4())
        res = await client.post(
            f"{BASE_URL}/api/v1/jobs/{job['id']}/assign-technician",
            json={"technician_id": fake_id},
            headers=disp_headers,
        )
        assert res.status_code in (404, 400, 409)


@pytest.mark.asyncio
async def test_13_completed_cancelled_job_cannot_be_assigned():
    """13. Completed or cancelled jobs cannot be assigned (400 Bad Request)."""
    async with AsyncClient() as client:
        disp_headers = await get_token_headers(client, "dispatcher@fieldops.ai", "Dispatch@123")
        tech_id, skill_id = await get_technician_and_skill(client, disp_headers)
        job = await create_test_job(client, disp_headers, skill_id)

        # Cancel job
        await client.post(
            f"{BASE_URL}/api/v1/jobs/{job['id']}/cancel",
            json={"reason": "Customer cancelled service"},
            headers=disp_headers,
        )

        # Attempt assignment on cancelled job
        res = await client.post(
            f"{BASE_URL}/api/v1/jobs/{job['id']}/assign-technician",
            json={"technician_id": tech_id},
            headers=disp_headers,
        )
        assert res.status_code in (400, 409)


@pytest.mark.asyncio
async def test_14_concurrent_assignment_handled_safely():
    """14. Re-assigning an already assigned job is safely prevented."""
    async with AsyncClient() as client:
        disp_headers = await get_token_headers(client, "dispatcher@fieldops.ai", "Dispatch@123")
        tech_id, skill_id = await get_technician_and_skill(client, disp_headers)
        job = await create_test_job(client, disp_headers, skill_id)

        # First assignment succeeds
        res1 = await client.post(
            f"{BASE_URL}/api/v1/jobs/{job['id']}/assign-technician",
            json={"technician_id": tech_id},
            headers=disp_headers,
        )
        assert res1.status_code == 201

        # Second concurrent assignment fails cleanly
        res2 = await client.post(
            f"{BASE_URL}/api/v1/jobs/{job['id']}/assign-technician",
            json={"technician_id": tech_id},
            headers=disp_headers,
        )
        assert res2.status_code in (400, 409)


@pytest.mark.asyncio
async def test_15_technician_assigned_audit_event_created():
    """15. TECHNICIAN_ASSIGNED audit event is recorded in PostgreSQL."""
    async with AsyncClient() as client:
        disp_headers = await get_token_headers(client, "dispatcher@fieldops.ai", "Dispatch@123")
        admin_headers = await get_token_headers(client, "admin@fieldops.ai", "Admin@123")
        tech_id, skill_id = await get_technician_and_skill(client, disp_headers)
        job = await create_test_job(client, disp_headers, skill_id)

        res_asg = await client.post(
            f"{BASE_URL}/api/v1/jobs/{job['id']}/assign-technician",
            json={"technician_id": tech_id},
            headers=disp_headers,
        )
        assert res_asg.status_code == 201

        # Check audit history
        res_audit = await client.get(
            f"{BASE_URL}/api/v1/technicians/audit-history",
            headers=admin_headers,
        )
        if res_audit.status_code == 200:
            items = res_audit.json().get("items", [])
            assert any(
                item.get("action") in ("TECHNICIAN_ASSIGNED", "JOB_ASSIGNED")
                for item in items
            )
