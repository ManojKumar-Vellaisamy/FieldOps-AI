import apiClient from './api';
import type { OperationalAnalytics } from '@/types/analytics.types';

export const analyticsService = {
  /** Fetch real operational analytics KPIs from PostgreSQL */
  async getOperationalAnalytics(): Promise<OperationalAnalytics> {
    const response = await apiClient.get<OperationalAnalytics>('/analytics/operational');
    return response.data;
  },
};
