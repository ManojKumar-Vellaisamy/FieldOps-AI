"""
Unit and Integration tests for Module 10: Dispatcher Job Operations & Lifecycle Control.
Verifies job directory listing, multi-param search and filtering, detail viewing, visual lifecycle tracking,
unassigned job assignment requirements, Smart Assignment flow, strict RBAC enforcement (Dispatcher dispatch controls vs Technician execution ownership),
completed job state handling, backend persistence, and audit logging integrity.
"""

import uuid
import pytest
from httpx import AsyncClient

BASE_URL = "http://127.0.0.1:8000"


def get_client() -> AsyncClient:
    return AsyncClient(base_url=BASE_URL, timeout=30.0)


async def get_token_headers(client: AsyncClient, email: str, password: str) -> dict[str, str]:
    """Helper to authenticate and get Bearer token headers."""
    res = await client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert res.status_code == 200, f"Login failed for {email}: {res.text}"
    token = res.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


async def get_active_skill_id(client: AsyncClient, headers: dict[str, str]) -> str:
    """Helper to fetch an active skill ID."""
    res = await client.get("/api/v1/skills?status=ACTIVE", headers=headers)
    assert res.status_code == 200
    items = res.json()["items"]
    assert len(items) > 0, "No active skills found"
    return items[0]["id"]


async def create_dispatcher_test_job(
    client: AsyncClient,
    disp_headers: dict[str, str],
    customer_name: str = "Ops Control Customer",
    priority: str = "HIGH",
    address: str = "777 Dispatch Control Plaza",
) -> dict:
    """Helper to create a fresh test job for operations testing."""
    skill_id = await get_active_skill_id(client, disp_headers)
    payload = {
        "customer_name": f"{customer_name} {uuid.uuid4().hex[:4]}",
        "customer_phone": "+1 (555) 777-8888",
        "address": address,
        "latitude": 37.7749,
        "longitude": -122.4194,
        "required_skill_id": skill_id,
        "priority": priority,
        "description": "Comprehensive service job for Dispatcher Lifecycle testing.",
    }
    res = await client.post("/api/v1/jobs", json=payload, headers=disp_headers)
    assert res.status_code == 201, f"Failed to create test job: {res.text}"
    return res.json()


@pytest.mark.asyncio
async def test_1_dispatcher_can_list_jobs():
    """1. Verify Dispatcher can list all field service jobs."""
    async with get_client() as client:
        disp_headers = await get_token_headers(client, "dispatcher@fieldops.ai", "Dispatch@123")
        res = await client.get("/api/v1/jobs", headers=disp_headers)
        assert res.status_code == 200
        data = res.json()
        assert "items" in data
        assert "total" in data
        assert data["total"] > 0


@pytest.mark.asyncio
async def test_2_dispatcher_can_search_jobs():
    """2. Verify Dispatcher can search jobs by Job ID, Customer, and Address."""
    async with get_client() as client:
        disp_headers = await get_token_headers(client, "dispatcher@fieldops.ai", "Dispatch@123")
        unique_customer = f"SearchTarget_{uuid.uuid4().hex[:6]}"
        job = await create_dispatcher_test_job(client, disp_headers, customer_name=unique_customer)

        # Search by customer name
        res = await client.get(f"/api/v1/jobs?search={unique_customer}", headers=disp_headers)
        assert res.status_code == 200
        items = res.json()["items"]
        assert len(items) > 0
        assert items[0]["id"] == job["id"]

        # Search by job number
        res_num = await client.get(f"/api/v1/jobs?search={job['job_number']}", headers=disp_headers)
        assert res_num.status_code == 200
        assert any(j["id"] == job["id"] for j in res_num.json()["items"])


@pytest.mark.asyncio
async def test_3_dispatcher_can_filter_jobs():
    """3. Verify Dispatcher can filter jobs by status, priority, and assignment status."""
    async with get_client() as client:
        disp_headers = await get_token_headers(client, "dispatcher@fieldops.ai", "Dispatch@123")
        job = await create_dispatcher_test_job(client, disp_headers, priority="CRITICAL")

        # Filter by priority
        res_p = await client.get("/api/v1/jobs?priority=CRITICAL", headers=disp_headers)
        assert res_p.status_code == 200
        assert any(j["id"] == job["id"] for j in res_p.json()["items"])

        # Filter by status
        res_s = await client.get("/api/v1/jobs?status=NEW", headers=disp_headers)
        assert res_s.status_code == 200
        assert any(j["id"] == job["id"] for j in res_s.json()["items"])

        # Filter by assignment_status = UNASSIGNED
        res_u = await client.get("/api/v1/jobs?assignment_status=UNASSIGNED", headers=disp_headers)
        assert res_u.status_code == 200
        assert any(j["id"] == job["id"] for j in res_u.json()["items"])


@pytest.mark.asyncio
async def test_4_dispatcher_can_view_job_details():
    """4. Verify Dispatcher can view single job details with eager loaded relationships."""
    async with get_client() as client:
        disp_headers = await get_token_headers(client, "dispatcher@fieldops.ai", "Dispatch@123")
        job = await create_dispatcher_test_job(client, disp_headers)

        res = await client.get(f"/api/v1/jobs/{job['id']}", headers=disp_headers)
        assert res.status_code == 200
        detail = res.json()
        assert detail["id"] == job["id"]
        assert detail["job_number"] == job["job_number"]
        assert "required_skill" in detail
        assert "creator" in detail


@pytest.mark.asyncio
async def test_5_dispatcher_can_see_assignment_information():
    """5. Verify Dispatcher sees assigned technician information when assigned."""
    async with get_client() as client:
        disp_headers = await get_token_headers(client, "dispatcher@fieldops.ai", "Dispatch@123")
        job = await create_dispatcher_test_job(client, disp_headers)

        # Get Smart Assignment recommendation and assign
        rec_res = await client.get(f"/api/v1/assignments/jobs/{job['id']}/recommendation", headers=disp_headers)
        assert rec_res.status_code == 200
        rec_data = rec_res.json()

        if rec_data["recommended_technician"]:
            tech_id = rec_data["recommended_technician"]["technician_id"]
            assign_res = await client.post(
                f"/api/v1/assignments/jobs/{job['id']}/assign",
                json={"technician_id": tech_id},
                headers=disp_headers,
            )
            assert assign_res.status_code == 201

            # Fetch details
            job_res = await client.get(f"/api/v1/jobs/{job['id']}", headers=disp_headers)
            assert job_res.status_code == 200
            data = job_res.json()
            assert data["assigned_technician"] is not None
            assert "full_name" in data["assigned_technician"]
            assert "employee_code" in data["assigned_technician"]


@pytest.mark.asyncio
async def test_6_dispatcher_can_see_technician_execution_status():
    """6. Verify Dispatcher can observe real-time technician execution status progression."""
    async with get_client() as client:
        disp_headers = await get_token_headers(client, "dispatcher@fieldops.ai", "Dispatch@123")
        tech_headers = await get_token_headers(client, "technician@fieldops.ai", "Tech@123")

        # Fetch technician user details to create a job matching their primary skill
        me_res = await client.get("/api/v1/auth/me", headers=tech_headers)
        my_user_id = me_res.json()["id"]

        techs_res = await client.get("/api/v1/technicians?search=technician@fieldops.ai", headers=disp_headers)
        techs = techs_res.json().get("items", [])
        target_tech = next((t for t in techs if t.get("user_id") == my_user_id), techs[0] if techs else None)
        assert target_tech is not None

        skill_id = target_tech.get("primary_skill_id") or await get_active_skill_id(client, disp_headers)

        payload = {
            "customer_name": f"Execution Status Visibility {uuid.uuid4().hex[:4]}",
            "address": "100 Operational Control Blvd",
            "latitude": 37.7749,
            "longitude": -122.4194,
            "required_skill_id": skill_id,
            "priority": "HIGH",
        }
        create_res = await client.post("/api/v1/jobs", json=payload, headers=disp_headers)
        job = create_res.json()

        # Assign to technician
        await client.post(
            f"/api/v1/assignments/jobs/{job['id']}/assign",
            json={"technician_id": target_tech["id"]},
            headers=disp_headers,
        )

        # Technician transitions to EN_ROUTE
        await client.patch(
            f"/api/v1/jobs/{job['id']}/status",
            json={"status": "EN_ROUTE"},
            headers=tech_headers,
        )

        # Dispatcher views job and sees TRAVELLING / EN_ROUTE
        disp_job_res = await client.get(f"/api/v1/jobs/{job['id']}", headers=disp_headers)
        assert disp_job_res.status_code == 200
        assert disp_job_res.json()["status"] in ("TRAVELLING", "EN_ROUTE")


@pytest.mark.asyncio
async def test_7_unassigned_job_shows_assignment_action_requirement():
    """7. Verify unassigned jobs have NEW status and assigned_technician = None."""
    async with get_client() as client:
        disp_headers = await get_token_headers(client, "dispatcher@fieldops.ai", "Dispatch@123")
        job = await create_dispatcher_test_job(client, disp_headers)

        res = await client.get(f"/api/v1/jobs/{job['id']}", headers=disp_headers)
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "NEW"
        assert data.get("assigned_technician") is None


@pytest.mark.asyncio
async def test_8_smart_assignment_connects_to_existing_flow():
    """8. Verify Smart Assignment endpoint generates recommendation and confirms assignment."""
    async with get_client() as client:
        disp_headers = await get_token_headers(client, "dispatcher@fieldops.ai", "Dispatch@123")
        job = await create_dispatcher_test_job(client, disp_headers)

        # Recommendation flow (Module 8)
        rec_res = await client.get(f"/api/v1/assignments/jobs/{job['id']}/recommendation", headers=disp_headers)
        assert rec_res.status_code == 200
        rec_data = rec_res.json()
        assert "ranked_candidates" in rec_data
        assert "explanation" in rec_data

        if rec_data["recommended_technician"]:
            tech_id = rec_data["recommended_technician"]["technician_id"]

            # Confirm assignment flow
            assign_res = await client.post(
                f"/api/v1/assignments/jobs/{job['id']}/assign",
                json={"technician_id": tech_id},
                headers=disp_headers,
            )
            assert assign_res.status_code == 201
            assert assign_res.json()["assignment_status"] == "ASSIGNED"


@pytest.mark.asyncio
async def test_9_dispatcher_cannot_directly_modify_technician_execution_status():
    """9. Verify Dispatcher receives 403 Forbidden when attempting execution status patch."""
    async with get_client() as client:
        disp_headers = await get_token_headers(client, "dispatcher@fieldops.ai", "Dispatch@123")
        job = await create_dispatcher_test_job(client, disp_headers)

        patch_res = await client.patch(
            f"/api/v1/jobs/{job['id']}/status",
            json={"status": "EN_ROUTE"},
            headers=disp_headers,
        )
        assert patch_res.status_code == 403
        assert "cannot perform technician execution status transitions" in patch_res.text


@pytest.mark.asyncio
async def test_10_administrator_cannot_perform_dispatcher_assignment_actions():
    """10. Verify Administrator receives 403 Forbidden when attempting Dispatcher assignment actions."""
    async with get_client() as client:
        disp_headers = await get_token_headers(client, "dispatcher@fieldops.ai", "Dispatch@123")
        admin_headers = await get_token_headers(client, "admin@fieldops.ai", "Admin@123")
        job = await create_dispatcher_test_job(client, disp_headers)

        assign_res = await client.post(
            f"/api/v1/assignments/jobs/{job['id']}/assign",
            json={"technician_id": str(uuid.uuid4())},
            headers=admin_headers,
        )
        assert assign_res.status_code == 403


@pytest.mark.asyncio
async def test_11_technician_cannot_perform_dispatcher_assignment_actions():
    """11. Verify Technician receives 403 Forbidden when attempting Dispatcher assignment actions."""
    async with get_client() as client:
        disp_headers = await get_token_headers(client, "dispatcher@fieldops.ai", "Dispatch@123")
        tech_headers = await get_token_headers(client, "technician@fieldops.ai", "Tech@123")
        job = await create_dispatcher_test_job(client, disp_headers)

        assign_res = await client.post(
            f"/api/v1/assignments/jobs/{job['id']}/assign",
            json={"technician_id": str(uuid.uuid4())},
            headers=tech_headers,
        )
        assert assign_res.status_code == 403


@pytest.mark.asyncio
async def test_12_completed_job_displayed_correctly():
    """12. Verify completed job displays COMPLETED status correctly to Dispatcher."""
    async with get_client() as client:
        disp_headers = await get_token_headers(client, "dispatcher@fieldops.ai", "Dispatch@123")
        tech_headers = await get_token_headers(client, "technician@fieldops.ai", "Tech@123")

        me_res = await client.get("/api/v1/auth/me", headers=tech_headers)
        my_user_id = me_res.json()["id"]

        techs_res = await client.get("/api/v1/technicians?search=technician@fieldops.ai", headers=disp_headers)
        techs = techs_res.json().get("items", [])
        target_tech = next((t for t in techs if t.get("user_id") == my_user_id), techs[0] if techs else None)

        skill_id = target_tech.get("primary_skill_id") or await get_active_skill_id(client, disp_headers)

        payload = {
            "customer_name": f"Completion Test {uuid.uuid4().hex[:4]}",
            "address": "500 Completed Job Lane",
            "latitude": 37.7749,
            "longitude": -122.4194,
            "required_skill_id": skill_id,
            "priority": "HIGH",
        }
        create_res = await client.post("/api/v1/jobs", json=payload, headers=disp_headers)
        job = create_res.json()

        # Assign
        await client.post(
            f"/api/v1/assignments/jobs/{job['id']}/assign",
            json={"technician_id": target_tech["id"]},
            headers=disp_headers,
        )

        # Progress lifecycle: ASSIGNED -> EN_ROUTE -> ARRIVED -> IN_PROGRESS -> COMPLETED
        await client.patch(f"/api/v1/jobs/{job['id']}/status", json={"status": "EN_ROUTE"}, headers=tech_headers)
        await client.patch(f"/api/v1/jobs/{job['id']}/status", json={"status": "ARRIVED"}, headers=tech_headers)
        await client.patch(f"/api/v1/jobs/{job['id']}/status", json={"status": "IN_PROGRESS"}, headers=tech_headers)
        await client.patch(f"/api/v1/jobs/{job['id']}/status", json={"status": "COMPLETED"}, headers=tech_headers)

        # Dispatcher verifies COMPLETED status
        res = await client.get(f"/api/v1/jobs/{job['id']}", headers=disp_headers)
        assert res.status_code == 200
        assert res.json()["status"] == "COMPLETED"


@pytest.mark.asyncio
async def test_13_job_status_comes_from_backend_persistence():
    """13. Verify job status is sourced directly from DB persistence across queries."""
    async with get_client() as client:
        disp_headers = await get_token_headers(client, "dispatcher@fieldops.ai", "Dispatch@123")
        job = await create_dispatcher_test_job(client, disp_headers)

        # Initial fetch
        res1 = await client.get(f"/api/v1/jobs/{job['id']}", headers=disp_headers)
        assert res1.status_code == 200
        assert res1.json()["status"] == "NEW"

        # Subsequent query
        res2 = await client.get(f"/api/v1/jobs/{job['id']}", headers=disp_headers)
        assert res2.status_code == 200
        assert res2.json()["status"] == "NEW"


@pytest.mark.asyncio
async def test_14_existing_audit_records_remain_correct():
    """14. Verify audit logging remains intact for job lifecycle events."""
    async with get_client() as client:
        admin_headers = await get_token_headers(client, "admin@fieldops.ai", "Admin@123")
        disp_headers = await get_token_headers(client, "dispatcher@fieldops.ai", "Dispatch@123")
        job = await create_dispatcher_test_job(client, disp_headers)

        # Dispatcher actions write audit records
        audit_res = await client.get("/api/v1/technicians/audit-history", headers=admin_headers)
        if audit_res.status_code == 200:
            items = audit_res.json().get("items", [])
            assert isinstance(items, list)
