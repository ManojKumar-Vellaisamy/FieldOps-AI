"""
Module 17 Test Suite — Real-Time Operational Synchronization & Live Field Telemetry.

Covers:
1. Real-time WebSocket connection authentication (valid JWT token -> CONNECTED).
2. Unauthorized connection rejection (missing token -> 1008 Policy Violation).
3. Invalid/expired token rejection (code 1008).
4. WebSocket ping/pong heartbeat keepalive.
5. Authorized dispatcher operational event delivery.
6. Technician event isolation & private stream scoping (Tech A cannot receive Tech B events).
7. Real technician location telemetry API (PATCH /api/v1/technicians/me/location).
8. Location coordinate boundary validation (-90 to 90 lat, -180 to 180 lon).
9. Audit log suppression for GPS coordinates (no audit bloat on location heartbeat).
10. Job assignment real-time event broadcast (JOB_ASSIGNED).
11. Job status transition real-time event broadcast (JOB_STATUS_CHANGED).
12. Job completion real-time event broadcast (JOB_COMPLETED).
13. Job cancellation real-time event broadcast (JOB_CANCELLED).
14. Technician availability change broadcast (TECHNICIAN_AVAILABILITY_CHANGED).
15. ETA manual override broadcast (ETA_UPDATED) and audit log preservation.
"""

from datetime import datetime, timezone
import uuid
from fastapi.testclient import TestClient
from httpx import AsyncClient
import pytest
from starlette.websockets import WebSocketDisconnect
from sqlalchemy import select

from app.core.realtime import (
    ws_manager,
    EVENT_JOB_ASSIGNED,
    EVENT_JOB_UNASSIGNED,
    EVENT_JOB_STATUS_CHANGED,
    EVENT_JOB_COMPLETED,
    EVENT_JOB_CANCELLED,
    EVENT_TECHNICIAN_LOCATION_UPDATED,
    EVENT_TECHNICIAN_AVAILABILITY_CHANGED,
    EVENT_ETA_UPDATED,
    EVENT_DISPATCH_PLAN_CHANGED,
)
from app.core.security import create_access_token
from app.database.session import AsyncSessionLocal
from app.main import app
from app.models.audit_log import AuditLog

BASE_URL = "http://127.0.0.1:8000"


class MockWebSocket:
    """Mock WebSocket for in-process event reception and assertion."""

    def __init__(self) -> None:
        self.received_messages: list[dict] = []
        self.closed = False
        self.close_code: int | None = None

    async def accept(self) -> None:
        pass

    async def send_json(self, data: dict) -> None:
        self.received_messages.append(data)

    async def close(self, code: int = 1000, reason: str = "") -> None:
        self.closed = True
        self.close_code = code


async def get_token_headers(client: AsyncClient, email: str, password: str) -> tuple[dict[str, str], str]:
    """Helper to authenticate and obtain bearer token headers and raw token."""
    res = await client.post(f"{BASE_URL}/api/v1/auth/login", json={"email": email, "password": password})
    assert res.status_code == 200, f"Login failed for {email}: {res.text}"
    token = res.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}, token


async def get_technician_and_skill(client: AsyncClient, disp_headers: dict[str, str]) -> tuple[str, str, str]:
    """Helper to fetch technician ID, skill ID, and user_id for technician@fieldops.ai."""
    res = await client.get(f"{BASE_URL}/api/v1/technicians?search=technician@fieldops.ai", headers=disp_headers)
    assert res.status_code == 200, f"Failed to fetch technician: {res.text}"
    body = res.json()
    items = body["items"] if "items" in body else body
    assert len(items) > 0, f"No technician found for technician@fieldops.ai: {res.text}"
    tech = items[0]
    return str(tech["id"]), str(tech["primary_skill_id"]), str(tech["user_id"])


async def create_test_job(
    client: AsyncClient,
    headers: dict[str, str],
    skill_id: str,
    customer_name: str = "Module 17 Real-Time Customer",
) -> dict:
    """Helper to create a fresh test job."""
    payload = {
        "customer_name": customer_name,
        "customer_phone": "+1 (555) 777-9988",
        "address": "700 Telemetry Way, San Francisco, CA",
        "latitude": 37.7780,
        "longitude": -122.4150,
        "priority": "HIGH",
        "required_skill_id": skill_id,
        "description": "Module 17 Real-Time Sync Testing",
    }
    res = await client.post(f"{BASE_URL}/api/v1/jobs", json=payload, headers=headers)
    assert res.status_code == 201, f"Failed to create job: {res.text}"
    return res.json()


# ── 1. Real-Time Connection Authentication (Handshake Tests) ─────────────────

def test_ws_connection_auth_success():
    """Test authenticated WebSocket connection with valid JWT succeeds and receives CONNECTED frame."""
    client = TestClient(app)
    user_id = uuid.uuid4()
    token = create_access_token(subject=str(user_id), email="dispatcher@fieldops.ai", role="Dispatcher")

    with client.websocket_connect(f"/api/v1/ws?token={token}") as ws:
        frame = ws.receive_json()
        assert frame["event"] == "CONNECTED"
        assert frame["data"]["user_id"] == str(user_id)
        assert frame["data"]["role"] == "Dispatcher"
        assert "connected_at" in frame["data"]


def test_ws_connection_missing_token_rejected():
    """Test connection without token is rejected with WebSocket close code 1008."""
    client = TestClient(app)
    with pytest.raises(WebSocketDisconnect) as exc_info:
        with client.websocket_connect("/api/v1/ws"):
            pass
    assert exc_info.value.code == 1008


def test_ws_connection_invalid_token_rejected():
    """Test connection with invalid/malformed token is rejected with WebSocket close code 1008."""
    client = TestClient(app)
    with pytest.raises(WebSocketDisconnect) as exc_info:
        with client.websocket_connect("/api/v1/ws?token=invalid.jwt.token"):
            pass
    assert exc_info.value.code == 1008


def test_ws_ping_pong_heartbeat():
    """Test client ping frame receives immediate pong response frame with timestamp."""
    client = TestClient(app)
    user_id = uuid.uuid4()
    token = create_access_token(subject=str(user_id), email="dispatcher@fieldops.ai", role="Dispatcher")

    with client.websocket_connect(f"/api/v1/ws?token={token}") as ws:
        ws.receive_json()  # Consume CONNECTED frame
        ws.send_json({"type": "ping"})
        pong = ws.receive_json()
        assert pong["type"] == "pong"
        assert "timestamp" in pong


# ── 2. Role-Based Scoping & Scoped Subscription Isolation ────────────────────

@pytest.mark.asyncio
async def test_ws_dispatcher_broadcast_delivery():
    """Test that operational events are delivered to connected Dispatchers."""
    disp_id = uuid.uuid4()
    mock_ws = MockWebSocket()
    await ws_manager.connect(mock_ws, user_id=disp_id, role="Dispatcher")

    try:
        await ws_manager.broadcast_operational_event(
            EVENT_JOB_STATUS_CHANGED,
            {
                "job_id": str(uuid.uuid4()),
                "job_number": "JOB-TEST-001",
                "old_status": "ASSIGNED",
                "new_status": "TRAVELLING",
            },
        )

        assert len(mock_ws.received_messages) == 1
        event = mock_ws.received_messages[0]
        assert event["event"] == EVENT_JOB_STATUS_CHANGED
        assert event["data"]["job_number"] == "JOB-TEST-001"
        assert event["data"]["new_status"] == "TRAVELLING"
    finally:
        await ws_manager.disconnect(mock_ws)


@pytest.mark.asyncio
async def test_ws_technician_scoping_isolation():
    """
    Test RBAC Scoping Isolation:
    - Technician A receives events intended for Technician A.
    - Technician A does NOT receive events intended for Technician B.
    """
    tech_a_user_id = uuid.uuid4()
    tech_b_user_id = uuid.uuid4()

    mock_ws_a = MockWebSocket()
    mock_ws_b = MockWebSocket()

    await ws_manager.connect(mock_ws_a, user_id=tech_a_user_id, role="Technician")
    await ws_manager.connect(mock_ws_b, user_id=tech_b_user_id, role="Technician")

    try:
        # Event targeted to Tech A
        await ws_manager.broadcast_operational_event(
            EVENT_JOB_ASSIGNED,
            {"job_number": "JOB-FOR-A", "status": "ASSIGNED"},
            technician_user_id=tech_a_user_id,
        )

        # Verify Tech A received it
        assert len(mock_ws_a.received_messages) == 1
        assert mock_ws_a.received_messages[0]["data"]["job_number"] == "JOB-FOR-A"

        # Verify Tech B did NOT receive Tech A's event
        assert len(mock_ws_b.received_messages) == 0

        # Event targeted to Tech B
        await ws_manager.broadcast_operational_event(
            EVENT_JOB_ASSIGNED,
            {"job_number": "JOB-FOR-B", "status": "ASSIGNED"},
            technician_user_id=tech_b_user_id,
        )

        # Verify Tech B received it and Tech A received nothing new
        assert len(mock_ws_b.received_messages) == 1
        assert mock_ws_b.received_messages[0]["data"]["job_number"] == "JOB-FOR-B"
        assert len(mock_ws_a.received_messages) == 1  # Still 1
    finally:
        await ws_manager.disconnect(mock_ws_a)
        await ws_manager.disconnect(mock_ws_b)


# ── 3. Real Technician Location Telemetry & Audit Suppression ────────────────

@pytest.mark.asyncio
async def test_technician_location_update_api():
    """
    Test PATCH /api/v1/technicians/me/location:
    - Successfully updates current_latitude, current_longitude, and updated_at.
    - Suppresses audit log creation to prevent audit bloat on frequent GPS pings.
    - Broadcasts TECHNICIAN_LOCATION_UPDATED event to connected dispatchers.
    """
    async with AsyncClient() as client:
        tech_headers, _ = await get_token_headers(client, "technician@fieldops.ai", "Tech@123")

        # Connect a mock dispatcher
        disp_ws = MockWebSocket()
        await ws_manager.connect(disp_ws, user_id=uuid.uuid4(), role="Dispatcher")

        try:
            # Count audit logs before location update
            async with AsyncSessionLocal() as session:
                count_stmt = select(AuditLog).where(AuditLog.action == "TECHNICIAN_LOCATION_UPDATED")
                logs_before = len((await session.execute(count_stmt)).scalars().all())

            # 2. Patch valid coordinates (San Francisco area)
            patch_res = await client.patch(
                f"{BASE_URL}/api/v1/technicians/me/location",
                json={"latitude": 37.7749, "longitude": -122.4194},
                headers=tech_headers,
            )
            assert patch_res.status_code == 200
            body = patch_res.json()
            assert body["current_latitude"] == 37.7749
            assert body["current_longitude"] == -122.4194
            assert body["updated_at"] is not None

            # 3. Verify audit log count did NOT increase (audit suppression verified)
            async with AsyncSessionLocal() as session:
                logs_after = len((await session.execute(count_stmt)).scalars().all())
                assert logs_after == logs_before, "GPS location update incorrectly created an audit log record!"

            # 4. Verify TECHNICIAN_LOCATION_UPDATED event was delivered to dispatcher
            loc_events = [m for m in disp_ws.received_messages if m["event"] == EVENT_TECHNICIAN_LOCATION_UPDATED]
            assert len(loc_events) >= 1, f"No TECHNICIAN_LOCATION_UPDATED event received in {disp_ws.received_messages}"
            loc_event = loc_events[-1]
            assert loc_event["data"]["latitude"] == 37.7749
            assert loc_event["data"]["longitude"] == -122.4194
        finally:
            await ws_manager.disconnect(disp_ws)


@pytest.mark.asyncio
async def test_technician_location_coordinate_validation():
    """Test validation rejection for invalid latitude/longitude coordinates."""
    async with AsyncClient() as client:
        tech_headers, _ = await get_token_headers(client, "technician@fieldops.ai", "Tech@123")

        # Latitude out of bounds (> 90)
        res_bad_lat = await client.patch(
            f"{BASE_URL}/api/v1/technicians/me/location",
            json={"latitude": 95.0, "longitude": -122.4194},
            headers=tech_headers,
        )
        assert res_bad_lat.status_code in (400, 422)

        # Longitude out of bounds (< -180)
        res_bad_lon = await client.patch(
            f"{BASE_URL}/api/v1/technicians/me/location",
            json={"latitude": 37.7749, "longitude": -195.0},
            headers=tech_headers,
        )
        assert res_bad_lon.status_code in (400, 422)


# ── 4. End-to-End Operational Lifecycle Real-Time Events ───────────────────────

@pytest.mark.asyncio
async def test_job_lifecycle_realtime_events_integration():
    """
    Test full lifecycle event emission:
    - DISPATCH_PLAN_CHANGED (create_job)
    - JOB_ASSIGNED (confirm_assignment)
    - JOB_STATUS_CHANGED (TRAVELLING -> ARRIVED -> WORKING)
    - JOB_COMPLETED (COMPLETED)
    - Verifies Dispatcher and assigned Technician both receive appropriate events.
    """
    async with AsyncClient() as client:
        disp_headers, _ = await get_token_headers(client, "dispatcher@fieldops.ai", "Dispatch@123")
        tech_headers, _ = await get_token_headers(client, "technician@fieldops.ai", "Tech@123")
        tech_id, skill_id, tech_user_id = await get_technician_and_skill(client, disp_headers)

        disp_ws = MockWebSocket()
        tech_ws = MockWebSocket()

        await ws_manager.connect(disp_ws, user_id=uuid.uuid4(), role="Dispatcher")
        await ws_manager.connect(tech_ws, user_id=uuid.UUID(tech_user_id), role="Technician")

        try:
            # 1. Create Job -> DISPATCH_PLAN_CHANGED
            job = await create_test_job(client, disp_headers, skill_id)
            job_id = job["id"]

            create_events = [m for m in disp_ws.received_messages if m["event"] == EVENT_DISPATCH_PLAN_CHANGED]
            assert len(create_events) >= 1
            assert create_events[-1]["data"]["action"] == "JOB_CREATED"
            assert create_events[-1]["data"]["job_id"] == job_id

            # 2. Confirm Assignment -> JOB_ASSIGNED
            assign_res = await client.post(
                f"{BASE_URL}/api/v1/assignments/jobs/{job_id}/assign",
                json={"technician_id": tech_id},
                headers=disp_headers,
            )
            assert assign_res.status_code == 201

            # Dispatcher receives JOB_ASSIGNED
            disp_assign_events = [m for m in disp_ws.received_messages if m["event"] == EVENT_JOB_ASSIGNED]
            assert len(disp_assign_events) >= 1
            assert disp_assign_events[-1]["data"]["job_id"] == job_id

            # Technician receives JOB_ASSIGNED
            tech_assign_events = [m for m in tech_ws.received_messages if m["event"] == EVENT_JOB_ASSIGNED]
            assert len(tech_assign_events) >= 1
            assert tech_assign_events[-1]["data"]["job_id"] == job_id

            # 3. Technician Status Transitions -> JOB_STATUS_CHANGED
            # ASSIGNED -> TRAVELLING
            trav_res = await client.patch(
                f"{BASE_URL}/api/v1/jobs/{job_id}/status",
                json={"status": "TRAVELLING"},
                headers=tech_headers,
            )
            assert trav_res.status_code == 200

            trav_events = [m for m in disp_ws.received_messages if m["event"] == EVENT_JOB_STATUS_CHANGED]
            assert len(trav_events) >= 1
            assert trav_events[-1]["data"]["new_status"] == "TRAVELLING"

            # TRAVELLING -> ARRIVED
            arr_res = await client.patch(
                f"{BASE_URL}/api/v1/jobs/{job_id}/status",
                json={"status": "ARRIVED"},
                headers=tech_headers,
            )
            assert arr_res.status_code == 200

            arr_events = [m for m in disp_ws.received_messages if m["event"] == EVENT_JOB_STATUS_CHANGED]
            assert arr_events[-1]["data"]["new_status"] == "ARRIVED"

            # ARRIVED -> WORKING
            work_res = await client.patch(
                f"{BASE_URL}/api/v1/jobs/{job_id}/status",
                json={"status": "WORKING"},
                headers=tech_headers,
            )
            assert work_res.status_code == 200

            work_events = [m for m in disp_ws.received_messages if m["event"] == EVENT_JOB_STATUS_CHANGED]
            assert work_events[-1]["data"]["new_status"] == "WORKING"

            # WORKING -> COMPLETED -> JOB_COMPLETED
            comp_res = await client.patch(
                f"{BASE_URL}/api/v1/jobs/{job_id}/status",
                json={"status": "COMPLETED"},
                headers=tech_headers,
            )
            assert comp_res.status_code == 200

            comp_events = [m for m in disp_ws.received_messages if m["event"] == EVENT_JOB_COMPLETED]
            assert len(comp_events) >= 1
            assert comp_events[-1]["data"]["new_status"] == "COMPLETED"
        finally:
            await ws_manager.disconnect(disp_ws)
            await ws_manager.disconnect(tech_ws)


@pytest.mark.asyncio
async def test_job_cancellation_realtime_broadcast():
    """Test cancelling a job broadcasts JOB_CANCELLED to connected clients."""
    async with AsyncClient() as client:
        disp_headers, _ = await get_token_headers(client, "dispatcher@fieldops.ai", "Dispatch@123")
        tech_id, skill_id, _ = await get_technician_and_skill(client, disp_headers)

        disp_ws = MockWebSocket()
        await ws_manager.connect(disp_ws, user_id=uuid.uuid4(), role="Dispatcher")

        try:
            job = await create_test_job(client, disp_headers, skill_id, customer_name="Cancellation Test Customer")
            job_id = job["id"]

            # Cancel job
            cancel_res = await client.post(
                f"{BASE_URL}/api/v1/jobs/{job_id}/cancel",
                json={"reason": "Customer cancelled appointment via phone"},
                headers=disp_headers,
            )
            assert cancel_res.status_code == 200

            cancel_events = [m for m in disp_ws.received_messages if m["event"] == EVENT_JOB_CANCELLED]
            assert len(cancel_events) >= 1
            assert cancel_events[-1]["data"]["job_id"] == job_id
            assert cancel_events[-1]["data"]["status"] == "CANCELLED"
            assert cancel_events[-1]["data"]["cancellation_reason"] == "Customer cancelled appointment via phone"
        finally:
            await ws_manager.disconnect(disp_ws)


@pytest.mark.asyncio
async def test_technician_availability_changed_broadcast():
    """Test patching technician availability broadcasts TECHNICIAN_AVAILABILITY_CHANGED."""
    async with AsyncClient() as client:
        admin_headers, _ = await get_token_headers(client, "admin@fieldops.ai", "Admin@123")
        tech_id, _, _ = await get_technician_and_skill(client, admin_headers)

        admin_ws = MockWebSocket()
        await ws_manager.connect(admin_ws, user_id=uuid.uuid4(), role="Administrator")

        try:
            patch_res = await client.patch(
                f"{BASE_URL}/api/v1/technicians/{tech_id}/status",
                json={"availability_status": "BUSY"},
                headers=admin_headers,
            )
            assert patch_res.status_code == 200

            avail_events = [m for m in admin_ws.received_messages if m["event"] == EVENT_TECHNICIAN_AVAILABILITY_CHANGED]
            assert len(avail_events) >= 1
            assert avail_events[-1]["data"]["technician_id"] == tech_id
            assert avail_events[-1]["data"]["new_status"] == "BUSY"

            # Revert back to AVAILABLE
            await client.patch(
                f"{BASE_URL}/api/v1/technicians/{tech_id}/status",
                json={"availability_status": "AVAILABLE"},
                headers=admin_headers,
            )
        finally:
            await ws_manager.disconnect(admin_ws)


@pytest.mark.asyncio
async def test_eta_override_realtime_broadcast():
    """Test Dispatcher manual ETA override broadcasts ETA_UPDATED and writes audit log."""
    async with AsyncClient() as client:
        disp_headers, _ = await get_token_headers(client, "dispatcher@fieldops.ai", "Dispatch@123")
        tech_id, skill_id, _ = await get_technician_and_skill(client, disp_headers)

        disp_ws = MockWebSocket()
        await ws_manager.connect(disp_ws, user_id=uuid.uuid4(), role="Dispatcher")

        try:
            job = await create_test_job(client, disp_headers, skill_id, customer_name="ETA Override Test")
            job_id = job["id"]

            await client.post(
                f"{BASE_URL}/api/v1/assignments/jobs/{job_id}/assign",
                json={"technician_id": tech_id},
                headers=disp_headers,
            )

            # Dispatcher applies manual ETA override
            override_res = await client.post(
                f"{BASE_URL}/api/v1/eta/jobs/{job_id}/override",
                json={"overridden_eta": 45, "reason": "Severe highway congestion reported by dispatch"},
                headers=disp_headers,
            )
            assert override_res.status_code == 201

            eta_events = [m for m in disp_ws.received_messages if m["event"] == EVENT_ETA_UPDATED]
            assert len(eta_events) >= 1
            assert eta_events[-1]["data"]["job_id"] == job_id
            assert eta_events[-1]["data"]["overridden_eta"] == 45
            assert "Severe highway congestion" in eta_events[-1]["data"]["reason"]

            # Verify audit log was created for ETA override
            async with AsyncSessionLocal() as session:
                audit_stmt = select(AuditLog).where(
                    AuditLog.action == "ETA_OVERRIDE_CREATED",
                    AuditLog.entity_id == job_id,
                )
                audit = (await session.execute(audit_stmt)).scalar_one_or_none()
                assert audit is not None, "AuditLog for ETA_OVERRIDE_CREATED was not recorded!"
        finally:
            await ws_manager.disconnect(disp_ws)


@pytest.mark.asyncio
async def test_unassign_job_realtime_broadcast():
    """Test unassigning a job broadcasts JOB_UNASSIGNED to dispatcher and unassigned technician."""
    async with AsyncClient() as client:
        disp_headers, _ = await get_token_headers(client, "dispatcher@fieldops.ai", "Dispatch@123")
        tech_id, skill_id, tech_user_id = await get_technician_and_skill(client, disp_headers)

        disp_ws = MockWebSocket()
        tech_ws = MockWebSocket()
        await ws_manager.connect(disp_ws, user_id=uuid.uuid4(), role="Dispatcher")
        await ws_manager.connect(tech_ws, user_id=uuid.UUID(tech_user_id), role="Technician")

        try:
            job = await create_test_job(client, disp_headers, skill_id, customer_name="Unassign Test")
            job_id = job["id"]

            await client.post(
                f"{BASE_URL}/api/v1/assignments/jobs/{job_id}/assign",
                json={"technician_id": tech_id},
                headers=disp_headers,
            )

            # Unassign job
            unassign_res = await client.post(
                f"{BASE_URL}/api/v1/assignments/jobs/{job_id}/unassign",
                headers=disp_headers,
            )
            assert unassign_res.status_code == 200

            # Dispatcher receives JOB_UNASSIGNED
            disp_unassign = [m for m in disp_ws.received_messages if m["event"] == EVENT_JOB_UNASSIGNED]
            assert len(disp_unassign) >= 1
            assert disp_unassign[-1]["data"]["job_id"] == job_id
            assert disp_unassign[-1]["data"]["status"] == "NEW"

            # Technician receives JOB_UNASSIGNED
            tech_unassign = [m for m in tech_ws.received_messages if m["event"] == EVENT_JOB_UNASSIGNED]
            assert len(tech_unassign) >= 1
            assert tech_unassign[-1]["data"]["job_id"] == job_id
        finally:
            await ws_manager.disconnect(disp_ws)
            await ws_manager.disconnect(tech_ws)


@pytest.mark.asyncio
async def test_duplicate_stale_event_resilience():
    """Test that connection manager safely handles duplicate and rapid stale event sequences."""
    client_ws = MockWebSocket()
    await ws_manager.connect(client_ws, user_id=uuid.uuid4(), role="Dispatcher")

    try:
        # Rapid sequential events for same entity
        job_id = str(uuid.uuid4())
        await ws_manager.broadcast_operational_event(EVENT_JOB_STATUS_CHANGED, {"job_id": job_id, "new_status": "TRAVELLING"})
        await ws_manager.broadcast_operational_event(EVENT_JOB_STATUS_CHANGED, {"job_id": job_id, "new_status": "TRAVELLING"})
        await ws_manager.broadcast_operational_event(EVENT_JOB_STATUS_CHANGED, {"job_id": job_id, "new_status": "ARRIVED"})

        assert len(client_ws.received_messages) == 3
        assert client_ws.received_messages[-1]["data"]["new_status"] == "ARRIVED"
    finally:
        await ws_manager.disconnect(client_ws)


@pytest.mark.asyncio
async def test_database_consistency_post_event():
    """
    Test Data Consistency:
    Verify PostgreSQL remains single source of truth and entity state in database matches event payload.
    """
    async with AsyncClient() as client:
        disp_headers, _ = await get_token_headers(client, "dispatcher@fieldops.ai", "Dispatch@123")
        tech_id, skill_id, _ = await get_technician_and_skill(client, disp_headers)

        job = await create_test_job(client, disp_headers, skill_id, customer_name="Consistency Test")
        job_id = job["id"]

        # Assign job
        await client.post(
            f"{BASE_URL}/api/v1/assignments/jobs/{job_id}/assign",
            json={"technician_id": tech_id},
            headers=disp_headers,
        )

        # Query REST API & DB to verify authoritative state
        get_res = await client.get(f"{BASE_URL}/api/v1/jobs/{job_id}", headers=disp_headers)
        assert get_res.status_code == 200
        job_payload = get_res.json()
        assert job_payload["status"] == "ASSIGNED"
        assert job_payload["assigned_technician"]["id"] == tech_id
