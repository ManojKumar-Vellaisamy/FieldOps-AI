import apiClient from './api';

export interface SystemSettings {
  jwt_expiration_hours: number;
  max_concurrent_sessions: number;
  weather_refresh_interval_minutes: number;
  traffic_provider_mode: string;
  baseline_eta_speed_mph: number;
  weather_delay_weight: number;
  audit_log_retention_days: number;
  auto_unassign_on_tech_inactive: boolean;
  id?: string;
  updated_at?: string;
  updated_by?: string;
}

/**
 * System Settings Service managing platform configuration API endpoints.
 */
export const settingsService = {
  /** Fetch current platform settings */
  getSettings: async (): Promise<SystemSettings> => {
    const response = await apiClient.get<SystemSettings>('/settings');
    return response.data;
  },

  /** Update platform settings */
  updateSettings: async (payload: SystemSettings): Promise<SystemSettings> => {
    const response = await apiClient.put<SystemSettings>('/settings', payload);
    return response.data;
  },

  /** Reset settings to factory defaults */
  resetSettings: async (): Promise<SystemSettings> => {
    const response = await apiClient.post<SystemSettings>('/settings/reset');
    return response.data;
  },
};
