"""
Operational Analytics API v1 Endpoints.
Calculates authoritative operational KPIs directly from PostgreSQL:
job volumes, status breakdown, completion/cancellation rates, and technician workforce metrics.
"""

from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import APIRouter, Depends, status
from sqlalchemy import Date, cast, func, select

from app.api.deps import get_current_user, require_roles
from app.database.session import AsyncSessionLocal
from app.models.assignment import Assignment
from app.models.enums import JobStatus, Priority, UserRole
from app.models.job import Job
from app.models.technician import Technician
from app.schemas.analytics import (
    DailyVolume,
    OperationalAnalyticsResponse,
    PriorityCount,
    StatusCount,
)
from app.schemas.auth import UserResponse

router = APIRouter(prefix="/analytics", tags=["Operational Analytics"])


@router.get(
    "/operational",
    response_model=OperationalAnalyticsResponse,
    status_code=status.HTTP_200_OK,
    summary="Get authoritative operational analytics KPIs from PostgreSQL",
    dependencies=[Depends(require_roles(UserRole.DISPATCHER, UserRole.ADMINISTRATOR))],
)
async def get_operational_analytics(
    current_user: UserResponse = Depends(get_current_user),
) -> OperationalAnalyticsResponse:
    """
    Computes live operational metrics directly from PostgreSQL tables.
    Restricted to Dispatcher and Administrator roles.
    Zero fabricated or random metrics.
    """
    async with AsyncSessionLocal() as session:
        # 1. Total jobs
        total_jobs = (await session.execute(select(func.count(Job.id)))).scalar() or 0

        # 2. Status distribution
        status_stmt = select(Job.status, func.count(Job.id)).group_by(Job.status)
        status_rows = (await session.execute(status_stmt)).all()
        status_map: dict[str, int] = {}
        for row in status_rows:
            st = row[0].value if hasattr(row[0], "value") else str(row[0])
            status_map[st] = row[1]

        status_distribution = [
            StatusCount(status=st, count=cnt)
            for st, cnt in sorted(status_map.items(), key=lambda x: x[0])
        ]

        # 3. Priority distribution
        priority_stmt = select(Job.priority, func.count(Job.id)).group_by(Job.priority)
        priority_rows = (await session.execute(priority_stmt)).all()
        priority_map: dict[str, int] = {}
        for row in priority_rows:
            pr = row[0].value if hasattr(row[0], "value") else str(row[0])
            priority_map[pr] = row[1]

        priority_distribution = [
            PriorityCount(priority=pr, count=cnt)
            for pr, cnt in sorted(priority_map.items(), key=lambda x: x[0])
        ]

        # 4. Computed job metrics
        unassigned_jobs = status_map.get(JobStatus.NEW.value, 0)
        completed_jobs = status_map.get(JobStatus.COMPLETED.value, 0)
        cancelled_jobs = status_map.get(JobStatus.CANCELLED.value, 0)
        in_progress_jobs = (
            status_map.get(JobStatus.TRAVELLING.value, 0)
            + status_map.get(JobStatus.ARRIVED.value, 0)
            + status_map.get(JobStatus.WORKING.value, 0)
        )
        active_jobs = total_jobs - completed_jobs - cancelled_jobs

        terminal_jobs = completed_jobs + cancelled_jobs
        completion_rate = (
            round((completed_jobs / terminal_jobs) * 100.0, 1)
            if terminal_jobs > 0
            else None
        )
        cancellation_rate = (
            round((cancelled_jobs / terminal_jobs) * 100.0, 1)
            if terminal_jobs > 0
            else None
        )

        # 5. Technician workforce metrics
        total_technicians = (await session.execute(select(func.count(Technician.id)))).scalar() or 0

        avail_stmt = select(func.count(Technician.id)).where(Technician.availability_status == "AVAILABLE")
        available_technicians = (await session.execute(avail_stmt)).scalar() or 0

        active_tech_stmt = select(func.count(Technician.id)).where(Technician.availability_status != "INACTIVE")
        active_technicians = (await session.execute(active_tech_stmt)).scalar() or 0

        gps_stmt = select(func.count(Technician.id)).where(
            Technician.current_latitude.isnot(None),
            Technician.current_longitude.isnot(None),
        )
        technicians_with_gps = (await session.execute(gps_stmt)).scalar() or 0

        # Assigned technicians currently working or travelling
        assigned_tech_stmt = (
            select(func.count(func.distinct(Assignment.technician_id)))
            .join(Job, Job.id == Assignment.job_id)
            .where(Job.status.in_([JobStatus.ASSIGNED, JobStatus.TRAVELLING, JobStatus.ARRIVED, JobStatus.WORKING]))
        )
        assigned_tech_count = (await session.execute(assigned_tech_stmt)).scalar() or 0

        technician_utilization = (
            round((assigned_tech_count / active_technicians) * 100.0, 1)
            if active_technicians > 0
            else None
        )

        # 6. Recent 7-day job volume
        now = datetime.now(timezone.utc)
        start_d = (now - timedelta(days=6)).date()
        daily_stmt = (
            select(cast(Job.created_at, Date).label("d"), func.count(Job.id))
            .where(cast(Job.created_at, Date) >= start_d)
            .group_by("d")
            .order_by("d")
        )
        daily_rows = (await session.execute(daily_stmt)).all()
        daily_dict = {str(row[0]): row[1] for row in daily_rows}

        recent_volume: list[DailyVolume] = []
        for i in range(7):
            day_str = (start_d + timedelta(days=i)).isoformat()
            recent_volume.append(DailyVolume(date=day_str, count=daily_dict.get(day_str, 0)))

        return OperationalAnalyticsResponse(
            total_jobs=total_jobs,
            active_jobs=active_jobs,
            unassigned_jobs=unassigned_jobs,
            in_progress_jobs=in_progress_jobs,
            completed_jobs=completed_jobs,
            cancelled_jobs=cancelled_jobs,
            status_distribution=status_distribution,
            priority_distribution=priority_distribution,
            completion_rate_percentage=completion_rate,
            cancellation_rate_percentage=cancellation_rate,
            total_technicians=total_technicians,
            active_technicians=active_technicians,
            available_technicians=available_technicians,
            technicians_with_gps=technicians_with_gps,
            technician_utilization_percentage=technician_utilization,
            recent_jobs_volume_7d=recent_volume,
        )
