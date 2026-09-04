"""
Health check endpoint — GET /api/v1/health
"""

from fastapi import APIRouter

from app.core.config import settings
from app.schemas.health import HealthResponse

router = APIRouter(tags=["Health"])


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Health Check",
    description="Returns the current health status of the FieldOps AI API.",
)
async def health_check() -> HealthResponse:
    """
    Returns a health check response.

    **Response:**
    - `status`: `healthy` | `degraded` | `unhealthy`
    - `service`: Name of the API service
    - `version`: Current API version
    """
    return HealthResponse(
        status="healthy",
        service=settings.APP_NAME,
        version=settings.APP_VERSION,
    )
