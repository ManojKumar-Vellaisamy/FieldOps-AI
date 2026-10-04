/**
 * Service for communicating with Context-Aware ETA Engine REST API endpoints.
 */

import apiClient from './api';
import type {
  ETAExperimentMetrics,
  ETAOverride,
  ETAOverrideCreate,
  ETAResponse,
} from '@/types/eta.types';

export const etaService = {
  /** Fetch context-aware ETA calculation for a field service job */
  async getJobEta(
    jobId: string,
    technicianId?: string,
    weather?: string,
    signal?: AbortSignal,
  ): Promise<ETAResponse> {
    const params: Record<string, string> = {};
    if (technicianId) params.technician_id = technicianId;
    if (weather) params.weather = weather;

    const config: { params: Record<string, string>; signal?: AbortSignal } = { params };
    if (signal) {
      config.signal = signal;
    }

    const response = await apiClient.get<ETAResponse>(`/jobs/${jobId}/eta`, config);
    return response.data;
  },

  /** Apply Dispatcher manual ETA override for a job */
  async createOverride(jobId: string, payload: ETAOverrideCreate): Promise<ETAOverride> {
    const response = await apiClient.post<ETAOverride>(`/jobs/${jobId}/override`, payload);
    return response.data;
  },

  /** Fetch override audit history for a job */
  async getOverrideHistory(jobId: string): Promise<ETAOverride[]> {
    const response = await apiClient.get<ETAOverride[]>(`/jobs/${jobId}/override-history`);
    return response.data;
  },

  /** Fetch ETA error experiment benchmark metrics (real or simulated) */
  async getExperimentMetrics(source = 'real'): Promise<ETAExperimentMetrics> {
    const response = await apiClient.get<ETAExperimentMetrics>('/eta/experiment', {
      params: { source },
    });
    return response.data;
  },

  /** Fetch recent Dispatcher manual ETA overrides across jobs */
  async getAllRecentOverrides(limit = 50): Promise<ETAOverride[]> {
    const response = await apiClient.get<ETAOverride[]>('/eta/overrides', { params: { limit } });
    return response.data;
  },

  /** Fetch live real weather from Open-Meteo via backend WeatherProvider */
  async getLiveWeather(lat: number, lon: number): Promise<{
    status: string;
    condition: string;
    temperature: string;
    temperature_c?: number;
    apparent_temperature?: string;
    apparent_temperature_c?: number;
    humidity?: string;
    humidity_percent?: number;
    wind_speed: string;
    wind_speed_kmh?: number;
    wind_direction?: string;
    wind_direction_deg?: number;
    precipitation: string;
    precipitation_mm?: number;
    precipitation_probability?: string | null;
    precipitation_probability_percent?: number | null;
    impact_minutes: number;
    description: string;
    provenance: string;
    sampled_at?: string | null;
    latitude?: number;
    longitude?: number;
  }> {
    const response = await apiClient.get('/eta/weather', { params: { lat, lon } });
    return response.data;
  },
};
