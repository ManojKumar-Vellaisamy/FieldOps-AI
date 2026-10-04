"""
Pydantic schemas for Operational Analytics module.
"""

from typing import Any, Optional
from pydantic import BaseModel, ConfigDict


class StatusCount(BaseModel):
    status: str
    count: int


class PriorityCount(BaseModel):
    priority: str
    count: int


class DailyVolume(BaseModel):
    date: str
    count: int


class OperationalAnalyticsResponse(BaseModel):
    """Authoritative operational analytics response calculated directly from PostgreSQL."""

    model_config = ConfigDict(from_attributes=True)

    total_jobs: int
    active_jobs: int
    unassigned_jobs: int
    in_progress_jobs: int
    completed_jobs: int
    cancelled_jobs: int
    status_distribution: list[StatusCount]
    priority_distribution: list[PriorityCount]
    completion_rate_percentage: Optional[float] = None
    cancellation_rate_percentage: Optional[float] = None
    total_technicians: int
    active_technicians: int
    available_technicians: int
    technicians_with_gps: int
    technician_utilization_percentage: Optional[float] = None
    recent_jobs_volume_7d: list[DailyVolume]
