import { useState, useEffect } from 'react';
import {
  Briefcase,
  Search,
  MapPin,
  Sparkles,
  Phone,
  Calendar,
  FileText,
  X,
  AlertCircle,
  Clock,
  Shield,
  Wrench,
  CheckCircle2,
  ChevronRight,
} from 'lucide-react';
import { useAuth } from '@/contexts/AuthContext';
import { jobService } from '@/services/job.service';
import type { Job } from '@/types/job.types';
import { formatDate } from '@/utils/format';
import { RealtimeConnectionBadge } from '@/components/common/RealtimeConnectionBadge';
import { useRealtimeSync } from '@/hooks/useRealtimeSync';

export default function TechnicianJobsPage() {
  const { user } = useAuth();
  const [jobs, setJobs] = useState<Job[]>([]);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  // Search & Filter State
  const [searchTerm, setSearchTerm] = useState<string>('');
  const [statusFilter, setStatusFilter] = useState<'ALL' | 'ACTIVE' | 'COMPLETED'>('ALL');
  const [selectedJob, setSelectedJob] = useState<Job | null>(null);

  const loadMyJobs = async (isInitial = false) => {
    if (isInitial || jobs.length === 0) {
      setIsLoading(true);
    }
    setErrorMessage(null);
    try {
      const data = await jobService.getMyJobs();
      setJobs(data);
    } catch (err: unknown) {
      console.error('Failed to load technician jobs', err);
      const msg = err instanceof Error ? err.message : 'Failed to load assigned jobs.';
      setErrorMessage(msg);
    } finally {
      setIsLoading(false);
    }
  };

  // Real-time synchronization for technician jobs
  useRealtimeSync(
    ['JOB_ASSIGNED', 'JOB_UNASSIGNED', 'JOB_STATUS_CHANGED', 'JOB_COMPLETED', 'JOB_CANCELLED'],
    () => {
      loadMyJobs(false);
    },
    () => loadMyJobs(false),
  );

  useEffect(() => {
    loadMyJobs(true);
    // Relaxed background polling fallback
    const interval = setInterval(() => loadMyJobs(false), 60000);
    return () => clearInterval(interval);
  }, []);

  const filteredJobs = jobs.filter((j) => {
    const matchesSearch =
      j.job_number.toLowerCase().includes(searchTerm.toLowerCase()) ||
      j.customer_name.toLowerCase().includes(searchTerm.toLowerCase()) ||
      j.address.toLowerCase().includes(searchTerm.toLowerCase());

    if (!matchesSearch) return false;

    if (statusFilter === 'ACTIVE') {
      return j.status !== 'COMPLETED' && j.status !== 'CANCELLED';
    }
    if (statusFilter === 'COMPLETED') {
      return j.status === 'COMPLETED';
    }
    return true;
  });

  const activeCount = jobs.filter((j) => j.status !== 'COMPLETED' && j.status !== 'CANCELLED').length;
  const completedCount = jobs.filter((j) => j.status === 'COMPLETED').length;

  return (
    <div className="flex flex-col gap-6 py-2 animate-fade-in select-none max-w-6xl mx-auto">
      {/* ── Page Header ── */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-slate-200 pb-5">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <span className="inline-flex items-center gap-1.5 rounded-full border border-emerald-200 bg-emerald-50 px-2.5 py-0.5 text-[11px] font-semibold text-emerald-700">
              <Briefcase className="h-3.5 w-3.5 text-emerald-600" />
              <span>Technician Work Orders</span>
            </span>
            <span className="inline-flex items-center gap-1 rounded-full border border-slate-200 bg-slate-100 px-2.5 py-0.5 text-[11px] font-medium text-slate-700">
              <Shield className="h-3 w-3 text-purple-600" />
              <span>{user?.role || 'Technician'}</span>
            </span>
            <RealtimeConnectionBadge />
          </div>

          <h1 className="text-2xl md:text-3xl font-extrabold tracking-tight text-slate-900">
            My Assigned Jobs
          </h1>
          <p className="text-xs md:text-sm text-slate-500 mt-0.5">
            Complete list of field service orders assigned to your profile by dispatchers.
          </p>
        </div>

        {/* Quick summary pill */}
        <div className="flex items-center gap-3 bg-white p-2.5 rounded-xl border border-slate-200 shadow-xs text-xs font-semibold text-slate-700">
          <div className="flex items-center gap-1.5">
            <span className="h-2 w-2 rounded-full bg-blue-600 animate-pulse" />
            <span>Active: <strong className="text-blue-700 font-extrabold">{activeCount}</strong></span>
          </div>
          <span className="text-slate-300">|</span>
          <div className="flex items-center gap-1.5">
            <CheckCircle2 className="h-4 w-4 text-emerald-600" />
            <span>Completed: <strong className="text-emerald-700 font-extrabold">{completedCount}</strong></span>
          </div>
        </div>
      </div>

      {errorMessage && (
        <div className="flex items-center gap-3 rounded-xl border border-rose-200 bg-rose-50 p-4 text-xs font-semibold text-rose-800 animate-shake">
          <AlertCircle className="h-5 w-5 shrink-0 text-rose-600" />
          <span>{errorMessage}</span>
        </div>
      )}

      {/* ── Search & Filters Bar ── */}
      <div className="flex flex-col sm:flex-row items-center justify-between gap-3 bg-white p-4 rounded-2xl border border-slate-200 shadow-xs">
        <div className="relative w-full sm:w-80">
          <Search className="absolute left-3.5 top-1/2 -translate-y-1/2 h-4 w-4 text-slate-400" />
          <input
            type="text"
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            placeholder="Search by job #, customer, address..."
            className="w-full rounded-xl border border-slate-200 bg-slate-50 pl-10 pr-4 py-2 text-xs text-slate-800 placeholder-slate-400 focus:border-blue-500 focus:bg-white focus:outline-none transition-all"
          />
          {searchTerm && (
            <button
              onClick={() => setSearchTerm('')}
              className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600"
            >
              <X className="h-3.5 w-3.5" />
            </button>
          )}
        </div>

        <div className="flex items-center gap-1 bg-slate-100 p-1 rounded-xl border border-slate-200 w-full sm:w-auto justify-center">
          <button
            onClick={() => setStatusFilter('ALL')}
            className={`px-3 py-1.5 rounded-lg text-xs font-bold transition-all cursor-pointer ${
              statusFilter === 'ALL'
                ? 'bg-white text-slate-900 shadow-xs'
                : 'text-slate-600 hover:text-slate-900'
            }`}
          >
            All ({jobs.length})
          </button>
          <button
            onClick={() => setStatusFilter('ACTIVE')}
            className={`px-3 py-1.5 rounded-lg text-xs font-bold transition-all cursor-pointer ${
              statusFilter === 'ACTIVE'
                ? 'bg-blue-600 text-white shadow-xs'
                : 'text-slate-600 hover:text-slate-900'
            }`}
          >
            Active ({activeCount})
          </button>
          <button
            onClick={() => setStatusFilter('COMPLETED')}
            className={`px-3 py-1.5 rounded-lg text-xs font-bold transition-all cursor-pointer ${
              statusFilter === 'COMPLETED'
                ? 'bg-emerald-600 text-white shadow-xs'
                : 'text-slate-600 hover:text-slate-900'
            }`}
          >
            Completed ({completedCount})
          </button>
        </div>
      </div>

      {/* ── Job Cards Directory ── */}
      {isLoading ? (
        <div className="rounded-2xl border border-slate-200 bg-white p-12 text-center text-xs text-slate-500">
          Loading assigned work orders...
        </div>
      ) : filteredJobs.length === 0 ? (
        <div className="rounded-2xl border border-slate-200 bg-white p-12 text-center text-xs text-slate-500 flex flex-col items-center gap-3">
          <CheckCircle2 className="h-10 w-10 text-slate-300" />
          <span className="text-sm font-bold text-slate-700">No matching work orders found</span>
          <span className="text-slate-400">Try clearing your search or status filters.</span>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {filteredJobs.map((j) => (
            <div
              key={j.id}
              onClick={() => setSelectedJob(j)}
              className="group rounded-2xl border border-slate-200 bg-white p-5 shadow-xs transition-all hover:border-blue-300 hover:shadow-md cursor-pointer space-y-4 relative overflow-hidden"
            >
              {/* Header */}
              <div className="flex items-start justify-between gap-3 border-b border-slate-100 pb-3">
                <div>
                  <div className="flex items-center gap-2 mb-1">
                    <span className="font-mono text-xs font-bold text-blue-700 bg-blue-50 px-2 py-0.5 rounded border border-blue-200">
                      {j.job_number}
                    </span>
                    <span
                      className={`text-[10px] font-extrabold uppercase px-2 py-0.5 rounded-full border ${
                        j.priority === 'CRITICAL'
                          ? 'bg-rose-50 text-rose-700 border-rose-200'
                          : j.priority === 'HIGH'
                          ? 'bg-amber-50 text-amber-700 border-amber-200'
                          : 'bg-slate-100 text-slate-700 border-slate-200'
                      }`}
                    >
                      {j.priority}
                    </span>
                    <span
                      className={`text-[10px] font-extrabold uppercase px-2 py-0.5 rounded-full border ${
                        j.status === 'COMPLETED'
                          ? 'bg-emerald-50 text-emerald-700 border-emerald-200'
                          : j.status === 'CANCELLED'
                          ? 'bg-slate-100 text-slate-500 border-slate-200'
                          : 'bg-purple-50 text-purple-700 border-purple-200'
                      }`}
                    >
                      {j.status}
                    </span>
                  </div>
                  <h3 className="text-base font-extrabold text-slate-900 group-hover:text-blue-600 transition-colors">
                    {j.customer_name}
                  </h3>
                </div>

                <ChevronRight className="h-5 w-5 text-slate-300 group-hover:text-blue-600 group-hover:translate-x-0.5 transition-all shrink-0 mt-1" />
              </div>

              {/* Body */}
              <div className="space-y-2 text-xs">
                <div className="flex items-start gap-2 text-slate-600">
                  <MapPin className="h-3.5 w-3.5 text-blue-600 shrink-0 mt-0.5" />
                  <span className="line-clamp-1">{j.address}</span>
                </div>

                <div className="flex items-center justify-between text-[11px] text-slate-500 pt-1 border-t border-slate-100">
                  <div className="flex items-center gap-1 font-medium">
                    <Wrench className="h-3 w-3 text-purple-600" />
                    <span>{j.required_skill?.skill_name || 'Standard Service'}</span>
                  </div>
                  <div className="flex items-center gap-1 font-mono text-slate-600">
                    <Calendar className="h-3 w-3 text-slate-400" />
                    <span>{j.scheduled_time ? formatDate(j.scheduled_time) : 'Asap'}</span>
                  </div>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* ── JOB DETAILS MODAL ── */}
      {selectedJob && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/40 backdrop-blur-sm p-4 animate-fade-in">
          <div className="w-full max-w-xl rounded-2xl border border-slate-200 bg-white p-6 shadow-2xl space-y-5 max-h-[90vh] overflow-y-auto">
            {/* Modal Header */}
            <div className="flex items-start justify-between border-b border-slate-100 pb-4">
              <div>
                <div className="flex items-center gap-2 mb-1">
                  <span className="font-mono text-xs font-bold text-blue-700 bg-blue-50 px-2.5 py-0.5 rounded border border-blue-200">
                    {selectedJob.job_number}
                  </span>
                  <span className="text-[10px] font-extrabold uppercase px-2.5 py-0.5 rounded-full bg-purple-50 text-purple-700 border border-purple-200">
                    STATUS: {selectedJob.status}
                  </span>
                  <span className="text-[10px] font-extrabold uppercase px-2.5 py-0.5 rounded-full bg-amber-50 text-amber-700 border border-amber-200">
                    {selectedJob.priority} PRIORITY
                  </span>
                </div>
                <h2 className="text-xl font-extrabold text-slate-900">{selectedJob.customer_name}</h2>
              </div>
              <button
                onClick={() => setSelectedJob(null)}
                className="rounded-lg p-1.5 text-slate-400 hover:bg-slate-100 hover:text-slate-700 cursor-pointer"
              >
                <X className="h-5 w-5" />
              </button>
            </div>

            {/* Modal Body Details */}
            <div className="space-y-4 text-xs">
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <div className="rounded-xl border border-slate-200 bg-slate-50 p-3.5 space-y-1">
                  <div className="flex items-center gap-1.5 text-slate-500 font-bold uppercase text-[10px]">
                    <MapPin className="h-3.5 w-3.5 text-blue-600" />
                    <span>Service Location</span>
                  </div>
                  <p className="font-semibold text-slate-800 leading-relaxed">{selectedJob.address}</p>
                </div>

                <div className="rounded-xl border border-slate-200 bg-slate-50 p-3.5 space-y-1">
                  <div className="flex items-center gap-1.5 text-slate-500 font-bold uppercase text-[10px]">
                    <Phone className="h-3.5 w-3.5 text-emerald-600" />
                    <span>Customer Contact</span>
                  </div>
                  <p className="font-semibold text-slate-800">
                    {selectedJob.customer_phone || 'No phone recorded'}
                  </p>
                </div>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <div className="rounded-xl border border-slate-200 bg-slate-50 p-3.5 space-y-1">
                  <div className="flex items-center gap-1.5 text-slate-500 font-bold uppercase text-[10px]">
                    <Sparkles className="h-3.5 w-3.5 text-purple-600" />
                    <span>Required Skill Qualification</span>
                  </div>
                  <p className="font-semibold text-slate-800">
                    {selectedJob.required_skill?.skill_name || 'Standard Field Operation'}
                  </p>
                </div>

                <div className="rounded-xl border border-slate-200 bg-slate-50 p-3.5 space-y-1">
                  <div className="flex items-center gap-1.5 text-slate-500 font-bold uppercase text-[10px]">
                    <Clock className="h-3.5 w-3.5 text-amber-600" />
                    <span>Scheduled Time</span>
                  </div>
                  <p className="font-semibold text-slate-800">
                    {selectedJob.scheduled_time ? formatDate(selectedJob.scheduled_time) : 'Asap Dispatch'}
                  </p>
                </div>
              </div>

              {selectedJob.description && (
                <div className="rounded-xl border border-slate-200 bg-slate-50 p-3.5 space-y-1">
                  <div className="flex items-center gap-1.5 text-slate-500 font-bold uppercase text-[10px]">
                    <FileText className="h-3.5 w-3.5 text-blue-600" />
                    <span>Dispatch Instructions</span>
                  </div>
                  <p className="text-slate-700 leading-relaxed">{selectedJob.description}</p>
                </div>
              )}

              {selectedJob.creator && (
                <div className="text-[11px] text-slate-500 italic pt-1">
                  Dispatched by: <strong className="text-slate-700">{selectedJob.creator.full_name}</strong> ({selectedJob.creator.email})
                </div>
              )}
            </div>

            {/* Modal Actions */}
            <div className="flex items-center justify-end border-t border-slate-100 pt-4">
              <button
                onClick={() => setSelectedJob(null)}
                className="rounded-xl bg-slate-900 px-5 py-2.5 text-xs font-bold text-white hover:bg-slate-800 cursor-pointer"
              >
                Close Details
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
