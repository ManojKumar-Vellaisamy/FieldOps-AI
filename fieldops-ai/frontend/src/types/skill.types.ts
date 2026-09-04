/**
 * TypeScript interface definitions for Skills Management DTOs and API responses.
 */

export interface Skill {
  id: string;
  skill_name: string;
  category: string;
  description?: string | null | undefined;
  status: 'ACTIVE' | 'INACTIVE';
  technician_count: number;
  created_at: string;
  updated_at: string;
}

export interface PaginatedSkillResponse {
  items: Skill[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
  total_active: number;
  total_inactive: number;
}

export interface SkillQueryParams {
  search?: string | undefined;
  category?: string | undefined;
  status?: string | undefined;
  sort_by?: string | undefined;
  sort_order?: 'asc' | 'desc' | undefined;
  page?: number | undefined;
  page_size?: number | undefined;
}

export interface SkillCreatePayload {
  skill_name: string;
  category: string;
  description?: string | undefined;
  status?: 'ACTIVE' | 'INACTIVE' | undefined;
}

export interface SkillUpdatePayload {
  skill_name?: string | undefined;
  category?: string | undefined;
  description?: string | undefined;
  status?: 'ACTIVE' | 'INACTIVE' | undefined;
}

export interface SkillTechnicianSummary {
  id: string;
  employee_code: string;
  full_name: string;
  email: string;
  years_experience: number;
  availability_status: string;
}

export interface SkillWithTechniciansResponse {
  skill: Skill;
  technicians: SkillTechnicianSummary[];
  technician_count: number;
}
