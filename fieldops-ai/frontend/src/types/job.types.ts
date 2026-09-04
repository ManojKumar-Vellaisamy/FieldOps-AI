/**
 * TypeScript interface definitions for Job Management DTOs and API responses.
 */

import type { Skill } from './skill.types';

export type JobStatus =
  | 'NEW'
  | 'ASSIGNED'
  | 'TRAVELLING'
  | 'ARRIVED'
  | 'WORKING'
  | 'COMPLETED'
  | 'CANCELLED';

export type Priority = 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL';

export interface JobCreatorSummary {
  id: string;
  full_name: string;
  email: string;
}

export interface JobAssignedTechnicianSummary {
  id: string;
  employee_code: string;
  full_name: string;
}

export interface Job {
  id: string;
  job_number: string;
  customer_name: string;
  customer_phone?: string | null | undefined;
  address: string;
  latitude?: number | null | undefined;
  longitude?: number | null | undefined;
  required_skill_id?: string | null | undefined;
  required_skill?: Skill | null | undefined;
  priority: Priority;
  status: JobStatus;
  scheduled_time?: string | null | undefined;
  description?: string | null | undefined;
  service_instructions?: string | null | undefined;
  created_by?: string | null | undefined;
  creator?: JobCreatorSummary | null | undefined;
  assigned_technician?: JobAssignedTechnicianSummary | null | undefined;
  created_at: string;
  updated_at: string;
}

export interface PaginatedJobResponse {
  items: Job[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

export interface JobQueryParams {
  search?: string | undefined;
  status?: string | undefined;
  priority?: string | undefined;
  required_skill_id?: string | undefined;
  scheduled_date?: string | undefined;
  assignment_status?: string | undefined;
  sort_by?: string | undefined;
  sort_order?: 'asc' | 'desc' | undefined;
  page?: number | undefined;
  page_size?: number | undefined;
}

export interface JobCreatePayload {
  customer_name: string;
  customer_phone?: string | undefined;
  address: string;
  latitude: number;
  longitude: number;
  required_skill_id: string;
  priority?: Priority | undefined;
  scheduled_time?: string | undefined;
  description?: string | undefined;
  service_instructions?: string | undefined;
}

export interface JobUpdatePayload {
  customer_name?: string | undefined;
  customer_phone?: string | undefined;
  address?: string | undefined;
  latitude?: number | undefined;
  longitude?: number | undefined;
  required_skill_id?: string | undefined;
  priority?: Priority | undefined;
  scheduled_time?: string | undefined;
  description?: string | undefined;
  service_instructions?: string | undefined;
}


export interface JobCancelPayload {
  reason: string;
}
