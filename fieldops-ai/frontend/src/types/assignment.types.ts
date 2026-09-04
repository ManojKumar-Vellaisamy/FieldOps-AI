/**
 * TypeScript interface definitions for Smart Technician Assignment module DTOs.
 */

export interface CandidateTechnician {
  technician_id: string;
  employee_code: string;
  full_name: string;
  availability_status: string;
  primary_skill_name?: string | null;
  years_experience: number;
  current_workload: number;
  is_eligible: boolean;
  ineligibility_reason?: string | null;
  distance_display: string;
  recommendation_score: number;
  ranking: number;
  explanation_reasons: string[];
}

export interface AssignmentRecommendationResponse {
  job_id: string;
  job_number: string;
  customer_name?: string | null;
  priority?: string | null;
  address?: string | null;
  scheduled_time?: string | null;
  assignment_status?: string | null;
  required_skill_name?: string | null;
  recommended_technician?: CandidateTechnician | null;
  recommendation_score?: number | null;
  ranked_candidates: CandidateTechnician[];
  alternative_technicians: CandidateTechnician[];
  explanation: string;
  generated_at: string;
}

export interface AssignmentCreatePayload {
  technician_id: string;
}

export interface AssignmentResponse {
  id: string;
  job_id: string;
  technician_id: string;
  assigned_by: string;
  assignment_type: string;
  assignment_status: string;
  assigned_at: string;
  technician_name?: string | null;
  job_number?: string | null;
}
