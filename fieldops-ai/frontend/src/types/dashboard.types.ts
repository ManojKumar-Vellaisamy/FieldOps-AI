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
  temperature_c?: number | null | undefined;
  apparentTemperature?: string | undefined;
  apparentTemperature_c?: number | null | undefined;
  location: string;
  latitude?: number | null | undefined;
  longitude?: number | null | undefined;
  impact: string;
  etaImpact?: string | undefined;
  impactSeverity: 'low' | 'moderate' | 'high';
  windSpeed: string;
  windSpeed_kmh?: number | null | undefined;
  windDirection?: string | undefined;
  windDirectionDeg?: number | null | undefined;
  humidity: string;
  humidityPercent?: number | null | undefined;
  precipitation: string;
  precipitation_mm?: number | null | undefined;
  precipitationProbability?: string | null | undefined;
  precipitationProbabilityPercent?: number | null | undefined;
  observedAt?: string | null | undefined;
  provenance?: string | undefined;
}
