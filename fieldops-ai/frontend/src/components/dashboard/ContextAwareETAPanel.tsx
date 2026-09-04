import { useState, useEffect, useCallback } from 'react';
import {
  Clock,
  Navigation,
  CloudRain,
  Sparkles,
  AlertTriangle,
  RefreshCw,
  Info,
  Layers,
  Radio,
  CalendarX,
  ShieldAlert,
  MapPin,
  CheckCircle2,
  XCircle,
  AlertCircle,
  Minus,
  Edit3,
  Award,
  Check,
} from 'lucide-react';
import { etaService } from '@/services/eta.service';
import type { ETAResponse, DataSource, ETAExperimentMetrics } from '@/types/eta.types';
import type { Job } from '@/types/job.types';
import { cn } from '@/utils/cn';
import { formatDate } from '@/utils/format';

interface ContextAwareETAPanelProps {
  jobs: Job[];
  selectedJobId?: string | undefined;
  onSelectJob?: ((jobId: string) => void) | undefined;
  className?: string | undefined;
}

const OVERRIDE_REASONS = [
  'Road closure not reflected in provider',
  'Local traffic knowledge',
  'Customer priority',
  'Emergency dispatch',
  'Temporary access restriction',
  'Other',
];

function getSourceIcon(category: string, className?: string) {
  const cls = cn('h-3.5 w-3.5 shrink-0', className);
  switch (category.toUpperCase()) {
    case 'GPS':      return <Navigation className={cls} />;
    case 'WEATHER':  return <CloudRain className={cls} />;
    case 'TRAFFIC':  return <Radio className={cls} />;
    case 'EVENTS':   return <CalendarX className={cls} />;
    case 'ROAD':     return <ShieldAlert className={cls} />;
    default:         return <Layers className={cls} />;
  }
}

function StatusIcon({ status }: { status: string }) {
  switch (status) {
    case 'AVAILABLE':
      return <CheckCircle2 className="h-3.5 w-3.5 text-emerald-600 shrink-0" />;
    case 'STALE':
      return <AlertCircle className="h-3.5 w-3.5 text-amber-600 shrink-0" />;
    case 'UNAVAILABLE':
      return <Minus className="h-3.5 w-3.5 text-slate-400 shrink-0" />;
    case 'INVALID':
      return <XCircle className="h-3.5 w-3.5 text-rose-600 shrink-0" />;
    default:
      return <Minus className="h-3.5 w-3.5 text-slate-400 shrink-0" />;
  }
}

function statusColor(status: string): string {
  switch (status) {
    case 'AVAILABLE':   return 'text-emerald-600';
    case 'STALE':       return 'text-amber-600';
    case 'UNAVAILABLE': return 'text-slate-400';
    case 'INVALID':     return 'text-rose-600';
    default:            return 'text-slate-400';
  }
}

function formatArrivalTime(isoString: string | null): string {
  if (!isoString) return '—';
  try {
    const dt = new Date(isoString);
    return dt.toLocaleTimeString('en-US', {
      hour: '2-digit',
      minute: '2-digit',
      timeZoneName: 'short',
    });
  } catch {
    return '—';
  }
}

function DataSourceRow({ source }: { source: DataSource }) {
  return (
    <div className="flex items-center justify-between py-1.5 px-2.5 rounded-lg bg-slate-50 border border-slate-200">
      <div className="flex items-center gap-2 min-w-0">
        {getSourceIcon(source.category, statusColor(source.status))}
        <span className="text-[11px] font-bold text-slate-800 truncate">{source.name}</span>
      </div>
      <div className="flex items-center gap-2 shrink-0 ml-2">
        {source.impact_minutes > 0 && (
          <span className="font-mono text-[10px] font-extrabold text-amber-700">
            +{source.impact_minutes}m
          </span>
        )}
        <div className="flex items-center gap-1">
          <StatusIcon status={source.status} />
          <span className={cn('text-[10px] font-bold uppercase tracking-wider', statusColor(source.status))}>
            {source.status === 'UNAVAILABLE' ? '—' : source.status.slice(0, 4)}
          </span>
        </div>
      </div>
    </div>
  );
}

export function ContextAwareETAPanel({
  jobs,
  selectedJobId,
  onSelectJob,
  className,
}: ContextAwareETAPanelProps) {
  const activeJobs = jobs.filter((j) => j.status !== 'COMPLETED' && j.status !== 'CANCELLED');
  const defaultTarget = activeJobs.length > 0 ? activeJobs[0] : jobs.length > 0 ? jobs[0] : null;

  const [activeJobId, setActiveJobId] = useState<string | null>(
    selectedJobId || (defaultTarget ? defaultTarget.id : null),
  );
  const [etaData, setEtaData] = useState<ETAResponse | null>(null);
  const [metrics, setMetrics] = useState<ETAExperimentMetrics | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  // Dispatcher override state
  const [overrideInput, setOverrideInput] = useState<string>('');
  const [overrideReasonSelect, setOverrideReasonSelect] = useState<string>(OVERRIDE_REASONS[0] || 'Local traffic knowledge');
  const [overrideReasonCustom, setOverrideReasonCustom] = useState<string>('');
  const [isSubmittingOverride, setIsSubmittingOverride] = useState<boolean>(false);
  const [overrideSuccessMsg, setOverrideSuccessMsg] = useState<string | null>(null);

  useEffect(() => {
    if (selectedJobId) {
      setActiveJobId(selectedJobId);
    } else if (!activeJobId && defaultTarget) {
      setActiveJobId(defaultTarget.id);
    }
  }, [selectedJobId, defaultTarget]);

  const loadEta = useCallback(async (jobId: string) => {
    setIsLoading(true);
    setError(null);
    try {
      const data = await etaService.getJobEta(jobId);
      setEtaData(data);
      if (data.active_override) {
        setOverrideInput(data.active_override.overridden_eta.toString());
      } else if (data.context_aware_eta_minutes) {
        setOverrideInput(data.context_aware_eta_minutes.toString());
      }
    } catch (err: unknown) {
      console.error('Failed to calculate Context-Aware ETA', err);
      const msg = err instanceof Error ? err.message : 'Failed to retrieve ETA calculation.';
      setError(msg);
      setEtaData(null);
    } finally {
      setIsLoading(false);
    }
  }, []);

  const loadMetrics = useCallback(async () => {
    try {
      const data = await etaService.getExperimentMetrics();
      setMetrics(data);
    } catch (err) {
      console.error('Failed to load ETA experiment metrics', err);
    }
  }, []);

  useEffect(() => {
    if (activeJobId) {
      loadEta(activeJobId);
    }
    loadMetrics();
  }, [activeJobId, loadEta, loadMetrics]);

  const handleApplyOverride = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!activeJobId) return;
    const minutes = parseInt(overrideInput, 10);
    if (isNaN(minutes) || minutes <= 0) {
      setError('Please enter a valid override ETA in minutes.');
      return;
    }

    const finalReason =
      overrideReasonSelect === 'Other'
        ? overrideReasonCustom.trim()
        : overrideReasonSelect;

    if (!finalReason) {
      setError('Please select or specify a reason for the manual override.');
      return;
    }

    setIsSubmittingOverride(true);
    setError(null);
    try {
      await etaService.createOverride(activeJobId, {
        overridden_eta: minutes,
        reason: finalReason,
      });
      setOverrideSuccessMsg(`Dispatcher override applied (${minutes} min).`);
      setTimeout(() => setOverrideSuccessMsg(null), 4000);
      await loadEta(activeJobId);
    } catch (err: unknown) {
      console.error('Failed to submit dispatcher override', err);
      const msg = err instanceof Error ? err.message : 'Failed to submit dispatcher override.';
      setError(msg);
    } finally {
      setIsSubmittingOverride(false);
    }
  };

  const currentJob = jobs.find((j) => j.id === activeJobId) || defaultTarget;

  return (
    <div
      className={cn(
        'rounded-xl border border-slate-200 bg-white p-5 shadow-xs flex flex-col justify-between select-none relative overflow-hidden space-y-5',
        className,
      )}
    >
      {/* Header */}
      <div>
        <div className="flex flex-wrap items-center justify-between gap-2 border-b border-slate-100 pb-3 mb-4">
          <div className="flex items-center gap-2">
            <span className="inline-flex items-center gap-1.5 rounded-full border border-blue-200 bg-blue-50 px-2.5 py-1 text-xs font-bold text-blue-700">
              <Navigation className="h-3.5 w-3.5 text-blue-600" />
              <span>Context-Aware ETA Engine</span>
            </span>
            <span className="rounded-md border border-slate-200 bg-slate-100 px-2 py-0.5 text-[10px] font-mono font-bold text-slate-600">
              Module 11
            </span>
          </div>

          <div className="flex items-center gap-2">
            {jobs.length > 1 && (
              <select
                aria-label="Select job for ETA evaluation"
                value={activeJobId || ''}
                onChange={(e) => {
                  setActiveJobId(e.target.value);
                  if (onSelectJob) onSelectJob(e.target.value);
                }}
                className="rounded-lg border border-slate-200 bg-slate-50 px-2.5 py-1 text-[11px] font-bold text-slate-800 focus:border-blue-500 focus:bg-white focus:outline-none"
              >
                {jobs.map((j) => (
                  <option key={j.id} value={j.id}>
                    {j.job_number} — {j.customer_name.slice(0, 18)}
                  </option>
                ))}
              </select>
            )}

            <button
              onClick={() => activeJobId && loadEta(activeJobId)}
              title="Recalculate Context ETA"
              disabled={isLoading || !activeJobId}
              className="flex items-center gap-1 rounded-lg border border-slate-200 bg-slate-50 p-1.5 text-slate-600 hover:bg-slate-100 hover:text-slate-900 transition-colors disabled:opacity-50"
            >
              <RefreshCw className={cn('h-3.5 w-3.5', isLoading && 'animate-spin')} />
            </button>
          </div>
        </div>

        {/* Current Job Identification */}
        {currentJob && (
          <div className="flex items-center justify-between text-xs mb-4 text-slate-500 px-1">
            <div className="flex items-center gap-2 truncate">
              <span className="font-mono font-bold text-blue-600">{currentJob.job_number}</span>
              <span className="text-slate-700 font-bold truncate">{currentJob.customer_name}</span>
            </div>
            <span
              className={cn(
                'rounded-full px-2 py-0.5 text-[10px] font-bold border',
                currentJob.status === 'ASSIGNED' || currentJob.status === 'TRAVELLING'
                  ? 'bg-blue-50 border-blue-200 text-blue-800'
                  : 'bg-slate-100 border-slate-200 text-slate-600',
              )}
            >
              {currentJob.status}
            </span>
          </div>
        )}

        {/* Main Content State */}
        {isLoading ? (
          <div className="rounded-lg border border-slate-200 bg-slate-50 p-8 text-center space-y-2">
            <div className="flex justify-center">
              <RefreshCw className="h-6 w-6 text-blue-600 animate-spin" />
            </div>
            <div className="text-xs font-bold text-slate-800">Evaluating Context Data Providers...</div>
            <p className="text-[11px] text-slate-500 font-medium">Checking GPS, weather, traffic, events, and road restrictions</p>
          </div>
        ) : error ? (
          <div className="rounded-lg border border-rose-200 bg-rose-50 p-4 text-center space-y-1 text-xs text-rose-800 font-bold">
            <AlertTriangle className="h-5 w-5 text-rose-600 mx-auto mb-1" />
            <div className="font-extrabold">ETA Engine Error</div>
            <p className="text-[11px] text-slate-600">{error}</p>
          </div>
        ) : !currentJob ? (
          <div className="rounded-lg border border-slate-200 bg-slate-50 p-8 text-center space-y-2">
            <Clock className="h-8 w-8 text-slate-400 mx-auto" />
            <div className="text-xs font-bold text-slate-800">No Service Jobs Available</div>
            <p className="text-[11px] text-slate-500">Select a job to compute context-aware ETA.</p>
          </div>
        ) : etaData && !etaData.is_context_sufficient ? (
          /* Missing Context State */
          <div className="space-y-4">
            <div className="rounded-lg border border-amber-200 bg-amber-50 p-4 space-y-3">
              <div className="flex items-center gap-2 text-amber-800">
                <AlertTriangle className="h-4 w-4 shrink-0 text-amber-600" />
                <span className="text-xs font-extrabold uppercase tracking-wider">ETA Unavailable</span>
              </div>
              <p className="text-xs font-bold text-slate-800">{etaData.reason}</p>
              {etaData.missing_context.length > 0 && (
                <div className="space-y-1.5 pt-1 border-t border-amber-200">
                  <span className="text-[10px] font-bold uppercase text-amber-900 tracking-wider block">
                    Missing Prerequisites:
                  </span>
                  <ul className="text-[11px] text-slate-700 space-y-1 list-disc list-inside font-medium">
                    {etaData.missing_context.map((item, idx) => (
                      <li key={idx}>{item}</li>
                    ))}
                  </ul>
                </div>
              )}
            </div>

            {etaData.data_sources && etaData.data_sources.length > 0 && (
              <DataSourcesPanel sources={etaData.data_sources} />
            )}
          </div>
        ) : etaData ? (
          /* Sufficient Context — Primary ETA Panels */
          <div className="space-y-4">
            {/* Primary ETA Numbers Grid */}
            <div className="grid grid-cols-3 gap-2">
              {/* Baseline ETA */}
              <div className="rounded-lg border border-slate-200 bg-slate-50 p-3 text-center">
                <div className="text-[10px] uppercase font-bold text-slate-500 tracking-wider">
                  Baseline
                </div>
                <div className="mt-1 text-2xl font-black text-slate-900 font-mono">
                  {etaData.baseline_eta_minutes}
                  <span className="text-xs font-normal text-slate-500"> min</span>
                </div>
                <div className="mt-0.5 text-[10px] text-slate-500 font-medium">Unobstructed</div>
              </div>

              {/* Context-Aware ETA */}
              <div className="rounded-lg border border-blue-200 bg-blue-50 p-3 text-center shadow-2xs">
                <div className="text-[10px] uppercase font-extrabold text-blue-700 tracking-wider flex items-center justify-center gap-1">
                  <Sparkles className="h-3 w-3 text-blue-600" />
                  <span>Context ETA</span>
                </div>
                <div className="mt-1 text-2xl font-black text-blue-700 font-mono">
                  {etaData.context_aware_eta_minutes}
                  <span className="text-xs font-bold text-blue-600"> min</span>
                </div>
                <div className="mt-0.5 text-[10px] text-blue-700 font-bold">Operational</div>
              </div>

              {/* Adjustment */}
              <div className="rounded-lg border border-slate-200 bg-slate-50 p-3 text-center">
                <div className="text-[10px] uppercase font-bold text-slate-500 tracking-wider">
                  Adjustment
                </div>
                <div
                  className={cn(
                    'mt-1 text-2xl font-black font-mono',
                    (etaData.adjustment_minutes || 0) > 0
                      ? 'text-amber-800'
                      : (etaData.adjustment_minutes || 0) < 0
                      ? 'text-emerald-700'
                      : 'text-slate-700',
                  )}
                >
                  {(etaData.adjustment_minutes || 0) > 0
                    ? `+${etaData.adjustment_minutes}`
                    : etaData.adjustment_minutes}
                  <span className="text-xs font-normal text-slate-500"> min</span>
                </div>
                <div className="mt-0.5 text-[10px] text-slate-500 font-medium">Context delta</div>
              </div>
            </div>

            {/* Estimated Arrival + Distance Row */}
            <div className="grid grid-cols-2 gap-2">
              {/* Estimated Arrival Time */}
              {etaData.estimated_arrival_time && (
                <div className="rounded-lg border border-slate-200 bg-slate-50 p-2.5 flex items-center gap-2">
                  <Clock className="h-4 w-4 text-blue-600 shrink-0" />
                  <div className="min-w-0">
                    <div className="text-[10px] uppercase font-bold text-slate-500 tracking-wider">
                      Est. Arrival
                    </div>
                    <div className="text-sm font-bold text-slate-900 font-mono truncate">
                      {formatArrivalTime(etaData.estimated_arrival_time)}
                    </div>
                  </div>
                </div>
              )}

              {/* Distance */}
              {etaData.distance_km !== null && (
                <div className="rounded-lg border border-slate-200 bg-slate-50 p-2.5 flex items-center gap-2">
                  <MapPin className="h-4 w-4 text-emerald-600 shrink-0" />
                  <div className="min-w-0">
                    <div className="text-[10px] uppercase font-bold text-slate-500 tracking-wider">
                      Distance
                    </div>
                    <div className="text-sm font-bold text-slate-900 font-mono">
                      {etaData.distance_km} km
                      <span className="text-[10px] font-medium text-slate-500 ml-1">
                        ({etaData.distance_miles} mi)
                      </span>
                    </div>
                  </div>
                </div>
              )}
            </div>

            {/* Why / Operational Explanation Banner */}
            <div className="rounded-lg border border-slate-200 bg-slate-50 p-3 space-y-1.5 text-xs">
              <div className="flex items-center justify-between">
                <span className="text-[10px] font-bold uppercase tracking-wider text-slate-500 flex items-center gap-1.5">
                  <Info className="h-3.5 w-3.5 text-blue-600" />
                  <span>Why did ETA change?</span>
                </span>
                {etaData.technician_name && (
                  <span className="text-[11px] font-mono text-slate-600">
                    Tech: <strong className="text-slate-900">{etaData.technician_name}</strong>{' '}
                    ({etaData.technician_code})
                  </span>
                )}
              </div>
              <p className="text-slate-800 font-bold leading-snug">{etaData.reason}</p>
            </div>

            {/* Context Data Sources Panel */}
            {etaData.data_sources && etaData.data_sources.length > 0 && (
              <DataSourcesPanel sources={etaData.data_sources} />
            )}

            {/* ── DISPATCHER OVERRIDE SECTION ── */}
            <div className="rounded-lg border border-amber-200 bg-amber-50/70 p-3.5 space-y-3">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-1.5 text-amber-900 font-extrabold">
                  <Edit3 className="h-4 w-4 shrink-0 text-amber-700" />
                  <span className="text-xs font-extrabold uppercase tracking-wider">Dispatcher Manual Override</span>
                </div>
                {etaData.active_override && (
                  <span className="rounded-full bg-amber-100 border border-amber-300 px-2 py-0.5 text-[10px] font-mono font-bold text-amber-900">
                    Override Active: {etaData.active_override.overridden_eta}m
                  </span>
                )}
              </div>

              {/* Comparison Summary Banner */}
              <div className="grid grid-cols-3 gap-2 py-2 px-2.5 rounded-lg bg-white border border-slate-200 text-center">
                <div>
                  <span className="text-[9px] uppercase font-bold text-slate-500 block">System Rec.</span>
                  <span className="font-mono text-sm font-bold text-blue-700">{etaData.context_aware_eta_minutes} min</span>
                </div>
                <div>
                  <span className="text-[9px] uppercase font-bold text-slate-500 block">Override Value</span>
                  <span className="font-mono text-sm font-bold text-amber-800">
                    {etaData.active_override ? `${etaData.active_override.overridden_eta} min` : '—'}
                  </span>
                </div>
                <div>
                  <span className="text-[9px] uppercase font-bold text-slate-500 block">Final Dispatch ETA</span>
                  <span className="font-mono text-sm font-black text-emerald-700">{etaData.final_dispatch_eta_minutes} min</span>
                </div>
              </div>

              {overrideSuccessMsg && (
                <div className="flex items-center gap-1.5 text-xs text-emerald-800 bg-emerald-50 border border-emerald-200 px-2.5 py-1.5 rounded-md font-bold">
                  <Check className="h-3.5 w-3.5 shrink-0 text-emerald-600" />
                  <span>{overrideSuccessMsg}</span>
                </div>
              )}

              {/* Form */}
              <form onSubmit={handleApplyOverride} className="space-y-2.5">
                <div className="grid grid-cols-2 gap-2">
                  <div>
                    <label className="text-[10px] font-bold uppercase text-slate-600 block mb-1">
                      Override ETA (Min)
                    </label>
                    <input
                      type="number"
                      min={1}
                      max={1440}
                      value={overrideInput}
                      onChange={(e) => setOverrideInput(e.target.value)}
                      placeholder="e.g. 45"
                      className="w-full rounded-md border border-slate-200 bg-white px-2.5 py-1 text-xs font-mono text-slate-800 focus:border-amber-500 focus:outline-none"
                    />
                  </div>

                  <div>
                    <label className="text-[10px] font-bold uppercase text-slate-600 block mb-1">
                      Operational Rationale
                    </label>
                    <select
                      value={overrideReasonSelect}
                      onChange={(e) => setOverrideReasonSelect(e.target.value)}
                      className="w-full rounded-md border border-slate-200 bg-white px-2 py-1 text-[11px] text-slate-800 focus:border-amber-500 focus:outline-none"
                    >
                      {OVERRIDE_REASONS.map((r) => (
                        <option key={r} value={r}>
                          {r}
                        </option>
                      ))}
                    </select>
                  </div>
                </div>

                {overrideReasonSelect === 'Other' && (
                  <div>
                    <input
                      type="text"
                      value={overrideReasonCustom}
                      onChange={(e) => setOverrideReasonCustom(e.target.value)}
                      placeholder="Specify rationale reason..."
                      className="w-full rounded-md border border-slate-200 bg-white px-2.5 py-1 text-xs text-slate-800 focus:border-amber-500 focus:outline-none"
                    />
                  </div>
                )}

                <button
                  type="submit"
                  disabled={isSubmittingOverride || !activeJobId}
                  className="w-full flex items-center justify-center gap-1.5 rounded-md bg-amber-500 hover:bg-amber-600 text-white px-3 py-1.5 text-xs font-bold transition-colors disabled:opacity-50 shadow-2xs"
                >
                  {isSubmittingOverride ? (
                    <RefreshCw className="h-3.5 w-3.5 animate-spin" />
                  ) : (
                    <Edit3 className="h-3.5 w-3.5" />
                  )}
                  <span>Apply Dispatcher Override</span>
                </button>
              </form>
            </div>

            {/* ── ETA ERROR EXPERIMENT PERFORMANCE PANEL ── */}
            {metrics && (
              <div className="rounded-lg border border-slate-200 bg-slate-50 p-3.5 space-y-2.5">
                <div className="flex items-center justify-between">
                  <span className="text-[10px] font-bold uppercase tracking-wider text-slate-600 flex items-center gap-1.5">
                    <Award className="h-3.5 w-3.5 text-emerald-600" />
                    <span>Model Prediction Accuracy (MAE Experiment)</span>
                  </span>
                  <span className="text-[9px] font-mono text-emerald-800 font-bold bg-emerald-50 px-2 py-0.5 rounded border border-emerald-200">
                    +{metrics.improvement_percent}% Error Reduction
                  </span>
                </div>

                {/* Metrics Grid */}
                <div className="grid grid-cols-4 gap-1.5 text-center font-mono">
                  <div className="rounded bg-white border border-slate-200 p-1.5">
                    <span className="text-[9px] text-slate-500 block uppercase font-bold">Base MAE</span>
                    <span className="text-xs font-bold text-slate-700">{metrics.baseline_mae_minutes}m</span>
                  </div>
                  <div className="rounded bg-white border border-slate-200 p-1.5">
                    <span className="text-[9px] text-blue-600 block uppercase font-bold">Model MAE</span>
                    <span className="text-xs font-bold text-blue-700">{metrics.context_aware_mae_minutes}m</span>
                  </div>
                  <div className="rounded bg-white border border-slate-200 p-1.5">
                    <span className="text-[9px] text-amber-700 block uppercase font-bold">Base Non-Rtn</span>
                    <span className="text-xs font-bold text-amber-800">{metrics.baseline_non_routine_mae}m</span>
                  </div>
                  <div className="rounded bg-white border border-slate-200 p-1.5">
                    <span className="text-[9px] text-emerald-700 block uppercase font-bold">Model Non-Rtn</span>
                    <span className="text-xs font-bold text-emerald-700">{metrics.context_aware_non_routine_mae}m</span>
                  </div>
                </div>

                <p className="text-[11px] text-slate-600 leading-snug font-medium">
                  {metrics.narrative_summary}
                </p>
              </div>
            )}
          </div>
        ) : null}
      </div>

      {/* Footer / Last Calculated Timestamp */}
      <div className="pt-3 border-t border-slate-100 flex items-center justify-between text-[10px] text-slate-500">
        <div className="flex items-center gap-1.5">
          <span>Context Telemetry Sync</span>
          {etaData?.calculation_status && (
            <span
              className={cn(
                'rounded px-1.5 py-0.5 font-bold uppercase text-[9px] border',
                etaData.calculation_status === 'COMPLETE'
                  ? 'bg-emerald-50 border-emerald-200 text-emerald-800'
                  : etaData.calculation_status === 'PARTIAL'
                  ? 'bg-amber-50 border-amber-200 text-amber-900'
                  : 'bg-slate-100 border-slate-200 text-slate-600',
              )}
            >
              {etaData.calculation_status}
            </span>
          )}
        </div>
        <span>
          {etaData?.calculated_at
            ? `Calculated: ${formatDate(etaData.calculated_at)}`
            : 'Awaiting context evaluation'}
        </span>
      </div>
    </div>
  );
}

function DataSourcesPanel({ sources }: { sources: DataSource[] }) {
  const availableCount = sources.filter((s) => s.status === 'AVAILABLE').length;
  const totalCount = sources.length;

  return (
    <div className="space-y-1.5">
      <div className="flex items-center justify-between px-1">
        <span className="text-[10px] font-bold uppercase tracking-wider text-surface-400">
          Context Data Sources
        </span>
        <span className="text-[10px] text-surface-500 font-mono">
          {availableCount}/{totalCount} available
        </span>
      </div>
      <div className="space-y-1">
        {sources.map((source, idx) => (
          <DataSourceRow key={idx} source={source} />
        ))}
      </div>
    </div>
  );
}
