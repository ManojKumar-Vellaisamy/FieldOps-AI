"""
Tests for operational realism, territory service area guards, and data provenance integrity.
Verifies that:
1. Long-distance / cross-continental routes are flagged as OUT_OF_SERVICE_AREA (is_operationally_realistic=False).
2. Local routes within max_service_radius_miles are marked VALID (is_operationally_realistic=True).
3. Data provenance is accurately recorded: factors are DERIVED, external APIs are REAL, internal GPS is SYSTEM.
4. Unassigned jobs or missing GPS context return UNROUTEABLE with an explicit explanatory message.
"""

import pytest
import uuid
from unittest.mock import AsyncMock, patch
from httpx import Response
from sqlalchemy import select

from app.database.session import AsyncSessionLocal
from app.models.job import Job
from app.models.technician import Technician
from app.models.assignment import Assignment
from app.services.eta_service import ETAService
from app.core.config import settings
from app.models.enums import JobStatus, Priority


@pytest.mark.asyncio
async def test_eta_out_of_service_area_guard():
    """Technician located in India (Coimbatore: 10.9292, 76.9726) assigned to SF Job (>8,000 miles)
    must trigger OUT_OF_SERVICE_AREA and is_operationally_realistic=False."""
    async with AsyncSessionLocal() as db:
        stmt = select(Job).where(Job.job_number == "JOB-10001").limit(1)
        job = (await db.execute(stmt)).scalar_one()

        # Get technician assigned to JOB-10001
        stmt_asg = select(Assignment).where(Assignment.job_id == job.id).limit(1)
        asg = (await db.execute(stmt_asg)).scalar_one_or_none()
        if asg and asg.technician_id:
            tech = (await db.execute(select(Technician).where(Technician.id == asg.technician_id))).scalar_one()
        else:
            tech = (await db.execute(select(Technician).limit(1))).scalar_one()
            asg = Assignment(
                job_id=job.id,
                technician_id=tech.id,
                assignment_status="ASSIGNED",
                assigned_by="SYSTEM",
            )
            db.add(asg)
            await db.commit()

        # Temporarily place technician in Coimbatore, India
        original_lat = tech.current_latitude
        original_lon = tech.current_longitude
        tech.current_latitude = 10.9292
        tech.current_longitude = 76.9726
        await db.commit()

        try:
            eta_service = ETAService()
            with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
                mock_get.return_value = Response(200, json={})
                resp = await eta_service.calculate_job_eta(
                    job_id=job.id,
                    technician_id=tech.id,
                )

            assert resp is not None
            assert resp.is_operationally_realistic is False
            assert resp.route_validity == "OUT_OF_SERVICE_AREA"
            assert resp.service_range_message is not None
            assert "exceeds maximum operational dispatch radius" in resp.service_range_message
            assert resp.distance_miles > 5000.0

            # Verify factor provenance integrity
            for factor in resp.factors:
                assert factor.provenance == "DERIVED"

        finally:
            tech.current_latitude = original_lat
            tech.current_longitude = original_lon
            await db.commit()


@pytest.mark.asyncio
async def test_eta_local_service_area_valid():
    """Technician located in San Francisco (37.7749, -122.4194) assigned to SF Job (~2 miles)
    must be VALID and is_operationally_realistic=True."""
    async with AsyncSessionLocal() as db:
        stmt = select(Job).where(Job.job_number == "JOB-10001").limit(1)
        job = (await db.execute(stmt)).scalar_one()

        # Get technician assigned to JOB-10001
        stmt_asg = select(Assignment).where(Assignment.job_id == job.id).limit(1)
        asg = (await db.execute(stmt_asg)).scalar_one_or_none()
        if asg and asg.technician_id:
            tech = (await db.execute(select(Technician).where(Technician.id == asg.technician_id))).scalar_one()
        else:
            tech = (await db.execute(select(Technician).limit(1))).scalar_one()
            asg = Assignment(
                job_id=job.id,
                technician_id=tech.id,
                assignment_status="ASSIGNED",
                assigned_by="SYSTEM",
            )
            db.add(asg)
            await db.commit()

        # Place technician nearby in SF
        original_lat = tech.current_latitude
        original_lon = tech.current_longitude
        tech.current_latitude = 37.7749
        tech.current_longitude = -122.4194
        await db.commit()

        try:
            eta_service = ETAService()
            with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
                mock_get.return_value = Response(200, json={})
                resp = await eta_service.calculate_job_eta(
                    job_id=job.id,
                    technician_id=tech.id,
                )

            assert resp is not None
            assert resp.is_operationally_realistic is True
            assert resp.route_validity == "VALID"
            assert resp.service_range_message is None
            assert resp.distance_miles < 50.0

            # Verify GPS source is present and marked SYSTEM
            sources_by_name = {ds.name: ds for ds in resp.data_sources}
            assert "GPS Location" in sources_by_name
            assert sources_by_name["GPS Location"].provenance == "SYSTEM"

            # Check factor provenance
            for factor in resp.factors:
                assert factor.provenance == "DERIVED"

        finally:
            tech.current_latitude = original_lat
            tech.current_longitude = original_lon
            await db.commit()


@pytest.mark.asyncio
async def test_eta_unassigned_job_unrouteable():
    """A job without an assigned technician is marked UNROUTEABLE with explanatory message."""
    async with AsyncSessionLocal() as db:
        job = Job(
            id=uuid.uuid4(),
            job_number=f"JOB-TEST-UNASSIGNED-{uuid.uuid4().hex[:6]}",
            customer_name="Unassigned Test Customer",
            customer_phone="+15550001111",
            address="San Francisco, CA",
            latitude=37.7749,
            longitude=-122.4194,
            priority=Priority.MEDIUM,
            status=JobStatus.NEW,
        )
        db.add(job)
        await db.commit()

        try:
            eta_service = ETAService()
            resp = await eta_service.calculate_job_eta(job.id)

            assert resp is not None
            assert resp.is_operationally_realistic is False
            assert resp.route_validity == "UNROUTEABLE"
            assert resp.service_range_message is not None
            assert "Cannot calculate valid transit route" in resp.service_range_message
        finally:
            await db.delete(job)
            await db.commit()
