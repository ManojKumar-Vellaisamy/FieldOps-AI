import { useState, useEffect, useCallback } from 'react';
import {
  Sparkles,
  UserCheck,
  CheckCircle2,
  AlertCircle,
  Wrench,
  Layers,
  RefreshCw,
  X,
} from 'lucide-react';
import { assignmentService } from '@/services/assignment.service';
import type { AssignmentRecommendationResponse, CandidateTechnician } from '@/types/assignment.types';
import type { Job } from '@/types/job.types';
import { cn } from '@/utils/cn';

interface SmartAssignmentSectionProps {
  unassignedJobs: Job[];
  onAssignmentComplete: () => void;
  className?: string | undefined;
}

export function SmartAssignmentSection({
  unassignedJobs,
  onAssignmentComplete,
  className,
}: SmartAssignmentSectionProps) {
  const [selectedJobId, setSelectedJobId] = useState<string>('');
  const [recommendation, setRecommendation] = useState<AssignmentRecommendationResponse | null>(null);
  const [selectedCandidate, setSelectedCandidate] = useState<CandidateTechnician | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [isAssigning, setIsAssigning] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [showConfirmModal, setShowConfirmModal] = useState<boolean>(false);

  // Sync selected job ID when list changes
  useEffect(() => {
    if (unassignedJobs.length > 0) {
      if (!selectedJobId || !unassignedJobs.find((j) => j.id === selectedJobId)) {
        const first = unassignedJobs[0];
        if (first) {
          setSelectedJobId(first.id);
        }
      }
    } else {
      setSelectedJobId('');
      setRecommendation(null);
      setSelectedCandidate(null);
    }
  }, [unassignedJobs, selectedJobId]);

  const loadRecommendation = useCallback(async (jobId: string) => {
    if (!jobId) return;
    setIsLoading(true);
    setError(null);
    try {
      const data = await assignmentService.getAssignmentRecommendations(jobId);
      setRecommendation(data);
      setSelectedCandidate(data.recommended_technician || null);
    } catch (err: unknown) {
      console.error('Failed to load recommendation', err);
      const msg = err instanceof Error ? err.message : 'Could not generate assignment recommendation.';
      setError(msg);
      setRecommendation(null);
      setSelectedCandidate(null);
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    if (selectedJobId) {
      loadRecommendation(selectedJobId);
    }
  }, [selectedJobId, loadRecommendation]);

  const handleConfirmAssignment = async () => {
    if (!selectedJobId || !selectedCandidate) return;
    setIsAssigning(true);
    try {
      await assignmentService.assignTechnician(selectedJobId, selectedCandidate.technician_id);
      setShowConfirmModal(false);
      onAssignmentComplete();
    } catch (err: unknown) {
      console.error('Assignment failed', err);
      const msg = err instanceof Error ? err.message : 'Failed to confirm technician assignment.';
      alert(`Assignment Error: ${msg}`);
    } finally {
      setIsAssigning(false);
    }
  };

  const currentJob = unassignedJobs.find((j) => j.id === selectedJobId);

  // All jobs assigned state
  if (unassignedJobs.length === 0) {
    return (
      <div
        className={cn(
          'rounded-2xl border border-slate-200 bg-white p-6 shadow-xs select-none',
          className,
        )}
      >
        <div className="flex items-center gap-2 mb-3">
          <span className="inline-flex items-center gap-1.5 rounded-full border border-purple-200 bg-purple-50 px-2.5 py-0.5 text-[11px] font-bold text-purple-700">
            <Sparkles className="h-3 w-3 text-purple-600" />
            <span>Smart Assignment Engine</span>
          </span>
          <span className="rounded bg-emerald-50 border border-emerald-200 px-2 py-0.5 text-[10px] font-mono font-bold text-emerald-700">
            100% Dispatched
          </span>
        </div>

        <div className="rounded-xl border border-slate-200 bg-slate-50 p-8 text-center flex flex-col items-center justify-center gap-2">
          <CheckCircle2 className="h-10 w-10 text-emerald-600" />
          <h4 className="text-base font-extrabold text-slate-900">All Service Jobs Dispatched</h4>
          <p className="text-xs text-slate-600 max-w-md">
            There are currently no unassigned work orders in the queue. Create a new service job or monitor active
            technician progress.
          </p>
        </div>
      </div>
    );
  }

  return (
    <div
      className={cn(
        'rounded-2xl border border-purple-200 bg-white p-6 shadow-xs space-y-5 select-none relative overflow-hidden',
        className,
      )}
    >
      {/* ── Section Header ── */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-slate-100 pb-4">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <span className="inline-flex items-center gap-1.5 rounded-full border border-purple-200 bg-purple-50 px-2.5 py-0.5 text-[11px] font-bold text-purple-700">
              <Sparkles className="h-3.5 w-3.5 text-purple-600" />
              <span>Smart Assignment Engine</span>
            </span>
            <span className="rounded bg-slate-100 border border-slate-200 px-2 py-0.5 text-[10px] font-mono font-bold text-slate-600">
              Module 9
            </span>
          </div>
          <h3 className="text-lg font-extrabold text-slate-900 tracking-tight">AI &amp; Rule-Based Technician Match</h3>
          <p className="text-xs text-slate-500">
            Real-time candidate evaluation based on active status, skill certification, backlog, and proximity.
          </p>
        </div>

        <div className="flex items-center gap-2">
          {/* Job Selector Dropdown */}
          <div className="flex items-center gap-1.5 text-xs text-slate-700">
            <span className="text-[11px] text-slate-500 font-bold">Job:</span>
            <select
              value={selectedJobId}
              onChange={(e) => setSelectedJobId(e.target.value)}
              className="rounded-lg border border-slate-200 bg-slate-50 px-2.5 py-1.5 text-xs font-mono font-bold text-blue-700 focus:border-purple-500 focus:bg-white focus:outline-none"
            >
              {unassignedJobs.map((job) => (
                <option key={job.id} value={job.id}>
                  {job.job_number} — {job.customer_name} ({job.priority})
                </option>
              ))}
            </select>
          </div>

          <button
            onClick={() => loadRecommendation(selectedJobId)}
            disabled={isLoading}
            title="Refresh Candidate Recommendations"
            className="p-1.5 rounded-lg border border-slate-200 bg-slate-50 text-slate-600 hover:text-slate-900 hover:bg-slate-100 transition-colors disabled:opacity-50"
          >
            <RefreshCw className={cn('h-3.5 w-3.5', isLoading && 'animate-spin')} />
          </button>
        </div>
      </div>

      {/* ── Selected Job Summary Card ── */}
      {currentJob && (
        <div className="rounded-xl border border-slate-200 bg-slate-50 p-3.5 text-xs grid grid-cols-2 sm:grid-cols-4 gap-3">
          <div>
            <span className="text-[10px] uppercase font-bold text-slate-500 tracking-wider block">Customer</span>
            <span className="font-bold text-slate-900 truncate block">{currentJob.customer_name}</span>
            <span className="text-[10px] text-slate-500 truncate block">{currentJob.customer_phone || 'No phone'}</span>
          </div>

          <div>
            <span className="text-[10px] uppercase font-bold text-slate-500 tracking-wider block">Required Skill</span>
            <span className="inline-flex items-center gap-1 rounded bg-purple-50 border border-purple-200 px-1.5 py-0.5 text-[11px] font-bold text-purple-700 mt-0.5">
              <Wrench className="h-3 w-3" />
              <span>{currentJob.required_skill?.skill_name || 'N/A'}</span>
            </span>
          </div>

          <div>
            <span className="text-[10px] uppercase font-bold text-slate-500 tracking-wider block">Priority</span>
            <span
              className={cn(
                'inline-flex items-center rounded px-1.5 py-0.5 text-[10px] font-extrabold border mt-0.5',
                currentJob.priority === 'CRITICAL'
                  ? 'bg-rose-50 border-rose-200 text-rose-800'
                  : currentJob.priority === 'HIGH'
                    ? 'bg-amber-50 border-amber-200 text-amber-900'
                    : 'bg-blue-50 border-blue-200 text-blue-800',
              )}
            >
              {currentJob.priority}
            </span>
          </div>

          <div>
            <span className="text-[10px] uppercase font-bold text-slate-500 tracking-wider block">Service Address</span>
            <span className="text-slate-700 truncate block text-[11px] font-medium" title={currentJob.address}>
              {currentJob.address}
            </span>
          </div>
        </div>
      )}

      {/* ── Main Recommendation Workspace ── */}
      {isLoading ? (
        <div className="py-12 text-center text-xs text-slate-500 flex flex-col items-center justify-center gap-3 animate-pulse font-medium">
          <Sparkles className="h-8 w-8 text-purple-600 animate-spin" />
          <span className="font-bold text-slate-800">Evaluating technician candidate pool...</span>
          <span className="text-[11px] text-slate-500">
            Checking certifications, real-time availability, and active job backlogs.
          </span>
        </div>
      ) : error ? (
        <div className="rounded-xl border border-rose-200 bg-rose-50 p-4 text-xs text-rose-800 flex items-center gap-2 font-bold">
          <AlertCircle className="h-4 w-4 shrink-0 text-rose-600" />
          <span>{error}</span>
        </div>
      ) : recommendation?.recommended_technician ? (
        <div className="space-y-4">
          {/* Top Recommended Card */}
          <div className="rounded-2xl border-2 border-purple-300 bg-gradient-to-br from-purple-50/60 via-white to-slate-50 p-5 shadow-xs space-y-4">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-purple-100 pb-3">
              <div className="flex items-center gap-3">
                <div className="h-12 w-12 rounded-xl bg-purple-100 border border-purple-200 flex items-center justify-center text-purple-800 font-extrabold text-base font-mono">
                  {recommendation.recommended_technician.employee_code.replace('TECH-', '#')}
                </div>
                <div>
                  <div className="flex items-center gap-2">
                    <span className="text-[10px] font-extrabold uppercase tracking-wider text-purple-700">
                      Recommended Technician
                    </span>
                    <span className="rounded-full bg-emerald-50 border border-emerald-200 px-2 py-0.2 text-[9px] font-bold text-emerald-700">
                      Available Now
                    </span>
                  </div>
                  <h4 className="text-lg font-black text-slate-900">
                    {recommendation.recommended_technician.full_name}
                  </h4>
                  <div className="flex items-center gap-2 text-[11px] text-slate-500 mt-0.5">
                    <span className="text-purple-700 font-bold">
                      {recommendation.recommended_technician.primary_skill_name || 'Certified Tech'} • Certified
                    </span>
                    <span>•</span>
                    <span className="font-mono">{recommendation.recommended_technician.employee_code}</span>
                  </div>
                </div>
              </div>

              {/* Match Score Badge */}
              <div className="flex items-center gap-4 sm:text-right">
                <div>
                  <span className="text-[10px] font-bold uppercase tracking-wider text-slate-500 block">
                    Match Score
                  </span>
                  <div className="text-2xl sm:text-3xl font-black text-purple-700 font-mono flex items-baseline gap-0.5">
                    <span>{Math.round(recommendation.recommended_technician.recommendation_score)}</span>
                    <span className="text-sm font-bold text-purple-600">%</span>
                  </div>
                </div>

                <button
                  onClick={() => {
                    setSelectedCandidate(recommendation.recommended_technician!);
                    setShowConfirmModal(true);
                  }}
                  className="rounded-xl bg-purple-600 hover:bg-purple-700 px-5 py-2.5 text-xs font-extrabold text-white shadow-xs transition-all active:scale-[0.98] flex items-center gap-2"
                >
                  <UserCheck className="h-4 w-4" />
                  <span>Assign Technician</span>
                </button>
              </div>
            </div>

            {/* Why This Technician? Breakdown */}
            <div className="space-y-2">
              <span className="text-[11px] font-bold uppercase tracking-wider text-slate-700 flex items-center gap-1.5">
                <CheckCircle2 className="h-3.5 w-3.5 text-emerald-600" />
                <span>Why this technician?</span>
              </span>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 text-xs">
                {recommendation.recommended_technician.explanation_reasons.map((reason, idx) => (
                  <div
                    key={idx}
                    className="flex items-center gap-2 rounded-lg bg-white border border-slate-200 px-3 py-1.5 text-slate-700 font-medium"
                  >
                    <span className="text-emerald-600 font-extrabold">✓</span>
                    <span>{reason}</span>
                  </div>
                ))}
              </div>
            </div>
          </div>

          {/* ── Alternative Eligible Technicians ── */}
          {recommendation.alternative_technicians && recommendation.alternative_technicians.length > 0 && (
            <div className="rounded-xl border border-slate-200 bg-slate-50 p-4 space-y-3">
              <div className="flex items-center justify-between">
                <span className="text-xs font-bold uppercase tracking-wider text-slate-700 flex items-center gap-1.5">
                  <Layers className="h-3.5 w-3.5 text-blue-600" />
                  <span>Alternative Eligible Candidates ({recommendation.alternative_technicians.length})</span>
                </span>
                <span className="text-[10px] text-slate-500 font-medium">Ranked by explainable scoring</span>
              </div>

              <div className="space-y-2">
                {recommendation.alternative_technicians.map((alt) => (
                  <div
                    key={alt.technician_id}
                    className="flex items-center justify-between gap-3 rounded-lg border border-slate-200 bg-white p-3 hover:border-slate-300 transition-all text-xs shadow-2xs"
                  >
                    <div className="flex items-center gap-3">
                      <span className="h-6 w-6 rounded-md bg-slate-100 flex items-center justify-center font-mono text-[10px] font-bold text-slate-600 border border-slate-200">
                        #{alt.ranking}
                      </span>
                      <div>
                        <div className="font-bold text-slate-900 flex items-center gap-2">
                          <span>{alt.full_name}</span>
                          <span className="text-[10px] text-slate-500 font-mono">({alt.employee_code})</span>
                        </div>
                        <div className="text-[11px] text-slate-500 flex items-center gap-2 mt-0.5">
                          <span className="text-purple-700 font-bold">{alt.primary_skill_name}</span>
                          <span>•</span>
                          <span>Active Workload: {alt.current_workload} jobs</span>
                        </div>
                      </div>
                    </div>

                    <div className="flex items-center gap-3">
                      <div className="text-right">
                        <span className="text-sm font-black font-mono text-slate-800">
                          {Math.round(alt.recommendation_score)}%
                        </span>
                        <span className="text-[10px] text-slate-500 block font-medium">Match</span>
                      </div>

                      <button
                        onClick={() => {
                          setSelectedCandidate(alt);
                          setShowConfirmModal(true);
                        }}
                        className="rounded-lg bg-white hover:bg-slate-50 border border-slate-300 px-3 py-1.5 text-[11px] font-bold text-slate-700 hover:text-slate-900 transition-all active:scale-95 shadow-2xs"
                      >
                        Assign
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      ) : (
        <div className="rounded-xl border border-amber-200 bg-amber-50 p-6 text-center space-y-2 text-xs">
          <AlertCircle className="h-8 w-8 text-amber-600 mx-auto" />
          <h4 className="font-bold text-amber-900 text-sm">No Certified Technicians Available</h4>
          <p className="text-slate-600 max-w-md mx-auto">
            {recommendation?.explanation ||
              'No active technicians hold certification for this job’s required skill, or all certified technicians are currently busy.'}
          </p>
        </div>
      )}

      {/* ── Dispatcher Explicit Confirmation Modal ── */}
      {showConfirmModal && selectedCandidate && currentJob && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/40 backdrop-blur-xs p-4 animate-fade-in">
          <div className="relative w-full max-w-md rounded-2xl border border-purple-200 bg-white p-6 shadow-2xl space-y-4 text-xs">
            <div className="flex items-center justify-between border-b border-slate-100 pb-3">
              <div className="flex items-center gap-2">
                <Sparkles className="h-4 w-4 text-purple-600" />
                <h3 className="text-base font-extrabold text-slate-900">Confirm Technician Assignment</h3>
              </div>
              <button
                onClick={() => setShowConfirmModal(false)}
                disabled={isAssigning}
                className="text-slate-400 hover:text-slate-700 p-1"
              >
                <X className="h-4 w-4" />
              </button>
            </div>

            <p className="text-slate-600 leading-relaxed">
              You are about to assign technician <strong className="text-purple-700">{selectedCandidate.full_name}</strong> to
              work order <strong className="text-blue-600">{currentJob.job_number}</strong>.
            </p>

            <div className="rounded-xl border border-slate-200 bg-slate-50 p-3.5 space-y-2">
              <div className="flex justify-between py-0.5 border-b border-slate-200/60">
                <span className="text-slate-500">Work Order:</span>
                <span className="font-mono font-bold text-slate-800">{currentJob.job_number}</span>
              </div>
              <div className="flex justify-between py-0.5 border-b border-slate-200/60">
                <span className="text-slate-500">Customer:</span>
                <span className="font-bold text-slate-800">{currentJob.customer_name}</span>
              </div>
              <div className="flex justify-between py-0.5 border-b border-slate-200/60">
                <span className="text-slate-500">Required Skill:</span>
                <span className="text-purple-700 font-bold">
                  {currentJob.required_skill?.skill_name || 'N/A'}
                </span>
              </div>
              <div className="flex justify-between py-0.5 border-b border-slate-200/60">
                <span className="text-slate-500">Assigned Technician:</span>
                <span className="font-bold text-slate-900">
                  {selectedCandidate.full_name} ({selectedCandidate.employee_code})
                </span>
              </div>
              <div className="flex justify-between py-0.5">
                <span className="text-slate-500">AI Match Score:</span>
                <span className="font-mono font-black text-purple-700">
                  {Math.round(selectedCandidate.recommendation_score)}%
                </span>
              </div>
            </div>

            <p className="text-[11px] text-slate-500 italic leading-relaxed">
              This action transitions the job status to ASSIGNED, generates an immutable TECHNICIAN_ASSIGNED audit event,
              and activates real-time transit ETA telemetry.
            </p>

            <div className="flex justify-end gap-2.5 pt-3 border-t border-slate-100">
              <button
                type="button"
                onClick={() => setShowConfirmModal(false)}
                disabled={isAssigning}
                className="rounded-xl border border-slate-200 bg-slate-50 px-4 py-2 text-xs font-semibold text-slate-700 hover:bg-slate-100 transition-colors disabled:opacity-50"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={handleConfirmAssignment}
                disabled={isAssigning}
                className="rounded-xl bg-purple-600 hover:bg-purple-700 px-5 py-2 text-xs font-bold text-white shadow-xs transition-all active:scale-[0.98] disabled:opacity-50 flex items-center gap-1.5"
              >
                {isAssigning ? (
                  <>
                    <RefreshCw className="h-3.5 w-3.5 animate-spin" />
                    <span>Assigning...</span>
                  </>
                ) : (
                  <>
                    <UserCheck className="h-3.5 w-3.5" />
                    <span>Confirm Assignment</span>
                  </>
                )}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
