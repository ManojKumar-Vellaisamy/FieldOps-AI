import { useState, useEffect, useCallback } from 'react';
import {
  BarChart3,
  Shield,
  RefreshCw,
  Briefcase,
  Users,
  CheckCircle2,
  TrendingUp,
  Layers,
  Activity,
  AlertCircle,
} from 'lucide-react';
import { useAuth } from '@/contexts/AuthContext';
import { analyticsService } from '@/services/analytics.service';
import type { OperationalAnalytics } from '@/types/analytics.types';
import { RealtimeConnectionBadge } from '@/components/common/RealtimeConnectionBadge';
import { useRealtimeSync } from '@/hooks/useRealtimeSync';
import { cn } from '@/utils/cn';

export default function AnalyticsPage() {
  const { user } = useAuth();
  const [analytics, setAnalytics] = useState<OperationalAnalytics | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(true);

  const loadAnalytics = useCallback(async () => {
    setIsLoading(true);
    try {
      const data = await analyticsService.getOperationalAnalytics();
      setAnalytics(data);
    } catch (err) {
      console.error('Failed to load operational analytics', err);
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    loadAnalytics();
  }, [loadAnalytics]);

  // Real-time synchronization
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
      loadAnalytics();
    },
    loadAnalytics,
  );

  return (
    <div className="flex flex-col gap-6 py-2 animate-fade-in select-none">
      {/* ── Header ── */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-slate-200 pb-5">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <span className="inline-flex items-center gap-1.5 rounded-full border border-blue-200 bg-blue-50 px-2.5 py-0.5 text-[11px] font-bold text-blue-700">
              <BarChart3 className="h-3.5 w-3.5 text-blue-600" />
              <span>Operational Analytics</span>
            </span>
            <span className="inline-flex items-center gap-1 rounded-full border border-slate-200 bg-slate-100 px-2.5 py-0.5 text-[11px] font-bold text-slate-700">
              <Shield className="h-3 w-3 text-purple-600" />
              <span>{user?.role || 'Dispatcher'}</span>
            </span>
            <RealtimeConnectionBadge />
          </div>

          <h1 className="text-2xl md:text-3xl font-extrabold tracking-tight text-slate-900">
            Field Operations Analytics
          </h1>
          <p className="text-xs md:text-sm text-slate-500 mt-0.5 font-medium">
            Authoritative operational KPIs, work order volume, status breakdowns, and workforce utilization.
          </p>
        </div>

        <div className="flex items-center gap-2.5 self-start md:self-auto">
          <button
            onClick={loadAnalytics}
            disabled={isLoading}
            className="flex items-center gap-1.5 rounded-xl border border-slate-200 bg-white px-3.5 py-2 text-xs font-bold text-slate-700 hover:bg-slate-50 transition-colors shadow-2xs cursor-pointer"
          >
            <RefreshCw className={cn('h-3.5 w-3.5', isLoading && 'animate-spin')} />
            <span>Refresh Analytics</span>
          </button>
        </div>
      </div>

      {/* ── High-Level Operational KPI Cards ── */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {/* Total Service Orders */}
        <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-xs">
          <div className="flex items-center justify-between text-xs font-bold uppercase tracking-wider text-slate-500">
            <span>Total Service Orders</span>
            <Briefcase className="h-5 w-5 text-blue-600" />
          </div>
          <div className="mt-3 text-3xl font-black text-slate-900 font-mono">
            {analytics ? analytics.total_jobs.toLocaleString() : '—'}
          </div>
          <div className="mt-1 text-[11px] text-slate-500 font-medium">Authoritative PostgreSQL orders</div>
        </div>

        {/* Active In-Flight Jobs */}
        <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-xs">
          <div className="flex items-center justify-between text-xs font-bold uppercase tracking-wider text-slate-500">
            <span>Active In-Flight Work</span>
            <Activity className="h-5 w-5 text-indigo-600" />
          </div>
          <div className="mt-3 text-3xl font-black text-indigo-700 font-mono">
            {analytics ? analytics.active_jobs.toLocaleString() : '—'}
          </div>
          <div className="mt-1 text-[11px] text-slate-500 font-medium">
            {analytics ? `${analytics.in_progress_jobs} travelling/working` : 'Active orders'}
          </div>
        </div>

        {/* Completion Rate */}
        <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-xs">
          <div className="flex items-center justify-between text-xs font-bold uppercase tracking-wider text-slate-500">
            <span>Terminal Completion Rate</span>
            <CheckCircle2 className="h-5 w-5 text-emerald-600" />
          </div>
          <div className="mt-3 text-3xl font-black text-emerald-700 font-mono">
            {analytics?.completion_rate_percentage !== null && analytics?.completion_rate_percentage !== undefined
              ? `${analytics.completion_rate_percentage}%`
              : '—'}
          </div>
          <div className="mt-1 text-[11px] text-slate-500 font-medium">
            {analytics ? `${analytics.completed_jobs} completed vs ${analytics.cancelled_jobs} cancelled` : 'Resolution rate'}
          </div>
        </div>

        {/* Technician Utilization */}
        <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-xs">
          <div className="flex items-center justify-between text-xs font-bold uppercase tracking-wider text-slate-500">
            <span>Workforce Utilization</span>
            <Users className="h-5 w-5 text-purple-600" />
          </div>
          <div className="mt-3 text-3xl font-black text-purple-700 font-mono">
            {analytics?.technician_utilization_percentage !== null && analytics?.technician_utilization_percentage !== undefined
              ? `${analytics.technician_utilization_percentage}%`
              : '—'}
          </div>
          <div className="mt-1 text-[11px] text-slate-500 font-medium">
            {analytics ? `${analytics.active_technicians} active field techs` : 'Active utilization'}
          </div>
        </div>
      </div>

      {/* ── Status & Priority Breakdown Grids ── */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* Status Distribution */}
        <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-xs flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between border-b border-slate-100 pb-3 mb-4">
              <div className="flex items-center gap-2">
                <Layers className="h-4 w-4 text-blue-600" />
                <h3 className="font-bold text-slate-900 text-sm">Work Order Status Breakdown</h3>
              </div>
              <span className="text-[11px] font-mono text-slate-500">
                {analytics?.status_distribution.length || 0} active statuses
              </span>
            </div>

            {!analytics || analytics.status_distribution.length === 0 ? (
              <div className="py-8 text-center text-slate-400 text-xs font-medium">
                No production data available yet.
              </div>
            ) : (
              <div className="space-y-3">
                {analytics.status_distribution.map((item) => {
                  const pct = analytics.total_jobs > 0 ? (item.count / analytics.total_jobs) * 100 : 0;
                  return (
                    <div key={item.status} className="space-y-1">
                      <div className="flex items-center justify-between text-xs font-bold">
                        <span className="text-slate-700">{item.status}</span>
                        <span className="font-mono text-slate-900">
                          {item.count.toLocaleString()}{' '}
                          <span className="text-slate-400 text-[10px] font-normal">({pct.toFixed(1)}%)</span>
                        </span>
                      </div>
                      <div className="h-2 w-full rounded-full bg-slate-100 overflow-hidden">
                        <div
                          className={cn(
                            'h-full rounded-full transition-all duration-500',
                            item.status === 'COMPLETED'
                              ? 'bg-emerald-500'
                              : item.status === 'CANCELLED'
                              ? 'bg-rose-500'
                              : item.status === 'NEW'
                              ? 'bg-purple-500'
                              : item.status === 'WORKING'
                              ? 'bg-blue-600'
                              : item.status === 'TRAVELLING'
                              ? 'bg-amber-500'
                              : 'bg-indigo-500',
                          )}
                          style={{ width: `${Math.max(pct, 2)}%` }}
                        />
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        </div>

        {/* Priority Distribution */}
        <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-xs flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between border-b border-slate-100 pb-3 mb-4">
              <div className="flex items-center gap-2">
                <AlertCircle className="h-4 w-4 text-purple-600" />
                <h3 className="font-bold text-slate-900 text-sm">Priority Distribution</h3>
              </div>
              <span className="text-[11px] font-mono text-slate-500">
                {analytics?.priority_distribution.length || 0} tiers
              </span>
            </div>

            {!analytics || analytics.priority_distribution.length === 0 ? (
              <div className="py-8 text-center text-slate-400 text-xs font-medium">
                No production data available yet.
              </div>
            ) : (
              <div className="space-y-3">
                {analytics.priority_distribution.map((item) => {
                  const pct = analytics.total_jobs > 0 ? (item.count / analytics.total_jobs) * 100 : 0;
                  return (
                    <div key={item.priority} className="space-y-1">
                      <div className="flex items-center justify-between text-xs font-bold">
                        <span className="text-slate-700">{item.priority}</span>
                        <span className="font-mono text-slate-900">
                          {item.count.toLocaleString()}{' '}
                          <span className="text-slate-400 text-[10px] font-normal">({pct.toFixed(1)}%)</span>
                        </span>
                      </div>
                      <div className="h-2 w-full rounded-full bg-slate-100 overflow-hidden">
                        <div
                          className={cn(
                            'h-full rounded-full transition-all duration-500',
                            item.priority === 'CRITICAL'
                              ? 'bg-rose-600'
                              : item.priority === 'HIGH'
                              ? 'bg-amber-500'
                              : item.priority === 'MEDIUM'
                              ? 'bg-blue-500'
                              : 'bg-slate-400',
                          )}
                          style={{ width: `${Math.max(pct, 2)}%` }}
                        />
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        </div>
      </div>

      {/* ── 7-Day Work Order Volume History ── */}
      <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-xs">
        <div className="flex items-center justify-between border-b border-slate-100 pb-3 mb-4">
          <div className="flex items-center gap-2">
            <TrendingUp className="h-4 w-4 text-emerald-600" />
            <h3 className="font-bold text-slate-900 text-sm">7-Day Work Order Volume Trend</h3>
          </div>
          <span className="text-[11px] font-mono text-slate-500">Trailing 7 Days</span>
        </div>

        {!analytics?.recent_jobs_volume_7d || analytics.recent_jobs_volume_7d.length === 0 ? (
          <div className="py-8 text-center text-slate-400 text-xs font-medium">
            No production data available yet.
          </div>
        ) : (
          <div className="grid grid-cols-7 gap-2 pt-4">
            {analytics.recent_jobs_volume_7d.map((day) => (
              <div key={day.date} className="flex flex-col items-center gap-1.5 text-center">
                <div className="h-24 w-full bg-slate-50 rounded-lg flex items-end justify-center p-1 border border-slate-100">
                  <div
                    className="w-full bg-blue-600/80 rounded-sm hover:bg-blue-600 transition-all cursor-default"
                    style={{
                      height: `${Math.min(
                        Math.max((day.count / (Math.max(...analytics.recent_jobs_volume_7d.map((d) => d.count)) || 1)) * 100, 4),
                        100,
                      )}%`,
                    }}
                    title={`${day.date}: ${day.count} jobs`}
                  />
                </div>
                <div className="font-mono text-xs font-bold text-slate-900">{day.count}</div>
                <div className="text-[10px] text-slate-400 font-mono">{day.date.slice(5)}</div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
