import { useState, useEffect } from 'react';
import {
  Calendar as CalendarIcon,
  Clock,
  MapPin,
  CheckCircle2,
  AlertCircle,
  Shield,
  Wrench,
} from 'lucide-react';
import { useAuth } from '@/contexts/AuthContext';
import { jobService } from '@/services/job.service';
import type { Job } from '@/types/job.types';
import { formatDate } from '@/utils/format';
import { RealtimeConnectionBadge } from '@/components/common/RealtimeConnectionBadge';
import { useRealtimeSync } from '@/hooks/useRealtimeSync';

export default function TechnicianSchedulePage() {
  const { user } = useAuth();
  const [jobs, setJobs] = useState<Job[]>([]);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const loadSchedule = async (isInitial = false) => {
    if (isInitial || jobs.length === 0) {
      setIsLoading(true);
    }
    setErrorMessage(null);
    try {
      const data = await jobService.getMyJobs();
      // Sort jobs chronologically by scheduled_time or created_at
      const sorted = [...data].sort((a, b) => {
        const timeA = a.scheduled_time ? new Date(a.scheduled_time).getTime() : 0;
        const timeB = b.scheduled_time ? new Date(b.scheduled_time).getTime() : 0;
        return timeA - timeB;
      });
      setJobs(sorted);
    } catch (err: unknown) {
      console.error('Failed to load technician schedule', err);
      const msg = err instanceof Error ? err.message : 'Failed to load schedule.';
      setErrorMessage(msg);
    } finally {
      setIsLoading(false);
    }
  };

  // Real-time synchronization for schedule updates
  useRealtimeSync(
    ['JOB_ASSIGNED', 'JOB_UNASSIGNED', 'JOB_STATUS_CHANGED', 'JOB_COMPLETED', 'JOB_CANCELLED'],
    () => {
      loadSchedule(false);
    },
    () => loadSchedule(false),
  );

  useEffect(() => {
    loadSchedule(true);
    // Relaxed background polling safety net (60s)
    const interval = setInterval(() => loadSchedule(false), 60000);
    return () => clearInterval(interval);
  }, []);

  // Filter for today's or active/upcoming schedule
  const activeJobs = jobs.filter((j) => j.status !== 'COMPLETED' && j.status !== 'CANCELLED');
  const completedJobs = jobs.filter((j) => j.status === 'COMPLETED');

  return (
    <div className="flex flex-col gap-6 py-2 animate-fade-in select-none max-w-5xl mx-auto">
      {/* ── Header ── */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-slate-200 pb-5">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <span className="inline-flex items-center gap-1.5 rounded-full border border-blue-200 bg-blue-50 px-2.5 py-0.5 text-[11px] font-semibold text-blue-700">
              <CalendarIcon className="h-3.5 w-3.5 text-blue-600" />
              <span>Shift Dispatch Schedule</span>
            </span>
            <span className="inline-flex items-center gap-1 rounded-full border border-slate-200 bg-slate-100 px-2.5 py-0.5 text-[11px] font-medium text-slate-700">
              <Shield className="h-3 w-3 text-purple-600" />
              <span>{user?.role || 'Technician'}</span>
            </span>
            <RealtimeConnectionBadge />
          </div>

          <h1 className="text-2xl md:text-3xl font-extrabold tracking-tight text-slate-900">
            Today's Schedule
          </h1>
          <p className="text-xs md:text-sm text-slate-500 mt-0.5">
            Chronological field dispatch schedule generated from your assigned service orders.
          </p>
        </div>

        <div className="flex items-center gap-3 bg-white p-2.5 rounded-xl border border-slate-200 shadow-xs text-xs font-semibold text-slate-700">
          <Clock className="h-4 w-4 text-blue-600" />
          <span>{jobs.length} Total Orders Scheduled</span>
        </div>
      </div>

      {errorMessage && (
        <div className="flex items-center gap-3 rounded-xl border border-rose-200 bg-rose-50 p-4 text-xs font-semibold text-rose-800 animate-shake">
          <AlertCircle className="h-5 w-5 shrink-0 text-rose-600" />
          <span>{errorMessage}</span>
        </div>
      )}

      {/* ── Timeline Schedule List ── */}
      {isLoading ? (
        <div className="rounded-2xl border border-slate-200 bg-white p-12 text-center text-xs text-slate-500">
          Loading dispatch schedule...
        </div>
      ) : jobs.length === 0 ? (
        <div className="rounded-2xl border border-slate-200 bg-white p-12 text-center text-xs text-slate-500 flex flex-col items-center gap-3 shadow-xs">
          <CheckCircle2 className="h-10 w-10 text-emerald-500" />
          <span className="text-base font-extrabold text-slate-800">No Scheduled Jobs Today</span>
          <span className="text-slate-500 max-w-md">
            You have no active or completed field service orders assigned on your schedule for today.
          </span>
        </div>
      ) : (
        <div className="space-y-6">
          {/* Active Schedule Section */}
          <div className="space-y-4">
            <div className="flex items-center gap-2 border-b border-slate-200 pb-2">
              <span className="h-2.5 w-2.5 rounded-full bg-blue-600 animate-pulse" />
              <h2 className="text-sm font-extrabold uppercase tracking-wider text-slate-800">
                Pending & Active Field Execution ({activeJobs.length})
              </h2>
            </div>

            {activeJobs.length === 0 ? (
              <div className="rounded-xl border border-dashed border-slate-200 bg-slate-50 p-6 text-center text-xs text-slate-500">
                All scheduled tasks for today have been completed.
              </div>
            ) : (
              <div className="relative border-l-2 border-blue-200 ml-4 pl-6 space-y-6">
                {activeJobs.map((job, idx) => (
                  <div key={job.id} className="relative group">
                    {/* Timeline Node Icon */}
                    <div className="absolute -left-[31px] top-1.5 flex h-6 w-6 items-center justify-center rounded-full bg-blue-600 text-white font-mono text-[10px] font-extrabold shadow-xs">
                      {idx + 1}
                    </div>

                    <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-xs transition-all hover:border-blue-300 hover:shadow-md space-y-3">
                      <div className="flex flex-wrap items-center justify-between gap-2 border-b border-slate-100 pb-3">
                        <div className="flex items-center gap-2">
                          <span className="font-mono text-xs font-bold text-blue-700 bg-blue-50 px-2 py-0.5 rounded border border-blue-200">
                            {job.job_number}
                          </span>
                          <span className="text-[10px] uppercase font-extrabold px-2 py-0.5 rounded-full bg-amber-50 text-amber-700 border border-amber-200">
                            {job.priority} PRIORITY
                          </span>
                          <span className="text-[10px] uppercase font-extrabold px-2 py-0.5 rounded-full bg-purple-50 text-purple-700 border border-purple-200">
                            {job.status}
                          </span>
                        </div>

                        <div className="flex items-center gap-1.5 font-mono text-xs font-bold text-slate-700">
                          <Clock className="h-3.5 w-3.5 text-blue-600" />
                          <span>{job.scheduled_time ? formatDate(job.scheduled_time) : 'Immediate Dispatch'}</span>
                        </div>
                      </div>

                      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 text-xs">
                        <div>
                          <span className="text-[10px] uppercase font-bold text-slate-400 tracking-wider block mb-0.5">
                            Customer / Contact
                          </span>
                          <div className="font-extrabold text-slate-900 text-sm">{job.customer_name}</div>
                          <div className="text-slate-500">{job.customer_phone || 'No phone recorded'}</div>
                        </div>

                        <div>
                          <span className="text-[10px] uppercase font-bold text-slate-400 tracking-wider block mb-0.5">
                            Service Location & Skill
                          </span>
                          <div className="flex items-center gap-1 text-slate-700 font-semibold truncate">
                            <MapPin className="h-3.5 w-3.5 text-blue-600 shrink-0" />
                            <span className="truncate">{job.address}</span>
                          </div>
                          <div className="flex items-center gap-1 text-slate-500 text-[11px] mt-0.5">
                            <Wrench className="h-3 w-3 text-purple-600 shrink-0" />
                            <span>{job.required_skill?.skill_name || 'Standard Operation'}</span>
                          </div>
                        </div>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Completed Schedule Section */}
          {completedJobs.length > 0 && (
            <div className="space-y-4 pt-4 border-t border-slate-200">
              <div className="flex items-center gap-2 border-b border-slate-200 pb-2">
                <CheckCircle2 className="h-4 w-4 text-emerald-600" />
                <h2 className="text-sm font-extrabold uppercase tracking-wider text-slate-800">
                  Completed Shift Orders ({completedJobs.length})
                </h2>
              </div>

              <div className="space-y-3">
                {completedJobs.map((job) => (
                  <div
                    key={job.id}
                    className="rounded-xl border border-slate-200 bg-slate-50 p-4 text-xs space-y-2 opacity-80"
                  >
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        <span className="font-mono font-bold text-slate-700">{job.job_number}</span>
                        <span className="font-bold text-slate-900">{job.customer_name}</span>
                      </div>
                      <span className="rounded-full bg-emerald-50 border border-emerald-200 px-2.5 py-0.5 text-[10px] font-bold text-emerald-700">
                        COMPLETED
                      </span>
                    </div>
                    <div className="flex items-center gap-1.5 text-slate-500 text-[11px]">
                      <MapPin className="h-3 w-3 text-slate-400 shrink-0" />
                      <span className="truncate">{job.address}</span>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
