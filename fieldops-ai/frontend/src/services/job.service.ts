/**
 * Service for communicating with Job Management REST API endpoints.
 */

import apiClient from './api';
import type {
  Job,
  JobCreatePayload,
  JobQueryParams,
  JobUpdatePayload,
  PaginatedJobResponse,
} from '@/types/job.types';

export const jobService = {
  /** Fetch paginated job records with search, status, priority, skill, and date filters */
  async getJobs(params?: JobQueryParams): Promise<PaginatedJobResponse> {
    const response = await apiClient.get<PaginatedJobResponse>('/jobs', { params });
    return response.data;
  },

  /** Get jobs assigned to current authenticated technician */
  async getMyJobs(): Promise<Job[]> {
    const response = await apiClient.get<Job[]>('/jobs/my');
    return response.data;
  },

  /** Get single job profile details by ID */
  async getJobById(id: string): Promise<Job> {
    const response = await apiClient.get<Job>(`/jobs/${id}`);
    return response.data;
  },

  /** Create a new field service job (Dispatcher only) */
  async createJob(payload: JobCreatePayload): Promise<Job> {
    const response = await apiClient.post<Job>('/jobs', payload);
    return response.data;
  },

  /** Update an existing job record (Dispatcher only) */
  async updateJob(id: string, payload: JobUpdatePayload): Promise<Job> {
    const response = await apiClient.put<Job>(`/jobs/${id}`, payload);
    return response.data;
  },

  /** Patch job status transition */
  async updateJobStatus(id: string, status: string, completion_notes?: string): Promise<Job> {
    const response = await apiClient.patch<Job>(`/jobs/${id}/status`, { status, completion_notes });
    return response.data;
  },


  /** Cancel a job with controlled state transition and reason (Dispatcher only) */
  async cancelJob(id: string, reason: string): Promise<Job> {
    const response = await apiClient.post<Job>(`/jobs/${id}/cancel`, { reason });
    return response.data;
  },
};
