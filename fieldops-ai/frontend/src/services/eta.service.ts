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
  async getJobEta(jobId: string, technicianId?: string, weather?: string): Promise<ETAResponse> {
    const params: Record<string, string> = {};
    if (technicianId) params.technician_id = technicianId;
    if (weather) params.weather = weather;

    const response = await apiClient.get<ETAResponse>(`/jobs/${jobId}/eta`, { params });
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

  /** Fetch ETA error experiment benchmark metrics */
  async getExperimentMetrics(): Promise<ETAExperimentMetrics> {
    const response = await apiClient.get<ETAExperimentMetrics>('/eta/experiment');
    return response.data;
  },
};
