/**
 * Service for communicating with Technician REST API endpoints.
 */

import apiClient from './api';
import type {
  PaginatedTechnicianResponse,
  Technician,
  TechnicianCreatePayload,
  TechnicianDependencyCheck,
  TechnicianQueryParams,
  TechnicianSkillsResponse,
  TechnicianUpdatePayload,
} from '@/types/technician.types';

export const technicianService = {
  /** Fetch paginated technician records with optional search, filters, and sorting */
  async getTechnicians(params?: TechnicianQueryParams): Promise<PaginatedTechnicianResponse> {
    const response = await apiClient.get<PaginatedTechnicianResponse>('/technicians', { params });
    return response.data;
  },

  /** Get single technician profile by ID */
  async getTechnicianById(id: string): Promise<Technician> {
    const response = await apiClient.get<Technician>(`/technicians/${id}`);
    return response.data;
  },

  /** Get skills associated with a technician by ID */
  async getTechnicianSkills(id: string): Promise<TechnicianSkillsResponse> {
    const response = await apiClient.get<TechnicianSkillsResponse>(`/technicians/${id}/skills`);
    return response.data;
  },

  /** Get profile of authenticated technician user */
  async getMyProfile(): Promise<Technician> {
    const response = await apiClient.get<Technician>('/technicians/me');
    return response.data;
  },

  /** Create a new technician record and user account */
  async createTechnician(payload: TechnicianCreatePayload): Promise<Technician> {
    const response = await apiClient.post<Technician>('/technicians', payload);
    return response.data;
  },

  /** Update an existing technician profile */
  async updateTechnician(id: string, payload: TechnicianUpdatePayload): Promise<Technician> {
    const response = await apiClient.put<Technician>(`/technicians/${id}`, payload);
    return response.data;
  },

  /** Patch technician availability status */
  async updateTechnicianStatus(id: string, availability_status: string): Promise<Technician> {
    const response = await apiClient.patch<Technician>(`/technicians/${id}/status`, {
      availability_status,
    });
    return response.data;
  },

  /** Activate deactivated technician */
  async activateTechnician(id: string): Promise<Technician> {
    const response = await apiClient.post<Technician>(`/technicians/${id}/activate`);
    return response.data;
  },

  /** Deactivate active technician */
  async deactivateTechnician(id: string): Promise<Technician> {
    const response = await apiClient.post<Technician>(`/technicians/${id}/deactivate`);
    return response.data;
  },

  /** Check operational dependencies before permanent deletion */
  async checkDependencies(id: string): Promise<TechnicianDependencyCheck> {
    const response = await apiClient.get<TechnicianDependencyCheck>(`/technicians/${id}/dependencies`);
    return response.data;
  },

  /** Permanently delete technician (fails if operational dependencies exist) */
  async permanentDeleteTechnician(id: string): Promise<void> {
    await apiClient.delete(`/technicians/${id}`);
  },

  /** Legacy delete alias pointing to permanent delete */
  async deleteTechnician(id: string): Promise<void> {
    await apiClient.delete(`/technicians/${id}`);
  },

  /** Update current authenticated technician live GPS location */
  async updateMyLocation(
    latitude: number,
    longitude: number,
    recordedAtIso?: string,
  ): Promise<Technician> {
    const payload: { latitude: number; longitude: number; recorded_at?: string } = {
      latitude,
      longitude,
    };
    if (recordedAtIso) {
      payload.recorded_at = recordedAtIso;
    }
    const response = await apiClient.patch<Technician>('/technicians/me/location', payload);
    return response.data;
  },
};


