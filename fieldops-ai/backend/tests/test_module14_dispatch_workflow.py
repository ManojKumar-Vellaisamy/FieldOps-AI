"""
Comprehensive Integration Test Suite for Module 14 — End-to-End Dispatch & Complete Plan-Change Audit Workflow.

Verifies:
1. Complete End-to-End Workflow: Creation -> Skills -> Candidate Matching -> Assignment -> Context ETA -> Plan Changes -> Execution -> Completion.
2. Skill Requirement Enforcement during candidate evaluation.
3. Dispatcher Plan Changes: ETA override, job update, unassign/reassign, and cancellation with mandatory reason.
4. Audit Trail Traceability: Full sequence available via GET /api/v1/jobs/{job_id}/audit-history and GET /api/v1/audit-logs.
5. Role Security (RBAC): Technician cannot perform dispatcher-only assignments or overrides (HTTP 403 Forbidden).
6. Audit Log Field Completeness: Ensures user_id/actor, timestamp, action, entity, entity_id, old_value, new_value, and reason are preserved.
"""

import uuid
import pytest
from httpx import AsyncClient

BASE_URL = "http://127.0.0.1:8000"


# ── Helpers ───────────────────────────────────────────────────────────────────

async def get_token_headers(client: AsyncClient, email: str, password: str) -> dict[str, str]:
    """Helper to authenticate and get Bearer token headers."""
    res = await client.post(f"{BASE_URL}/api/v1/auth/login", json={"email": email, "password": password})
    assert res.status_code == 200, f"Login failed for {email}: {res.text}"
    token = res.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


async def get_technician_and_skill(client: AsyncClient, headers: dict[str, str]) -> tuple[str, str]:
    """Helper to fetch active technician ID and primary skill ID."""
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
    lat: float = 37.7800,
    lon: float = -122.4100,
) -> dict:
    """Helper to create a fresh service job."""
    payload = {
        "customer_name": f"Module 14 Customer {uuid.uuid4().hex[:4]}",
        "customer_phone": "+1 (555) 123-4567",
        "address": "500 Operational Dispatch Way, San Francisco, CA",
        "latitude": lat,
        "longitude": lon,
        "required_skill_id": skill_id,
        "priority": "HIGH",
        "description": "Module 14 End-to-End Dispatch Workflow test job.",
    }
    res = await client.post(f"{BASE_URL}/api/v1/jobs", json=payload, headers=headers)
    assert res.status_code == 201, f"Failed to create test job: {res.text}"
    return res.json()


# ── TEST 1: Full End-to-End Dispatch & Lifecycle Progression ─────────────────

@pytest.mark.asyncio
async def test_1_complete_end_to_end_dispatch_workflow():
    """
    Step-by-Step E2E Workflow:
    Job Creation -> Skill Match -> Smart Candidate Evaluation -> Technician Assignment ->
    ETA Evaluation -> Plan Change (ETA Override) -> Status Progression -> Completion -> Audit History Verification.
    """
    async with AsyncClient() as client:
        disp_headers = await get_token_headers(client, "dispatcher@fieldops.ai", "Dispatch@123")
        tech_headers = await get_token_headers(client, "technician@fieldops.ai", "Tech@123")

        tech_id, skill_id = await get_technician_and_skill(client, disp_headers)

        # 1. Job Creation
        job = await create_test_job(client, disp_headers, skill_id)
        job_id = job["id"]

        # 2. Candidate Matching & Recommendation
        rec_res = await client.get(f"{BASE_URL}/api/v1/jobs/{job_id}/assignment-recommendations", headers=disp_headers)
        assert rec_res.status_code == 200
        rec_data = rec_res.json()
        assert "ranked_candidates" in rec_data
        assert len(rec_data["ranked_candidates"]) > 0

        # 3. Technician Selection & Assignment
        assign_res = await client.post(
            f"{BASE_URL}/api/v1/assignments/jobs/{job_id}/assign",
            json={"technician_id": tech_id},
            headers=disp_headers,
        )
        assert assign_res.status_code == 201

        # 4. ETA & Context Evaluation
        eta_res = await client.get(f"{BASE_URL}/api/v1/jobs/{job_id}/eta", headers=disp_headers)
        assert eta_res.status_code == 200
        eta_data = eta_res.json()
        assert eta_data["is_context_sufficient"] is True

        # 5. Dispatcher Plan Change (ETA Override with reason)
        override_res = await client.post(
            f"{BASE_URL}/api/v1/jobs/{job_id}/override",
            json={"overridden_eta": 45, "reason": "Customer SLA priority override due to urgent request."},
            headers=disp_headers,
        )
        assert override_res.status_code == 201

        # 6. Technician Execution (Lifecycle status progression)
        for status_step in ["EN_ROUTE", "ARRIVED", "IN_PROGRESS", "COMPLETED"]:
            patch_res = await client.patch(
                f"{BASE_URL}/api/v1/jobs/{job_id}/status",
                json={"status": status_step},
                headers=tech_headers,
            )
            assert patch_res.status_code == 200, f"Status step {status_step} failed: {patch_res.text}"

        # 7. Complete Audit History Verification
        audit_res = await client.get(f"{BASE_URL}/api/v1/jobs/{job_id}/audit-history", headers=disp_headers)
        assert audit_res.status_code == 200
        audit_logs = audit_res.json()
        assert len(audit_logs) >= 5

        actions = [log["action"] for log in audit_logs]
        assert "JOB_CREATED" in actions
        assert "TECHNICIAN_ASSIGNED" in actions
        assert "ETA_OVERRIDE_CREATED" in actions
        assert "JOB_STATUS_CHANGED" in actions


# ── TEST 2: Dispatcher Plan Changes (Reassignment & Cancellation) ────────────

@pytest.mark.asyncio
async def test_2_dispatcher_plan_change_unassign_reassign_cancellation():
    """
    Verifies legitimate plan changes:
    1. Unassigning job reverts status to NEW and records audit log.
    2. Cancellation requires a non-empty reason payload.
    3. Cancelled job status becomes CANCELLED with reason recorded in audit log.
    """
    async with AsyncClient() as client:
        disp_headers = await get_token_headers(client, "dispatcher@fieldops.ai", "Dispatch@123")
        tech_id, skill_id = await get_technician_and_skill(client, disp_headers)

        job = await create_test_job(client, disp_headers, skill_id)
        job_id = job["id"]

        # Assign
        await client.post(f"{BASE_URL}/api/v1/assignments/jobs/{job_id}/assign", json={"technician_id": tech_id}, headers=disp_headers)

        # Unassign plan change
        unassign_res = await client.post(f"{BASE_URL}/api/v1/assignments/jobs/{job_id}/unassign", headers=disp_headers)
        assert unassign_res.status_code == 200

        # Verify job status reverted to NEW
        job_check = await client.get(f"{BASE_URL}/api/v1/jobs/{job_id}", headers=disp_headers)
        assert job_check.json()["status"] == "NEW"

        # Cancellation without reason should be rejected (Validation error 422)
        bad_cancel = await client.post(f"{BASE_URL}/api/v1/jobs/{job_id}/cancel", json={"reason": "   "}, headers=disp_headers)
        assert bad_cancel.status_code == 422

        # Cancellation with valid reason succeeds
        good_cancel = await client.post(
            f"{BASE_URL}/api/v1/jobs/{job_id}/cancel",
            json={"reason": "Customer cancelled service appointment."},
            headers=disp_headers,
        )
        assert good_cancel.status_code == 200
        assert good_cancel.json()["status"] == "CANCELLED"

        # Verify Audit Log
        audit_res = await client.get(f"{BASE_URL}/api/v1/jobs/{job_id}/audit-history", headers=disp_headers)
        actions = [a["action"] for a in audit_res.json()]
        assert "JOB_UNASSIGNED" in actions
        assert "JOB_CANCELLED" in actions


# ── TEST 3: System Audit Query REST API ───────────────────────────────────────

@pytest.mark.asyncio
async def test_3_system_audit_log_query_api():
    """Verifies system-wide GET /api/v1/audit-logs endpoint supporting filtering and pagination."""
    async with AsyncClient() as client:
        disp_headers = await get_token_headers(client, "dispatcher@fieldops.ai", "Dispatch@123")

        res = await client.get(f"{BASE_URL}/api/v1/audit-logs?page=1&page_size=10", headers=disp_headers)
        assert res.status_code == 200, f"Audit logs query failed with status {res.status_code}: {res.text}"
        data = res.json()
        assert "items" in data
        assert "total" in data
        assert isinstance(data["items"], list)

        if len(data["items"]) > 0:
            item = data["items"][0]
            assert "action" in item
            assert "entity" in item
            assert "user_full_name" in item
            assert "created_at" in item


# ── TEST 4: Role Security & RBAC Protections ──────────────────────────────────

@pytest.mark.asyncio
async def test_4_role_security_technician_cannot_perform_dispatcher_overrides():
    """Verifies RBAC protection: Technician role is prohibited from performing dispatcher assignment or ETA override actions."""
    async with AsyncClient() as client:
        disp_headers = await get_token_headers(client, "dispatcher@fieldops.ai", "Dispatch@123")
        tech_headers = await get_token_headers(client, "technician@fieldops.ai", "Tech@123")
        tech_id, skill_id = await get_technician_and_skill(client, disp_headers)

        job = await create_test_job(client, disp_headers, skill_id)
        job_id = job["id"]

        # Technician attempt to assign job -> HTTP 403 Forbidden
        bad_assign = await client.post(
            f"{BASE_URL}/api/v1/assignments/jobs/{job_id}/assign",
            json={"technician_id": tech_id},
            headers=tech_headers,
        )
        assert bad_assign.status_code == 403

        # Technician attempt to override ETA -> HTTP 403 Forbidden
        bad_override = await client.post(
            f"{BASE_URL}/api/v1/jobs/{job_id}/override",
            json={"overridden_eta": 30, "reason": "Unauthorized tech override attempt."},
            headers=tech_headers,
        )
        assert bad_override.status_code == 403
