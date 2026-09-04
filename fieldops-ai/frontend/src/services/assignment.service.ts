/**
 * Service for communicating with Smart Technician Assignment REST API endpoints.
 */

import apiClient from './api';
import type {
  AssignmentRecommendationResponse,
  AssignmentResponse,
  CandidateTechnician,
} from '@/types/assignment.types';

export const assignmentService = {
  /** Fetch evaluated candidate technicians list for a job (Dispatcher only) */
  async getCandidates(jobId: string): Promise<CandidateTechnician[]> {
    const response = await apiClient.get<CandidateTechnician[]>(`/jobs/${jobId}/candidates`);
    return response.data;
  },

  /** Fetch deterministic Smart Assignment recommendation for a job (Dispatcher only) */
  async getRecommendation(jobId: string): Promise<AssignmentRecommendationResponse> {
    const response = await apiClient.get<AssignmentRecommendationResponse>(`/jobs/${jobId}/assignment-recommendations`);
    return response.data;
  },

  /** Alias: Fetch Smart Assignment recommendations */
  async getAssignmentRecommendations(jobId: string): Promise<AssignmentRecommendationResponse> {
    const response = await apiClient.get<AssignmentRecommendationResponse>(`/jobs/${jobId}/assignment-recommendations`);
    return response.data;
  },

  /** Confirm technician assignment for a job (Dispatcher only) */
  async confirmAssignment(jobId: string, technicianId: string): Promise<AssignmentResponse> {
    const response = await apiClient.post<AssignmentResponse>(`/jobs/${jobId}/assign-technician`, {
      technician_id: technicianId,
    });
    return response.data;
  },

  /** Alias: Assign technician to job */
  async assignTechnician(jobId: string, technicianId: string): Promise<AssignmentResponse> {
    const response = await apiClient.post<AssignmentResponse>(`/jobs/${jobId}/assign-technician`, {
      technician_id: technicianId,
    });
    return response.data;
  },

  /** Unassign technician from a job, reverting state to NEW (Dispatcher only) */
  async unassignJob(jobId: string): Promise<{ message: string; job_id: string; job_number: string; status: string }> {
    const response = await apiClient.post<{ message: string; job_id: string; job_number: string; status: string }>(
      `/jobs/${jobId}/unassign-technician`
    );
    return response.data;
  },
};
