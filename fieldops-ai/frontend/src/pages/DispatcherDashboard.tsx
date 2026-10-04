import { useState, useEffect } from 'react';
import { Sparkles, Shield, Briefcase, Plus, RefreshCw, Eye } from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '@/contexts/AuthContext';
import { ContextAwareETAPanel } from '@/components/dashboard/ContextAwareETAPanel';
import { SmartAssignmentSection } from '@/components/dashboard/SmartAssignmentSection';
import { JobETABadge } from '@/components/dashboard/JobETABadge';
import { WeatherWidget } from '@/components/dashboard/WeatherWidget';
import { ActivityTimeline } from '@/components/dashboard/ActivityTimeline';
import apiClient from '@/services/api';
import { jobService } from '@/services/job.service';
import { etaService } from '@/services/eta.service';
import { assignmentService } from '@/services/assignment.service';
import type { Job } from '@/types/job.types';
import type { ETAResponse } from '@/types/eta.types';
import type { ActivityItem, ActivityType } from '@/types/dashboard.types';
import { cn } from '@/utils/cn';
import { RealtimeConnectionBadge } from '@/components/common/RealtimeConnectionBadge';
import { useRealtimeSync } from '@/hooks/useRealtimeSync';

function formatRelativeTime(dateString?: string): string {
  if (!dateString) return 'Just now';
  const date = new Date(dateString);
  if (isNaN(date.getTime())) return 'Recently';
  const now = new Date();
  const diffSec = Math.floor((now.getTime() - date.getTime()) / 1000);

  if (diffSec < 45) return 'Just now';
  const diffMin = Math.floor(diffSec / 60);
  if (diffMin < 60) return `${diffMin}m ago`;
  const diffHour = Math.floor(diffMin / 60);
  if (diffHour < 24) return `${diffHour}h ago`;
  const diffDay = Math.floor(diffHour / 24);
  if (diffDay < 30) return `${diffDay}d ago`;
  return date.toLocaleDateString();
}

function getAdjustmentSourceLabel(eta: ETAResponse): string {
  // 1. Inspect data sources contributing positive delay
  const activeSources = (eta.data_sources || []).filter(
    (ds) => (ds.impact_minutes || 0) > 0 && ds.status === 'AVAILABLE',
  );

  const firstSource = activeSources[0];
  if (activeSources.length === 1 && firstSource) {
    const cat = (firstSource.category || firstSource.name || '').toUpperCase();
    if (cat.includes('TRAFFIC')) return 'traffic';
    if (cat.includes('WEATHER')) return 'weather';
    if (cat.includes('EVENT')) return 'events';
    if (cat.includes('ROAD') || cat.includes('RESTRICTION')) return 'road restrictions';
    return 'context';
  }

  if (activeSources.length > 1) {
    return 'context';
  }

  // 2. Inspect factors contributing positive delay
  if (eta.factors && eta.factors.length > 0) {
    const activeFactors = eta.factors.filter(
      (f) => (f.impact_minutes || 0) > 0 && f.category !== 'TRAVEL' && f.category !== 'GPS',
    );
    const firstFactor = activeFactors[0];
    if (activeFactors.length === 1 && firstFactor) {
      const cat = (firstFactor.category || '').toUpperCase();
      if (cat === 'TRAFFIC') return 'traffic';
      if (cat === 'WEATHER') return 'weather';
      if (cat === 'EVENTS' || cat === 'EVENT') return 'events';
      if (cat === 'ROAD' || cat === 'RESTRICTIONS') return 'road restrictions';
      return 'context';
    }
    if (activeFactors.length > 1) {
      return 'context';
    }
  }

  // 3. Fallback: inspect reason text for single distinct context factor
  const reasonUpper = (eta.reason || '').toUpperCase();
  const hasTraffic = reasonUpper.includes('TRAFFIC') || reasonUpper.includes('CONGESTION');
  const hasWeather = reasonUpper.includes('WEATHER') || reasonUpper.includes('RAIN');
  const hasEvents = reasonUpper.includes('EVENT');
  const hasRoad = reasonUpper.includes('ROAD') || reasonUpper.includes('RESTRICTION');

  const matchCount = [hasTraffic, hasWeather, hasEvents, hasRoad].filter(Boolean).length;
  if (matchCount === 1) {
    if (hasTraffic) return 'traffic';
    if (hasWeather) return 'weather';
    if (hasEvents) return 'events';
    if (hasRoad) return 'road restrictions';
  }

  return 'context';
}

export default function DispatcherDashboard() {
  const { user } = useAuth();
  const navigate = useNavigate();
  const [jobs, setJobs] = useState<Job[]>([]);
  const [totalJobs, setTotalJobs] = useState<number>(0);
  const [totalUnassigned, setTotalUnassigned] = useState<number>(0);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [selectedJobModal, setSelectedJobModal] = useState<Job | null>(null);
  const [topEtaData, setTopEtaData] = useState<ETAResponse | null>(null);
  const [isEtaLoading, setIsEtaLoading] = useState<boolean>(false);
  const [topMatchScore, setTopMatchScore] = useState<number | null>(null);
  const [topMatchCandidateName, setTopMatchCandidateName] = useState<string | null>(null);


  const [activities, setActivities] = useState<ActivityItem[]>([]);
  const [isActivitiesLoading, setIsActivitiesLoading] = useState<boolean>(true);
  const [activitiesError, setActivitiesError] = useState<string | null>(null);

  const fetchRecentActivities = async () => {
    setIsActivitiesLoading(true);
    setActivitiesError(null);
    try {
      const res = await apiClient.get('/audit-logs?page_size=10');
      if (res.data && Array.isArray(res.data.items)) {
        const mapped: ActivityItem[] = res.data.items.map((log: {
          id?: string;
          created_at?: string;
          user_full_name?: string | null;
          action?: string;
          entity?: string;
          entity_id?: string | null;
          reason?: string | null;
        }) => {
          const action = log.action || 'OPERATIONAL_EVENT';
          const actionUpper = action.toUpperCase();

          let type: ActivityType = 'system';
          if (actionUpper.includes('RECOMMENDATION')) {
            type = 'recommendation';
          } else if (actionUpper.includes('ASSIGN')) {
            type = 'assign';
          } else if (actionUpper.includes('OVERRIDE')) {
            type = 'override';
          } else if (actionUpper.includes('CREATE')) {
            type = 'create';
          } else if (actionUpper.includes('AVAILABILITY')) {
            type = 'availability';
          } else if (actionUpper.includes('CANCEL') || actionUpper.includes('FAIL') || actionUpper.includes('WARN')) {
            type = 'warning';
          } else if (actionUpper.includes('TECHNICIAN') || actionUpper.includes('LOCATION') || actionUpper.includes('STATUS')) {
            type = 'technician';
          } else if (actionUpper.includes('JOB') || actionUpper.includes('DISPATCH')) {
            type = 'dispatcher';
          }

          const title = action
            .split('_')
            .map((w) => w.charAt(0).toUpperCase() + w.slice(1).toLowerCase())
            .join(' ');

          const description =
            log.reason ||
            (log.entity
              ? `${action.replace(/_/g, ' ')} on ${log.entity}${log.entity_id ? ` (#${log.entity_id.slice(0, 8)})` : ''}`
              : action.replace(/_/g, ' '));

          return {
            id: log.id ? String(log.id) : `act-${Math.random().toString(36).slice(2, 7)}`,
            type,
            title,
            description,
            timestamp: formatRelativeTime(log.created_at),
            actor: log.user_full_name || 'System / Automated',
          };
        });
        setActivities(mapped);
      } else {
        setActivities([]);
      }
    } catch (err) {
      console.error('Failed to load recent activities telemetry', err);
      setActivitiesError('Activity unavailable');
      setActivities([]);
    } finally {
      setIsActivitiesLoading(false);
    }
  };

  const loadDashboardData = async () => {
    setIsLoading(true);
    fetchRecentActivities();
    try {
      const [res, unassignedRes] = await Promise.all([
        jobService.getJobs({ page_size: 10 }),
        jobService.getJobs({ status: 'NEW', page_size: 1 }).catch(() => ({ total: 0 })),
      ]);
      setJobs(res.items);
      setTotalJobs(res.total);
      setTotalUnassigned(unassignedRes.total);

      // 1. Evaluate top KPI ETA from first active/assigned operational job
      const activeJob = res.items.find(
        (j) => j.status !== 'COMPLETED' && j.status !== 'CANCELLED' && j.status !== 'NEW',
      ) || res.items[0];

      if (activeJob) {
        setIsEtaLoading(true);
        try {
          const eta = await etaService.getJobEta(activeJob.id);
          setTopEtaData(eta);
        } catch (err) {
          console.error('Failed to load top ETA telemetry', err);
          setTopEtaData(null);
        } finally {
          setIsEtaLoading(false);
        }
      } else {
        setTopEtaData(null);
      }

      // 2. Evaluate top AI Match Score from first unassigned job
      const newJob = res.items.find((j) => j.status === 'NEW');
      if (newJob) {
        try {
          const rec = await assignmentService.getAssignmentRecommendations(newJob.id);
          if (rec.recommended_technician) {
            setTopMatchScore(Math.round(rec.recommended_technician.recommendation_score));
            setTopMatchCandidateName(rec.recommended_technician.full_name);
          } else {
            setTopMatchScore(null);
            setTopMatchCandidateName(null);
          }
        } catch {
          setTopMatchScore(null);
          setTopMatchCandidateName(null);
        }
      } else {
        setTopMatchScore(null);
        setTopMatchCandidateName(null);
      }
    } catch (err) {
      console.error('Failed to load dashboard jobs', err);
    } finally {
      setIsLoading(false);
    }
  };

  // Subscribe to real-time events and resync
  useRealtimeSync(
    [
      'JOB_ASSIGNED',
      'JOB_UNASSIGNED',
      'JOB_STATUS_CHANGED',
      'JOB_COMPLETED',
      'JOB_CANCELLED',
      'DISPATCH_PLAN_CHANGED',
      'TECHNICIAN_AVAILABILITY_CHANGED',
    ],
    () => {
      loadDashboardData();
    },
    loadDashboardData,
  );

  useEffect(() => {
    loadDashboardData();
    // Background polling relaxed to 60s as a fallback safety net for WebSocket
    const interval = setInterval(() => {
      loadDashboardData();
    }, 60000);
    return () => clearInterval(interval);
  }, []);

  const unassignedJobs = jobs.filter((j) => j.status === 'NEW');

  return (
    <div className="flex flex-col gap-6 py-2 animate-fade-in select-none">
      {/* ── Dashboard Header ── */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-slate-200 pb-5">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <span className="inline-flex items-center gap-1 rounded-full border border-blue-200 bg-blue-50 px-2.5 py-0.5 text-[11px] font-bold text-blue-700">
              <Sparkles className="h-3 w-3 text-blue-600" />
              <span>Dispatch Control Center</span>
            </span>
            <span className="inline-flex items-center gap-1 rounded-full border border-slate-200 bg-slate-100 px-2.5 py-0.5 text-[11px] font-bold text-slate-700">
              <Shield className="h-3 w-3 text-purple-600" />
              <span>{user?.role || 'Dispatcher'}</span>
            </span>
            <RealtimeConnectionBadge />
          </div>

          <h1 className="text-2xl md:text-3xl font-extrabold tracking-tight text-slate-900">
            Dispatch Control Center
          </h1>
          <p className="text-xs md:text-sm text-slate-500 mt-0.5 font-medium">
            Smart technician matching, real-time context ETA prediction, and work order dispatching.
          </p>
        </div>

        <div className="flex items-center gap-2.5">
          <button
            onClick={() => navigate('/jobs')}
            className="flex items-center gap-2 rounded-xl bg-blue-600 px-4 py-2 text-xs font-bold text-white shadow-xs transition-all hover:bg-blue-700 active:scale-[0.98]"
          >
            <Plus className="h-4 w-4" />
            <span>Create Job</span>
          </button>
          <button
            onClick={loadDashboardData}
            title="Refresh Dashboard"
            className="flex items-center gap-1.5 rounded-xl border border-slate-200 bg-white px-3 py-2 text-xs font-bold text-slate-700 hover:bg-slate-50 transition-colors shadow-2xs"
          >
            <RefreshCw className={cn('h-3.5 w-3.5', (isLoading || isEtaLoading) && 'animate-spin')} />
            <span>Refresh</span>
          </button>
        </div>
      </div>

      {/* ── Dispatcher Operational Workflow Banner (Requirement 7) ── */}
      <div className="rounded-xl border border-blue-200 bg-gradient-to-r from-blue-50/80 via-indigo-50/50 to-purple-50/60 p-4 shadow-xs">
        <div className="text-[10px] font-extrabold uppercase tracking-wider text-blue-700 mb-2.5 flex items-center gap-1.5">
          <Sparkles className="h-3.5 w-3.5 text-blue-600" />
          <span>Dispatcher Operational Workflow</span>
        </div>
        <div className="flex flex-wrap items-center gap-2 text-xs font-bold text-slate-800">
          <span className="rounded-lg bg-white border border-slate-200 px-3 py-1.5 shadow-2xs flex items-center gap-1.5">
            <span className="h-5 w-5 rounded-full bg-blue-100 text-blue-700 text-[10px] font-black flex items-center justify-center">1</span>
            <span>Job</span>
          </span>
          <span className="text-slate-400 font-black">→</span>

          <span className="rounded-lg bg-white border border-slate-200 px-3 py-1.5 shadow-2xs flex items-center gap-1.5">
            <span className="h-5 w-5 rounded-full bg-purple-100 text-purple-700 text-[10px] font-black flex items-center justify-center">2</span>
            <span>Required Skill</span>
          </span>
          <span className="text-slate-400 font-black">→</span>

          <span className="rounded-lg bg-white border border-slate-200 px-3 py-1.5 shadow-2xs flex items-center gap-1.5">
            <span className="h-5 w-5 rounded-full bg-purple-100 text-purple-700 text-[10px] font-black flex items-center justify-center">3</span>
            <span>Recommended Tech</span>
          </span>
          <span className="text-slate-400 font-black">→</span>

          <span className="rounded-lg bg-white border border-slate-200 px-3 py-1.5 shadow-2xs flex items-center gap-1.5">
            <span className="h-5 w-5 rounded-full bg-purple-100 text-purple-700 text-[10px] font-black flex items-center justify-center">4</span>
            <span>Match Score</span>
          </span>
          <span className="text-slate-400 font-black">→</span>

          <span className="rounded-lg bg-white border border-slate-200 px-3 py-1.5 shadow-2xs flex items-center gap-1.5">
            <span className="h-5 w-5 rounded-full bg-blue-100 text-blue-700 text-[10px] font-black flex items-center justify-center">5</span>
            <span>Assign Tech</span>
          </span>
          <span className="text-slate-400 font-black">→</span>

          <span className="rounded-lg bg-white border border-slate-200 px-3 py-1.5 shadow-2xs flex items-center gap-1.5">
            <span className="h-5 w-5 rounded-full bg-blue-100 text-blue-700 text-[10px] font-black flex items-center justify-center">6</span>
            <span>Context-Aware ETA</span>
          </span>
          <span className="text-slate-400 font-black">→</span>

          <span className="rounded-lg bg-white border border-slate-200 px-3 py-1.5 shadow-2xs flex items-center gap-1.5">
            <span className="h-5 w-5 rounded-full bg-emerald-100 text-emerald-700 text-[10px] font-black flex items-center justify-center">7</span>
            <span>Job Monitoring</span>
          </span>
        </div>
      </div>

      {/* ── Top Real KPI Cards ── */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {/* Real Job Count */}
        <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-xs">
          <div className="flex items-center justify-between">
            <span className="text-xs font-bold uppercase tracking-wider text-slate-500">Total Service Jobs</span>
            <Briefcase className="h-5 w-5 text-blue-600" />
          </div>
          <div className="mt-3 text-3xl font-black text-slate-900 font-mono">{totalJobs}</div>
          <div className="mt-1 text-[11px] text-slate-500 font-medium">Real PostgreSQL work orders</div>
        </div>

        {/* Pending Assignments */}
        <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-xs">
          <div className="flex items-center justify-between">
            <span className="text-xs font-bold uppercase tracking-wider text-slate-500">New / Unassigned</span>
            <span className="rounded-full bg-purple-50 border border-purple-200 px-2 py-0.5 text-[10px] font-extrabold text-purple-700">
              NEW
            </span>
          </div>
          <div className="mt-3 text-3xl font-black text-purple-700 font-mono">
            {totalUnassigned}
          </div>
          <div className="mt-1 text-[11px] text-slate-500 font-medium">Awaiting technician assignment</div>
        </div>

        {/* Real Live Context-Aware ETA KPI */}
        <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-xs">
          <div className="flex items-center justify-between">
            <span className="text-xs font-bold uppercase tracking-wider text-slate-500">Context-Aware ETA</span>
            <span className="rounded-full bg-blue-50 border border-blue-200 px-2 py-0.5 text-[10px] font-mono font-bold text-blue-700">
              Module 8
            </span>
          </div>
          {isEtaLoading ? (
            <div className="mt-3 text-sm text-slate-400 animate-pulse font-medium">Calculating ETA...</div>
          ) : topEtaData && topEtaData.is_context_sufficient && topEtaData.context_aware_eta_minutes !== null ? (
            <div>
              <div className="mt-2 flex items-baseline gap-2">
                <span className="text-3xl font-black text-blue-700 font-mono">
                  {topEtaData.context_aware_eta_minutes} <span className="text-xs text-slate-500 font-normal">min</span>
                </span>
                {(topEtaData.adjustment_minutes || 0) > 0 && (
                  <span className="rounded bg-amber-50 border border-amber-200 px-1.5 py-0.5 text-[10px] font-mono font-bold text-amber-800">
                    +{topEtaData.adjustment_minutes}m {getAdjustmentSourceLabel(topEtaData)}
                  </span>
                )}
              </div>
              <div className="mt-1 text-[11px] text-slate-500 font-medium truncate" title={topEtaData.reason}>
                Baseline: {topEtaData.baseline_eta_minutes}m • {topEtaData.reason}
              </div>
            </div>
          ) : (
            <div>
              <div className="mt-3 text-sm font-bold text-slate-700 italic">
                {topEtaData ? 'ETA unavailable' : 'Awaiting active dispatch'}
              </div>
              <div className="mt-1 text-[11px] text-slate-400 truncate font-medium">
                {topEtaData?.reason || 'Assign a technician to compute transit route'}
              </div>
            </div>
          )}
        </div>

        {/* Real Smart Assignment Match Score KPI */}
        <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-xs">
          <div className="flex items-center justify-between">
            <span className="text-xs font-bold uppercase tracking-wider text-slate-500">Technician Match Score</span>
            <span className="rounded-full bg-purple-50 border border-purple-200 px-2 py-0.5 text-[10px] font-mono font-bold text-purple-700">
              Module 9
            </span>
          </div>
          {topMatchScore !== null ? (
            <div>
              <div className="mt-2 text-3xl font-black text-purple-700 font-mono">
                {topMatchScore}%
              </div>
              <div className="mt-1 text-[11px] text-slate-500 font-medium truncate">
                {topMatchCandidateName ? `${topMatchCandidateName} • Top Match` : 'Candidate evaluated'}
              </div>
            </div>
          ) : totalJobs === 0 ? (
            <div>
              <div className="mt-2 text-2xl font-black text-slate-400 font-mono">
                --
              </div>
              <div className="mt-1 text-[11px] text-slate-500 font-medium">No service jobs to dispatch</div>
            </div>
          ) : unassignedJobs.length === 0 ? (
            <div>
              <div className="mt-2 text-2xl font-black text-emerald-700 font-mono">
                100%
              </div>
              <div className="mt-1 text-[11px] text-slate-500 font-medium">All work orders dispatched</div>
            </div>
          ) : (
            <div>
              <div className="mt-3 text-sm font-bold text-slate-700 italic">No candidates available</div>
              <div className="mt-1 text-[11px] text-slate-400 font-medium">Skill certification required</div>
            </div>
          )}
        </div>
      </div>

      {/* ── Main Dashboard Workspace Grid ── */}
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        {/* Left 2 Columns: Smart Assignment Section, Context ETA Panel, Weather & Real Jobs Table */}
        <div className="lg:col-span-2 flex flex-col gap-6">
          {/* Module 9: Professional Smart Technician Assignment Engine */}
          <SmartAssignmentSection
            unassignedJobs={unassignedJobs}
            totalJobs={totalJobs}
            onAssignmentComplete={loadDashboardData}
          />

          {/* Module 8: Professional Context-Aware ETA Engine Section */}
          <ContextAwareETAPanel jobs={jobs} selectedJobId={selectedJobModal?.id} />

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <WeatherWidget />
          </div>

          {/* Real Jobs Table */}
          <div className="rounded-xl border border-slate-200 bg-white shadow-xs overflow-hidden select-none">
            <div className="flex items-center justify-between p-4 border-b border-slate-100">
              <div>
                <h3 className="text-base font-bold text-slate-900 tracking-tight">Recent Service Jobs</h3>
                <p className="text-xs text-slate-500 mt-0.5">Real PostgreSQL jobs database records</p>
              </div>
              <button
                onClick={() => navigate('/jobs')}
                className="text-xs font-bold text-blue-600 hover:underline"
              >
                View All Jobs →
              </button>
            </div>

            <div className="overflow-x-auto scrollbar-thin">
              <table className="w-full text-left text-xs">
                <thead className="bg-slate-50 text-slate-500 border-b border-slate-200 font-bold uppercase tracking-wider text-[10px]">
                  <tr>
                    <th className="py-3 px-4">Job #</th>
                    <th className="py-3 px-4">Customer</th>
                    <th className="py-3 px-4">Required Skill</th>
                    <th className="py-3 px-4">Priority</th>
                    <th className="py-3 px-4">Status</th>
                    <th className="py-3 px-4">ETA (Context)</th>
                    <th className="py-3 px-4 text-right">Action</th>
                  </tr>
                </thead>

                <tbody className="divide-y divide-slate-100 text-slate-700">
                  {isLoading ? (
                    <tr>
                      <td colSpan={7} className="py-8 text-center text-slate-500 font-medium">
                        Loading real job records...
                      </td>
                    </tr>
                  ) : jobs.length === 0 ? (
                    <tr>
                      <td colSpan={7} className="py-8 text-center text-slate-500 font-medium">
                        No service jobs created yet. Click "+ Create Job" above.
                      </td>
                    </tr>
                  ) : (
                    jobs.map((job) => (
                      <tr key={job.id} className="hover:bg-slate-50/80 transition-colors">
                        <td className="py-3 px-4 font-mono font-bold text-blue-600">{job.job_number}</td>
                        <td className="py-3 px-4">
                          <div className="font-bold text-slate-900">{job.customer_name}</div>
                          <div className="text-[10px] text-slate-500 truncate max-w-xs">{job.address}</div>
                        </td>
                        <td className="py-3 px-4">
                          <span className="rounded-md bg-purple-50 px-2 py-0.5 text-[11px] font-bold text-purple-700 border border-purple-200">
                            {job.required_skill ? job.required_skill.skill_name : 'N/A'}
                          </span>
                        </td>
                        <td className="py-3 px-4">
                          <span className="rounded-md bg-amber-50 px-2 py-0.5 text-[10px] font-bold text-amber-800 border border-amber-200">
                            {job.priority}
                          </span>
                        </td>
                        <td className="py-3 px-4">
                          <span className="rounded-full bg-blue-50 px-2.5 py-0.5 text-[10px] font-bold text-blue-700 border border-blue-200">
                            {job.status}
                          </span>
                        </td>
                        <td className="py-3 px-4">
                          <JobETABadge jobId={job.id} onClick={() => setSelectedJobModal(job)} />
                        </td>
                        <td className="py-3 px-4 text-right">
                          <button
                            onClick={() => setSelectedJobModal(job)}
                            className="p-1 rounded text-slate-400 hover:text-slate-900 hover:bg-slate-100 transition-colors"
                          >
                            <Eye className="h-3.5 w-3.5" />
                          </button>
                        </td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>
          </div>
        </div>

        {/* Right Col: Audit & Activity Timeline */}
        <div className="lg:col-span-1 flex flex-col gap-6">
          <ActivityTimeline
            activities={activities}
            isLoading={isActivitiesLoading}
            error={activitiesError}
          />
        </div>
      </div>

      {/* ── View Job Preview Modal ── */}
      {selectedJobModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/40 backdrop-blur-xs p-4 animate-fade-in">
          <div className="relative w-full max-w-md rounded-2xl border border-slate-200 bg-white p-6 shadow-2xl space-y-3 text-xs">
            <div className="flex items-center justify-between border-b border-slate-100 pb-3">
              <div>
                <span className="text-[10px] font-bold font-mono text-blue-600">{selectedJobModal.job_number}</span>
                <h3 className="text-base font-bold text-slate-900">{selectedJobModal.customer_name}</h3>
              </div>
              <button
                onClick={() => setSelectedJobModal(null)}
                className="text-slate-400 hover:text-slate-700 text-sm font-bold"
              >
                Close
              </button>
            </div>

            <div className="space-y-2">
              <div className="flex justify-between py-1 border-b border-slate-100">
                <span className="text-slate-500">Address:</span>
                <span className="font-bold text-slate-800">{selectedJobModal.address}</span>
              </div>
              <div className="flex justify-between py-1 border-b border-slate-100">
                <span className="text-slate-500">Required Skill:</span>
                <span className="font-bold text-purple-700">{selectedJobModal.required_skill?.skill_name || 'N/A'}</span>
              </div>
              <div className="flex justify-between py-1 border-b border-slate-100">
                <span className="text-slate-500">Priority:</span>
                <span className="font-extrabold text-amber-800">{selectedJobModal.priority}</span>
              </div>
              <div className="flex justify-between py-1 border-b border-slate-100">
                <span className="text-slate-500">Status:</span>
                <span className="font-bold text-blue-700">{selectedJobModal.status}</span>
              </div>
              <div className="flex justify-between py-1 border-b border-slate-100">
                <span className="text-slate-500">Assigned Technician:</span>
                <span className="font-bold text-slate-800">
                  {selectedJobModal.assigned_technician
                    ? selectedJobModal.assigned_technician.full_name
                    : 'Awaiting technician assignment'}
                </span>
              </div>
              <div className="flex justify-between py-1 items-center">
                <span className="text-slate-500">Context-Aware ETA:</span>
                <JobETABadge jobId={selectedJobModal.id} />
              </div>
            </div>

            <div className="mt-4 flex justify-end gap-2 pt-2 border-t border-slate-100">
              <button
                onClick={() => setSelectedJobModal(null)}
                className="rounded-lg bg-blue-600 px-4 py-2 text-xs font-bold text-white hover:bg-blue-700 transition-colors shadow-2xs"
              >
                Dismiss
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
