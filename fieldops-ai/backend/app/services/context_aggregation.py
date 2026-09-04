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


class ContextAggregationService:
    """
    Service layer for aggregating and validating context provider outputs.
    Guarantees deterministic, explainable calculations.
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
        factors: list[ContextFactor] = []
        data_sources: list[DataSource] = []

        available_count = 0
        unavailable_count = 0
        stale_count = 0
        invalid_count = 0

        # Always include baseline travel as the initial factor
        factors.append(
            ContextFactor(
                category="TRAVEL",
                factor="Base Transit Distance",
                impact_minutes=baseline_eta_minutes,
                description=(
                    f"Distance: {distance_km} km ({distance_miles} mi) at 40 km/h "
                    "urban transit speed (+3m staging)"
                ),
            )
        )

        for result in provider_results:
            # Count status
            if result.status == DataSourceStatus.AVAILABLE:
                available_count += 1
            elif result.status == DataSourceStatus.UNAVAILABLE:
                unavailable_count += 1
            elif result.status == DataSourceStatus.STALE:
                stale_count += 1
            elif result.status == DataSourceStatus.INVALID:
                invalid_count += 1

            # Safety enforcement: non-AVAILABLE providers MUST have 0 impact
            impact = result.impact_minutes if result.status == DataSourceStatus.AVAILABLE else 0

            # Convert to DataSource dict/model
            ds_dict = result.to_data_source_dict()
            ds_dict["impact_minutes"] = impact
            data_sources.append(DataSource(**ds_dict))

            # If AVAILABLE with non-zero impact (or informational 0 impact for Weather/Availability), add factor
            if result.status == DataSourceStatus.AVAILABLE:
                if impact > 0:
                    total_adjustment += impact
                    factors.append(ContextFactor(**result.to_factor_dict()))
                elif result.category in ("WEATHER", "AVAILABILITY"):
                    factors.append(ContextFactor(**result.to_factor_dict()))

        # Technician operational availability adjustment
        tech_status_upper = technician_status.upper()
        if tech_status_upper in ("BUSY", "ON_BREAK"):
            status_delay = 10
            total_adjustment += status_delay
            factors.append(
                ContextFactor(
                    category="AVAILABILITY",
                    factor=f"Technician Status ({technician_status})",
                    impact_minutes=status_delay,
                    description=(
                        f"Technician currently {technician_status.lower()} "
                        f"(+{status_delay} min staging delay before dispatch)"
                    ),
                )
            )
        else:
            factors.append(
                ContextFactor(
                    category="AVAILABILITY",
                    factor="Technician Status (Available)",
                    impact_minutes=0,
                    description="Technician available for immediate dispatch without staging delay.",
                )
            )

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
        )
