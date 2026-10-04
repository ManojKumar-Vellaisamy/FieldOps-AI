"""
Context Aggregation & Evaluation Layer — Module 11.

Responsible for safely aggregating outputs from all context providers:
- Distinguishes AVAILABLE / STALE / UNAVAILABLE / INVALID states.
- Ensures UNAVAILABLE / INVALID providers contribute exactly 0 impact.
- Sums adjustments strictly from valid AVAILABLE inputs.
- Preserves individual data source and factor contributions for UI explainability.
"""

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Sequence

from app.schemas.eta import ContextFactor, DataSource
from app.services.context_providers import ContextProviderResult, DataSourceStatus


@dataclass
class ContextAggregationSummary:
    """Consolidated summary from evaluating all context providers."""

    total_adjustment_minutes: int
    data_sources: list[DataSource]
    factors: list[ContextFactor]
    calculation_status: str
    available_count: int
    unavailable_count: int
    stale_count: int
    invalid_count: int
    additional_verified_impact_minutes: int = 0


class ContextAggregationService:
    """
    Service layer for aggregating and validating context provider outputs.
    Guarantees deterministic, explainable calculations with causal deduplication,
    real-time freshness tracking, and layered sanity guards.
    """

    def aggregate(
        self,
        provider_results: Sequence[ContextProviderResult],
        baseline_eta_minutes: int,
        distance_km: float,
        distance_miles: float,
        technician_status: str = "AVAILABLE",
    ) -> ContextAggregationSummary:
        total_adjustment = 0
        additional_verified_impact = 0
        factors: list[ContextFactor] = []
        data_sources: list[DataSource] = []

        available_count = 0
        unavailable_count = 0
        stale_count = 0
        invalid_count = 0

        # Always include baseline travel as the initial factor
        dist_km_disp = round(distance_km, 2)
        dist_mi_disp = round(distance_miles, 2)
        factors.append(
            ContextFactor(
                category="TRAVEL",
                factor="Base Transit Distance",
                impact_minutes=baseline_eta_minutes,
                description=(
                    f"Transit distance: {dist_km_disp} km ({dist_mi_disp} mi) "
                    f"at 40 km/h urban transit speed (+3m staging)"
                ),
                impact_classification="INCLUDED_IN_LIVE_ROUTE",
                freshness="FRESH",
            )
        )

        # 1. First pass: classify providers and extract individual source contributions
        provider_map: dict[str, ContextProviderResult] = {}
        for result in provider_results:
            is_stale = (result.status == DataSourceStatus.STALE or result.freshness == "STALE")
            if is_stale:
                stale_count += 1
                effective_status = DataSourceStatus.STALE
                impact = 0
            elif result.status == DataSourceStatus.AVAILABLE:
                available_count += 1
                effective_status = DataSourceStatus.AVAILABLE
                impact = result.impact_minutes
            elif result.status == DataSourceStatus.INVALID:
                invalid_count += 1
                effective_status = DataSourceStatus.INVALID
                impact = 0
            else:
                unavailable_count += 1
                effective_status = DataSourceStatus.UNAVAILABLE
                impact = 0

            ds_dict = result.to_data_source_dict()
            ds_dict["status"] = effective_status.value
            ds_dict["impact_minutes"] = impact
            if is_stale:
                ds_dict["freshness"] = "STALE"
                ds_dict["impact_classification"] = "NOT_APPLIED"

            data_sources.append(DataSource(**ds_dict))
            provider_map[result.category.upper()] = result

        # 2. Cross-provider deduplication & causal classifications
        traffic_res = provider_map.get("TRAFFIC")
        road_res = provider_map.get("ROAD")
        events_res = provider_map.get("EVENTS")
        weather_res = provider_map.get("WEATHER")

        traffic_is_stale = traffic_res and (traffic_res.status == DataSourceStatus.STALE or traffic_res.freshness == "STALE")
        traffic_imp = traffic_res.impact_minutes if (traffic_res and traffic_res.status == DataSourceStatus.AVAILABLE and not traffic_is_stale) else 0
        # CRITICAL RULE (Phase 4E): TomTom authoritative live routing traffic delay is REAL measured telemetry
        # and must NEVER be arbitrarily capped or clamped. Only derived/synthetic fallback traffic feeds are bounded.
        if traffic_res and traffic_res.provenance != "REAL":
            traffic_imp = max(0, min(traffic_imp, max(15, baseline_eta_minutes * 3)))
        else:
            traffic_imp = max(0, traffic_imp)

        road_is_stale = road_res and (road_res.status == DataSourceStatus.STALE or road_res.freshness == "STALE")
        road_imp = road_res.impact_minutes if (road_res and road_res.status == DataSourceStatus.AVAILABLE and not road_is_stale) else 0

        event_is_stale = events_res and (events_res.status == DataSourceStatus.STALE or events_res.freshness == "STALE")
        event_imp = events_res.impact_minutes if (events_res and events_res.status == DataSourceStatus.AVAILABLE and not event_is_stale) else 0
        # Event sanity guard: maximum 15 minutes impact
        event_imp = min(15, max(0, event_imp))

        weather_is_stale = weather_res and (weather_res.status == DataSourceStatus.STALE or weather_res.freshness == "STALE")
        weather_imp = weather_res.impact_minutes if (weather_res and weather_res.status == DataSourceStatus.AVAILABLE and not weather_is_stale) else 0
        # Weather sanity guard: capped at max 30% of baseline route duration (or absolute max 25 min)
        max_weather_allowed = min(25, max(2, round(baseline_eta_minutes * 0.30)))
        weather_adjusted_imp = min(weather_imp, max_weather_allowed)

        # Causal Deduplication: Road Restriction vs Live Traffic
        road_adjusted_imp = road_imp
        if road_res and road_res.impact_classification == "INCREMENTAL_DETOUR":
            road_adjusted_imp = road_imp
        elif road_res and road_res.impact_classification == "INCLUDED_IN_LIVE_ROUTE":
            road_adjusted_imp = 0
        elif road_res and road_res.impact_classification == "RELEVANT_INCIDENT_DELAY":
            # Non-closure incident traversal delay: deduplicate against live route traffic delay
            if traffic_imp > 0 and road_imp > 0:
                road_adjusted_imp = max(0, road_imp - traffic_imp)
            else:
                road_adjusted_imp = road_imp
        elif traffic_imp > 0 and road_imp > 0:
            road_adjusted_imp = max(0, road_imp - traffic_imp)

        # Causal Deduplication: Events vs Live Traffic
        event_adjusted_imp = event_imp
        if events_res and events_res.impact_classification == "INCLUDED_IN_LIVE_ROUTE":
            event_adjusted_imp = 0
        elif traffic_imp > 0 and event_imp > 0:
            event_adjusted_imp = max(0, event_imp - traffic_imp)

        # 3. Compile model context factors with deduplicated impacts
        for result in provider_results:
            cat = result.category.upper()
            f_dict = result.to_factor_dict()
            is_stale = (result.status == DataSourceStatus.STALE or result.freshness == "STALE")

            if is_stale:
                f_dict["impact_minutes"] = 0
                f_dict["freshness"] = "STALE"
                f_dict["impact_classification"] = "NOT_APPLIED"
                factors.append(ContextFactor(**f_dict))
                continue

            if result.status != DataSourceStatus.AVAILABLE:
                f_dict["impact_minutes"] = 0
                f_dict["impact_classification"] = "UNAVAILABLE"
                factors.append(ContextFactor(**f_dict))
                continue

            if cat == "ROAD":
                f_dict["impact_minutes"] = road_adjusted_imp
                if road_imp > 0 and road_adjusted_imp < road_imp:
                    f_dict["description"] += f" (Adjusted from +{road_imp}m to avoid double-counting traffic feed)."
                if road_adjusted_imp == 0 and road_imp > 0:
                    f_dict["impact_classification"] = "INCLUDED_IN_LIVE_ROUTE"
                if road_adjusted_imp > 0:
                    total_adjustment += road_adjusted_imp
                    additional_verified_impact += road_adjusted_imp
                factors.append(ContextFactor(**f_dict))

            elif cat == "EVENTS":
                f_dict["impact_minutes"] = event_adjusted_imp
                if event_imp > 0 and event_adjusted_imp < event_imp:
                    f_dict["description"] += f" (Adjusted from +{event_imp}m to avoid double-counting traffic feed)."
                if event_adjusted_imp == 0 and event_imp > 0:
                    f_dict["impact_classification"] = "INCLUDED_IN_LIVE_ROUTE"
                if event_adjusted_imp > 0:
                    total_adjustment += event_adjusted_imp
                    additional_verified_impact += event_adjusted_imp
                factors.append(ContextFactor(**f_dict))

            elif cat == "WEATHER":
                f_dict["impact_minutes"] = weather_adjusted_imp
                if weather_imp > 0 and weather_adjusted_imp < weather_imp:
                    f_dict["description"] += f" (Capped from +{weather_imp}m by route-duration sanity guard)."
                if weather_adjusted_imp > 0:
                    total_adjustment += weather_adjusted_imp
                    additional_verified_impact += weather_adjusted_imp
                factors.append(ContextFactor(**f_dict))

            elif cat == "TRAFFIC":
                f_dict["impact_minutes"] = traffic_imp
                total_adjustment += traffic_imp
                factors.append(ContextFactor(**f_dict))

            else:
                factors.append(ContextFactor(**f_dict))

        # 4. Technician operational availability adjustment
        tech_status_upper = technician_status.upper()
        if tech_status_upper in ("BUSY", "ON_BREAK"):
            status_delay = 10
            total_adjustment += status_delay
            additional_verified_impact += status_delay
            factors.append(
                ContextFactor(
                    category="AVAILABILITY",
                    factor=f"Technician Status ({technician_status})",
                    impact_minutes=status_delay,
                    description=(
                        f"Technician currently {technician_status.lower()} "
                        f"(+{status_delay} min staging delay before dispatch)"
                    ),
                    impact_classification="INDEPENDENT_CONTEXT",
                    freshness="FRESH",
                )
            )
        else:
            factors.append(
                ContextFactor(
                    category="AVAILABILITY",
                    factor="Technician Status (Available)",
                    impact_minutes=0,
                    description="Technician available for immediate dispatch without staging delay.",
                    impact_classification="NOT_APPLIED",
                    freshness="FRESH",
                )
            )

        # 5. Operational Realism Guard: Bounds check for short routes
        # CRITICAL RULE (Phase 4E): The short-route guard and aggregate caps protect strictly
        # against over-inflated DERIVED additive context (weather, events, staging).
        # They must NEVER clamp or reduce:
        #   A. TomTom live-route travel time
        #   B. TomTom measured traffic delay
        #   C. Verified alternate-route road detour
        derived_additive_context = weather_adjusted_imp + event_adjusted_imp
        if tech_status_upper in ("BUSY", "ON_BREAK"):
            derived_additive_context += status_delay

        is_short_route = (distance_km <= 5.0 or distance_miles <= 3.0 or baseline_eta_minutes <= 10)

        if is_short_route and derived_additive_context > 0:
            max_realistic_derived = max(6, round(baseline_eta_minutes * 1.5))
            if derived_additive_context > max_realistic_derived:
                excess = derived_additive_context - max_realistic_derived
                derived_additive_context = max_realistic_derived
                additional_verified_impact = max(road_adjusted_imp, additional_verified_impact - excess)

        # General aggregate sanity cap: derived environmental context cannot exceed 2.0x baseline (max 60 min)
        if derived_additive_context > 0:
            max_derived_cap = min(60, max(15, baseline_eta_minutes * 2))
            if derived_additive_context > max_derived_cap:
                excess = derived_additive_context - max_derived_cap
                derived_additive_context = max_derived_cap
                additional_verified_impact = max(road_adjusted_imp, additional_verified_impact - excess)

        # Re-compute total_adjustment ensuring TomTom live traffic delay and verified detour are preserved in full:
        total_adjustment = traffic_imp + additional_verified_impact

        # Determine overall calculation status
        total_providers = len(provider_results)
        if unavailable_count == 0 and invalid_count == 0 and stale_count == 0:
            calc_status = "COMPLETE"
        elif available_count > 0:
            calc_status = "PARTIAL"
        else:
            calc_status = "INSUFFICIENT"

        return ContextAggregationSummary(
            total_adjustment_minutes=total_adjustment,
            data_sources=data_sources,
            factors=factors,
            calculation_status=calc_status,
            available_count=available_count,
            unavailable_count=unavailable_count,
            stale_count=stale_count,
            invalid_count=invalid_count,
            additional_verified_impact_minutes=additional_verified_impact,
        )
