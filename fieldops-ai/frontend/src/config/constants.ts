import { env } from './env';

/** Application-wide constants. Avoid magic strings throughout the codebase. */
export const APP_CONSTANTS = {
  APP_NAME: env.appName,
  APP_VERSION: env.appVersion,
  API_BASE_URL: env.apiBaseUrl,

  // ── React Query defaults ─────────────────────────────────────────────────
  QUERY: {
    STALE_TIME: 1000 * 60 * 5, // 5 minutes
    CACHE_TIME: 1000 * 60 * 10, // 10 minutes
    RETRY_COUNT: 2,
    RETRY_DELAY: 1000, // 1 second base
  },

  // ── HTTP ─────────────────────────────────────────────────────────────────
  HTTP: {
    TIMEOUT: 30_000, // 30 seconds
  },

  // ── Pagination ───────────────────────────────────────────────────────────
  PAGINATION: {
    DEFAULT_PAGE: 1,
    DEFAULT_PAGE_SIZE: 20,
    MAX_PAGE_SIZE: 100,
  },

  // ── Theme ────────────────────────────────────────────────────────────────
  THEME: {
    DEFAULT: 'light' as const,
    STORAGE_KEY: 'fieldops-theme',
  },

  // ── Sidebar ──────────────────────────────────────────────────────────────
  SIDEBAR: {
    EXPANDED_WIDTH: 256,
    COLLAPSED_WIDTH: 72,
    STORAGE_KEY: 'fieldops-sidebar-collapsed',
  },
} as const;

export type Theme = 'light' | 'dark';
