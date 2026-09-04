/**
 * Service for communicating with Skills REST API endpoints.
 */

import apiClient from './api';
import type {
  PaginatedSkillResponse,
  Skill,
  SkillCreatePayload,
  SkillQueryParams,
  SkillUpdatePayload,
  SkillWithTechniciansResponse,
} from '@/types/skill.types';

export const skillService = {
  /** Fetch paginated skill records with search, category, status, and sorting */
  async getSkills(params?: SkillQueryParams): Promise<PaginatedSkillResponse> {
    const response = await apiClient.get<PaginatedSkillResponse>('/skills', { params });
    return response.data;
  },

  /** Get skills for current authenticated technician */
  async getMySkills(): Promise<Skill[]> {
    const response = await apiClient.get<Skill[]>('/skills/me');
    return response.data;
  },

  /** Get single skill details by ID */
  async getSkillById(id: string): Promise<Skill> {
    const response = await apiClient.get<Skill>(`/skills/${id}`);
    return response.data;
  },

  /** Get skill details with associated qualified technicians */
  async getSkillTechnicians(id: string): Promise<SkillWithTechniciansResponse> {
    const response = await apiClient.get<SkillWithTechniciansResponse>(`/skills/${id}/technicians`);
    return response.data;
  },

  /** Create a new skill taxonomy record */
  async createSkill(payload: SkillCreatePayload): Promise<Skill> {
    const response = await apiClient.post<Skill>('/skills', payload);
    return response.data;
  },

  /** Update an existing skill record */
  async updateSkill(id: string, payload: SkillUpdatePayload): Promise<Skill> {
    const response = await apiClient.put<Skill>(`/skills/${id}`, payload);
    return response.data;
  },

  /** Patch skill active/inactive status */
  async updateSkillStatus(id: string, status: 'ACTIVE' | 'INACTIVE'): Promise<Skill> {
    const response = await apiClient.patch<Skill>(`/skills/${id}/status`, { status });
    return response.data;
  },
};
