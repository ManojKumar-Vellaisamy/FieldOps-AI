"""
Integration and Unit Tests for Context-Aware ETA Engine (Module 10).

Verifies:
1.  Baseline ETA calculation from transit distance.
2.  Context-aware ETA calculation combining baseline and operational factors.
3.  Operational weather adjustment impact.
4.  Positive adjustment (+5 min delay for moderate rain).
5.  Zero adjustment under clear conditions and zero backlog.
6.  Missing context handling (unassigned job, missing GPS telemetry).
7.  Invalid job handling (404 Not Found).
8.  Dispatcher authorization (200 OK across operational jobs).
9.  Administrator authorization (200 OK read telemetry across jobs).
10. Technician ownership restriction (403 Forbidden on other jobs, 200 OK on own assigned job).
11. ETA response consistency and explainability factors schema.
12. Existing job execution lifecycle regression safety.
13. data_sources array present with all 5 context sources enumerated.
14. Traffic source is explicitly UNAVAILABLE (no external data feed integrated).
15. estimated_arrival_time is a valid ISO-8601 UTC datetime after calculated_at.
16. distance_km is positive and consistent with distance_miles.
17. Technician cannot access another technician's ETA (cross-technician RBAC).
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
    latitude: float | None = 37.7749,
    longitude: float | None = -122.4194,
) -> dict:
    """Helper to create a fresh test job."""
    payload = {
        "customer_name": f"ETA Test Customer {uuid.uuid4().hex[:4]}",
        "customer_phone": "+1 (555) 999-0011",
        "address": "742 Evergreen Terrace, San Francisco, CA",
        "latitude": latitude if latitude is not None else 37.7749,
        "longitude": longitude if longitude is not None else -122.4194,
        "required_skill_id": skill_id,
        "priority": "HIGH",
        "description": "Validation job for Context-Aware ETA Engine.",
    }
    res = await client.post(f"{BASE_URL}/api/v1/jobs", json=payload, headers=headers)
    assert res.status_code == 201, f"Failed to create test job: {res.text}"
    return res.json()


async def assign_technician_to_job(
    client: AsyncClient, headers: dict[str, str], job_id: str, technician_id: str
) -> dict:
    """Helper to assign technician to job via Dispatcher endpoint."""
    res = await client.post(
        f"{BASE_URL}/api/v1/assignments/jobs/{job_id}/assign",
        json={"technician_id": technician_id},
        headers=headers,
    )
    assert res.status_code == 201, f"Failed to assign technician: {res.text}"
    return res.json()


@pytest.mark.asyncio
async def test_1_baseline_eta_calculation():
    """1. Test that baseline ETA is deterministically calculated from geospatial travel distance."""
    async with AsyncClient() as client:
        disp_headers = await get_token_headers(client, "dispatcher@fieldops.ai", "Dispatch@123")
        tech_id, skill_id = await get_technician_and_skill(client, disp_headers)

        job = await create_test_job(client, disp_headers, skill_id)
        await assign_technician_to_job(client, disp_headers, job["id"], tech_id)

        res = await client.get(f"{BASE_URL}/api/v1/jobs/{job['id']}/eta?weather=Clear", headers=disp_headers)
        assert res.status_code == 200, f"Failed to get ETA: {res.text}"

        data = res.json()
        assert data["job_id"] == job["id"]
        assert data["is_context_sufficient"] is True
        assert data["baseline_eta_minutes"] is not None
        assert data["baseline_eta_minutes"] > 0
        assert data["distance_miles"] is not None
        assert data["distance_miles"] > 0


@pytest.mark.asyncio
async def test_2_context_aware_eta_calculation():
    """2. Test context-aware ETA combines baseline with environmental and operational factors."""
    async with AsyncClient() as client:
        disp_headers = await get_token_headers(client, "dispatcher@fieldops.ai", "Dispatch@123")
        tech_id, skill_id = await get_technician_and_skill(client, disp_headers)

        job = await create_test_job(client, disp_headers, skill_id)
        await assign_technician_to_job(client, disp_headers, job["id"], tech_id)

        res = await client.get(f"{BASE_URL}/api/v1/jobs/{job['id']}/eta", headers=disp_headers)
        assert res.status_code == 200

        data = res.json()
        assert data["is_context_sufficient"] is True
        assert data["context_aware_eta_minutes"] is not None
        # Default weather is Moderate Rain (+5 min)
        assert data["context_aware_eta_minutes"] >= data["baseline_eta_minutes"]
        assert data["adjustment_minutes"] == data["context_aware_eta_minutes"] - data["baseline_eta_minutes"]
        assert len(data["factors"]) >= 2


@pytest.mark.asyncio
async def test_3_operational_weather_adjustment():
    """3. Test that changing weather operational context alters the ETA adjustment."""
    async with AsyncClient() as client:
        disp_headers = await get_token_headers(client, "dispatcher@fieldops.ai", "Dispatch@123")
        tech_id, skill_id = await get_technician_and_skill(client, disp_headers)

        job = await create_test_job(client, disp_headers, skill_id)
        await assign_technician_to_job(client, disp_headers, job["id"], tech_id)

        # Clear weather -> 0 min weather delay
        res_clear = await client.get(f"{BASE_URL}/api/v1/jobs/{job['id']}/eta?weather=Clear", headers=disp_headers)
        assert res_clear.status_code == 200
        data_clear = res_clear.json()

        # Storm weather -> 15 min weather delay
        res_storm = await client.get(f"{BASE_URL}/api/v1/jobs/{job['id']}/eta?weather=Storm", headers=disp_headers)
        assert res_storm.status_code == 200
        data_storm = res_storm.json()

        assert data_storm["context_aware_eta_minutes"] > data_clear["context_aware_eta_minutes"]
        assert data_storm["adjustment_minutes"] == data_clear["adjustment_minutes"] + 15


@pytest.mark.asyncio
async def test_4_positive_adjustment():
    """4. Test that adverse conditions yield a strictly positive adjustment (+5 min for Moderate Rain)."""
    async with AsyncClient() as client:
        disp_headers = await get_token_headers(client, "dispatcher@fieldops.ai", "Dispatch@123")
        tech_id, skill_id = await get_technician_and_skill(client, disp_headers)

        job = await create_test_job(client, disp_headers, skill_id)
        await assign_technician_to_job(client, disp_headers, job["id"], tech_id)

        res = await client.get(
            f"{BASE_URL}/api/v1/jobs/{job['id']}/eta?weather=Moderate%20Rain", headers=disp_headers
        )
        assert res.status_code == 200

        data = res.json()
        assert data["adjustment_minutes"] >= 5
        assert "Moderate Rain" in data["reason"] or "transit delay" in data["reason"]


@pytest.mark.asyncio
async def test_5_zero_adjustment():
    """5. Test zero adjustment under clear conditions with available technician."""
    async with AsyncClient() as client:
        disp_headers = await get_token_headers(client, "dispatcher@fieldops.ai", "Dispatch@123")
        tech_id, skill_id = await get_technician_and_skill(client, disp_headers)

        job = await create_test_job(client, disp_headers, skill_id)
        await assign_technician_to_job(client, disp_headers, job["id"], tech_id)

        res = await client.get(f"{BASE_URL}/api/v1/jobs/{job['id']}/eta?weather=Clear", headers=disp_headers)
        assert res.status_code == 200

        data = res.json()
        assert data["adjustment_minutes"] == 0
        assert data["context_aware_eta_minutes"] == data["baseline_eta_minutes"]


@pytest.mark.asyncio
async def test_6_missing_context_handling():
    """6. Test that missing context (unassigned job) returns explainable insufficient context response."""
    async with AsyncClient() as client:
        disp_headers = await get_token_headers(client, "dispatcher@fieldops.ai", "Dispatch@123")
        _, skill_id = await get_technician_and_skill(client, disp_headers)

        # Create unassigned job
        job = await create_test_job(client, disp_headers, skill_id)

        res = await client.get(f"{BASE_URL}/api/v1/jobs/{job['id']}/eta", headers=disp_headers)
        assert res.status_code == 200

        data = res.json()
        assert data["is_context_sufficient"] is False
        assert data["baseline_eta_minutes"] is None
        assert data["context_aware_eta_minutes"] is None
        assert len(data["missing_context"]) > 0
        assert "No technician assigned" in data["missing_context"][0]
        assert "ETA unavailable" in data["reason"]


@pytest.mark.asyncio
async def test_7_invalid_job_handling():
    """7. Test querying ETA for non-existent job UUID returns 404 NotFound."""
    non_existent_id = uuid.uuid4()

    async with AsyncClient() as client:
        disp_headers = await get_token_headers(client, "dispatcher@fieldops.ai", "Dispatch@123")
        res = await client.get(f"{BASE_URL}/api/v1/jobs/{non_existent_id}/eta", headers=disp_headers)
        assert res.status_code == 404
        assert "not found" in res.text.lower()


@pytest.mark.asyncio
async def test_8_dispatcher_authorization():
    """8. Test Dispatcher role has full authorization to view job ETA."""
    async with AsyncClient() as client:
        disp_headers = await get_token_headers(client, "dispatcher@fieldops.ai", "Dispatch@123")
        _, skill_id = await get_technician_and_skill(client, disp_headers)
        job = await create_test_job(client, disp_headers, skill_id)

        res = await client.get(f"{BASE_URL}/api/v1/jobs/{job['id']}/eta", headers=disp_headers)
        assert res.status_code == 200
        assert res.json()["job_id"] == job["id"]


@pytest.mark.asyncio
async def test_9_administrator_authorization():
    """9. Test Administrator role has telemetry read authorization for operational ETA."""
    async with AsyncClient() as client:
        disp_headers = await get_token_headers(client, "dispatcher@fieldops.ai", "Dispatch@123")
        admin_headers = await get_token_headers(client, "admin@fieldops.ai", "Admin@123")

        _, skill_id = await get_technician_and_skill(client, disp_headers)
        job = await create_test_job(client, disp_headers, skill_id)

        res = await client.get(f"{BASE_URL}/api/v1/jobs/{job['id']}/eta", headers=admin_headers)
        assert res.status_code == 200
        assert res.json()["job_id"] == job["id"]


@pytest.mark.asyncio
async def test_10_technician_ownership_restriction():
    """10. Test Technician can view ETA ONLY for their own assigned job; other jobs return 403 Forbidden."""
    async with AsyncClient() as client:
        disp_headers = await get_token_headers(client, "dispatcher@fieldops.ai", "Dispatch@123")
        tech_headers = await get_token_headers(client, "technician@fieldops.ai", "Tech@123")
        tech_id, skill_id = await get_technician_and_skill(client, disp_headers)

        # 1. Assigned job
        assigned_job = await create_test_job(client, disp_headers, skill_id)
        await assign_technician_to_job(client, disp_headers, assigned_job["id"], tech_id)

        # 2. Unassigned job
        other_job = await create_test_job(client, disp_headers, skill_id)

        # A. Technician accessing their OWN assigned job -> 200 OK
        res_own = await client.get(f"{BASE_URL}/api/v1/jobs/{assigned_job['id']}/eta", headers=tech_headers)
        assert res_own.status_code == 200, f"Technician could not access own job: {res_own.text}"
        assert res_own.json()["job_id"] == assigned_job["id"]

        # B. Technician accessing a job NOT assigned to them -> 403 Forbidden
        res_other = await client.get(f"{BASE_URL}/api/v1/jobs/{other_job['id']}/eta", headers=tech_headers)
        assert res_other.status_code == 403, f"Technician gained unauthorized access: {res_other.text}"
        assert "assigned to themselves" in res_other.text


@pytest.mark.asyncio
async def test_11_eta_response_consistency():
    """11. Test that ETA response contains all required fields with consistent data types."""
    async with AsyncClient() as client:
        disp_headers = await get_token_headers(client, "dispatcher@fieldops.ai", "Dispatch@123")
        tech_id, skill_id = await get_technician_and_skill(client, disp_headers)

        job = await create_test_job(client, disp_headers, skill_id)
        await assign_technician_to_job(client, disp_headers, job["id"], tech_id)

        res = await client.get(
            f"{BASE_URL}/api/v1/jobs/{job['id']}/eta?record_audit=true", headers=disp_headers
        )
        assert res.status_code == 200

        data = res.json()
        required_keys = [
            "job_id",
            "job_number",
            "is_context_sufficient",
            "baseline_eta_minutes",
            "context_aware_eta_minutes",
            "adjustment_minutes",
            "technician_id",
            "technician_name",
            "technician_code",
            "distance_miles",
            "factors",
            "reason",
            "missing_context",
            "calculated_at",
        ]
        for key in required_keys:
            assert key in data, f"Missing required key: {key}"

        assert isinstance(data["factors"], list)
        if data["factors"]:
            factor = data["factors"][0]
            assert "category" in factor
            assert "factor" in factor
            assert "impact_minutes" in factor
            assert "description" in factor


@pytest.mark.asyncio
async def test_12_existing_job_execution_regression():
    """12. Test that existing job execution lifecycle (TRAVELLING -> ARRIVED -> WORKING -> COMPLETED) is intact."""
    async with AsyncClient() as client:
        disp_headers = await get_token_headers(client, "dispatcher@fieldops.ai", "Dispatch@123")
        tech_headers = await get_token_headers(client, "technician@fieldops.ai", "Tech@123")
        tech_id, skill_id = await get_technician_and_skill(client, disp_headers)

        job = await create_test_job(client, disp_headers, skill_id)
        await assign_technician_to_job(client, disp_headers, job["id"], tech_id)


        # Step 1: Start travel -> TRAVELLING
        res1 = await client.patch(
            f"{BASE_URL}/api/v1/jobs/{job['id']}/status",
            json={"status": "TRAVELLING", "notes": "En route with context ETA check."},
            headers=tech_headers,
        )
        assert res1.status_code == 200
        assert res1.json()["status"] == "TRAVELLING"

        # Step 2: Mark arrived -> ARRIVED
        res2 = await client.patch(
            f"{BASE_URL}/api/v1/jobs/{job['id']}/status",
            json={"status": "ARRIVED", "notes": "Arrived on site."},
            headers=tech_headers,
        )
        assert res2.status_code == 200
        assert res2.json()["status"] == "ARRIVED"

        # Step 3: Start work -> WORKING
        res3 = await client.patch(
            f"{BASE_URL}/api/v1/jobs/{job['id']}/status",
            json={"status": "WORKING", "notes": "Commencing repairs."},
            headers=tech_headers,
        )
        assert res3.status_code == 200
        assert res3.json()["status"] == "WORKING"

        # Step 4: Complete job -> COMPLETED
        res4 = await client.patch(
            f"{BASE_URL}/api/v1/jobs/{job['id']}/status",
            json={"status": "COMPLETED", "notes": "Repairs verified complete."},
            headers=tech_headers,
        )
        assert res4.status_code == 200
        assert res4.json()["status"] == "COMPLETED"


@pytest.mark.asyncio
async def test_13_data_sources_array_present():
    """
    13. Test that the ETA response includes a data_sources array containing
    all 5 context source entries: GPS, Weather, Traffic, Events, Road Restrictions.
    """
    async with AsyncClient() as client:
        disp_headers = await get_token_headers(client, "dispatcher@fieldops.ai", "Dispatch@123")
        tech_id, skill_id = await get_technician_and_skill(client, disp_headers)

        job = await create_test_job(client, disp_headers, skill_id)
        await assign_technician_to_job(client, disp_headers, job["id"], tech_id)

        res = await client.get(f"{BASE_URL}/api/v1/jobs/{job['id']}/eta?weather=Clear", headers=disp_headers)
        assert res.status_code == 200, f"ETA request failed: {res.text}"

        data = res.json()
        assert "data_sources" in data, "data_sources field missing from ETA response"
        sources = data["data_sources"]
        assert isinstance(sources, list), "data_sources must be a list"
        assert len(sources) == 5, f"Expected 5 data sources, got {len(sources)}"

        source_names = [s["name"] for s in sources]
        assert "GPS Location" in source_names, "GPS Location source missing"
        assert "Weather" in source_names, "Weather source missing"
        assert "Traffic Data" in source_names, "Traffic Data source missing"
        assert "Events" in source_names, "Events source missing"
        assert "Road Restrictions" in source_names, "Road Restrictions source missing"

        for source in sources:
            assert "status" in source, f"status missing from source: {source}"
            assert "description" in source, f"description missing from source: {source}"
            assert source["status"] in (
                "AVAILABLE", "STALE", "UNAVAILABLE", "INVALID"
            ), f"Invalid status '{source['status']}' for source {source['name']}"


@pytest.mark.asyncio
async def test_14_traffic_source_unavailable():
    """
    14. Test that Traffic Data source is explicitly marked as UNAVAILABLE
    since no real-time traffic API is integrated — no fake data should be applied.
    """
    async with AsyncClient() as client:
        disp_headers = await get_token_headers(client, "dispatcher@fieldops.ai", "Dispatch@123")
        tech_id, skill_id = await get_technician_and_skill(client, disp_headers)

        job = await create_test_job(client, disp_headers, skill_id)
        await assign_technician_to_job(client, disp_headers, job["id"], tech_id)

        res = await client.get(f"{BASE_URL}/api/v1/jobs/{job['id']}/eta", headers=disp_headers)
        assert res.status_code == 200

        data = res.json()
        sources = {s["name"]: s for s in data["data_sources"]}

        # Traffic must be UNAVAILABLE — do not fake or estimate
        assert "Traffic Data" in sources, "Traffic Data source missing"
        traffic = sources["Traffic Data"]
        assert traffic["status"] == "UNAVAILABLE", (
            f"Traffic source should be UNAVAILABLE but got '{traffic['status']}'"
        )
        assert traffic["impact_minutes"] == 0, (
            "Traffic source must not contribute any ETA adjustment when UNAVAILABLE"
        )

        # Events and Road Restrictions must also be UNAVAILABLE
        assert sources["Events"]["status"] == "UNAVAILABLE"
        assert sources["Road Restrictions"]["status"] == "UNAVAILABLE"
        assert sources["Events"]["impact_minutes"] == 0
        assert sources["Road Restrictions"]["impact_minutes"] == 0


@pytest.mark.asyncio
async def test_15_estimated_arrival_time_is_valid():
    """
    15. Test that estimated_arrival_time is a valid ISO-8601 datetime string
    that falls after calculated_at by at least baseline_eta_minutes.
    """
    from datetime import datetime, timezone

    async with AsyncClient() as client:
        disp_headers = await get_token_headers(client, "dispatcher@fieldops.ai", "Dispatch@123")
        tech_id, skill_id = await get_technician_and_skill(client, disp_headers)

        job = await create_test_job(client, disp_headers, skill_id)
        await assign_technician_to_job(client, disp_headers, job["id"], tech_id)

        res = await client.get(f"{BASE_URL}/api/v1/jobs/{job['id']}/eta?weather=Clear", headers=disp_headers)
        assert res.status_code == 200

        data = res.json()
        assert data["estimated_arrival_time"] is not None, "estimated_arrival_time should not be None"
        assert data["calculated_at"] is not None

        # Parse both timestamps
        try:
            arrival = datetime.fromisoformat(data["estimated_arrival_time"].replace("Z", "+00:00"))
            calculated = datetime.fromisoformat(data["calculated_at"].replace("Z", "+00:00"))
        except ValueError as e:
            raise AssertionError(f"Invalid datetime format in ETA response: {e}") from e

        assert arrival > calculated, (
            f"estimated_arrival_time ({arrival}) must be after calculated_at ({calculated})"
        )
        # Arrival should be at least baseline_eta_minutes ahead of calculation time
        diff_minutes = (arrival - calculated).total_seconds() / 60
        assert diff_minutes >= data["context_aware_eta_minutes"] - 1, (
            f"Arrival time gap ({diff_minutes:.1f} min) inconsistent with context ETA "
            f"({data['context_aware_eta_minutes']} min)"
        )


@pytest.mark.asyncio
async def test_16_distance_km_consistent_with_miles():
    """
    16. Test that distance_km > 0 and is mathematically consistent with distance_miles
    (within ±2% rounding tolerance from 1 mile = 1.60934 km conversion).
    """
    async with AsyncClient() as client:
        disp_headers = await get_token_headers(client, "dispatcher@fieldops.ai", "Dispatch@123")
        tech_id, skill_id = await get_technician_and_skill(client, disp_headers)

        job = await create_test_job(client, disp_headers, skill_id)
        await assign_technician_to_job(client, disp_headers, job["id"], tech_id)

        res = await client.get(f"{BASE_URL}/api/v1/jobs/{job['id']}/eta?weather=Clear", headers=disp_headers)
        assert res.status_code == 200

        data = res.json()
        assert data["distance_km"] is not None, "distance_km should be present"
        assert data["distance_miles"] is not None, "distance_miles should be present"
        assert data["distance_km"] > 0, "distance_km must be positive"
        assert data["distance_miles"] > 0, "distance_miles must be positive"

        # Validate km/miles consistency within 2% tolerance
        expected_km = data["distance_miles"] * 1.60934
        tolerance = expected_km * 0.02
        assert abs(data["distance_km"] - expected_km) <= tolerance, (
            f"distance_km ({data['distance_km']}) inconsistent with "
            f"distance_miles ({data['distance_miles']}) * 1.60934 = {expected_km:.2f} km"
        )


@pytest.mark.asyncio
async def test_17_technician_cannot_access_other_technician_eta():
    """
    17. Test that a technician cannot access ETA for a job assigned to a DIFFERENT
    technician — cross-technician ETA/location access must be blocked (403 Forbidden).
    """
    async with AsyncClient() as client:
        disp_headers = await get_token_headers(client, "dispatcher@fieldops.ai", "Dispatch@123")

        # Authenticate as TECH-001
        tech1_headers = await get_token_headers(client, "technician@fieldops.ai", "Tech@123")
        tech1_id, skill_id = await get_technician_and_skill(client, disp_headers)

        # Find TECH-002 (second technician)
        res2 = await client.get(f"{BASE_URL}/api/v1/technicians?search=TECH-002", headers=disp_headers)
        assert res2.status_code == 200
        body2 = res2.json()
        items2 = body2["items"] if "items" in body2 else body2

        if len(items2) == 0:
            # Only one technician in system; skip cross-technician check
            # (cannot test cross-access without a second technician)
            pytest.skip("No second technician (TECH-002) available for cross-access test")

        # Create a job and assign to TECH-001
        job = await create_test_job(client, disp_headers, skill_id)
        await assign_technician_to_job(client, disp_headers, job["id"], tech1_id)

        # TECH-001 accessing their OWN job -> 200 OK
        res_own = await client.get(
            f"{BASE_URL}/api/v1/jobs/{job['id']}/eta", headers=tech1_headers
        )
        assert res_own.status_code == 200, (
            f"Technician should access own assigned job ETA but got {res_own.status_code}: {res_own.text}"
        )

        # Create a second job and assign to TECH-002
        tech2_id = str(items2[0]["id"])
        job2 = await create_test_job(client, disp_headers, skill_id)
        await assign_technician_to_job(client, disp_headers, job2["id"], tech2_id)

        # TECH-001 accessing a job assigned to TECH-002 -> 403 Forbidden
        res_other = await client.get(
            f"{BASE_URL}/api/v1/jobs/{job2['id']}/eta", headers=tech1_headers
        )
        assert res_other.status_code == 403, (
            f"Technician gained unauthorized access to another technician's ETA: {res_other.text}"
        )
        assert "assigned to themselves" in res_other.text.lower() or "forbidden" in res_other.text.lower()
