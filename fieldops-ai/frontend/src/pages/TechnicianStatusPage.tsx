import { useState, useEffect } from 'react';
import {
  CheckCircle2,
  Navigation,
  MapPin,
  Play,
  CheckSquare,
  Clock,
  Shield,
  AlertCircle,
  Check,
  X,
  FileText,
} from 'lucide-react';
import { useAuth } from '@/contexts/AuthContext';
import { jobService } from '@/services/job.service';
import { technicianService } from '@/services/technician.service';
import type { Job } from '@/types/job.types';
import { RealtimeConnectionBadge } from '@/components/common/RealtimeConnectionBadge';
import { GeolocationStatusBadge } from '@/components/common/GeolocationStatusBadge';
import { useRealtimeSync } from '@/hooks/useRealtimeSync';
import { useTechnicianGeolocation } from '@/hooks/useTechnicianGeolocation';
import { TechnicianLocationModal } from '@/components/common/TechnicianLocationModal';

export default function TechnicianStatusPage() {
  const { user } = useAuth();
  const [activeJob, setActiveJob] = useState<Job | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [isUpdating, setIsUpdating] = useState<boolean>(false);
  const [actionNotice, setActionNotice] = useState<string | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  // Completion modal state
  const [showCompleteModal, setShowCompleteModal] = useState<boolean>(false);
  const [completionNotes, setCompletionNotes] = useState<string>('');
  const [isLocationModalOpen, setIsLocationModalOpen] = useState<boolean>(false);

  const triggerNotice = (msg: string) => {
    setActionNotice(msg);
    setTimeout(() => setActionNotice(null), 4000);
  };

  const loadActiveJob = async (isInitial = false) => {
    if (isInitial) {
      setIsLoading(true);
    }
    setErrorMessage(null);
    try {
      const jobs = await jobService.getMyJobs();
      const active = jobs.find((j) => j.status !== 'COMPLETED' && j.status !== 'CANCELLED');
      setActiveJob(active || null);
    } catch (err: unknown) {
      console.error('Failed to load active job for status update', err);
      const msg = err instanceof Error ? err.message : 'Failed to load active job.';
      setErrorMessage(msg);
    } finally {
      if (isInitial) {
        setIsLoading(false);
      }
    }
  };

  // Real browser geolocation telemetry tracking
  const geo = useTechnicianGeolocation({ enabled: !!activeJob });

  // Real-time synchronization for status changes and assignments
  useRealtimeSync(
    ['JOB_STATUS_CHANGED', 'JOB_COMPLETED', 'JOB_CANCELLED', 'JOB_ASSIGNED'],
    () => {
      loadActiveJob(false);
    },
    () => loadActiveJob(false),
  );

  useEffect(() => {
    loadActiveJob(true);
    // Relaxed background polling safety net (60s)
    const interval = setInterval(() => loadActiveJob(false), 60000);
    return () => clearInterval(interval);
  }, []);

  const handleStatusTransition = async (nextStatus: string, notes?: string) => {
    if (!activeJob) return;
    setIsUpdating(true);
    setErrorMessage(null);
    try {
      const updated = await jobService.updateJobStatus(activeJob.id, nextStatus, notes);
      setActiveJob(updated.status === 'COMPLETED' ? null : updated);

      // Push real browser GPS coordinates upon status transition if fix is active
      if (geo.coordinates) {
        await technicianService
          .updateMyLocation(geo.coordinates.latitude, geo.coordinates.longitude)
          .catch(() => null);
      }

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
      console.error('Status update error', err);
      const msg = err instanceof Error ? err.message : 'Failed to update job status.';
      setErrorMessage(msg);
    } finally {
      setIsUpdating(false);
    }
  };

  const getStatusStepIndex = (status: string) => {
    const s = status.toUpperCase();
    if (s === 'ASSIGNED') return 0;
    if (s === 'EN_ROUTE' || s === 'TRAVELLING') return 1;
    if (s === 'ARRIVED') return 2;
    if (s === 'IN_PROGRESS' || s === 'WORKING') return 3;
    if (s === 'COMPLETED') return 4;
    return 0;
  };

  const currentStep = activeJob ? getStatusStepIndex(activeJob.status) : 0;
  const STEPS = [
    { label: 'Assigned', status: 'ASSIGNED' },
    { label: 'En Route', status: 'EN_ROUTE' },
    { label: 'Arrived', status: 'ARRIVED' },
    { label: 'In Progress', status: 'IN_PROGRESS' },
    { label: 'Completed', status: 'COMPLETED' },
  ];

  return (
    <div className="flex flex-col gap-6 py-2 animate-fade-in select-none max-w-4xl mx-auto">
      {/* ── Page Header ── */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-slate-200 pb-5">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <span className="inline-flex items-center gap-1.5 rounded-full border border-emerald-200 bg-emerald-50 px-2.5 py-0.5 text-[11px] font-semibold text-emerald-700">
              <CheckCircle2 className="h-3.5 w-3.5 text-emerald-600" />
              <span>Operational Lifecycle Workflow</span>
            </span>
            <span className="inline-flex items-center gap-1 rounded-full border border-slate-200 bg-slate-100 px-2.5 py-0.5 text-[11px] font-medium text-slate-700">
              <Shield className="h-3 w-3 text-purple-600" />
              <span>{user?.role || 'Technician'}</span>
            </span>
            <RealtimeConnectionBadge />
            <div className="flex items-center gap-1.5">
              <GeolocationStatusBadge geo={geo} showCoordinates />
              <button
                type="button"
                onClick={() => setIsLocationModalOpen(true)}
                className="inline-flex items-center gap-1 rounded-md border border-slate-200 bg-white hover:bg-slate-50 px-2 py-0.5 text-[10px] font-bold text-slate-700 shadow-2xs transition-colors cursor-pointer"
                title="Calibrate technician GPS location"
              >
                <MapPin className="h-3 w-3 text-purple-600" />
                <span>Calibrate</span>
              </button>
            </div>
          </div>

          <h1 className="text-2xl md:text-3xl font-extrabold tracking-tight text-slate-900">
            Update Work Status
          </h1>
          <p className="text-xs md:text-sm text-slate-500 mt-0.5">
            Step-by-step job execution state machine synced directly to backend and dispatcher control center.
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

      {isLoading ? (
        <div className="rounded-2xl border border-slate-200 bg-white p-12 text-center text-xs text-slate-500">
          Loading operational job status...
        </div>
      ) : activeJob ? (
        <div className="rounded-2xl border border-blue-200 bg-white p-6 sm:p-8 shadow-xs space-y-6">
          {/* Job Overview */}
          <div className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-100 pb-4">
            <div>
              <div className="flex items-center gap-2 mb-1">
                <span className="font-mono text-xs font-extrabold text-blue-700 bg-blue-50 px-2.5 py-0.5 rounded border border-blue-200">
                  {activeJob.job_number}
                </span>
                <span className="text-[10px] uppercase font-extrabold px-2.5 py-0.5 rounded-full bg-amber-50 text-amber-700 border border-amber-200">
                  {activeJob.priority} PRIORITY
                </span>
              </div>
              <h2 className="text-xl sm:text-2xl font-black text-slate-900">{activeJob.customer_name}</h2>
              <p className="text-xs text-slate-500 mt-1 flex items-center gap-1">
                <MapPin className="h-3.5 w-3.5 text-blue-600 shrink-0" />
                <span>{activeJob.address}</span>
              </p>
            </div>

            <div className="text-right font-mono text-xs">
              <span className="text-[10px] uppercase font-bold text-slate-400 block">Current Execution State</span>
              <span className="text-sm font-extrabold text-emerald-700 bg-emerald-50 px-3 py-1 rounded-lg border border-emerald-200 inline-block mt-0.5">
                {activeJob.status}
              </span>
            </div>
          </div>

          {/* Stepper Progress Bar */}
          <div className="py-4">
            <div className="relative flex items-center justify-between w-full">
              {/* Connector line */}
              <div className="absolute top-1/2 left-0 right-0 h-1 bg-slate-200 -translate-y-1/2 z-0" />
              <div
                className="absolute top-1/2 left-0 h-1 bg-emerald-500 -translate-y-1/2 transition-all duration-500 z-0"
                style={{ width: `${(currentStep / (STEPS.length - 1)) * 100}%` }}
              />

              {STEPS.map((step, idx) => {
                const isPassed = idx <= currentStep;
                const isCurrent = idx === currentStep;

                return (
                  <div key={step.status} className="relative z-10 flex flex-col items-center gap-2">
                    <div
                      className={`flex h-10 w-10 items-center justify-center rounded-full border-2 font-bold text-xs transition-all ${
                        isPassed
                          ? 'bg-emerald-600 border-emerald-600 text-white shadow-xs'
                          : 'bg-white border-slate-300 text-slate-400'
                      } ${isCurrent ? 'ring-4 ring-emerald-100 scale-110' : ''}`}
                    >
                      {isPassed ? <Check className="h-5 w-5" /> : idx + 1}
                    </div>
                    <span
                      className={`text-[11px] font-bold ${
                        isCurrent ? 'text-emerald-700 font-extrabold' : isPassed ? 'text-slate-800' : 'text-slate-400'
                      }`}
                    >
                      {step.label}
                    </span>
                  </div>
                );
              })}
            </div>
          </div>

          {/* Action Step Card */}
          <div className="rounded-2xl border border-slate-200 bg-slate-50 p-6 space-y-4 shadow-xs">
            <div className="flex items-center justify-between">
              <span className="text-xs font-bold uppercase tracking-wider text-slate-500 flex items-center gap-2">
                <Clock className="h-4 w-4 text-blue-600" />
                <span>Next Lifecycle Action</span>
              </span>
            </div>

            {activeJob.status === 'ASSIGNED' && (
              <button
                disabled={isUpdating}
                onClick={() => handleStatusTransition('TRAVELLING')}
                className="w-full flex items-center justify-center gap-3 rounded-xl bg-blue-600 px-6 py-4 text-base font-extrabold text-white shadow-xs hover:bg-blue-700 active:scale-[0.99] disabled:opacity-50 transition-all cursor-pointer"
              >
                <Navigation className="h-5 w-5 animate-pulse" />
                <span>{isUpdating ? 'Updating...' : 'Start Travel (En Route)'}</span>
              </button>
            )}

            {((activeJob.status as string) === 'TRAVELLING' || (activeJob.status as string) === 'EN_ROUTE') && (
              <button
                disabled={isUpdating}
                onClick={() => handleStatusTransition('ARRIVED')}
                className="w-full flex items-center justify-center gap-3 rounded-xl bg-amber-600 px-6 py-4 text-base font-extrabold text-white shadow-xs hover:bg-amber-700 active:scale-[0.99] disabled:opacity-50 transition-all cursor-pointer"
              >
                <MapPin className="h-5 w-5" />
                <span>{isUpdating ? 'Updating...' : 'Mark Arrived at Site'}</span>
              </button>
            )}

            {activeJob.status === 'ARRIVED' && (
              <button
                disabled={isUpdating}
                onClick={() => handleStatusTransition('WORKING')}
                className="w-full flex items-center justify-center gap-3 rounded-xl bg-purple-600 px-6 py-4 text-base font-extrabold text-white shadow-xs hover:bg-purple-700 active:scale-[0.99] disabled:opacity-50 transition-all cursor-pointer"
              >
                <Play className="h-5 w-5 fill-current" />
                <span>{isUpdating ? 'Updating...' : 'Start Work (In Progress)'}</span>
              </button>
            )}

            {((activeJob.status as string) === 'WORKING' || (activeJob.status as string) === 'IN_PROGRESS') && (
              <button
                disabled={isUpdating}
                onClick={() => setShowCompleteModal(true)}
                className="w-full flex items-center justify-center gap-3 rounded-xl bg-emerald-600 px-6 py-4 text-base font-extrabold text-white shadow-xs hover:bg-emerald-700 active:scale-[0.99] disabled:opacity-50 transition-all cursor-pointer"
              >
                <CheckSquare className="h-5 w-5" />
                <span>{isUpdating ? 'Updating...' : 'Complete Job'}</span>
              </button>
            )}
          </div>
        </div>
      ) : (
        <div className="rounded-2xl border border-slate-200 bg-white p-12 text-center text-xs text-slate-500 flex flex-col items-center gap-3 shadow-xs">
          <CheckCircle2 className="h-10 w-10 text-emerald-500" />
          <span className="text-base font-extrabold text-slate-800">All Work Orders Completed</span>
          <span className="text-slate-500 max-w-md">
            You currently have no active work order requiring status updates.
          </span>
        </div>
      )}

      {/* ── COMPLETION CONFIRMATION MODAL ── */}
      {showCompleteModal && activeJob && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/40 backdrop-blur-sm p-4 animate-fade-in">
          <div className="w-full max-w-lg rounded-2xl border border-slate-200 bg-white p-6 shadow-xl space-y-5">
            <div className="flex items-center justify-between border-b border-slate-100 pb-4">
              <div className="flex items-center gap-2">
                <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-emerald-50 text-emerald-700 border border-emerald-200">
                  <CheckSquare className="h-5 w-5 text-emerald-600" />
                </div>
                <div>
                  <h3 className="text-base font-extrabold text-slate-900">Confirm Job Completion</h3>
                  <p className="text-xs text-slate-500 font-mono">{activeJob.job_number}</p>
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
                You are marking work order <strong className="text-slate-900">{activeJob.job_number}</strong> as{' '}
                <strong className="text-emerald-700">COMPLETED</strong>.
              </p>

              <div className="space-y-1.5">
                <label className="block text-xs font-semibold text-slate-700 flex items-center gap-1">
                  <FileText className="h-3.5 w-3.5 text-blue-600" />
                  <span>Completion Notes / Field Report (Optional)</span>
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
                onClick={() => handleStatusTransition('COMPLETED', completionNotes)}
                className="flex items-center gap-2 rounded-xl bg-emerald-600 px-5 py-2.5 text-xs font-extrabold text-white shadow-xs hover:bg-emerald-700 active:scale-[0.98] disabled:opacity-50 cursor-pointer"
              >
                <Check className="h-4 w-4" />
                <span>{isUpdating ? 'Submitting...' : 'Confirm Completion'}</span>
              </button>
            </div>
          </div>
        </div>
      )}

      <TechnicianLocationModal
        isOpen={isLocationModalOpen}
        onClose={() => setIsLocationModalOpen(false)}
        assignedJobLocation={
          activeJob && typeof activeJob.latitude === 'number' && typeof activeJob.longitude === 'number'
            ? {
                latitude: activeJob.latitude,
                longitude: activeJob.longitude,
                address: activeJob.address,
              }
            : null
        }
        onLocationUpdated={() => loadActiveJob(false)}
      />
    </div>
  );
}
