"""
Context-Aware ETA Engine Service — Module 11 Upgrade.

Calculates deterministic baseline travel ETAs and context-aware operational adjustments
using the provider-based context architecture (context_providers.py) and context aggregation layer.

Data pipeline:
  PostgreSQL (Job + Technician + Assignment)
    → GPSLocationProvider     (AVAILABLE / STALE / UNAVAILABLE / INVALID)
    → WeatherProvider         (AVAILABLE — dispatcher-supplied or default)
    → TrafficDataProvider     (UNAVAILABLE unless integrated feed available)
    → EventsDataProvider      (UNAVAILABLE unless integrated feed available)
    → RoadRestrictionProvider (UNAVAILABLE unless integrated feed available)
  → ContextAggregationService (Validates status & aggregates adjustments)
  → Baseline ETA (Haversine distance / 40 km/h + 3 min staging)
  → Context-Aware ETA (baseline + sum of valid AVAILABLE adjustments)
  → Dispatcher Override Check (if override present, set final_dispatch_eta_minutes)
  → ETAResponse (fully explainable with data_sources, factors, override)

Baseline speed: 40 km/h (urban/suburban transit — no highway routing assumed).
"""

from datetime import datetime, timedelta, timezone
import math
from typing import Optional
import uuid

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.core.exceptions import NotFoundError, ValidationError
from app.database.session import AsyncSessionLocal
from app.models.assignment import Assignment
from app.models.audit_log import AuditLog
from app.models.eta_override import ETAOverride
from app.models.job import Job
from app.models.technician import Technician
from app.models.user import User
from app.schemas.eta import (
    ContextFactor,
    DataSource,
    ETAOverrideResponse,
    ETAResponse,
)
from app.services.context_aggregation import ContextAggregationService
from app.services.context_providers import (
    DataSourceStatus,
    EventsDataProvider,
    GPSLocationProvider,
    RoadRestrictionProvider,
    TrafficDataProvider,
    WeatherProvider,
)


# ── Geospatial helpers ─────────────────────────────────────────────────────────

_EARTH_RADIUS_MILES = 3958.8
_EARTH_RADIUS_KM = 6371.0
_MILES_TO_KM = 1.60934
_BASELINE_SPEED_KMH = 40.0          # Urban / suburban transit assumption
_DISPATCH_STAGING_MINUTES = 3        # Fixed staging / route prep overhead


def _haversine_miles(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Haversine great-circle distance in miles."""
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2) ** 2
    )
    return _EARTH_RADIUS_MILES * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def _miles_to_km(miles: float) -> float:
    return round(miles * _MILES_TO_KM, 2)


def _baseline_minutes(distance_miles: float) -> int:
    """
    Compute baseline travel time in minutes.
    Converts miles to km, divides by urban speed (40 km/h), adds staging overhead.
    """
    if distance_miles == 0.0:
        return 0
    km = distance_miles * _MILES_TO_KM
    travel_min = (km / _BASELINE_SPEED_KMH) * 60.0
    return max(1, round(travel_min + _DISPATCH_STAGING_MINUTES))


# ── ETA Service ────────────────────────────────────────────────────────────────

class ETAService:
    """
    Business service responsible for deterministic, explainable context-aware
    ETA calculations, context aggregation, dispatcher overrides, and compliance audit logging.
    """

    async def calculate_job_eta(
        self,
        job_id: uuid.UUID,
        technician_id: Optional[uuid.UUID] = None,
        weather_condition: Optional[str] = None,
        actor_id: Optional[uuid.UUID] = None,
        record_audit: bool = False,
    ) -> ETAResponse:
        """
        Calculates baseline travel ETA and context-aware operational adjustments.
        Checks for any active Dispatcher Override on the job and reflects it cleanly.
        """
        now = datetime.now(timezone.utc)

        async with AsyncSessionLocal() as session:
            # ── 1. Fetch Job with assignments, technician, user & overrides ─────
            stmt = (
                select(Job)
                .where(Job.id == job_id)
                .options(
                    selectinload(Job.assignments)
                    .selectinload(Assignment.technician)
                    .selectinload(Technician.user),
                    selectinload(Job.eta_overrides).selectinload(ETAOverride.dispatcher),
                )
            )
            result = await session.execute(stmt)
            job = result.scalar_one_or_none()

            if not job:
                raise NotFoundError("Job", str(job_id))

            # ── 2. Identify target technician ──────────────────────────────────
            target_tech: Optional[Technician] = None

            if technician_id:
                tech_stmt = (
                    select(Technician)
                    .where(Technician.id == technician_id)
                    .options(
                        selectinload(Technician.user),
                        selectinload(Technician.assignments),
                    )
                )
                tech_res = await session.execute(tech_stmt)
                target_tech = tech_res.scalar_one_or_none()
            else:
                active_assignments = [
                    asg
                    for asg in job.assignments
                    if getattr(asg, "assignment_status", "") in (
                        "ASSIGNED", "TRAVELLING", "ARRIVED", "WORKING"
                    )
                ]
                if active_assignments:
                    target_tech = active_assignments[0].technician

            # ── 3. Check for active dispatcher override ────────────────────────
            active_override_resp: Optional[ETAOverrideResponse] = None
            if job.eta_overrides:
                sorted_overrides = sorted(job.eta_overrides, key=lambda o: o.created_at, reverse=True)
                latest_override = sorted_overrides[0]
                active_override_resp = ETAOverrideResponse(
                    id=latest_override.id,
                    job_id=latest_override.job_id,
                    technician_id=latest_override.technician_id,
                    dispatcher_id=latest_override.dispatcher_id,
                    dispatcher_name=latest_override.dispatcher.full_name if latest_override.dispatcher else "Dispatcher",
                    original_system_eta=latest_override.original_system_eta,
                    overridden_eta=latest_override.overridden_eta,
                    reason=latest_override.reason,
                    previous_value=latest_override.previous_value,
                    new_value=latest_override.new_value,
                    created_at=latest_override.created_at,
                )

            # ── 4. Evaluate required GPS context ──────────────────────────────
            missing_context: list[str] = []

            if not target_tech:
                missing_context.append("No technician assigned to calculate travel distance and route.")

            if job.latitude is None or job.longitude is None:
                missing_context.append("Job service address GPS coordinates are missing.")

            if target_tech and (
                target_tech.current_latitude is None or target_tech.current_longitude is None
            ):
                missing_context.append("Technician last known GPS coordinates are missing.")

            # ── 5. INSUFFICIENT context — return explainable unavailable state ──
            if missing_context:
                data_sources = await self._evaluate_unavailable_sources(
                    weather_condition=weather_condition,
                    missing_tech_location=True,
                )

                final_eta = active_override_resp.overridden_eta if active_override_resp else None
                arrival_time_iso = (
                    (now + timedelta(minutes=final_eta)).isoformat() if final_eta else None
                )

                return ETAResponse(
                    job_id=job.id,
                    job_number=job.job_number,
                    is_context_sufficient=False,
                    calculation_status="INSUFFICIENT",
                    baseline_eta_minutes=None,
                    context_aware_eta_minutes=None,
                    adjustment_minutes=None,
                    final_dispatch_eta_minutes=final_eta,
                    estimated_arrival_time=arrival_time_iso,
                    technician_id=target_tech.id if target_tech else None,
                    technician_name=(
                        target_tech.user.full_name
                        if (target_tech and target_tech.user)
                        else None
                    ),
                    technician_code=target_tech.employee_code if target_tech else None,
                    active_override=active_override_resp,
                    distance_miles=None,
                    distance_km=None,
                    factors=[],
                    data_sources=data_sources,
                    reason=(
                        f"ETA unavailable: {missing_context[0]}"
                        if missing_context
                        else "ETA unavailable: Insufficient operational context."
                    ),
                    missing_context=missing_context,
                    calculated_at=now,
                )

            # ── 6. SUFFICIENT — compute baseline distance ──────────────────────
            assert target_tech is not None
            assert job.latitude is not None
            assert job.longitude is not None
            assert target_tech.current_latitude is not None
            assert target_tech.current_longitude is not None

            dist_miles = round(
                _haversine_miles(
                    job.latitude,
                    job.longitude,
                    target_tech.current_latitude,
                    target_tech.current_longitude,
                ),
                2,
            )
            dist_km = _miles_to_km(dist_miles)
            baseline_eta = _baseline_minutes(dist_miles)

            # ── 7. Evaluate context providers ─────────────────────────────────
            tech_updated_at: Optional[datetime] = getattr(target_tech, "updated_at", None)

            gps_provider = GPSLocationProvider()
            weather_provider = WeatherProvider()
            traffic_provider = TrafficDataProvider()
            events_provider = EventsDataProvider()
            road_provider = RoadRestrictionProvider()

            gps_result = await gps_provider.evaluate(
                technician_lat=target_tech.current_latitude,
                technician_lon=target_tech.current_longitude,
                tech_updated_at=tech_updated_at,
            )
            weather_result = await weather_provider.evaluate(
                weather_condition=weather_condition,
            )
            traffic_result = await traffic_provider.evaluate()
            events_result = await events_provider.evaluate()
            road_result = await road_provider.evaluate()

            all_results = [gps_result, weather_result, traffic_result, events_result, road_result]

            # ── 8. Aggregate via ContextAggregationService ────────────────────
            agg_service = ContextAggregationService()
            summary = agg_service.aggregate(
                provider_results=all_results,
                baseline_eta_minutes=baseline_eta,
                distance_km=dist_km,
                distance_miles=dist_miles,
                technician_status=target_tech.availability_status,
            )

            context_aware_eta = baseline_eta + summary.total_adjustment_minutes

            # Final dispatch ETA: overridden_eta if active override exists, else context_aware_eta
            final_dispatch_eta = (
                active_override_resp.overridden_eta
                if active_override_resp
                else context_aware_eta
            )

            estimated_arrival_dt = now + timedelta(minutes=final_dispatch_eta)
            estimated_arrival_iso = estimated_arrival_dt.isoformat()

            # Compose summary reason
            adj_reasons = [f.description for f in summary.factors if f.impact_minutes > 0]
            if adj_reasons:
                reason = " / ".join(adj_reasons)
            else:
                reason = (
                    "Clear transit conditions — direct route with no operational delay. "
                    "Traffic, events, and road restriction data not integrated."
                )

            if active_override_resp:
                reason += f" [Dispatcher Manual Override: {active_override_resp.overridden_eta} min - Reason: {active_override_resp.reason}]"

            # ── 9. Audit (only on explicit request) ───────────────────────────
            if record_audit:
                audit_entry = AuditLog(
                    id=uuid.uuid4(),
                    user_id=actor_id,
                    action="CALCULATE_ETA",
                    entity="Job",
                    entity_id=str(job.id),
                    reason=reason,
                    old_value=None,
                    new_value=(
                        f"Baseline: {baseline_eta} min | Context-Aware: {context_aware_eta} min "
                        f"| Final Dispatch ETA: {final_dispatch_eta} min | Distance: {dist_km} km | "
                        f"Tech: {target_tech.employee_code} | "
                        f"Sources: {summary.calculation_status} ({summary.unavailable_count} unavailable)"
                    ),
                    created_at=now,
                )
                session.add(audit_entry)
                await session.commit()

            return ETAResponse(
                job_id=job.id,
                job_number=job.job_number,
                is_context_sufficient=True,
                calculation_status=summary.calculation_status,
                baseline_eta_minutes=baseline_eta,
                context_aware_eta_minutes=context_aware_eta,
                adjustment_minutes=summary.total_adjustment_minutes,
                final_dispatch_eta_minutes=final_dispatch_eta,
                estimated_arrival_time=estimated_arrival_iso,
                technician_id=target_tech.id,
                technician_name=(
                    target_tech.user.full_name if target_tech.user else "Technician"
                ),
                technician_code=target_tech.employee_code,
                active_override=active_override_resp,
                distance_miles=dist_miles,
                distance_km=dist_km,
                factors=summary.factors,
                data_sources=summary.data_sources,
                reason=reason,
                missing_context=[],
                calculated_at=now,
            )

    async def create_dispatcher_override(
        self,
        job_id: uuid.UUID,
        overridden_eta: int,
        reason: str,
        dispatcher_id: uuid.UUID,
    ) -> ETAOverrideResponse:
        """
        Creates an immutable Dispatcher manual ETA override record and logs an ETA_OVERRIDE_CREATED audit event.
        Requires a non-empty rationale reason.
        """
        now = datetime.now(timezone.utc)
        clean_reason = reason.strip()
        if not clean_reason:
            raise ValidationError("A valid operational reason is required for dispatcher ETA override.")

        async with AsyncSessionLocal() as session:
            # 1. Fetch Job
            stmt = (
                select(Job)
                .where(Job.id == job_id)
                .options(
                    selectinload(Job.assignments).selectinload(Assignment.technician),
                    selectinload(Job.eta_overrides),
                )
            )
            res = await session.execute(stmt)
            job = res.scalar_one_or_none()
            if not job:
                raise NotFoundError("Job", str(job_id))

            # Fetch dispatcher user profile
            disp_res = await session.execute(select(User).where(User.id == dispatcher_id))
            dispatcher_user = disp_res.scalar_one_or_none()

            # Find target technician
            target_tech: Optional[Technician] = None
            active_asgs = [
                a for a in job.assignments
                if a.assignment_status in ("ASSIGNED", "TRAVELLING", "ARRIVED", "WORKING")
            ]
            if active_asgs:
                target_tech = active_asgs[0].technician

            # 2. Compute current system context-aware ETA
            calc_resp = await self.calculate_job_eta(job_id=job_id, technician_id=target_tech.id if target_tech else None)
            sys_eta = calc_resp.context_aware_eta_minutes or calc_resp.baseline_eta_minutes or 0

            prev_value_str = f"context_aware_eta={sys_eta}"
            new_value_str = f"dispatcher_eta={overridden_eta}"

            # 3. Create ETAOverride ORM entity
            override = ETAOverride(
                id=uuid.uuid4(),
                job_id=job.id,
                technician_id=target_tech.id if target_tech else None,
                dispatcher_id=dispatcher_id,
                original_system_eta=sys_eta,
                overridden_eta=overridden_eta,
                reason=clean_reason,
                previous_value=prev_value_str,
                new_value=new_value_str,
                created_at=now,
            )
            session.add(override)

            # 4. Create immutable AuditLog entry with action ETA_OVERRIDE_CREATED
            audit_log = AuditLog(
                id=uuid.uuid4(),
                user_id=dispatcher_id,
                action="ETA_OVERRIDE_CREATED",
                entity="Job",
                entity_id=str(job.id),
                reason=clean_reason,
                old_value=prev_value_str,
                new_value=new_value_str,
                created_at=now,
            )
            session.add(audit_log)

            await session.commit()
            await session.refresh(override)

            return ETAOverrideResponse(
                id=override.id,
                job_id=override.job_id,
                technician_id=override.technician_id,
                dispatcher_id=override.dispatcher_id,
                dispatcher_name=dispatcher_user.full_name if dispatcher_user else "Dispatcher",
                original_system_eta=override.original_system_eta,
                overridden_eta=override.overridden_eta,
                reason=override.reason,
                previous_value=override.previous_value,
                new_value=override.new_value,
                created_at=override.created_at,
            )

    async def get_override_history(self, job_id: uuid.UUID) -> list[ETAOverrideResponse]:
        """Returns all historical ETA overrides recorded for a job."""
        async with AsyncSessionLocal() as session:
            stmt = (
                select(ETAOverride)
                .where(ETAOverride.job_id == job_id)
                .options(selectinload(ETAOverride.dispatcher))
                .order_by(ETAOverride.created_at.desc())
            )
            res = await session.execute(stmt)
            overrides = res.scalars().all()

            return [
                ETAOverrideResponse(
                    id=o.id,
                    job_id=o.job_id,
                    technician_id=o.technician_id,
                    dispatcher_id=o.dispatcher_id,
                    dispatcher_name=o.dispatcher.full_name if o.dispatcher else "Dispatcher",
                    original_system_eta=o.original_system_eta,
                    overridden_eta=o.overridden_eta,
                    reason=o.reason,
                    previous_value=o.previous_value,
                    new_value=o.new_value,
                    created_at=o.created_at,
                )
                for o in overrides
            ]

    async def _evaluate_unavailable_sources(
        self,
        weather_condition: Optional[str] = None,
        missing_tech_location: bool = False,
    ) -> list[DataSource]:
        """Evaluate provider statuses when mandatory GPS context is missing."""
        now = datetime.now(timezone.utc)

        gps_source = DataSource(
            name="GPS Location",
            status=DataSourceStatus.UNAVAILABLE.value,
            description="Technician GPS coordinates not available.",
            impact_minutes=0,
            sampled_at=now.isoformat(),
            category="GPS",
        )

        weather_provider = WeatherProvider()
        weather_result = await weather_provider.evaluate(weather_condition=weather_condition)
        weather_source = DataSource(**weather_result.to_data_source_dict())

        traffic_result = await TrafficDataProvider().evaluate()
        events_result = await EventsDataProvider().evaluate()
        road_result = await RoadRestrictionProvider().evaluate()

        return [
            gps_source,
            weather_source,
            DataSource(**traffic_result.to_data_source_dict()),
            DataSource(**events_result.to_data_source_dict()),
            DataSource(**road_result.to_data_source_dict()),
        ]
