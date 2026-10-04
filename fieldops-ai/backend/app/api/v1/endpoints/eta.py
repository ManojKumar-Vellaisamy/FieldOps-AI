"""
Context-Aware ETA Engine API v1 Endpoints (Module 11 Upgrade).
Provides RESTful endpoints for retrieving explainable baseline and context-aware ETA calculations,
creating Dispatcher manual ETA overrides with audit tracking, viewing override history, and
benchmarking ETA prediction error performance.

RBAC Enforcement:
- DISPATCHER: Full access to view ETAs, apply manual overrides, and view override history.
- ADMINISTRATOR: Full access to view operational telemetry, audit logs, and experiment benchmarks.
- TECHNICIAN: Strictly restricted to viewing ETA for own assigned jobs. Override actions return 403 Forbidden.
"""

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status

from app.api.deps import get_current_user
from app.core.exceptions import ForbiddenError, NotFoundError
from app.models.enums import UserRole
from app.repositories.job_repository import JobRepository
from app.schemas.auth import UserResponse
from app.schemas.eta import (
    ETAExperimentResponse,
    ETAOverrideCreate,
    ETAOverrideResponse,
    ETAResponse,
)
from app.services.eta_experiment_service import ETAExperimentService
from app.services.eta_service import ETAService

router = APIRouter(tags=["Context-Aware ETA Engine"])


@router.get(
    "/experiment",
    response_model=ETAExperimentResponse,
    status_code=status.HTTP_200_OK,
    summary="Get ETA prediction error benchmark metrics (Baseline vs Context-Aware)",
)
@router.get(
    "/evaluations",
    response_model=ETAExperimentResponse,
    status_code=status.HTTP_200_OK,
    summary="Get ETA prediction error benchmark metrics (alias)",
    include_in_schema=False,
)
async def get_eta_experiment_metrics(
    source: str = Query("real", description="Telemetry source: 'real' (default) or 'simulated'"),
    current_user: UserResponse = Depends(get_current_user),
) -> ETAExperimentResponse:
    """
    Retrieve measurable ETA prediction error benchmarks comparing simple distance baseline against
    the Context-Aware ETA model across normal and non-routine operational transit scenarios.
    """
    service = ETAExperimentService()
    return service.evaluate_experiment(source=source)


@router.get(
    "/weather",
    status_code=status.HTTP_200_OK,
    summary="Get real-time weather telemetry from Open-Meteo via WeatherProvider",
)
async def get_live_weather(
    lat: Optional[float] = Query(None, ge=-90.0, le=90.0, description="Latitude"),
    lon: Optional[float] = Query(None, ge=-180.0, le=180.0, description="Longitude"),
    current_user: UserResponse = Depends(get_current_user),
):
    """
    Retrieve live weather observations (temperature, precipitation, wind, conditions)
    from Open-Meteo Meteorological API via WeatherProvider.
    """
    if lat is None or lon is None:
        return {
            "status": "UNAVAILABLE",
            "condition": "Weather unavailable",
            "temperature": "",
            "provenance": "UNAVAILABLE",
        }

    from app.services.context_providers import WeatherProvider

    provider = WeatherProvider()
    res = await provider.evaluate(lat=lat, lon=lon)

    temp_val = getattr(res, "temperature_c", None)
    app_temp_val = getattr(res, "apparent_temperature_c", None)
    humidity_val = getattr(res, "humidity_percent", None)
    precip_prob_val = getattr(res, "precipitation_probability_percent", None)

    temp_str = f"{temp_val:.1f}°C" if temp_val is not None else ""
    app_temp_str = f"{app_temp_val:.1f}°C" if app_temp_val is not None else ""
    humidity_str = f"{humidity_val:.0f}%" if humidity_val is not None else ""
    cond_str = getattr(res, "condition", None) or "Live Weather"

    def deg_to_compass(deg: Optional[float]) -> str:
        if deg is None:
            return ""
        val = int((deg / 22.5) + 0.5)
        dirs = ["N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE", "S", "SSW", "SW", "WSW", "W", "WNW", "NW", "NNW"]
        return dirs[val % 16]

    compass = deg_to_compass(res.wind_direction_deg)
    wind_dir_str = f"{compass} ({res.wind_direction_deg:.0f}°)" if compass and res.wind_direction_deg is not None else ""

    return {
        "status": res.status.value,
        "condition": cond_str,
        "temperature": temp_str,
        "temperature_c": temp_val,
        "apparent_temperature": app_temp_str,
        "apparent_temperature_c": app_temp_val,
        "humidity": humidity_str,
        "humidity_percent": humidity_val,
        "wind_speed": f"{res.wind_speed_kmh:.1f} km/h" if res.wind_speed_kmh is not None else "0.0 km/h",
        "wind_speed_kmh": res.wind_speed_kmh,
        "wind_direction": wind_dir_str,
        "wind_direction_deg": res.wind_direction_deg,
        "precipitation": f"{res.precipitation_mm:.1f} mm" if res.precipitation_mm is not None else "0.0 mm",
        "precipitation_mm": res.precipitation_mm,
        "precipitation_probability": f"{precip_prob_val:.0f}%" if precip_prob_val is not None else None,
        "precipitation_probability_percent": precip_prob_val,
        "impact_minutes": res.impact_minutes,
        "description": res.description,
        "provenance": res.provenance,
        "sampled_at": res.sampled_at.isoformat() if res.sampled_at else None,
        "latitude": lat,
        "longitude": lon,
    }


@router.get(
    "/overrides",
    response_model=list[ETAOverrideResponse],
    status_code=status.HTTP_200_OK,
    summary="Get all recent Dispatcher manual ETA overrides across jobs",
)
async def get_all_recent_overrides(
    limit: int = Query(50, ge=1, le=100),
    current_user: UserResponse = Depends(get_current_user),
) -> list[ETAOverrideResponse]:
    """Retrieve all recent Dispatcher manual ETA overrides across jobs (Dispatcher/Admin only)."""
    if current_user.role not in (UserRole.DISPATCHER.value, UserRole.ADMINISTRATOR.value):
        raise ForbiddenError("Only dispatchers and administrators may view global ETA overrides.")

    service = ETAService()
    return await service.get_all_recent_overrides(limit=limit)


@router.get(
    "/jobs/{job_id}/eta",
    response_model=ETAResponse,
    status_code=status.HTTP_200_OK,
    summary="Get Context-Aware ETA for a field service job",
)
@router.get(
    "/{job_id}",
    response_model=ETAResponse,
    status_code=status.HTTP_200_OK,
    summary="Get Context-Aware ETA for a field service job (direct path)",
    include_in_schema=False,
)
async def get_job_eta(
    job_id: UUID,
    technician_id: Optional[UUID] = Query(
        None, description="Optional target technician UUID to evaluate prospective travel ETA"
    ),
    weather: Optional[str] = Query(
        None, description="Optional environmental weather condition override (e.g. 'Moderate Rain', 'Clear')"
    ),
    record_audit: bool = Query(
        False, description="Flag indicating whether to record a permanent AuditLog entry for this calculation"
    ),
    current_user: UserResponse = Depends(get_current_user),
) -> ETAResponse:
    """
    Retrieve deterministic baseline and context-aware travel ETA for a service job.

    RBAC Enforcement:
    - DISPATCHER & ADMINISTRATOR: Can view ETA across all operational jobs.
    - TECHNICIAN: Strictly restricted to their own assigned job(s). Access to other jobs returns 403 Forbidden.
    """
    job_repo = JobRepository()

    job = await job_repo.get_by_id(job_id)
    if not job:
        raise NotFoundError("Job", str(job_id))

    if current_user.role == UserRole.TECHNICIAN.value:
        if technician_id is not None:
            raise ForbiddenError("Technicians cannot evaluate ETAs for other technicians.")

        is_assigned = await job_repo.is_technician_assigned_to_job(current_user.id, job_id)
        if not is_assigned:
            raise ForbiddenError("Technicians can only access ETA information for jobs assigned to themselves.")

    service = ETAService()
    return await service.calculate_job_eta(
        job_id=job_id,
        technician_id=technician_id,
        weather_condition=weather,
        actor_id=current_user.id,
        record_audit=record_audit,
    )


@router.post(
    "/jobs/{job_id}/override",
    response_model=ETAOverrideResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Apply Dispatcher manual ETA override for a service job",
)
async def create_dispatcher_eta_override(
    job_id: UUID,
    payload: ETAOverrideCreate,
    current_user: UserResponse = Depends(get_current_user),
) -> ETAOverrideResponse:
    """
    Apply a manual Dispatcher ETA override with mandatory rationale reason.
    Generates an immutable audit log entry (ETA_OVERRIDE_CREATED).

    RBAC Enforcement:
    - DISPATCHER & ADMINISTRATOR: Authorized to create manual ETA overrides.
    - TECHNICIAN: Unauthorized (returns 403 Forbidden).
    """
    if current_user.role not in (UserRole.DISPATCHER.value, UserRole.ADMINISTRATOR.value):
        raise ForbiddenError("Technicians are not authorized to create dispatcher ETA overrides.")

    service = ETAService()
    return await service.create_dispatcher_override(
        job_id=job_id,
        overridden_eta=payload.overridden_eta,
        reason=payload.reason,
        dispatcher_id=current_user.id,
    )


@router.get(
    "/jobs/{job_id}/override-history",
    response_model=list[ETAOverrideResponse],
    status_code=status.HTTP_200_OK,
    summary="Get Dispatcher ETA override audit history for a service job",
)
async def get_job_eta_override_history(
    job_id: UUID,
    current_user: UserResponse = Depends(get_current_user),
) -> list[ETAOverrideResponse]:
    """
    Retrieve historical Dispatcher manual ETA overrides applied to a specific service job.

    RBAC Enforcement:
    - DISPATCHER & ADMINISTRATOR: Full access to view override history.
    - TECHNICIAN: Can view history for own assigned job only. Access to unassigned jobs returns 403 Forbidden.
    """
    job_repo = JobRepository()
    job = await job_repo.get_by_id(job_id)
    if not job:
        raise NotFoundError("Job", str(job_id))

    if current_user.role == UserRole.TECHNICIAN.value:
        is_assigned = await job_repo.is_technician_assigned_to_job(current_user.id, job_id)
        if not is_assigned:
            raise ForbiddenError("Technicians can only access ETA information for jobs assigned to themselves.")

    service = ETAService()
    return await service.get_override_history(job_id)



