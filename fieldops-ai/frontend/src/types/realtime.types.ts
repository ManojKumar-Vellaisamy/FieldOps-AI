import type { ETAResponse } from './eta.types';

/**
 * FieldOps AI Real-Time Operational Event Types.
 */

export type RealtimeConnectionStatus = 'CONNECTING' | 'CONNECTED' | 'DISCONNECTED' | 'RECONNECTING';

export type GeolocationFreshness = 'LIVE' | 'STALE' | 'UNAVAILABLE';

export type OperationalEventType =
  | 'CONNECTED'
  | 'JOB_ASSIGNED'
  | 'JOB_UNASSIGNED'
  | 'JOB_STATUS_CHANGED'
  | 'JOB_COMPLETED'
  | 'JOB_CANCELLED'
  | 'TECHNICIAN_LOCATION_UPDATED'
  | 'TECHNICIAN_AVAILABILITY_CHANGED'
  | 'ETA_UPDATED'
  | 'DISPATCH_PLAN_CHANGED';

export interface JobAssignedEventData {
  assignment_id: string;
  job_id: string;
  job_number: string;
  customer_name: string;
  address: string;
  priority: string;
  status: string;
  technician_id: string;
  technician_name: string;
  technician_user_id?: string | null;
  assigned_at?: string | null;
}

export interface JobUnassignedEventData {
  job_id: string;
  job_number: string;
  status: string;
  unassigned_at?: string | null;
}

export interface JobStatusChangedEventData {
  job_id: string;
  job_number: string;
  customer_name: string;
  old_status: string;
  new_status: string;
  priority: string;
  updated_at?: string | null;
}

export interface JobCancelledEventData {
  job_id: string;
  job_number: string;
  customer_name: string;
  status: string;
  cancellation_reason: string;
  cancelled_at?: string | null;
}

export interface TechnicianLocationUpdatedEventData {
  technician_id: string;
  user_id: string;
  employee_code: string;
  full_name: string;
  latitude: number;
  longitude: number;
  updated_at?: string | null;
}

export interface TechnicianAvailabilityChangedEventData {
  technician_id: string;
  user_id: string;
  employee_code: string;
  full_name: string;
  old_status: string;
  new_status: string;
  updated_at?: string | null;
}

export interface ETAUpdatedEventData extends Partial<ETAResponse> {
  job_id: string;
  technician_id?: string | null;
  dispatcher_name?: string;
  overridden_eta?: number;
  original_system_eta?: number | null;
  reason?: string;
  updated_at?: string | null;
}

export interface DispatchPlanChangedEventData {
  action: 'JOB_CREATED' | 'JOB_UPDATED';
  job_id: string;
  job_number: string;
  customer_name: string;
  priority: string;
  status: string;
}

export interface RealtimeEvent<T = any> {
  event: OperationalEventType;
  timestamp: string;
  data: T;
}

export type RealtimeEventHandler<T = any> = (event: RealtimeEvent<T>) => void;
