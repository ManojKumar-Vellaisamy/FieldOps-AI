import apiClient from './api';
import type { HealthResponse } from '@/types/api.types';

/**
 * Health service — checks backend API availability.
 */
export const healthService = {
  /**
   * Fetches the health status of the backend API.
   * @returns {Promise<HealthResponse>} The health check response.
   */
  check: async (): Promise<HealthResponse> => {
    const response = await apiClient.get<HealthResponse>('/health');
    return response.data;
  },
};
