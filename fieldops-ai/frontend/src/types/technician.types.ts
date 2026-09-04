/**
 * TypeScript interface definitions for Technician Management DTOs and API states.
 */

export interface SkillSummary {
  id: string;
  skill_name: string;
  category: string;
}

export interface UserSummary {
  id: string;
  full_name: string;
  email: string;
  phone?: string | null | undefined;
  status: string;
}

export interface Technician {
  id: string;
  user_id: string;
  employee_code: string;
  primary_skill_id?: string | null | undefined;
  years_experience: number;
  availability_status: string;
  current_latitude?: number | null | undefined;
  current_longitude?: number | null | undefined;
  created_at: string;
  updated_at: string;
  user?: UserSummary | null | undefined;
  primary_skill?: SkillSummary | null | undefined;
}

export interface PaginatedTechnicianResponse {
  items: Technician[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

export interface TechnicianQueryParams {
  search?: string | undefined;
  availability_status?: string | undefined;
  skill_id?: string | undefined;
  sort_by?: string | undefined;
  sort_order?: 'asc' | 'desc' | undefined;
  page?: number | undefined;
  page_size?: number | undefined;
}

export interface TechnicianCreatePayload {
  employee_code: string;
  full_name: string;
  email: string;
  password: string;
  phone?: string | undefined;
  primary_skill_id: string;
  years_experience: number;
  availability_status?: string | undefined;
  current_latitude?: number | undefined;
  current_longitude?: number | undefined;
}

export interface TechnicianUpdatePayload {
  full_name?: string | undefined;
  email?: string | undefined;
  phone?: string | undefined;
  primary_skill_id?: string | undefined;
  years_experience?: number | undefined;
  availability_status?: string | undefined;
  current_latitude?: number | undefined;
  current_longitude?: number | undefined;
}

export interface TechnicianSkillsResponse {
  technician_id: string;
  employee_code: string;
  primary_skill?: SkillSummary | null;
  skills: SkillSummary[];
}

