// ── API Response Types ───────────────────────────────────────────────────────

/** Standard health check response shape from GET /api/v1/health */
export interface HealthResponse {
  status: 'healthy' | 'degraded' | 'unhealthy';
  service: string;
  version: string;
}

/** Generic paginated response envelope */
export interface PaginatedResponse<T> {
  data: T[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

/** Generic single-item response envelope */
export interface ApiResponse<T> {
  data: T;
  message?: string;
}

/** Standard API error shape */
export interface ApiError {
  detail: string;
  code?: string;
  field?: string;
}

/** Pydantic validation error shape */
export interface ValidationError {
  detail: Array<{
    loc: string[];
    msg: string;
    type: string;
  }>;
}

/** Generic query params for list endpoints */
export interface PaginationParams {
  page?: number;
  page_size?: number;
  search?: string;
  sort_by?: string;
  sort_order?: 'asc' | 'desc';
}
