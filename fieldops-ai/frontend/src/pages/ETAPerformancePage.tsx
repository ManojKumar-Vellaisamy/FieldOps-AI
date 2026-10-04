import { useState, useEffect, useCallback } from 'react';
import {
  Gauge,
  Shield,
  RefreshCw,
  TrendingUp,
  CloudRain,
  Car,
  Clock,
  Zap,
  Info,
} from 'lucide-react';
import { useAuth } from '@/contexts/AuthContext';
import { etaService } from '@/services/eta.service';
import type { ETAExperimentMetrics, ETAOverride } from '@/types/eta.types';
import { RealtimeConnectionBadge } from '@/components/common/RealtimeConnectionBadge';
import { useRealtimeSync } from '@/hooks/useRealtimeSync';
import { cn } from '@/utils/cn';

export default function ETAPerformancePage() {
  const { user } = useAuth();
  const [sourceType, setSourceType] = useState<'real' | 'simulated'>('real');
  const [metrics, setMetrics] = useState<ETAExperimentMetrics | null>(null);
  const [overrides, setOverrides] = useState<ETAOverride[]>([]);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [activeTab, setActiveTab] = useState<'benchmarks' | 'scenarios' | 'overrides'>('benchmarks');

  const loadData = useCallback(async () => {
    setIsLoading(true);
    try {
      const [expRes, ovrRes] = await Promise.all([
        etaService.getExperimentMetrics(sourceType).catch(() => null),
        etaService.getAllRecentOverrides(20).catch(() => []),
      ]);
      setMetrics(expRes);
      setOverrides(ovrRes || []);
    } catch (err) {
      console.error('Failed to load ETA performance telemetry', err);
    } finally {
      setIsLoading(false);
    }
  }, [sourceType]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  // Subscribe to real-time ETA updates
  useRealtimeSync(['ETA_UPDATED', 'DISPATCH_PLAN_CHANGED'], () => {
    loadData();
  });

  return (
    <div className="flex flex-col gap-6 py-2 animate-fade-in select-none">
      {/* ── Page Header ── */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-slate-200 pb-5">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <span className="inline-flex items-center gap-1.5 rounded-full border border-blue-200 bg-blue-50 px-2.5 py-0.5 text-[11px] font-bold text-blue-700">
              <Gauge className="h-3.5 w-3.5 text-blue-600" />
              <span>ETA Performance & Accuracy</span>
            </span>
            <span className="inline-flex items-center gap-1 rounded-full border border-slate-200 bg-slate-100 px-2.5 py-0.5 text-[11px] font-bold text-slate-700">
              <Shield className="h-3 w-3 text-purple-600" />
              <span>{user?.role || 'Dispatcher'}</span>
            </span>
            <RealtimeConnectionBadge />
          </div>

          <h1 className="text-2xl md:text-3xl font-extrabold tracking-tight text-slate-900">
            ETA Performance & Prediction Engine
          </h1>
          <p className="text-xs md:text-sm text-slate-500 mt-0.5 font-medium">
            Evaluate baseline vs. context-aware ETA accuracy, weather/traffic impact adjustments, and dispatcher override telemetry.
          </p>
        </div>

        <div className="flex items-center gap-2.5 self-start md:self-auto">
          {/* Dataset Selector Toggle */}
          <div className="flex items-center rounded-xl bg-slate-100 p-1 border border-slate-200 text-xs font-bold">
            <button
              type="button"
              onClick={() => setSourceType('real')}
              className={cn(
                'px-3 py-1.5 rounded-lg transition-all cursor-pointer',
                sourceType === 'real'
                  ? 'bg-blue-600 text-white shadow-2xs'
                  : 'text-slate-600 hover:text-slate-900',
              )}
            >
              Real Telemetry (80 Trips)
            </button>
            <button
              type="button"
              onClick={() => setSourceType('simulated')}
              className={cn(
                'px-3 py-1.5 rounded-lg transition-all cursor-pointer',
                sourceType === 'simulated'
                  ? 'bg-blue-600 text-white shadow-2xs'
                  : 'text-slate-600 hover:text-slate-900',
              )}
            >
              Simulated (50 Scenarios)
            </button>
          </div>

          <button
            onClick={loadData}
            disabled={isLoading}
            className="flex items-center gap-1.5 rounded-xl border border-slate-200 bg-white px-3.5 py-2 text-xs font-bold text-slate-700 hover:bg-slate-50 transition-colors shadow-2xs cursor-pointer"
          >
            <RefreshCw className={cn('h-3.5 w-3.5', isLoading && 'animate-spin')} />
            <span>Refresh Telemetry</span>
          </button>
        </div>
      </div>

      {/* ── Navigation Tabs ── */}
      <div className="flex items-center gap-2 border-b border-slate-200 pb-1 text-xs font-bold">
        <button
          onClick={() => setActiveTab('benchmarks')}
          className={cn(
            'px-3.5 py-2 rounded-lg transition-all cursor-pointer',
            activeTab === 'benchmarks'
              ? 'bg-blue-600 text-white shadow-xs'
              : 'text-slate-600 hover:bg-slate-100',
          )}
        >
          Model Benchmarks
        </button>
        <button
          onClick={() => setActiveTab('scenarios')}
          className={cn(
            'px-3.5 py-2 rounded-lg transition-all cursor-pointer',
            activeTab === 'scenarios'
              ? 'bg-blue-600 text-white shadow-xs'
              : 'text-slate-600 hover:bg-slate-100',
          )}
        >
          Transit Evaluation Scenarios
        </button>
        <button
          onClick={() => setActiveTab('overrides')}
          className={cn(
            'px-3.5 py-2 rounded-lg transition-all cursor-pointer flex items-center gap-1.5',
            activeTab === 'overrides'
              ? 'bg-blue-600 text-white shadow-xs'
              : 'text-slate-600 hover:bg-slate-100',
          )}
        >
          <span>Manual Overrides</span>
          <span className="rounded-full bg-slate-200/80 px-1.5 py-0.2 text-[10px] text-slate-800">
            {overrides.length}
          </span>
        </button>
      </div>

      {/* ── Tab 1: Model Benchmarks ── */}
      {activeTab === 'benchmarks' && (
        <div className="flex flex-col gap-6">
          {/* Telemetry Status Banner */}
          {!metrics?.is_sufficient_data && (
            <div className="rounded-xl border border-amber-200 bg-amber-50/80 p-4 shadow-xs flex items-start gap-3">
              <Info className="h-5 w-5 text-amber-700 shrink-0 mt-0.5" />
              <div className="text-xs text-amber-900 leading-relaxed">
                <span className="font-extrabold uppercase tracking-wide block mb-0.5">
                  Insufficient Real Telemetry — Empirical Benchmarks Unavailable
                </span>
                <p className="font-medium text-amber-800">
                  {metrics?.narrative_summary ||
                    'At least 10 completed field dispatches with tracked actual transit outcomes are required to calculate empirical Mean Absolute Error (MAE) and accuracy gains.'}
                </p>
                <div className="mt-2 flex items-center gap-2 font-mono text-[11px] text-amber-900">
                  <span className="rounded bg-amber-100 border border-amber-300 px-2 py-0.5 font-bold">
                    Sample Progress: {metrics?.sample_count ?? 0} / {metrics?.min_required_samples ?? 10} completed dispatches
                  </span>
                  <span className="text-amber-700">• Real FieldOps Operational Telemetry</span>
                </div>
              </div>
            </div>
          )}

          {/* Top KPI Cards */}
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
            <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-xs">
              <div className="flex items-center justify-between text-xs font-bold uppercase tracking-wider text-slate-500">
                <span>Model Accuracy Gain</span>
                <TrendingUp className="h-5 w-5 text-emerald-600" />
              </div>
              <div className="mt-3">
                {metrics?.is_sufficient_data && metrics.improvement_percent != null ? (
                  <div className="text-3xl font-black text-emerald-700 font-mono">
                    +{metrics.improvement_percent.toFixed(1)}%
                  </div>
                ) : (
                  <div className="text-base font-bold text-slate-400 italic">
                    Insufficient real data
                  </div>
                )}
              </div>
              <div className="mt-1 text-[11px] text-slate-500 font-medium">
                {metrics?.is_sufficient_data && metrics.improvement_percent != null
                  ? 'Overall ETA prediction error reduction'
                  : `Requires ${metrics?.min_required_samples ?? 10} completed trips (${metrics?.sample_count ?? 0} recorded)`}
              </div>
            </div>

            <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-xs">
              <div className="flex items-center justify-between text-xs font-bold uppercase tracking-wider text-slate-500">
                <span>Context-Aware MAE</span>
                <Clock className="h-5 w-5 text-blue-600" />
              </div>
              <div className="mt-3">
                {metrics?.is_sufficient_data && metrics.context_aware_mae_minutes != null ? (
                  <div className="text-3xl font-black text-blue-700 font-mono">
                    {metrics.context_aware_mae_minutes.toFixed(1)}m
                  </div>
                ) : (
                  <div className="text-base font-bold text-slate-400 italic">
                    Insufficient real data
                  </div>
                )}
              </div>
              <div className="mt-1 text-[11px] text-slate-500 font-medium">
                {metrics?.is_sufficient_data && metrics.context_aware_mae_minutes != null
                  ? 'Mean absolute prediction error'
                  : 'Awaiting real travel time outcomes'}
              </div>
            </div>

            <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-xs">
              <div className="flex items-center justify-between text-xs font-bold uppercase tracking-wider text-slate-500">
                <span>Baseline Distance MAE</span>
                <Gauge className="h-5 w-5 text-slate-400" />
              </div>
              <div className="mt-3">
                {metrics?.is_sufficient_data && metrics.baseline_mae_minutes != null ? (
                  <div className="text-3xl font-black text-slate-700 font-mono">
                    {metrics.baseline_mae_minutes.toFixed(1)}m
                  </div>
                ) : (
                  <div className="text-base font-bold text-slate-400 italic">
                    Insufficient real data
                  </div>
                )}
              </div>
              <div className="mt-1 text-[11px] text-slate-500 font-medium">
                {metrics?.is_sufficient_data && metrics.baseline_mae_minutes != null
                  ? 'Standard distance-only baseline error'
                  : 'Awaiting baseline vs actual comparisons'}
              </div>
            </div>

            <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-xs">
              <div className="flex items-center justify-between text-xs font-bold uppercase tracking-wider text-slate-500">
                <span>Non-Routine Error Saved</span>
                <Zap className="h-5 w-5 text-purple-600" />
              </div>
              <div className="mt-3">
                {metrics?.is_sufficient_data &&
                metrics.baseline_non_routine_mae != null &&
                metrics.context_aware_non_routine_mae != null ? (
                  <div className="text-3xl font-black text-purple-700 font-mono">
                    {(metrics.baseline_non_routine_mae - metrics.context_aware_non_routine_mae).toFixed(1)}m
                  </div>
                ) : (
                  <div className="text-base font-bold text-slate-400 italic">
                    Insufficient real data
                  </div>
                )}
              </div>
              <div className="mt-1 text-[11px] text-slate-500 font-medium">
                {metrics?.is_sufficient_data && metrics.baseline_non_routine_mae != null
                  ? 'Adverse weather / congestion benefit'
                  : 'Awaiting non-routine event samples'}
              </div>
            </div>
          </div>

          {/* Environmental Context Factors */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-xs">
              <div className="flex items-center gap-2 mb-3">
                <CloudRain className="h-5 w-5 text-blue-600" />
                <h3 className="font-bold text-slate-900 text-sm">Weather Impact Modeling</h3>
              </div>
              <p className="text-xs text-slate-600 mb-4 leading-relaxed font-medium">
                Precipitation and road traction adjustments computed dynamically from live meteorological data.
              </p>
              <div className="space-y-2.5 text-xs font-mono">
                <div className="flex items-center justify-between p-2.5 rounded-lg bg-slate-50 border border-slate-200">
                  <span className="font-bold text-slate-700">Light Rain / Drizzle</span>
                  <span className="text-blue-700 font-bold">+5% travel time adjustment</span>
                </div>
                <div className="flex items-center justify-between p-2.5 rounded-lg bg-blue-50/60 border border-blue-200">
                  <span className="font-bold text-slate-700">Moderate Rain / Surface Wet</span>
                  <span className="text-blue-700 font-bold">+15% travel time adjustment</span>
                </div>
                <div className="flex items-center justify-between p-2.5 rounded-lg bg-purple-50/60 border border-purple-200">
                  <span className="font-bold text-slate-700">Heavy Rain / Thunderstorm</span>
                  <span className="text-purple-700 font-bold">+25% - 40% travel time adjustment</span>
                </div>
              </div>
            </div>

            <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-xs">
              <div className="flex items-center gap-2 mb-3">
                <Car className="h-5 w-5 text-indigo-600" />
                <h3 className="font-bold text-slate-900 text-sm">Real Traffic Provider Integration</h3>
              </div>
              <p className="text-xs text-slate-600 mb-4 leading-relaxed font-medium">
                Live roadway traffic via TomTom Traffic Flow API (REAL) when configured, or Open Source Routing Machine (OSRM) baseline route evaluation (DERIVED).
              </p>
              <div className="space-y-2.5 text-xs font-mono">
                <div className="flex items-center justify-between p-2.5 rounded-lg bg-slate-50 border border-slate-200">
                  <span className="font-bold text-slate-700">Free Flow Velocity</span>
                  <span className="text-emerald-700 font-bold">1.0x baseline duration</span>
                </div>
                <div className="flex items-center justify-between p-2.5 rounded-lg bg-amber-50/60 border border-amber-200">
                  <span className="font-bold text-slate-700">Moderate Arterial Congestion</span>
                  <span className="text-amber-800 font-bold">1.3x baseline duration</span>
                </div>
                <div className="flex items-center justify-between p-2.5 rounded-lg bg-rose-50/60 border border-rose-200">
                  <span className="font-bold text-slate-700">Severe Gridlock / Incident</span>
                  <span className="text-rose-700 font-bold">1.75x baseline duration</span>
                </div>
              </div>
            </div>
          </div>

          {/* Narrative Summary */}
          {metrics && (
            <div className="rounded-xl border border-blue-200 bg-gradient-to-r from-blue-50/80 to-indigo-50/60 p-5 shadow-xs">
              <div className="flex items-center gap-2 text-blue-900 font-bold text-sm mb-1.5">
                <Info className="h-4 w-4 text-blue-700" />
                <span>Context-Aware Engine Telemetry Summary</span>
              </div>
              <p className="text-xs text-slate-700 leading-relaxed font-medium">
                {metrics.narrative_summary}
              </p>
              <div className="mt-3 text-[11px] text-slate-500 font-mono">
                Dataset: {metrics.dataset_description} • Evaluated sample size: {metrics.sample_count} transit scenarios
              </div>
            </div>
          )}
        </div>
      )}

      {/* ── Tab 2: Transit Evaluation Scenarios ── */}
      {activeTab === 'scenarios' && (
        <div className="rounded-xl border border-slate-200 bg-white shadow-xs overflow-hidden">
          <div className="p-4 border-b border-slate-200 bg-slate-50/60 flex items-center justify-between">
            <h3 className="text-xs font-bold uppercase tracking-wider text-slate-700">
              Scenario-by-Scenario Validation Matrix
            </h3>
            <span className="text-xs text-slate-500 font-mono font-medium">
              {metrics?.sample_breakdown?.length || 0} scenarios evaluated
            </span>
          </div>

          {!metrics?.sample_breakdown || metrics.sample_breakdown.length === 0 ? (
            <div className="p-12 text-center text-slate-500 text-xs font-medium">
              No completed operational dispatches recorded yet. Complete real field dispatches to populate the empirical validation matrix from real telemetry.
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs border-collapse">
                <thead>
                  <tr className="border-b border-slate-200 bg-slate-100/80 text-[11px] font-bold uppercase text-slate-600">
                    <th className="p-3">Scenario #</th>
                    <th className="p-3">Transit Distance</th>
                    <th className="p-3">Operational Conditions</th>
                    <th className="p-3">Baseline ETA</th>
                    <th className="p-3">Context ETA</th>
                    <th className="p-3">Actual Travel</th>
                    <th className="p-3">Error Reduction</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100 font-mono text-[11px]">
                  {metrics.sample_breakdown.map((s) => (
                    <tr key={s.id} className="hover:bg-slate-50/80 transition-colors">
                      <td className="p-3 font-bold text-slate-900">SCN-{s.id.toString().padStart(3, '0')}</td>
                      <td className="p-3 text-slate-700">{s.distance_km.toFixed(1)} km</td>
                      <td className="p-3 font-sans">
                        <span
                          className={cn(
                            'inline-block px-2 py-0.5 rounded text-[10px] font-bold',
                            s.is_non_routine
                              ? 'bg-amber-100 text-amber-800 border border-amber-200'
                              : 'bg-slate-100 text-slate-700',
                          )}
                        >
                          {s.conditions}
                        </span>
                      </td>
                      <td className="p-3 text-slate-600">{s.baseline_eta_minutes.toFixed(0)} min</td>
                      <td className="p-3 font-bold text-blue-700">{s.context_aware_eta_minutes.toFixed(0)} min</td>
                      <td className="p-3 text-slate-800 font-bold">{s.actual_travel_minutes.toFixed(0)} min</td>
                      <td className="p-3">
                        <span
                          className={cn(
                            'inline-flex items-center gap-1 font-bold',
                            s.improvement_minutes >= 0 ? 'text-emerald-700' : 'text-rose-600',
                          )}
                        >
                          {s.improvement_minutes >= 0 ? '+' : ''}
                          {s.improvement_minutes.toFixed(1)} min
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {/* ── Tab 3: Dispatcher Manual Overrides ── */}
      {activeTab === 'overrides' && (
        <div className="rounded-xl border border-slate-200 bg-white shadow-xs overflow-hidden">
          <div className="p-4 border-b border-slate-200 bg-slate-50/60 flex items-center justify-between">
            <h3 className="text-xs font-bold uppercase tracking-wider text-slate-700">
              Dispatcher Manual ETA Overrides Audit Trail
            </h3>
            <span className="text-xs text-slate-500 font-mono font-medium">
              {overrides.length} records recorded
            </span>
          </div>

          {overrides.length === 0 ? (
            <div className="p-12 text-center text-slate-400 text-xs font-medium">
              No production dispatcher ETA overrides recorded yet.
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs border-collapse">
                <thead>
                  <tr className="border-b border-slate-200 bg-slate-100/80 text-[11px] font-bold uppercase text-slate-600">
                    <th className="p-3">Time</th>
                    <th className="p-3">Job ID</th>
                    <th className="p-3">Dispatcher</th>
                    <th className="p-3">System ETA</th>
                    <th className="p-3">Override ETA</th>
                    <th className="p-3">Delta</th>
                    <th className="p-3">Rationale Reason</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100 font-mono text-[11px]">
                  {overrides.map((ovr) => {
                    const delta = ovr.overridden_eta - ovr.original_system_eta;
                    return (
                      <tr key={ovr.id} className="hover:bg-slate-50/80 transition-colors">
                        <td className="p-3 text-slate-500">
                          {new Date(ovr.created_at).toLocaleTimeString([], {
                            hour: '2-digit',
                            minute: '2-digit',
                            second: '2-digit',
                          })}
                        </td>
                        <td className="p-3 font-bold text-blue-700">{ovr.job_id.slice(0, 8)}...</td>
                        <td className="p-3 font-sans text-slate-800 font-semibold">{ovr.dispatcher_name || 'Dispatcher'}</td>
                        <td className="p-3 text-slate-600">{ovr.original_system_eta} min</td>
                        <td className="p-3 font-bold text-purple-700">{ovr.overridden_eta} min</td>
                        <td className="p-3">
                          <span
                            className={cn(
                              'font-bold px-1.5 py-0.5 rounded text-[10px]',
                              delta > 0 ? 'bg-amber-50 text-amber-800 border border-amber-200' : 'bg-blue-50 text-blue-800 border border-blue-200',
                            )}
                          >
                            {delta > 0 ? `+${delta}m` : `${delta}m`}
                          </span>
                        </td>
                        <td className="p-3 font-sans text-slate-700 max-w-xs truncate" title={ovr.reason}>
                          {ovr.reason}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
