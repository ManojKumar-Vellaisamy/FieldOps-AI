/**
TypeScript definitions for Dispatcher Dashboard components and metrics.
*/

export type TrendDirection = 'increase' | 'decrease' | 'neutral';

export interface KPIStat {
  id: string;
  title: string;
  value: string | number;
  change: string;
  trend: TrendDirection;
  subtitle: string;
  iconName: 'Briefcase' | 'Users' | 'Clock' | 'AlertCircle' | 'Cpu' | 'Gauge';
}

export type JobPriority = 'High' | 'Medium' | 'Low';
export type JobStatus = 'Assigned' | 'In Progress' | 'Pending' | 'Completed';

export interface JobItem {
  id: string;
  customer: string;
  location: string;
  skill: string;
  priority: JobPriority;
  status: JobStatus;
  technician: string;
  eta: string;
  createdAt: string;
}

export type ActivityType =
  | 'create'
  | 'assign'
  | 'availability'
  | 'override'
  | 'recommendation'
  | 'dispatcher'
  | 'technician'
  | 'warning'
  | 'system';

export interface ActivityItem {
  id: string;
  type: ActivityType;
  title: string;
  description: string;
  timestamp: string;
  actor: string;
}

export interface Recommendation {
  id: string;
  jobId: string;
  jobTitle: string;
  technicianName: string;
  technicianAvatar?: string;
  skillMatch: string;
  reason: string;
  estimatedEta: string;
  confidenceScore: 'High Confidence' | 'Medium Confidence' | 'Low Confidence' | string;
  decisionFactors?: string[];
}

export interface WeatherData {
  condition: string;
  temperature: string;
  location: string;
  impact: string;
  etaImpact?: string;
  impactSeverity: 'low' | 'moderate' | 'high';
  windSpeed: string;
  humidity: string;
}
