import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Wrench,
  Shield,
  Briefcase,
  CheckCircle2,
  Clock,
  MapPin,
  Navigation,
  Sparkles,
  Phone,
  Calendar,
  FileText,
  AlertCircle,
  ChevronRight,
  UserCheck,
} from 'lucide-react';
import { useAuth } from '@/contexts/AuthContext';
import { jobService } from '@/services/job.service';
import { technicianService } from '@/services/technician.service';
import type { Job } from '@/types/job.types';
import type { Technician } from '@/types/technician.types';
import { TechnicianETACard } from '@/components/dashboard/TechnicianETACard';
import { formatDate } from '@/utils/format';
import { RealtimeConnectionBadge } from '@/components/common/RealtimeConnectionBadge';
import { useRealtimeSync } from '@/hooks/useRealtimeSync';

export default function TechnicianDashboard() {
  const { user } = useAuth();
  const navigate = useNavigate();
  const [myJobs, setMyJobs] = useState<Job[]>([]);
  const [techProfile, setTechProfile] = useState<Technician | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const loadData = async (isInitial = false) => {
    if (isInitial || myJobs.length === 0) {
      setIsLoading(true);
    }
    setErrorMessage(null);
    try {
      const [jobsData, profileData] = await Promise.all([
        jobService.getMyJobs(),
        technicianService.getMyProfile().catch(() => null),
      ]);
      setMyJobs(jobsData);
      setTechProfile(profileData);
    } catch (err: unknown) {
      console.error('Failed to load technician field workspace data', err);
      const msg = err instanceof Error ? err.message : 'Failed to load workspace data.';
      setErrorMessage(msg);
    } finally {
      setIsLoading(false);
    }
  };

  // Real-time synchronization for technician workspace
  useRealtimeSync(
    ['JOB_ASSIGNED', 'JOB_UNASSIGNED', 'JOB_STATUS_CHANGED', 'JOB_COMPLETED', 'JOB_CANCELLED', 'ETA_UPDATED'],
    () => {
      loadData(false);
    },
    () => loadData(false),
  );

  useEffect(() => {
    loadData(true);
    // Relaxed background polling fallback
    const interval = setInterval(() => loadData(false), 60000);
    return () => clearInterval(interval);
  }, []);

  const activeJobs = myJobs.filter((j) => j.status !== 'COMPLETED' && j.status !== 'CANCELLED');
  const completedJobs = myJobs.filter((j) => j.status === 'COMPLETED');
  const primaryJob = activeJobs.length > 0 ? activeJobs[0] : null;

  return (
    <div className="flex flex-col gap-6 py-2 animate-fade-in max-w-5xl mx-auto select-none">
      {/* ── Workspace Operational Header ── */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-slate-200 pb-5">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <span className="inline-flex items-center gap-1.5 rounded-full border border-emerald-200 bg-emerald-50 px-2.5 py-0.5 text-[11px] font-semibold text-emerald-700">
              <Wrench className="h-3.5 w-3.5 text-emerald-600" />
              <span>My Field Workspace</span>
            </span>
            <span className="inline-flex items-center gap-1 rounded-full border border-slate-200 bg-slate-100 px-2.5 py-0.5 text-[11px] font-medium text-slate-700">
              <Shield className="h-3 w-3 text-purple-600" />
              <span>{user?.role || 'Technician'}</span>
            </span>
            <RealtimeConnectionBadge />
          </div>

          <h1 className="text-2xl md:text-3xl font-extrabold tracking-tight text-slate-900">
            Welcome, {user?.full_name || 'Field Technician'}
          </h1>
          <p className="text-xs md:text-sm text-slate-500 mt-0.5">
            Operational dashboard overview, assigned work orders, and real-time transit telemetry.
          </p>
        </div>

        {/* Availability Status Badge */}
        <div className="flex items-center gap-3 bg-white p-3 rounded-xl border border-slate-200 shadow-xs">
          <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-emerald-50 text-emerald-700 border border-emerald-200">
            <UserCheck className="h-5 w-5" />
          </div>
          <div>
            <span className="text-[10px] uppercase font-bold text-slate-400 block">Duty Availability</span>
            <span className="text-xs font-extrabold text-emerald-700">
              {techProfile?.availability_status || (primaryJob ? 'ON_JOB' : 'AVAILABLE')}
            </span>
          </div>
        </div>
      </div>

      {errorMessage && (
        <div className="flex items-center gap-3 rounded-xl border border-rose-200 bg-rose-50 p-4 text-xs font-semibold text-rose-800 animate-shake">
          <AlertCircle className="h-5 w-5 shrink-0 text-rose-600" />
          <span>{errorMessage}</span>
        </div>
      )}

      {/* ── KPI Summary Cards ── */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-xs flex items-center justify-between">
          <div>
            <span className="text-[11px] font-bold text-slate-400 uppercase tracking-wider">Total Assigned Jobs</span>
            <div className="text-2xl font-black text-slate-900 mt-1">{myJobs.length}</div>
          </div>
          <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-blue-50 text-blue-600 border border-blue-200">
            <Briefcase className="h-6 w-6" />
          </div>
        </div>

        <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-xs flex items-center justify-between">
          <div>
            <span className="text-[11px] font-bold text-slate-400 uppercase tracking-wider">Active Service Order</span>
            <div className="text-2xl font-black text-blue-700 mt-1">
              {primaryJob ? primaryJob.job_number : 'None'}
            </div>
          </div>
          <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-amber-50 text-amber-600 border border-amber-200">
            <Clock className="h-6 w-6" />
          </div>
        </div>

        <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-xs flex items-center justify-between">
          <div>
            <span className="text-[11px] font-bold text-slate-400 uppercase tracking-wider">Completed Orders</span>
            <div className="text-2xl font-black text-emerald-700 mt-1">{completedJobs.length}</div>
          </div>
          <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-emerald-50 text-emerald-600 border border-emerald-200">
            <CheckCircle2 className="h-6 w-6" />
          </div>
        </div>
      </div>

      {/* ── PRIMARY ACTIVE ASSIGNED JOB CARD ── */}
      {isLoading ? (
        <div className="rounded-2xl border border-slate-200 bg-white p-12 text-center text-xs text-slate-500">
          Loading active service order...
        </div>
      ) : primaryJob ? (
        <div className="rounded-2xl border border-blue-200 bg-white p-6 sm:p-7 shadow-xs space-y-6">
          <div className="flex flex-wrap items-start justify-between gap-3 border-b border-slate-100 pb-4">
            <div>
              <div className="flex items-center gap-2 mb-1.5">
                <span className="font-mono text-xs font-extrabold text-blue-700 bg-blue-50 px-2.5 py-0.5 rounded-md border border-blue-200">
                  {primaryJob.job_number}
                </span>
                <span className="text-[10px] uppercase font-extrabold text-purple-700 bg-purple-50 px-2.5 py-0.5 rounded-full border border-purple-200">
                  {primaryJob.priority} PRIORITY
                </span>
                <span className="text-[10px] uppercase font-extrabold text-amber-700 bg-amber-50 px-2.5 py-0.5 rounded-full border border-amber-200">
                  STATUS: {primaryJob.status}
                </span>
              </div>
              <h2 className="text-xl sm:text-2xl font-black text-slate-900">{primaryJob.customer_name}</h2>
            </div>

            <div className="text-right">
              <span className="text-[10px] uppercase font-bold text-slate-400 tracking-wider block">Scheduled Time</span>
              <div className="flex items-center gap-1 text-xs font-semibold text-slate-700 mt-0.5">
                <Calendar className="h-3.5 w-3.5 text-blue-600" />
                <span>{primaryJob.scheduled_time ? formatDate(primaryJob.scheduled_time) : 'Asap Dispatch'}</span>
              </div>
            </div>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 text-xs">
            <div className="rounded-xl border border-slate-200 bg-slate-50 p-4 space-y-2">
              <div className="flex items-center gap-2 text-slate-500 font-bold uppercase text-[10px]">
                <MapPin className="h-3.5 w-3.5 text-blue-600" />
                <span>Service Address</span>
              </div>
              <p className="text-slate-800 font-semibold leading-relaxed">{primaryJob.address}</p>
              {primaryJob.customer_phone && (
                <div className="flex items-center gap-1.5 text-slate-600 pt-1 text-[11px]">
                  <Phone className="h-3 w-3 text-emerald-600" />
                  <span>{primaryJob.customer_phone}</span>
                </div>
              )}
            </div>

            <div className="rounded-xl border border-slate-200 bg-slate-50 p-4 space-y-2">
              <div className="flex items-center gap-2 text-slate-500 font-bold uppercase text-[10px]">
                <Sparkles className="h-3.5 w-3.5 text-purple-600" />
                <span>Required Skill Certification</span>
              </div>
              <p className="text-slate-800 font-semibold">
                {primaryJob.required_skill?.skill_name || 'Standard Field Operation'}
              </p>
            </div>
          </div>

          {primaryJob.description && (
            <div className="rounded-xl border border-slate-200 bg-slate-50 p-4 text-xs space-y-1">
              <div className="flex items-center gap-1.5 text-slate-500 font-bold uppercase text-[10px]">
                <FileText className="h-3.5 w-3.5 text-amber-600" />
                <span>Dispatch Instructions</span>
              </div>
              <p className="text-slate-700 leading-relaxed">{primaryJob.description}</p>
            </div>
          )}

          {/* Telemetry Card */}
          <TechnicianETACard
            jobId={primaryJob.id}
            assignedJobLocation={
              typeof primaryJob.latitude === 'number' && typeof primaryJob.longitude === 'number'
                ? {
                    latitude: primaryJob.latitude,
                    longitude: primaryJob.longitude,
                    address: primaryJob.address,
                  }
                : null
            }
          />

          {/* Quick Actions Bar */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 border-t border-slate-100 pt-4">
            <button
              onClick={async () => {
                if (primaryJob.status === 'ASSIGNED') {
                  try {
                    await jobService.updateJobStatus(primaryJob.id, 'EN_ROUTE');
                  } catch (e) {
                    console.warn('Failed auto-transitioning to EN_ROUTE:', e);
                  }
                }
                navigate('/technician/route');
              }}
              className="flex items-center justify-center gap-2 rounded-xl bg-blue-600 px-5 py-3 text-xs font-extrabold text-white shadow-xs hover:bg-blue-700 transition-all cursor-pointer"
            >
              <Navigation className="h-4 w-4 animate-pulse" />
              <span>{primaryJob.status === 'ASSIGNED' ? 'START NAVIGATION' : 'ROUTE NAVIGATION & ETA'}</span>
            </button>
            <button
              onClick={() => navigate('/technician/status')}
              className="flex items-center justify-center gap-2 rounded-xl bg-emerald-600 px-5 py-3 text-xs font-extrabold text-white shadow-xs hover:bg-emerald-700 transition-all cursor-pointer"
            >
              <CheckCircle2 className="h-4 w-4" />
              <span>Update Execution Status</span>
            </button>
          </div>
        </div>
      ) : (
        <div className="rounded-2xl border border-slate-200 bg-white p-12 text-center text-xs text-slate-500 flex flex-col items-center justify-center gap-3 shadow-xs">
          <CheckCircle2 className="h-10 w-10 text-emerald-500" />
          <span className="text-base font-extrabold text-slate-800">No active job assigned</span>
          <span className="text-xs text-slate-500 max-w-md">
            You currently have no pending active work orders assigned. New job assignments dispatched by your dispatcher will automatically appear here.
          </span>
        </div>
      )}

      {/* ── RECENT ASSIGNED WORK ORDERS DIRECTORY PREVIEW ── */}
      <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-xs space-y-4">
        <div className="flex items-center justify-between border-b border-slate-100 pb-3">
          <div className="flex items-center gap-2">
            <Briefcase className="h-5 w-5 text-blue-600" />
            <h3 className="text-base font-extrabold text-slate-900">Recent Assigned Work Orders</h3>
          </div>
          <button
            onClick={() => navigate('/technician/jobs')}
            className="flex items-center gap-1 text-xs font-bold text-blue-600 hover:text-blue-700 cursor-pointer"
          >
            <span>View All Jobs</span>
            <ChevronRight className="h-4 w-4" />
          </button>
        </div>

        {myJobs.length === 0 ? (
          <div className="py-6 text-center text-xs text-slate-500">No jobs assigned yet.</div>
        ) : (
          <div className="space-y-2.5">
            {myJobs.slice(0, 3).map((j) => (
              <div
                key={j.id}
                onClick={() => navigate('/technician/jobs')}
                className="p-3.5 rounded-xl border border-slate-200 bg-slate-50 text-xs flex items-center justify-between hover:bg-slate-100/70 transition-colors cursor-pointer"
              >
                <div className="flex items-center gap-3">
                  <span className="font-mono font-bold text-blue-700">{j.job_number}</span>
                  <div>
                    <span className="font-bold text-slate-900 block">{j.customer_name}</span>
                    <span className="text-[11px] text-slate-500 truncate max-w-xs block">{j.address}</span>
                  </div>
                </div>
                <span className="rounded-full bg-purple-50 border border-purple-200 px-2.5 py-0.5 text-[10px] font-bold text-purple-700 shrink-0">
                  {j.status}
                </span>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
