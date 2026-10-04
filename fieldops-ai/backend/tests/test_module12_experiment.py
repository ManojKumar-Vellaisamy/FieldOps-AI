"""
Comprehensive Integration & Unit Tests for Module 12 — Baseline vs Context-Aware ETA Experiment.

Verifies:
1. Baseline absolute error calculation (|Baseline ETA - Actual Travel Time|)
2. Context-aware absolute error calculation (|Context ETA - Actual Travel Time|)
3. MAE (Mean Absolute Error) calculation across benchmark dataset
4. Non-routine condition classification (adverse weather, heavy traffic, events, road closures)
5. Comparison result calculation (Baseline MAE vs Context MAE & improvement percentage)
6. Missing actual travel time / empty dataset graceful fallback handling
7. Existing ETA endpoint and context provider functionality remains unchanged
8. Existing traffic provider functionality remains unchanged
"""

import pytest
from httpx import AsyncClient

from app.services.eta_experiment_service import ETAExperimentService
from app.schemas.eta import ETAExperimentResponse, ETAExperimentSampleResult

BASE_URL = "http://127.0.0.1:8000"


@pytest.mark.asyncio
async def test_1_baseline_error_calculation():
    """1. Test baseline absolute error formula: |Baseline ETA - Actual Travel Time|."""
    service = ETAExperimentService()
    res = service.evaluate_experiment()

    assert res.sample_count > 0
    assert len(res.sample_breakdown) > 0

    # Pick a sample: distance = 12.5 km -> baseline = round(12.5/40*60)+3 = 22m. actual = 22m.
    sample1 = next((s for s in res.sample_breakdown if s.id == 1), None)
    assert sample1 is not None
    expected_baseline_eta = round((12.5 / 40.0) * 60.0) + 3  # 22
    assert sample1.baseline_eta_minutes == expected_baseline_eta
    assert sample1.baseline_absolute_error == abs(expected_baseline_eta - sample1.actual_travel_minutes)


@pytest.mark.asyncio
async def test_2_context_aware_error_calculation():
    """2. Test context-aware absolute error formula: |Context ETA - Actual Travel Time|."""
    service = ETAExperimentService()
    res = service.evaluate_experiment()

    # Sample 4 (Heavy Rain +12m, Traffic +8m): dist = 25km -> baseline = 41m -> context = 61m, actual = 60m
    sample4 = next((s for s in res.sample_breakdown if s.id == 4), None)
    assert sample4 is not None
    assert sample4.is_non_routine is True
    assert sample4.context_aware_eta_minutes > sample4.baseline_eta_minutes
    expected_context_error = abs(sample4.context_aware_eta_minutes - sample4.actual_travel_minutes)
    assert sample4.context_aware_absolute_error == expected_context_error


@pytest.mark.asyncio
async def test_3_mae_calculation_accuracy():
    """3. Test Mean Absolute Error (MAE) is correctly computed as mean of absolute errors."""
    service = ETAExperimentService()
    res = service.evaluate_experiment()

    samples = res.sample_breakdown
    assert len(samples) == res.sample_count

    calculated_baseline_mae = round(sum(s.baseline_absolute_error for s in samples) / len(samples), 2)
    calculated_context_mae = round(sum(s.context_aware_absolute_error for s in samples) / len(samples), 2)

    assert res.baseline_mae_minutes == calculated_baseline_mae
    assert res.context_aware_mae_minutes == calculated_context_mae


@pytest.mark.asyncio
async def test_4_non_routine_condition_classification():
    """4. Test that samples with adverse weather, traffic, events, or road closures are classified as non-routine."""
    service = ETAExperimentService()
    res = service.evaluate_experiment()

    samples = res.sample_breakdown
    routine_samples = [s for s in samples if not s.is_non_routine]
    non_routine_samples = [s for s in samples if s.is_non_routine]

    assert len(routine_samples) == res.routine_sample_count
    assert len(non_routine_samples) == res.non_routine_sample_count
    assert res.routine_sample_count + res.non_routine_sample_count == res.sample_count

    for s in non_routine_samples:
        # Must contain environmental factor indicator in conditions summary
        assert any(k in s.conditions for k in ("Weather", "Traffic", "Event", "Road Closure"))


@pytest.mark.asyncio
async def test_5_comparison_result_shows_significant_non_routine_improvement():
    """5. Test comparison results show Context-Aware MAE is significantly lower during non-routine conditions."""
    service = ETAExperimentService()
    res = service.evaluate_experiment()

    assert res.context_aware_non_routine_mae < res.baseline_non_routine_mae
    assert res.non_routine_improvement_percent > 50.0
    assert res.improvement_percent > 0.0


@pytest.mark.asyncio
async def test_6_disclaimer_and_transparency_labels():
    """6. Test evaluation service explicitly returns dataset simulation disclaimers and error analysis."""
    service = ETAExperimentService()
    res = service.evaluate_experiment()

    assert res.is_simulated_dataset is True
    assert "Simulated evaluation" in res.disclaimer
    assert len(res.error_analysis) >= 4
    for ea in res.error_analysis:
        assert "category" in ea
        assert "finding" in ea


@pytest.mark.asyncio
async def test_7_experiment_api_endpoint():
    """7. Test GET /api/v1/eta/experiment returns 200 OK with complete evaluation payload."""
    async with AsyncClient() as client:
        # Login as dispatcher
        login_res = await client.post(f"{BASE_URL}/api/v1/auth/login", json={"email": "dispatcher@fieldops.ai", "password": "Dispatch@123"})
        assert login_res.status_code == 200
        token = login_res.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        res = await client.get(f"{BASE_URL}/api/v1/eta/experiment?source=simulated", headers=headers)
        assert res.status_code == 200

        data = res.json()
        assert "baseline_mae_minutes" in data
        assert "context_aware_mae_minutes" in data
        assert "sample_breakdown" in data
        assert len(data["sample_breakdown"]) == 50
        assert "error_analysis" in data
        assert "disclaimer" in data

        # Also test default real operational telemetry with insufficient data
        real_res = await client.get(f"{BASE_URL}/api/v1/eta/experiment", headers=headers)
        assert real_res.status_code == 200
        real_data = real_res.json()
        assert real_data["is_sufficient_data"] is False
        assert real_data["sample_count"] == 0
        assert real_data["baseline_mae_minutes"] is None
        assert real_data["context_aware_mae_minutes"] is None
        assert len(real_data["sample_breakdown"]) == 0


@pytest.mark.asyncio
async def test_8_existing_eta_and_traffic_functionality_preserved():
    """8. Test existing job ETA calculation and traffic provider integration remain fully functional."""
    async with AsyncClient() as client:
        login_res = await client.post(f"{BASE_URL}/api/v1/auth/login", json={"email": "dispatcher@fieldops.ai", "password": "Dispatch@123"})
        headers = {"Authorization": f"Bearer {login_res.json()['access_token']}"}

        # Query tech directory to get valid technician & skill
        tech_res = await client.get(f"{BASE_URL}/api/v1/technicians?search=TECH-001", headers=headers)
        assert tech_res.status_code == 200
        items = tech_res.json()["items"] if "items" in tech_res.json() else tech_res.json()
        tech = items[0]

        # Create job
        job_res = await client.post(
            f"{BASE_URL}/api/v1/jobs",
            json={
                "customer_name": "Module 12 Regression Job",
                "customer_phone": "+1 (555) 333-2222",
                "address": "Market St, San Francisco, CA",
                "latitude": 37.789,
                "longitude": -122.401,
                "required_skill_id": tech["primary_skill_id"],
                "priority": "HIGH",
                "description": "Module 12 regression test.",
            },
            headers=headers,
        )
        assert job_res.status_code == 201
        job_id = job_res.json()["id"]

        # Assign technician
        asg_res = await client.post(
            f"{BASE_URL}/api/v1/assignments/jobs/{job_id}/assign",
            json={"technician_id": tech["id"]},
            headers=headers,
        )
        assert asg_res.status_code == 201

        # Calculate ETA
        eta_res = await client.get(f"{BASE_URL}/api/v1/jobs/{job_id}/eta", headers=headers)
        assert eta_res.status_code == 200
        eta_data = eta_res.json()

        assert eta_data["is_context_sufficient"] is True
        assert eta_data["baseline_eta_minutes"] is not None
        assert eta_data["context_aware_eta_minutes"] is not None
        assert "data_sources" in eta_data
        assert any(s["name"].startswith("Traffic Data") for s in eta_data["data_sources"])
