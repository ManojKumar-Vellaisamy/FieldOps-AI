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
 * ETA Experiment prediction error metrics.
 */
export interface ETAExperimentMetrics {
  baseline_mae_minutes: number;
  context_aware_mae_minutes: number;
  baseline_non_routine_mae: number;
  context_aware_non_routine_mae: number;
  improvement_percent: number;
  sample_count: number;
  is_simulated_dataset: boolean;
  dataset_description: string;
  narrative_summary: string;
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
  final_dispatch_eta_minutes: number | null;
  estimated_arrival_time: string | null;

  // Distance
  distance_miles: number | null;
  distance_km: number | null;

  // Technician
  technician_id: string | null;
  technician_name: string | null;
  technician_code: string | null;

  // Dispatcher Override
  active_override?: ETAOverride | null;

  // Context factors and data sources
  factors: ContextFactor[];
  data_sources: DataSource[];

  // Explainability
  reason: string;
  missing_context: string[];
  calculated_at: string;
}
