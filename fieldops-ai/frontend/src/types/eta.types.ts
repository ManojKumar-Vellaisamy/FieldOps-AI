/**
 * Context data source operational status.
 */
export type DataSourceStatus = 'AVAILABLE' | 'STALE' | 'UNAVAILABLE' | 'INVALID';

/**
 * Context factor category.
 */
export type FactorCategory = 'TRAVEL' | 'WEATHER' | 'TRAFFIC' | 'EVENTS' | 'ROAD' | 'GPS' | 'AVAILABILITY' | string;

/**
 * A single operational context factor that affects the ETA calculation.
 */
export interface ContextFactor {
  category: FactorCategory;
  factor: string;
  impact_minutes: number;
  description: string;
  provenance?: 'REAL' | 'DERIVED' | 'SYSTEM' | string;
  freshness?: 'FRESH' | 'STALE' | 'UNAVAILABLE' | 'UNKNOWN' | string;
  impact_classification?: 'INCLUDED_IN_LIVE_ROUTE' | 'INCREMENTAL_DETOUR' | 'INDEPENDENT_CONTEXT' | 'NOT_APPLIED' | 'UNAVAILABLE' | string;
  is_route_relevant?: boolean | null;
  relevance_status?: string | null;
  relevance_reason?: string | null;
  applied_to_eta?: boolean | null;
  distance_to_route?: number | null;
  distance_to_route_meters?: number | null;
  distance_to_route_km?: number | null;
  distance_to_route_display?: string | null;
  provider_timestamp?: string | null;
  fetched_timestamp?: string | null;
  data_age_seconds?: number | null;
  detour_seconds?: number | null;
  incident_delay_seconds?: number | null;
  alternate_route_available?: boolean | null;
  alternate_route_valid?: boolean | null;
  original_route_time_seconds?: number | null;
  alternate_route_time_seconds?: number | null;
  detour_display?: string | null;
  causal_status?: string | null;
}

/**
 * A context data source with its operational availability status.
 * All 5 sources are always returned: GPS, Weather, Traffic, Events, Road Restrictions.
 */
export interface DataSource {
  name: string;
  status: DataSourceStatus;
  description: string;
  impact_minutes: number;
  sampled_at: string | null;
  category: string;
  /**
   * Data provenance classification for UI display:
   *   REAL        — live external API data (Open-Meteo, TomTom with API key)
   *   DERIVED     — computed from routing engine or system data (OSRM, haversine)
   *   SYSTEM      — sourced from internal DB records (GPS location from PostgreSQL)
   *   UNAVAILABLE — source not configured, unreachable, or returned invalid data
   */
  provenance?: 'REAL' | 'DERIVED' | 'SYSTEM' | 'UNAVAILABLE';
  freshness?: 'FRESH' | 'STALE' | 'UNAVAILABLE' | 'UNKNOWN' | string;
  impact_classification?: 'INCLUDED_IN_LIVE_ROUTE' | 'INCREMENTAL_DETOUR' | 'INDEPENDENT_CONTEXT' | 'NOT_APPLIED' | 'UNAVAILABLE' | string;
  is_route_relevant?: boolean | null;
  relevance_status?: string | null;
  relevance_reason?: string | null;
  applied_to_eta?: boolean | null;
  distance_to_route?: number | null;
  distance_to_route_meters?: number | null;
  distance_to_route_km?: number | null;
  distance_to_route_display?: string | null;
  provider_timestamp?: string | null;
  fetched_timestamp?: string | null;
  data_age_seconds?: number | null;
  corridor_buffer_meters?: number | null;
  detour_travel_time_minutes?: number | null;
  evaluated_items?: Array<Record<string, any>> | null;
  precipitation_mm?: number | null;
  wind_speed_kmh?: number | null;
  wind_direction_deg?: number | null;
  apparent_temperature_c?: number | null;
  humidity_percent?: number | null;
  precipitation_probability_percent?: number | null;
  temperature_c?: number | null;
  condition?: string | null;
  event_count?: number | null;
  active_event_name?: string | null;
  event_category?: string | null;
  event_attendance?: number | null;
  event_rank?: number | null;
  event_id?: string | null;
  event_start?: string | null;
  event_end?: string | null;
  event_latitude?: number | null;
  event_longitude?: number | null;
  event_location_summary?: string | null;
  event_distance_miles?: number | null;
  event_relevance?: number | null;
  restriction_count?: number | null;
  active_restriction_name?: string | null;
  restriction_category?: string | null;
  restriction_severity?: string | null;
  restriction_id?: string | null;
  restriction_start?: string | null;
  restriction_end?: string | null;
  restriction_road_name?: string | null;
  restriction_delay_seconds?: number | null;
  restriction_distance_miles?: number | null;
  is_road_closed?: boolean | null;
  traffic_delay_seconds?: number | null;
  free_flow_eta_minutes?: number | null;
  live_route_eta_minutes?: number | null;
  routed_distance_meters?: number | null;
  routed_distance_miles?: number | null;
  routed_distance_km?: number | null;
  route_geometry?: [number, number][] | null;
  detour_seconds?: number | null;
  incident_delay_seconds?: number | null;
  alternate_route_available?: boolean | null;
  alternate_route_valid?: boolean | null;
  original_route_time_seconds?: number | null;
  alternate_route_time_seconds?: number | null;
  detour_display?: string | null;
  causal_status?: string | null;
}

/**
 * Dispatcher manual ETA override record.
 */
export interface ETAOverride {
  id: string;
  job_id: string;
  technician_id: string | null;
  dispatcher_id: string;
  dispatcher_name: string | null;
  original_system_eta: number;
  overridden_eta: number;
  reason: string;
  previous_value: string | null;
  new_value: string | null;
  created_at: string;
}

/**
 * Payload for applying a Dispatcher manual ETA override.
 */
export interface ETAOverrideCreate {
  overridden_eta: number;
  reason: string;
}

/**
 * Single evaluation scenario sample result.
 */
export interface ETAExperimentSampleResult {
  id: number;
  distance_km: number;
  baseline_eta_minutes: number;
  context_aware_eta_minutes: number;
  actual_travel_minutes: number;
  baseline_absolute_error: number;
  context_aware_absolute_error: number;
  improvement_minutes: number;
  is_non_routine: boolean;
  conditions: string;
}

/**
 * ETA Experiment prediction error metrics.
 */
export interface ETAExperimentMetrics {
  baseline_mae_minutes: number | null;
  context_aware_mae_minutes: number | null;
  baseline_routine_mae?: number | null;
  context_aware_routine_mae?: number | null;
  baseline_non_routine_mae?: number | null;
  context_aware_non_routine_mae?: number | null;
  improvement_percent: number | null;
  non_routine_improvement_percent?: number | null;
  sample_count: number;
  routine_sample_count?: number;
  non_routine_sample_count?: number;
  is_simulated_dataset: boolean;
  is_sufficient_data?: boolean;
  min_required_samples?: number;
  dataset_description: string;
  narrative_summary: string;
  disclaimer?: string;
  sample_breakdown?: ETAExperimentSampleResult[];
  error_analysis?: { category: string; finding: string }[];
}

/**
 * Complete explainable Context-Aware ETA response from the backend.
 */
export interface ETAResponse {
  // Job identification
  job_id: string;
  job_number: string;

  // Context sufficiency
  is_context_sufficient: boolean;
  calculation_status: 'COMPLETE' | 'PARTIAL' | 'INSUFFICIENT' | 'ERROR';

  // ETA metrics
  baseline_eta_minutes: number | null;
  context_aware_eta_minutes: number | null;
  adjustment_minutes: number | null;
  additional_verified_impact_minutes?: number | null;
  final_dispatch_eta_minutes: number | null;
  estimated_arrival_time: string | null;

  // Distance & Routing Telemetry
  distance_miles: number | null;
  distance_km: number | null;
  routed_distance_meters?: number | null;
  routed_distance_miles?: number | null;
  routed_distance_km?: number | null;
  haversine_distance_miles?: number | null;
  haversine_distance_km?: number | null;
  traffic_delay_minutes?: number | null;
  route_geometry?: [number, number][] | null;
  route_provenance?: 'REAL' | 'DERIVED' | 'SYSTEM' | 'UNAVAILABLE' | string;
  free_flow_eta_minutes?: number | null;
  live_route_eta_minutes?: number | null;

  // Technician
  technician_id: string | null;
  technician_name: string | null;
  technician_code: string | null;

  // Dispatcher Override
  active_override?: ETAOverride | null;

  // Context factors and data sources
  factors: ContextFactor[];
  data_sources: DataSource[];

  // Operational realism and service range
  is_operationally_realistic?: boolean;
  route_validity?: 'VALID' | 'OUT_OF_SERVICE_AREA' | 'UNROUTEABLE' | string;
  service_range_message?: string | null;

  // Explainability
  reason: string;
  missing_context: string[];
  calculated_at: string;

  // ETA Reliability & Confidence (Phase 4G)
  confidence_level?: 'HIGH' | 'MEDIUM' | 'LOW' | 'DEGRADED' | 'UNAVAILABLE';
  confidence_reason?: string;
  reliability_status?: 'HIGH' | 'MEDIUM' | 'LOW' | 'DEGRADED' | 'UNAVAILABLE' | string;
  degraded_sources?: string[];
  fresh_sources?: string[];
  stale_sources?: string[];
  unavailable_sources?: string[];
}
