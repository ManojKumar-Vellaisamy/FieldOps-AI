export interface StatusCount {
  status: string;
  count: number;
}

export interface PriorityCount {
  priority: string;
  count: number;
}

export interface DailyVolume {
  date: string;
  count: number;
}

export interface OperationalAnalytics {
  total_jobs: number;
  active_jobs: number;
  unassigned_jobs: number;
  in_progress_jobs: number;
  completed_jobs: number;
  cancelled_jobs: number;
  status_distribution: StatusCount[];
  priority_distribution: PriorityCount[];
  completion_rate_percentage: number | null;
  cancellation_rate_percentage: number | null;
  total_technicians: number;
  active_technicians: number;
  available_technicians: number;
  technicians_with_gps: number;
  technician_utilization_percentage: number | null;
  recent_jobs_volume_7d: DailyVolume[];
}
