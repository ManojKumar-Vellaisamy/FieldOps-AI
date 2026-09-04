import { useState, useEffect } from 'react';
import {
  Briefcase,
  Clock,
  Navigation,
  MapPin,
  Wrench,
  Shield,
  CheckCircle2,
  AlertCircle,
  Play,
  CheckSquare,
  Sparkles,
  Phone,
  Calendar,
  FileText,
  X,
  Check
} from 'lucide-react';
import { useAuth } from '@/contexts/AuthContext';
import { jobService } from '@/services/job.service';
import type { Job } from '@/types/job.types';
import { TechnicianETACard } from '@/components/dashboard/TechnicianETACard';
import { formatDate } from '@/utils/format';

export default function TechnicianDashboard() {
  const { user } = useAuth();
  const [myJobs, setMyJobs] = useState<Job[]>([]);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [isUpdating, setIsUpdating] = useState<boolean>(false);
  const [actionNotice, setActionNotice] = useState<string | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<'ACTIVE' | 'COMPLETED'>('ACTIVE');

  // Completion modal state
  const [showCompleteModal, setShowCompleteModal] = useState<boolean>(false);
  const [completionNotes, setCompletionNotes] = useState<string>('');

  const triggerNotice = (msg: string) => {
    setActionNotice(msg);
    setTimeout(() => setActionNotice(null), 4000);
  };

  const loadMyJobs = async () => {
    setIsLoading(true);
    setErrorMessage(null);
    try {
      const data = await jobService.getMyJobs();
      setMyJobs(data);
    } catch (err: unknown) {
      console.error('Failed to load technician assigned jobs', err);
      const msg = err instanceof Error ? err.message : 'Failed to load assigned jobs.';
      setErrorMessage(msg);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    loadMyJobs();
  }, []);

  const activeJobs = myJobs.filter((j) => j.status !== 'COMPLETED' && j.status !== 'CANCELLED');
  const completedJobs = myJobs.filter((j) => j.status === 'COMPLETED');
  const primaryJob = activeJobs.length > 0 ? activeJobs[0] : null;

  const handleStatusTransition = async (jobId: string, nextStatus: string, notes?: string) => {
    setIsUpdating(true);
    setErrorMessage(null);
    try {
      const updated = await jobService.updateJobStatus(jobId, nextStatus, notes);
      setMyJobs((prev) => prev.map((j) => (j.id === updated.id ? updated : j)));
      
      const statusLabels: Record<string, string> = {
        EN_ROUTE: 'Status updated: En Route to customer site',
        TRAVELLING: 'Status updated: En Route to customer site',
        ARRIVED: 'Status updated: Arrived at customer site',
        IN_PROGRESS: 'Status updated: Work started in progress',
        WORKING: 'Status updated: Work started in progress',
        COMPLETED: 'Job completed successfully!',
      };

      triggerNotice(statusLabels[nextStatus] || `Status updated to ${nextStatus}`);
      setShowCompleteModal(false);
      setCompletionNotes('');
    } catch (err: unknown) {
      console.error('Status update failed', err);
      const msg = err instanceof Error ? err.message : 'Failed to update job status.';
      setErrorMessage(msg);
    } finally {
      setIsUpdating(false);
    }
  };

  const renderNextActionButton = (job: Job) => {
    const currentStatus = job.status.toUpperCase();

    if (currentStatus === 'ASSIGNED') {
      return (
        <button
          disabled={isUpdating}
          onClick={() => handleStatusTransition(job.id, 'EN_ROUTE')}
          className="w-full flex items-center justify-center gap-3 rounded-xl bg-blue-600 px-6 py-4 text-base font-extrabold text-white shadow-xs transition-all hover:bg-blue-700 active:scale-[0.99] disabled:opacity-50 cursor-pointer"
        >
          <Navigation className="h-5 w-5 animate-pulse" />
          <span>{isUpdating ? 'Updating Status...' : 'Start Travel (En Route)'}</span>
        </button>
      );
    }

    if (currentStatus === 'TRAVELLING' || currentStatus === 'EN_ROUTE') {
      return (
        <button
          disabled={isUpdating}
          onClick={() => handleStatusTransition(job.id, 'ARRIVED')}
          className="w-full flex items-center justify-center gap-3 rounded-xl bg-amber-600 px-6 py-4 text-base font-extrabold text-white shadow-xs transition-all hover:bg-amber-700 active:scale-[0.99] disabled:opacity-50 cursor-pointer"
        >
          <MapPin className="h-5 w-5" />
          <span>{isUpdating ? 'Updating Status...' : 'Mark Arrived at Site'}</span>
        </button>
      );
    }

    if (currentStatus === 'ARRIVED') {
      return (
        <button
          disabled={isUpdating}
          onClick={() => handleStatusTransition(job.id, 'IN_PROGRESS')}
          className="w-full flex items-center justify-center gap-3 rounded-xl bg-purple-600 px-6 py-4 text-base font-extrabold text-white shadow-xs transition-all hover:bg-purple-700 active:scale-[0.99] disabled:opacity-50 cursor-pointer"
        >
          <Play className="h-5 w-5 fill-current" />
          <span>{isUpdating ? 'Updating Status...' : 'Start Work (In Progress)'}</span>
        </button>
      );
    }

    if (currentStatus === 'WORKING' || currentStatus === 'IN_PROGRESS') {
      return (
        <button
          disabled={isUpdating}
          onClick={() => setShowCompleteModal(true)}
          className="w-full flex items-center justify-center gap-3 rounded-xl bg-emerald-600 px-6 py-4 text-base font-extrabold text-white shadow-xs transition-all hover:bg-emerald-700 active:scale-[0.99] disabled:opacity-50 cursor-pointer"
        >
          <CheckSquare className="h-5 w-5" />
          <span>{isUpdating ? 'Updating Status...' : 'Complete Job'}</span>
        </button>
      );
    }

    if (currentStatus === 'COMPLETED') {
      return (
        <div className="w-full flex items-center justify-center gap-2 rounded-xl bg-emerald-50 border border-emerald-200 p-4 text-emerald-800 font-bold text-sm">
          <CheckCircle2 className="h-5 w-5 text-emerald-600" />
          <span>Job Completed & Verified</span>
        </div>
      );
    }

    return null;
  };

  return (
    <div className="flex flex-col gap-6 py-2 animate-fade-in max-w-5xl mx-auto select-none">
      {/* ── Workspace Header ── */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-slate-200 pb-5">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <span className="inline-flex items-center gap-1.5 rounded-full border border-emerald-200 bg-emerald-50 px-2.5 py-0.5 text-[11px] font-semibold text-emerald-700">
              <Wrench className="h-3.5 w-3.5" />
              <span>Technician Field Workspace</span>
            </span>
            <span className="inline-flex items-center gap-1 rounded-full border border-slate-200 bg-slate-100 px-2.5 py-0.5 text-[11px] font-medium text-slate-700">
              <Shield className="h-3 w-3 text-purple-600" />
              <span>{user?.role || 'Technician'}</span>
            </span>
          </div>

          <h1 className="text-2xl md:text-3xl font-extrabold tracking-tight text-slate-900">
            Field Job Execution
          </h1>
          <p className="text-xs md:text-sm text-slate-500 mt-0.5">
            Manage your assigned field service order, update travel & work status, and submit completion reports.
          </p>
        </div>

        {actionNotice && (
          <div className="flex items-center gap-2 text-xs font-semibold text-emerald-800 bg-emerald-50 border border-emerald-200 px-3.5 py-2 rounded-xl animate-fade-in shadow-xs">
            <Check className="h-4 w-4 text-emerald-600" />
            <span>{actionNotice}</span>
          </div>
        )}
      </div>

      {errorMessage && (
        <div className="flex items-center gap-3 rounded-xl border border-rose-200 bg-rose-50 p-4 text-xs font-semibold text-rose-800 animate-shake">
          <AlertCircle className="h-5 w-5 shrink-0 text-rose-600" />
          <span>{errorMessage}</span>
        </div>
      )}

      {/* ── PRIMARY ACTIVE ASSIGNED JOB ── */}
      {isLoading ? (
        <div className="rounded-2xl border border-slate-200 bg-white p-12 text-center text-xs text-slate-500">
          Loading assigned work orders...
        </div>
      ) : primaryJob ? (
        <div className="rounded-2xl border border-blue-200 bg-white p-5 sm:p-7 shadow-xs space-y-6 relative overflow-hidden">
          {/* Job Header Info */}
          <div className="flex flex-wrap items-start justify-between gap-3 border-b border-slate-100 pb-4">
            <div>
              <div className="flex items-center gap-2 mb-1.5">
                <span className="font-mono text-xs font-extrabold text-blue-700 bg-blue-50 px-2.5 py-0.5 rounded-md border border-blue-200">
                  {primaryJob.job_number}
                </span>
                <span className="text-[10px] uppercase tracking-wider font-extrabold text-purple-700 bg-purple-50 px-2.5 py-0.5 rounded-full border border-purple-200">
                  {primaryJob.priority} PRIORITY
                </span>
                <span className="text-[10px] uppercase tracking-wider font-extrabold text-amber-700 bg-amber-50 px-2.5 py-0.5 rounded-full border border-amber-200">
                  STATUS: {primaryJob.status}
                </span>
              </div>
              <h2 className="text-xl sm:text-2xl font-black text-slate-900">
                {primaryJob.customer_name}
              </h2>
            </div>

            <div className="text-right">
              <span className="text-[10px] uppercase font-bold text-slate-400 tracking-wider block">
                Scheduled Time
              </span>
              <div className="flex items-center gap-1 text-xs font-semibold text-slate-700 mt-0.5">
                <Calendar className="h-3.5 w-3.5 text-blue-600" />
                <span>{primaryJob.scheduled_time ? formatDate(primaryJob.scheduled_time) : 'Asap'}</span>
              </div>
            </div>
          </div>

          {/* Details Grid */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 text-xs">
            <div className="rounded-xl border border-slate-200 bg-slate-50 p-4 space-y-2">
              <div className="flex items-center gap-2 text-slate-500 font-bold uppercase tracking-wider text-[10px]">
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
              <div className="flex items-center gap-2 text-slate-500 font-bold uppercase tracking-wider text-[10px]">
                <Sparkles className="h-3.5 w-3.5 text-purple-600" />
                <span>Required Skill Certification</span>
              </div>
              <p className="text-slate-800 font-semibold">
                {primaryJob.required_skill?.skill_name || 'Standard Field Operation'}
              </p>
              {primaryJob.creator && (
                <p className="text-[11px] text-slate-500 pt-1">
                  Dispatched by: <strong className="text-slate-700">{primaryJob.creator.full_name}</strong>
                </p>
              )}
            </div>
          </div>

          {/* Dispatch Instructions */}
          {primaryJob.description && (
            <div className="rounded-xl border border-slate-200 bg-slate-50 p-4 space-y-1.5 text-xs">
              <div className="flex items-center gap-1.5 text-slate-500 font-bold uppercase tracking-wider text-[10px]">
                <FileText className="h-3.5 w-3.5 text-amber-600" />
                <span>Dispatch Instructions</span>
              </div>
              <p className="text-slate-700 leading-relaxed">{primaryJob.description}</p>
            </div>
          )}

          {/* Context-Aware Travel ETA Telemetry Card */}
          <TechnicianETACard jobId={primaryJob.id} />

          {/* STEP-BY-STEP EXECUTION ACTION CARD */}
          <div className="rounded-2xl border border-slate-200 bg-slate-50 p-5 space-y-3 shadow-xs">
            <div className="flex items-center justify-between">
              <span className="text-xs font-bold uppercase tracking-wider text-slate-500 flex items-center gap-2">
                <Clock className="h-4 w-4 text-emerald-600" />
                <span>Next Execution Step</span>
              </span>
              <span className="text-[11px] font-semibold text-slate-500 font-mono">
                Current State: <strong className="text-emerald-700">{primaryJob.status}</strong>
              </span>
            </div>

            {renderNextActionButton(primaryJob)}
          </div>
        </div>
      ) : (
        <div className="rounded-2xl border border-slate-200 bg-white p-12 text-center text-xs text-slate-500 flex flex-col items-center justify-center gap-3 shadow-xs">
          <CheckCircle2 className="h-10 w-10 text-emerald-500" />
          <span className="text-base font-extrabold text-slate-800">All Field Tasks Up To Date</span>
          <span className="text-xs text-slate-500 max-w-md">
            You currently have no pending active work orders assigned. New job assignments dispatched by your dispatcher will automatically appear here.
          </span>
        </div>
      )}

      {/* ── ALL ASSIGNED WORK ORDERS DIRECTORY ── */}
      <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-xs space-y-4">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-slate-100 pb-4">
          <div className="flex items-center gap-2">
            <Briefcase className="h-5 w-5 text-blue-600" />
            <h3 className="text-base font-extrabold text-slate-900">My Assigned Work Orders Directory</h3>
          </div>

          <div className="flex items-center gap-2 bg-slate-100 p-1 rounded-xl border border-slate-200 w-fit">
            <button
              onClick={() => setActiveTab('ACTIVE')}
              className={`px-3 py-1.5 rounded-lg text-xs font-bold transition-all cursor-pointer ${
                activeTab === 'ACTIVE'
                  ? 'bg-blue-600 text-white shadow-xs'
                  : 'text-slate-600 hover:text-slate-900'
              }`}
            >
              Active ({activeJobs.length})
            </button>
            <button
              onClick={() => setActiveTab('COMPLETED')}
              className={`px-3 py-1.5 rounded-lg text-xs font-bold transition-all cursor-pointer ${
                activeTab === 'COMPLETED'
                  ? 'bg-emerald-600 text-white shadow-xs'
                  : 'text-slate-600 hover:text-slate-900'
              }`}
            >
              Completed ({completedJobs.length})
            </button>
          </div>
        </div>

        {/* List Content */}
        {isLoading ? (
          <div className="py-8 text-center text-xs text-slate-500">Loading work orders...</div>
        ) : (activeTab === 'ACTIVE' ? activeJobs : completedJobs).length === 0 ? (
          <div className="py-8 text-center text-xs text-slate-500">
            No {activeTab.toLowerCase()} jobs found.
          </div>
        ) : (
          <div className="space-y-3">
            {(activeTab === 'ACTIVE' ? activeJobs : completedJobs).map((j) => (
              <div
                key={j.id}
                className="p-4 rounded-xl border border-slate-200 bg-slate-50 text-xs space-y-2 hover:border-slate-300 transition-colors"
              >
                <div className="flex flex-wrap items-center justify-between gap-2 border-b border-slate-200/80 pb-2">
                  <div className="flex items-center gap-2">
                    <span className="font-mono font-bold text-blue-700 text-sm">{j.job_number}</span>
                    <span className="rounded-full bg-purple-50 border border-purple-200 px-2 py-0.5 text-[10px] font-bold text-purple-700">
                      {j.status}
                    </span>
                    <span className="rounded-md bg-amber-50 border border-amber-200 px-2 py-0.5 text-[10px] font-bold text-amber-700">
                      {j.priority}
                    </span>
                  </div>
                  <div className="font-mono text-[11px] text-slate-500">
                    Scheduled: {j.scheduled_time ? formatDate(j.scheduled_time) : 'Asap'}
                  </div>
                </div>

                <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 pt-1">
                  <div>
                    <div className="font-bold text-slate-800">{j.customer_name}</div>
                    <div className="text-[11px] text-slate-500">{j.customer_phone || 'No Phone'}</div>
                  </div>
                  <div className="flex items-center gap-1.5 text-slate-600">
                    <MapPin className="h-3.5 w-3.5 text-blue-600 shrink-0" />
                    <span className="truncate">{j.address}</span>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* ── COMPLETION CONFIRMATION MODAL ── */}
      {showCompleteModal && primaryJob && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/40 backdrop-blur-sm p-4 animate-fade-in">
          <div className="w-full max-w-lg rounded-2xl border border-slate-200 bg-white p-6 shadow-xl space-y-5">
            <div className="flex items-center justify-between border-b border-slate-100 pb-4">
              <div className="flex items-center gap-2">
                <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-emerald-50 text-emerald-700 border border-emerald-200">
                  <CheckSquare className="h-5 w-5 text-emerald-600" />
                </div>
                <div>
                  <h3 className="text-base font-extrabold text-slate-900">Confirm Job Completion</h3>
                  <p className="text-xs text-slate-500 font-mono">{primaryJob.job_number}</p>
                </div>
              </div>
              <button
                onClick={() => setShowCompleteModal(false)}
                className="rounded-lg p-1 text-slate-400 hover:bg-slate-100 hover:text-slate-700 cursor-pointer"
              >
                <X className="h-5 w-5" />
              </button>
            </div>

            <div className="space-y-3 text-xs">
              <p className="text-slate-600">
                You are marking work order <strong className="text-slate-900">{primaryJob.job_number}</strong> for{' '}
                <strong className="text-slate-900">{primaryJob.customer_name}</strong> as <strong className="text-emerald-700">COMPLETED</strong>.
              </p>

              <div className="space-y-1.5">
                <label className="block text-xs font-semibold text-slate-700">
                  Completion Notes / Field Report (Optional)
                </label>
                <textarea
                  rows={3}
                  value={completionNotes}
                  onChange={(e) => setCompletionNotes(e.target.value)}
                  placeholder="Describe work completed, parts replaced, or customer feedback..."
                  className="w-full rounded-xl border border-slate-200 bg-slate-50 p-3 text-xs text-slate-800 placeholder-slate-400 focus:border-emerald-500 focus:bg-white focus:outline-none"
                />
              </div>
            </div>

            <div className="flex items-center justify-end gap-3 border-t border-slate-100 pt-4">
              <button
                disabled={isUpdating}
                onClick={() => setShowCompleteModal(false)}
                className="rounded-xl border border-slate-200 bg-white px-4 py-2.5 text-xs font-semibold text-slate-700 hover:bg-slate-50 cursor-pointer"
              >
                Cancel
              </button>
              <button
                disabled={isUpdating}
                onClick={() => handleStatusTransition(primaryJob.id, 'COMPLETED', completionNotes)}
                className="flex items-center gap-2 rounded-xl bg-emerald-600 px-5 py-2.5 text-xs font-extrabold text-white shadow-xs hover:bg-emerald-700 active:scale-[0.98] disabled:opacity-50 cursor-pointer"
              >
                <Check className="h-4 w-4" />
                <span>{isUpdating ? 'Submitting...' : 'Confirm Completion'}</span>
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

