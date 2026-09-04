import axios from 'axios';
import type { AxiosInstance, AxiosResponse, InternalAxiosRequestConfig } from 'axios';
import { env } from '@/config/env';
import { APP_CONSTANTS } from '@/config/constants';

/** Helper to retrieve stored auth token from local or session storage */
export const getStoredToken = (): string | null => {
  return localStorage.getItem('fieldops_token') || sessionStorage.getItem('fieldops_token');
};

/** Helper to clear stored auth token */
export const clearStoredToken = (): void => {
  localStorage.removeItem('fieldops_token');
  sessionStorage.removeItem('fieldops_token');
};

// ── Axios Instance ───────────────────────────────────────────────────────────
const apiClient: AxiosInstance = axios.create({
  baseURL: env.apiBaseUrl,
  timeout: APP_CONSTANTS.HTTP.TIMEOUT,
  headers: {
    'Content-Type': 'application/json',
    Accept: 'application/json',
  },
});

// ── Request Interceptor ──────────────────────────────────────────────────────
apiClient.interceptors.request.use(
  (config: InternalAxiosRequestConfig) => {
    const token = getStoredToken();
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }

    if (env.isDevelopment) {
      console.warn(`[API] ${config.method?.toUpperCase()} ${config.url}`);
    }

    return config;
  },
  (error: unknown) => Promise.reject(error),
);

// ── Response Interceptor ─────────────────────────────────────────────────────
apiClient.interceptors.response.use(
  (response: AxiosResponse) => response,
  (error: unknown) => {
    if (axios.isAxiosError(error)) {
      const status = error.response?.status;

      switch (status) {
        case 401:
          console.warn('[API] Unauthorized — clearing session token');
          clearStoredToken();
          // Dispatch global custom event for AuthContext listener
          window.dispatchEvent(new Event('fieldops:unauthorized'));
          break;
        case 403:
          console.warn('[API] Forbidden');
          break;
        case 422:
          console.warn('[API] Validation error', error.response?.data);
          break;
        case 500:
          console.error('[API] Server error', error.response?.data);
          break;
        default:
          console.error('[API] Unhandled error', status, error.message);
      }
    }

    return Promise.reject(error);
  },
);

export default apiClient;

