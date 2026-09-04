"""
Health check schemas.
"""

from typing import Literal

from app.schemas.base import BaseSchema


class HealthResponse(BaseSchema):
    """Response schema for GET /api/v1/health."""

    status: Literal["healthy", "degraded", "unhealthy"]
    service: str
    version: str
