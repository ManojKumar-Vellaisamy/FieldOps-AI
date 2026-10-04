import { useState, useEffect, useCallback, useRef } from 'react';
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
  ChevronDown,
  ChevronUp,
  FileText,
  Database,
} from 'lucide-react';
import { etaService } from '@/services/eta.service';
import type { ETAResponse, DataSource, ContextFactor, ETAExperimentMetrics } from '@/types/eta.types';
import type { ETAUpdatedEventData, RealtimeEvent } from '@/types/realtime.types';
import { useRealtimeSync } from '@/hooks/useRealtimeSync';
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


function provenanceBadge(source: DataSource) {
  const provenance = source.provenance ?? (source.status === 'UNAVAILABLE' ? 'UNAVAILABLE' : 'DERIVED');
  const isUnavailable = source.status === 'UNAVAILABLE' || provenance === 'UNAVAILABLE';
  const label = isUnavailable ? 'UNAVAIL' : provenance;
  const cls = isUnavailable
    ? 'bg-slate-100 text-slate-500'
    : provenance === 'REAL'
      ? 'bg-emerald-100 text-emerald-800 border border-emerald-300'
      : provenance === 'SYSTEM'
        ? 'bg-purple-100 text-purple-800 border border-purple-300'
        : 'bg-blue-100 text-blue-800 border border-blue-300';
  return (
    <span className={cn('px-1.5 py-0.5 rounded text-[8px] font-extrabold uppercase font-mono', cls)}>
      {label}
    </span>
  );
}

function freshnessBadge(freshness?: string, dataAgeSeconds?: number | null) {
  if (!freshness || freshness === 'UNKNOWN') return null;
  const isFresh = freshness === 'FRESH';
  const isStale = freshness === 'STALE';
  const cls = isFresh
    ? 'bg-emerald-50 text-emerald-700 border-emerald-200'
    : isStale
    ? 'bg-amber-50 text-amber-800 border-amber-300 animate-pulse'
    : 'bg-slate-100 text-slate-500 border-slate-200';
  const label = isStale && dataAgeSeconds != null
    ? `STALE (${Math.round(dataAgeSeconds)}s)`
    : freshness;
  return (
    <span className={cn('px-1.5 py-0.2 rounded text-[7.5px] font-extrabold uppercase font-mono border', cls)}>
      {label}
    </span>
  );
}

function classificationBadge(classification?: string) {
  if (!classification || classification === 'UNAVAILABLE') return null;
  switch (classification) {
    case 'INCLUDED_IN_LIVE_ROUTE':
      return (
        <span className="px-1.5 py-0.2 rounded text-[7.5px] font-bold font-mono bg-sky-50 text-sky-800 border border-sky-200" title="Slowdown already measured in TomTom live driving route — 0m additional penalty">
          IN LIVE ROUTE (0m addl)
        </span>
      );
    case 'INCREMENTAL_DETOUR':
      return (
        <span className="px-1.5 py-0.2 rounded text-[7.5px] font-bold font-mono bg-amber-50 text-amber-800 border border-amber-300" title="Verified detour time exceeding live route">
          DETOUR (+addl)
        </span>
      );
    case 'RELEVANT_INCIDENT_DELAY':
      return (
        <span className="px-1.5 py-0.2 rounded text-[7.5px] font-bold font-mono bg-amber-50 text-amber-800 border border-amber-300" title="Reported incident delay along route corridor">
          INCIDENT DELAY (+addl)
        </span>
      );
    case 'INDEPENDENT_CONTEXT':
      return (
        <span className="px-1.5 py-0.2 rounded text-[7.5px] font-bold font-mono bg-purple-50 text-purple-800 border border-purple-300" title="Independent verified operational context">
          INDEPENDENT (+addl)
        </span>
      );
    case 'NOT_APPLIED':
      return (
        <span className="px-1.5 py-0.2 rounded text-[7.5px] font-bold font-mono bg-slate-100 text-slate-600 border border-slate-200" title="Condition active but evaluated to 0 min impact">
          NOT APPLIED (0m)
        </span>
      );
    default:
      return null;
  }
}

function DataSourceRow({ source }: { source: DataSource }) {
  const [isExpanded, setIsExpanded] = useState(false);

  const displayName = source.category === 'EVENTS' && source.provenance === 'REAL'
    ? 'Events (PredictHQ)'
    : source.category === 'ROAD' && source.provenance === 'REAL'
    ? 'Road Restrictions (TomTom)'
    : source.name;

  const isRoad = source.category === 'ROAD';
  const isEvents = source.category === 'EVENTS';
  const hasTelemetry = isRoad || isEvents;

  const relevanceLabel = source.relevance_status === 'RELEVANT'
    ? 'Route-Relevant'
    : source.relevance_status === 'NOT_RELEVANT'
    ? 'Not Relevant'
    : source.is_route_relevant === true
    ? 'Route-Relevant'
    : source.is_route_relevant === false
    ? 'Not Relevant'
    : null;

  const impactSubtext = isRoad
    ? (source.detour_seconds && source.detour_seconds > 0
        ? 'Derived from alternate route'
        : source.incident_delay_seconds && source.incident_delay_seconds > 0
        ? 'Reported incident delay'
        : source.impact_minutes > 0
        ? 'Reported incident delay'
        : 'No selected-route impact')
    : isEvents
    ? (source.impact_minutes > 0 ? 'Derived route delay' : (source.is_route_relevant ? 'No measurable route slowdown' : 'Outside route corridor'))
    : null;

  const hasExpandableContent = Boolean(
    source.relevance_reason ||
    (source.evaluated_items && source.evaluated_items.length > 0) ||
    source.detour_travel_time_minutes ||
    source.distance_to_route !== undefined ||
    source.distance_to_route_display ||
    source.impact_classification ||
    source.freshness
  );

  return (
    <div className="py-2 px-2.5 rounded-lg bg-slate-50 border border-slate-200 space-y-1.5 transition-all">
      <div className="flex items-start justify-between gap-2">
        <div className="flex items-start gap-2 min-w-0 flex-1">
          <div className="mt-0.5">{getSourceIcon(source.category, statusColor(source.status))}</div>
          <div className="min-w-0 flex-1">
            <div className="flex items-center gap-1.5 flex-wrap">
              <span className="text-[11px] font-bold text-slate-900 truncate" title={source.description}>
                {displayName}
              </span>
              {provenanceBadge(source)}
              {freshnessBadge(source.freshness, source.data_age_seconds)}
              {classificationBadge(source.impact_classification)}
              {relevanceLabel && (
                <span
                  className={cn(
                    'px-1.5 py-0.2 rounded text-[8px] font-extrabold uppercase font-mono border',
                    relevanceLabel === 'Route-Relevant'
                      ? 'bg-emerald-50 text-emerald-800 border-emerald-300'
                      : 'bg-slate-100 text-slate-600 border-slate-300'
                  )}
                >
                  {relevanceLabel}
                </span>
              )}
            </div>

            {/* Concise operational summary banner */}
            {hasTelemetry && source.status === 'AVAILABLE' && (
              <div className="text-[9.5px] text-slate-600 mt-0.5 flex items-center gap-2 flex-wrap font-medium">
                {isRoad && (
                  <span>
                    {source.restriction_count || 1} restriction{(source.restriction_count || 1) > 1 ? 's' : ''} detected
                  </span>
                )}
                {isEvents && (
                  <span>
                    {source.event_count || 1} nearby event{(source.event_count || 1) > 1 ? 's' : ''}
                  </span>
                )}
                {impactSubtext && (
                  <span className="text-slate-500 italic">
                    • {impactSubtext}
                  </span>
                )}
              </div>
            )}
          </div>
        </div>

        {/* Right side: Impact + Status + Expand toggle */}
        <div className="flex items-center gap-2 shrink-0">
          <div className="text-right">
            <span
              className={cn(
                'font-mono text-xs font-black block',
                source.impact_minutes > 0 ? 'text-amber-700' : 'text-slate-500'
              )}
            >
              {source.impact_minutes > 0 ? `+${source.impact_minutes} min` : '0 min'}
            </span>
          </div>

          <div className="flex items-center gap-1">
            <StatusIcon status={source.status} />
            <span className={cn('text-[10px] font-bold uppercase tracking-wider', statusColor(source.status))}>
              {source.status === 'UNAVAILABLE' ? '—' : source.status.slice(0, 4)}
            </span>
          </div>

          {hasExpandableContent && (
            <button
              onClick={() => setIsExpanded(!isExpanded)}
              className="p-0.5 text-slate-400 hover:text-slate-700 rounded transition-colors"
              title={isExpanded ? 'Hide explanation' : 'Show relevance explanation & telemetry'}
            >
              {isExpanded ? <ChevronUp className="h-3.5 w-3.5" /> : <ChevronDown className="h-3.5 w-3.5" />}
            </button>
          )}
        </div>
      </div>

      {/* Concise Description line */}
      {source.status === 'AVAILABLE' && source.description && !isExpanded && (
        <div className="text-[9px] text-slate-500 font-medium truncate pl-5">
          {source.description}
        </div>
      )}

      {/* Expandable Route Relevance Details Panel */}
      {isExpanded && (
        <div className="mt-2 pl-4 pr-1 pt-2 pb-1 border-t border-slate-200 space-y-2 text-[10px] bg-white/70 rounded-md p-2">
          <div className="grid grid-cols-2 gap-2 text-[9.5px]">
            <div>
              <span className="text-slate-400 uppercase font-bold text-[8.5px] block">Provider / Feed</span>
              <span className="font-semibold text-slate-800">
                {isRoad ? 'TomTom Traffic Incidents v5' : isEvents ? 'PredictHQ Live Events' : source.name}
              </span>
            </div>
            <div>
              <span className="text-slate-400 uppercase font-bold text-[8.5px] block">Route Corridor Buffer</span>
              <span className="font-mono text-slate-800 font-semibold">
                {isRoad ? '0.03 mi (~50m)' : isEvents ? '0.25 mi (~400m)' : 'Direct corridor'}
              </span>
            </div>
          </div>

          {source.distance_to_route !== undefined && source.distance_to_route !== null && (
            <div className="flex items-center justify-between text-[9.5px] pt-1 border-t border-slate-100 font-mono">
              <span className="text-slate-500">Distance to Selected Route:</span>
              <span className="font-bold text-slate-900">{source.distance_to_route} mi</span>
            </div>
          )}

          {source.relevance_reason && (
            <div className="bg-slate-50 border border-slate-200 rounded p-1.5 text-[9.5px]">
              <span className="text-slate-500 font-bold uppercase text-[8px] block tracking-wider">
                Relevance Decision &amp; Rationale:
              </span>
              <p className="text-slate-800 font-medium leading-tight mt-0.5">
                {source.relevance_reason}
              </p>
            </div>
          )}

          {source.detour_travel_time_minutes !== undefined && source.detour_travel_time_minutes !== null && (
            <div className="flex items-center justify-between text-[9.5px] bg-amber-50 border border-amber-200 rounded p-1.5 font-mono text-amber-950 font-bold">
              <span>Alternate Detour Route Time:</span>
              <span>{source.detour_travel_time_minutes} min (vs original)</span>
            </div>
          )}

          {source.detour_seconds && source.detour_seconds > 0 && source.detour_display && (
            <div className="flex items-center justify-between text-[9.5px] bg-amber-50 border border-amber-200 rounded p-1.5 font-mono text-amber-950 font-bold">
              <span>Measured Road Detour:</span>
              <span className="text-amber-900 font-extrabold">{source.detour_display}</span>
            </div>
          )}

          {source.incident_delay_seconds !== undefined && source.incident_delay_seconds !== null && source.incident_delay_seconds > 0 && (
            <div className="flex items-center justify-between text-[9.5px] bg-amber-50 border border-amber-200 rounded p-1.5 font-mono text-amber-950 font-bold">
              <span>Reported Incident Delay:</span>
              <span className="text-amber-900 font-extrabold">
                +{Math.round(source.incident_delay_seconds / 60)} min (+{source.incident_delay_seconds}s)
              </span>
            </div>
          )}

          {/* Evaluated Items Breakdown */}
          {source.evaluated_items && source.evaluated_items.length > 0 && (
            <div className="space-y-1 pt-1 border-t border-slate-100">
              <span className="text-slate-500 font-bold uppercase text-[8.5px] block tracking-wider">
                Evaluated Incident / Event Items ({source.evaluated_items.length}):
              </span>
              <div className="space-y-1 max-h-36 overflow-y-auto">
                {source.evaluated_items.map((item: any, i: number) => {
                  const title = item.title || item.road_name || item.id || `Item #${i + 1}`;
                  const isRel = item.is_route_relevant;
                  const itemDelay = item.delay_min ?? (item.impact_minutes || 0);

                  return (
                    <div
                      key={i}
                      className={cn(
                        'p-1.5 rounded border flex items-center justify-between gap-2 text-[9px]',
                        isRel ? 'bg-emerald-50/50 border-emerald-200' : 'bg-slate-50 border-slate-200'
                      )}
                    >
                      <div className="min-w-0 flex-1">
                        <div className="flex items-center gap-1.5">
                          <span className="font-bold text-slate-800 truncate">{title}</span>
                          <span
                            className={cn(
                              'px-1 py-0.1 rounded text-[7.5px] font-extrabold uppercase font-mono',
                              isRel ? 'bg-emerald-100 text-emerald-800' : 'bg-slate-200 text-slate-600'
                            )}
                          >
                            {isRel ? 'Relevant' : 'Off-Corridor'}
                          </span>
                        </div>
                        {item.relevance_reason && (
                          <p className="text-slate-500 text-[8.5px] truncate mt-0.5">{item.relevance_reason}</p>
                        )}
                      </div>
                      <div className="text-right shrink-0 font-mono">
                        <span className={cn('font-bold', itemDelay > 0 ? 'text-amber-700' : 'text-slate-400')}>
                          {itemDelay > 0 ? `+${itemDelay}m` : '0m'}
                        </span>
                        {item.distance_to_route !== undefined && (
                          <span className="block text-[8px] text-slate-400">{item.distance_to_route} mi</span>
                        )}
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}


function parseTimestampMs(timestamp: string | null | undefined): number | null {
  if (!timestamp) return null;
  const direct = new Date(timestamp).getTime();
  if (!isNaN(direct)) return direct;
  const withZ = new Date(timestamp.trim() + 'Z').getTime();
  if (!isNaN(withZ)) return withZ;
  return null;
}

function formatFreshnessAge(timestamp: string | null | undefined, nowMs: number): string {
  const time = parseTimestampMs(timestamp);
  if (time === null) return 'Waiting for live ETA update';

  const diffSeconds = Math.max(0, Math.floor((nowMs - time) / 1000));
  if (diffSeconds < 5) {
    return 'Updated just now';
  }
  if (diffSeconds < 60) {
    return `Updated ${diffSeconds}s ago`;
  }
  const diffMinutes = Math.floor(diffSeconds / 60);
  if (diffMinutes < 60) {
    return `Updated ${diffMinutes}m ago`;
  }
  const diffHours = Math.floor(diffMinutes / 60);
  if (diffHours < 24) {
    return `Updated ${diffHours}h ago`;
  }
  const diffDays = Math.floor(diffHours / 24);
  return `Updated ${diffDays}d ago`;
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
  const [showBreakdown, setShowBreakdown] = useState<boolean>(false);

  // Dispatcher override state
  const [overrideInput, setOverrideInput] = useState<string>('');
  const [overrideReasonSelect, setOverrideReasonSelect] = useState<string>(OVERRIDE_REASONS[0] || 'Local traffic knowledge');
  const [overrideReasonCustom, setOverrideReasonCustom] = useState<string>('');
  const [isSubmittingOverride, setIsSubmittingOverride] = useState<boolean>(false);
  const [overrideSuccessMsg, setOverrideSuccessMsg] = useState<string | null>(null);

  // UI-only freshness tick timer (updates relative age display every second without network requests)
  const [nowMs, setNowMs] = useState<number>(() => Date.now());

  useEffect(() => {
    const timer = setInterval(() => {
      setNowMs(Date.now());
    }, 1000);
    return () => clearInterval(timer);
  }, []);

  // Stale and duplicate event protection refs
  const lastCalculatedAtRef = useRef<number>(0);
  const lastEventKeyRef = useRef<string>('');

  useEffect(() => {
    if (selectedJobId) {
      setActiveJobId(selectedJobId);
      lastCalculatedAtRef.current = 0;
      lastEventKeyRef.current = '';
    } else if (!activeJobId && defaultTarget) {
      setActiveJobId(defaultTarget.id);
      lastCalculatedAtRef.current = 0;
      lastEventKeyRef.current = '';
    }
  }, [selectedJobId, defaultTarget]);

  const loadEta = useCallback(async (jobId: string, silent = false) => {
    if (!silent) setIsLoading(true);
    setError(null);
    try {
      const data = await etaService.getJobEta(jobId);
      const incomingTime = data.calculated_at ? new Date(data.calculated_at).getTime() : 0;
      if (incomingTime && lastCalculatedAtRef.current && incomingTime < lastCalculatedAtRef.current) {
        return;
      }
      setEtaData(data);
      if (incomingTime) {
        lastCalculatedAtRef.current = incomingTime;
      }
      if (data.active_override) {
        setOverrideInput(data.active_override.overridden_eta.toString());
      } else if (data.context_aware_eta_minutes) {
        setOverrideInput(data.context_aware_eta_minutes.toString());
      }
    } catch (err: unknown) {
      console.error('Failed to calculate Context-Aware ETA', err);
      const msg = err instanceof Error ? err.message : 'Failed to retrieve ETA calculation.';
      setError(msg);
      if (!silent) setEtaData(null);
    } finally {
      if (!silent) setIsLoading(false);
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

  // Real-time ETA WebSocket Synchronization
  useRealtimeSync(
    ['ETA_UPDATED'],
    (event: RealtimeEvent<ETAUpdatedEventData>) => {
      const data = event.data;
      if (!data || !data.job_id) return;
      // Job identity verification: only update if event matches currently displayed job
      if (data.job_id !== activeJobId) return;

      const eventTimestamp = data.calculated_at || data.updated_at || event.timestamp;

      // Duplicate event protection: ignore repeated event delivery
      const eventKey = `${event.event}_${data.job_id}_${eventTimestamp}_${data.context_aware_eta_minutes ?? data.overridden_eta ?? ''}`;
      if (lastEventKeyRef.current === eventKey) {
        return;
      }
      lastEventKeyRef.current = eventKey;

      // Stale event protection: ignore older calculations arriving out of order
      const incomingTime = new Date(eventTimestamp).getTime();
      if (!isNaN(incomingTime) && lastCalculatedAtRef.current && incomingTime < lastCalculatedAtRef.current) {
        return;
      }
      if (!isNaN(incomingTime)) {
        lastCalculatedAtRef.current = incomingTime;
      }

      // Atomic UI update without loading flash or temporary unavailable state
      if (data.context_aware_eta_minutes !== undefined || data.baseline_eta_minutes !== undefined) {
        setEtaData((prev) => {
          const updated: ETAResponse = {
            ...(prev || ({} as ETAResponse)),
            ...(data as unknown as ETAResponse),
            job_id: data.job_id,
            job_number: data.job_number || prev?.job_number || '',
            is_context_sufficient: data.is_context_sufficient ?? (prev ? prev.is_context_sufficient : true),
            calculation_status: (data.calculation_status as any) || prev?.calculation_status || 'COMPLETE',
            baseline_eta_minutes: data.baseline_eta_minutes ?? prev?.baseline_eta_minutes ?? null,
            context_aware_eta_minutes: data.context_aware_eta_minutes ?? prev?.context_aware_eta_minutes ?? null,
            final_dispatch_eta_minutes: data.final_dispatch_eta_minutes ?? data.overridden_eta ?? prev?.final_dispatch_eta_minutes ?? null,
            live_route_eta_minutes: data.live_route_eta_minutes ?? prev?.live_route_eta_minutes ?? null,
            free_flow_eta_minutes: data.free_flow_eta_minutes ?? prev?.free_flow_eta_minutes ?? null,
            traffic_delay_minutes: data.traffic_delay_minutes ?? prev?.traffic_delay_minutes ?? null,
            additional_verified_impact_minutes: data.additional_verified_impact_minutes ?? prev?.additional_verified_impact_minutes ?? 0,
            adjustment_minutes: data.adjustment_minutes ?? prev?.adjustment_minutes ?? null,
            distance_km: data.distance_km ?? prev?.distance_km ?? null,
            distance_miles: data.distance_miles ?? prev?.distance_miles ?? null,
            routed_distance_km: data.routed_distance_km ?? prev?.routed_distance_km ?? null,
            routed_distance_miles: data.routed_distance_miles ?? prev?.routed_distance_miles ?? null,
            routed_distance_meters: data.routed_distance_meters ?? prev?.routed_distance_meters ?? null,
            route_geometry: data.route_geometry ?? prev?.route_geometry ?? null,
            route_provenance: data.route_provenance || prev?.route_provenance || 'REAL',
            estimated_arrival_time: data.estimated_arrival_time || prev?.estimated_arrival_time || null,
            data_sources: data.data_sources && data.data_sources.length > 0 ? data.data_sources : (prev?.data_sources || []),
            factors: data.factors && data.factors.length > 0 ? data.factors : (prev?.factors || []),
            reason: data.reason || prev?.reason || 'Calculated transit route',
            missing_context: data.missing_context || prev?.missing_context || [],
            calculated_at: eventTimestamp,
            confidence_level: data.confidence_level ?? prev?.confidence_level ?? 'HIGH',
            confidence_reason: data.confidence_reason ?? prev?.confidence_reason ?? '',
            reliability_status: data.reliability_status ?? prev?.reliability_status ?? 'HIGH',
            degraded_sources: data.degraded_sources ?? prev?.degraded_sources ?? [],
            fresh_sources: data.fresh_sources ?? prev?.fresh_sources ?? [],
            stale_sources: data.stale_sources ?? prev?.stale_sources ?? [],
            unavailable_sources: data.unavailable_sources ?? prev?.unavailable_sources ?? [],
          };
          return updated;
        });
        setIsLoading(false);
      } else if (typeof data.overridden_eta === 'number') {
        // Dispatcher manual override event
        const overriddenEta: number = data.overridden_eta;
        setEtaData((prev) => {
          if (!prev) return null;
          return {
            ...prev,
            final_dispatch_eta_minutes: overriddenEta,
            active_override: {
              id: 'ws-override',
              job_id: data.job_id,
              technician_id: data.technician_id ?? prev.technician_id,
              dispatcher_id: '',
              dispatcher_name: data.dispatcher_name || 'Dispatcher',
              original_system_eta: data.original_system_eta ?? prev.context_aware_eta_minutes ?? 0,
              overridden_eta: overriddenEta,
              reason: data.reason || 'Manual override',
              previous_value: null,
              new_value: `${overriddenEta}m`,
              created_at: eventTimestamp,
            },
            confidence_level: (data.confidence_level as any) || 'HIGH',
            confidence_reason: data.confidence_reason || `Dispatcher manual override active (${overriddenEta}m)`,
            reliability_status: (data.reliability_status as any) || 'HIGH',
            calculated_at: eventTimestamp,
          };
        });
        setIsLoading(false);
        setError(null);
      }
    },
    () => {
      // Authoritative state resync upon WebSocket reconnection without UI flash
      if (activeJobId) {
        loadEta(activeJobId, true);
      }
    },
  );

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
  const currentCalculatedAt =
    etaData && etaData.job_id === activeJobId ? etaData.calculated_at : null;
  const freshnessLabel = formatFreshnessAge(currentCalculatedAt, nowMs);

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
            {/* Real-time ETA Freshness Indicator */}
            <div
              id="eta-telemetry-freshness"
              className="inline-flex items-center gap-1.5 rounded-md border border-slate-200 bg-slate-50 px-2.5 py-1 text-[11px] font-mono text-slate-600 select-none shadow-2xs"
              title={
                currentCalculatedAt
                  ? `Authoritative ETA calculation timestamp: ${new Date(currentCalculatedAt).toLocaleTimeString()}`
                  : 'Waiting for live ETA update'
              }
            >
              <span
                className={cn(
                  'h-1.5 w-1.5 rounded-full shrink-0 transition-colors',
                  currentCalculatedAt ? 'bg-emerald-500 animate-pulse' : 'bg-amber-400',
                )}
                aria-hidden="true"
              />
              <span className="font-medium whitespace-nowrap">{freshnessLabel}</span>
            </div>

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
            {etaData.calculation_status === 'PARTIAL' && (
              <div className="flex items-center gap-1.5 rounded-lg border border-amber-200 bg-amber-50/90 px-3 py-1.5 text-[11px] text-amber-900 font-medium">
                <AlertCircle className="h-3.5 w-3.5 text-amber-600 shrink-0" />
                <span>
                  <strong>Partial Operational Context:</strong> Some data feeds are unavailable or stale. Fallback mode active — baseline ETA preserved safely.
                </span>
              </div>
            )}

            {/* Operational Territory Service Radius Guard Notice */}
            {(!etaData.is_operationally_realistic || etaData.route_validity === 'OUT_OF_SERVICE_AREA') && (
              <div className="rounded-lg border border-amber-300 bg-amber-50 p-3.5 space-y-2 text-xs">
                <div className="flex items-center gap-2 text-amber-900 font-bold">
                  <ShieldAlert className="h-4 w-4 text-amber-600 shrink-0" />
                  <span className="uppercase tracking-wider font-extrabold text-[11px]">
                    Operational Territory Notice: Route Exceeds Service Radius
                  </span>
                </div>
                <p className="text-slate-700 font-medium leading-relaxed">
                  {etaData.service_range_message || 'Assigned technician is located outside the configured maximum service area territory radius. Normal transit dispatch is not operationally feasible.'}
                </p>
                <div className="flex items-center justify-between pt-1 text-[11px] font-mono text-slate-600 border-t border-amber-200">
                  <span>Actual Haversine Distance: <strong className="text-slate-900">{etaData.distance_miles?.toLocaleString()} mi ({etaData.distance_km?.toLocaleString()} km)</strong></span>
                  <span className="rounded bg-amber-200 border border-amber-400 px-2 py-0.5 text-[10px] font-extrabold text-amber-950">
                    UNSERVICEABLE ROUTE
                  </span>
                </div>
              </div>
            )}

            {/* Phase 4G: Truthful ETA Reliability & Provenance Indicator */}
            <div className="flex flex-wrap items-center justify-between gap-2 px-2.5 py-1.5 rounded-lg bg-slate-50 border border-slate-200 text-xs">
              <div className="flex items-center gap-2">
                <span className="text-[10px] uppercase font-bold text-slate-500">Route:</span>
                <span
                  className={cn(
                    'px-1.5 py-0.5 rounded text-[10px] font-mono font-extrabold uppercase border',
                    etaData.route_provenance === 'REAL'
                      ? 'bg-emerald-50 text-emerald-800 border-emerald-300'
                      : etaData.route_provenance === 'SYSTEM'
                      ? 'bg-purple-50 text-purple-800 border-purple-300'
                      : 'bg-amber-50 text-amber-800 border-amber-300'
                  )}
                >
                  {etaData.route_provenance || 'REAL'}
                </span>
                <span className="text-[10px] uppercase font-bold text-slate-500 ml-1">Reliability:</span>
                <span
                  className={cn(
                    'px-2 py-0.5 rounded text-[10px] font-mono font-extrabold uppercase border cursor-help',
                    (etaData.confidence_level === 'HIGH' || etaData.reliability_status === 'HIGH')
                      ? 'bg-emerald-100 text-emerald-900 border-emerald-300'
                      : (etaData.confidence_level === 'MEDIUM' || etaData.reliability_status === 'MEDIUM')
                      ? 'bg-blue-100 text-blue-900 border-blue-300'
                      : (etaData.confidence_level === 'LOW' || etaData.reliability_status === 'LOW')
                      ? 'bg-amber-100 text-amber-900 border-amber-300'
                      : (etaData.confidence_level === 'DEGRADED' || etaData.reliability_status === 'DEGRADED')
                      ? 'bg-orange-100 text-orange-900 border-orange-300'
                      : 'bg-rose-100 text-rose-900 border-rose-300'
                  )}
                  title={etaData.confidence_reason || 'Source reliability assessment'}
                >
                  {etaData.confidence_level || etaData.reliability_status || 'HIGH'}
                </span>
              </div>
              {etaData.confidence_reason && (
                <span
                  className="text-[10.5px] text-slate-600 truncate max-w-[280px] cursor-help font-medium"
                  title={etaData.confidence_reason}
                >
                  {etaData.confidence_reason}
                </span>
              )}
            </div>

            {/* Primary ETA Numbers Grid: Phase 3 Authoritative Decomposition */}
            <div className="grid grid-cols-3 gap-2">
              {/* Live Route Travel Time (Authoritative Road Baseline) */}
              <div className="rounded-lg border border-slate-200 bg-slate-50 p-3 text-center">
                <div className="text-[10px] uppercase font-bold text-slate-500 tracking-wider">
                  Live Route Base
                </div>
                <div className="mt-1 text-2xl font-black text-slate-900 font-mono">
                  {(!etaData.is_operationally_realistic || etaData.route_validity === 'OUT_OF_SERVICE_AREA') ? (
                    <span className="text-base text-slate-500 font-bold" title={`${etaData.baseline_eta_minutes} min raw baseline calculation`}>
                      — <span className="text-[10px] font-normal text-slate-400">({etaData.baseline_eta_minutes}m)</span>
                    </span>
                  ) : (
                    <>
                      {etaData.live_route_eta_minutes ?? etaData.baseline_eta_minutes}
                      <span className="text-xs font-normal text-slate-500"> min</span>
                    </>
                  )}
                </div>
                <div className="mt-0.5 text-[9.5px] text-slate-500 font-medium truncate">
                  Free-flow: {etaData.free_flow_eta_minutes ?? etaData.baseline_eta_minutes}m
                  {Boolean(etaData.traffic_delay_minutes && etaData.traffic_delay_minutes > 0) && (
                    <span className="text-amber-700 font-bold ml-1">
                      (+{etaData.traffic_delay_minutes}m traffic)
                    </span>
                  )}
                </div>
              </div>

              {/* Additional Verified Impact (Detour, Weather, Events beyond Live Route) */}
              <div className="rounded-lg border border-slate-200 bg-slate-50 p-3 text-center">
                <div className="text-[10px] uppercase font-bold text-slate-500 tracking-wider">
                  Verified Impact
                </div>
                <div
                  className={cn(
                    'mt-1 text-2xl font-black font-mono',
                    ((etaData.additional_verified_impact_minutes ?? 0) > 0)
                      ? 'text-amber-800'
                      : 'text-slate-700',
                  )}
                >
                  {(etaData.additional_verified_impact_minutes ?? 0) > 0
                    ? `+${etaData.additional_verified_impact_minutes}`
                    : '+0'}
                  <span className="text-xs font-normal text-slate-500"> min</span>
                </div>
                <div className="mt-0.5 text-[9.5px] text-slate-500 font-medium">
                  Detour + Weather + Events
                </div>
              </div>

              {/* Context-Aware ETA */}
              <div className={cn(
                "rounded-lg p-3 text-center shadow-2xs border",
                (!etaData.is_operationally_realistic || etaData.route_validity === 'OUT_OF_SERVICE_AREA')
                  ? "border-amber-300 bg-amber-50"
                  : "border-blue-200 bg-blue-50"
              )}>
                <div className={cn(
                  "text-[10px] uppercase font-extrabold tracking-wider flex items-center justify-center gap-1",
                  (!etaData.is_operationally_realistic || etaData.route_validity === 'OUT_OF_SERVICE_AREA')
                    ? "text-amber-800"
                    : "text-blue-700"
                )}>
                  <Sparkles className="h-3 w-3" />
                  <span>Context ETA</span>
                </div>
                {(!etaData.is_operationally_realistic || etaData.route_validity === 'OUT_OF_SERVICE_AREA') ? (
                  <div className="mt-1">
                    <div className="text-sm font-black text-amber-900 font-mono">
                      Out of Area
                    </div>
                    <div className="mt-0.5 text-[9px] text-amber-700 font-bold uppercase tracking-wider">
                      Unserviceable
                    </div>
                  </div>
                ) : (
                  <>
                    <div className="mt-1 text-2xl font-black text-blue-700 font-mono">
                      {etaData.final_dispatch_eta_minutes ?? etaData.context_aware_eta_minutes}
                      <span className="text-xs font-bold text-blue-600"> min</span>
                    </div>
                    <div className="mt-0.5 text-[9.5px] text-blue-700 font-bold">
                      {etaData.active_override ? 'Dispatcher Override' : 'Live + Verified'}
                    </div>
                  </>
                )}
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

              {/* Distance: Metric Primary, Miles Secondary */}
              {etaData.distance_km !== null && (
                <div className="rounded-lg border border-slate-200 bg-slate-50 p-2.5 flex items-center gap-2">
                  <MapPin className="h-4 w-4 text-emerald-600 shrink-0" />
                  <div className="min-w-0">
                    <div className="text-[10px] uppercase font-bold text-slate-500 tracking-wider">
                      Routed Distance
                    </div>
                    <div className="text-sm font-bold text-slate-900 font-mono">
                      {etaData.routed_distance_km ? `${etaData.routed_distance_km} km` : `${etaData.distance_km} km`}
                      <span className="text-[10px] font-medium text-slate-500 ml-1">
                        ({etaData.routed_distance_miles ?? etaData.distance_miles} mi)
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

            {/* Model Context Factors Breakdown */}
            {etaData.factors && etaData.factors.length > 0 && (
              <ContextFactorsPanel factors={etaData.factors} />
            )}

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

            {/* ── ETA ERROR EXPERIMENT PERFORMANCE PANEL (MODULE 12) ── */}
            {metrics && (
              <div className="rounded-lg border border-slate-200 bg-slate-50 p-3.5 space-y-3">
                <div className="flex items-center justify-between">
                  <span className="text-[10px] font-bold uppercase tracking-wider text-slate-600 flex items-center gap-1.5">
                    <Award className="h-3.5 w-3.5 text-emerald-600" />
                    <span>Model Prediction Accuracy (MAE Experiment)</span>
                  </span>
                  <span className="text-[9px] font-mono text-emerald-800 font-bold bg-emerald-50 px-2 py-0.5 rounded border border-emerald-200">
                    +{metrics.improvement_percent}% Error Reduction
                  </span>
                </div>

                {/* Simulation Transparency Badge */}
                {metrics.is_simulated_dataset && (
                  <div className="flex items-center gap-1.5 bg-amber-50/80 border border-amber-200 px-2.5 py-1 rounded text-[10px] text-amber-900 font-medium">
                    <Database className="h-3 w-3 text-amber-600 shrink-0" />
                    <span className="font-bold">Evaluation Benchmark:</span>
                    <span>{metrics.disclaimer || 'Simulated evaluation — not real-world historical validation.'}</span>
                  </div>
                )}

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

                {/* Collapsible Sample Breakdown & Error Analysis Toggle */}
                {((metrics.sample_breakdown && metrics.sample_breakdown.length > 0) || (metrics.error_analysis && metrics.error_analysis.length > 0)) && (
                  <div className="pt-2 border-t border-slate-200">
                    <button
                      onClick={() => setShowBreakdown(!showBreakdown)}
                      className="w-full flex items-center justify-between text-xs font-bold text-slate-700 hover:text-blue-700 py-1 transition-colors"
                    >
                      <span className="flex items-center gap-1.5">
                        <FileText className="h-3.5 w-3.5 text-blue-600" />
                        <span>View Sample Breakdown ({metrics.sample_count} Scenarios) & Error Analysis</span>
                      </span>
                      {showBreakdown ? <ChevronUp className="h-3.5 w-3.5" /> : <ChevronDown className="h-3.5 w-3.5" />}
                    </button>

                    {showBreakdown && (
                      <div className="mt-3 space-y-3">
                        {/* Sample Breakdown Table */}
                        {metrics.sample_breakdown && metrics.sample_breakdown.length > 0 && (
                          <div className="overflow-x-auto rounded-lg border border-slate-200 bg-white max-h-56">
                            <table className="w-full text-left text-[10px]">
                              <thead className="bg-slate-100 text-slate-600 uppercase sticky top-0 font-mono font-bold">
                                <tr>
                                  <th className="py-1 px-2">#</th>
                                  <th className="py-1 px-2">Dist</th>
                                  <th className="py-1 px-2">Base ETA</th>
                                  <th className="py-1 px-2">Context ETA</th>
                                  <th className="py-1 px-2">Actual</th>
                                  <th className="py-1 px-2">Base Err</th>
                                  <th className="py-1 px-2">Context Err</th>
                                  <th className="py-1 px-2">Imprv</th>
                                  <th className="py-1 px-2">Conditions</th>
                                </tr>
                              </thead>
                              <tbody className="divide-y divide-slate-100 font-mono">
                                {metrics.sample_breakdown.slice(0, 15).map((s) => (
                                  <tr key={s.id} className={cn(s.is_non_routine ? 'bg-amber-50/40' : 'hover:bg-slate-50')}>
                                    <td className="py-1 px-2 text-slate-500 font-bold">#{s.id}</td>
                                    <td className="py-1 px-2 text-slate-800">{s.distance_km}km</td>
                                    <td className="py-1 px-2 text-slate-700">{s.baseline_eta_minutes}m</td>
                                    <td className="py-1 px-2 text-blue-700 font-bold">{s.context_aware_eta_minutes}m</td>
                                    <td className="py-1 px-2 text-slate-900 font-bold">{s.actual_travel_minutes}m</td>
                                    <td className="py-1 px-2 text-amber-800 font-bold">+{s.baseline_absolute_error}m</td>
                                    <td className="py-1 px-2 text-emerald-700 font-bold">+{s.context_aware_absolute_error}m</td>
                                    <td className="py-1 px-2 text-emerald-800 font-black">+{s.improvement_minutes}m</td>
                                    <td className="py-1 px-2 font-sans text-[9px] text-slate-600 truncate max-w-[120px]">{s.conditions}</td>
                                  </tr>
                                ))}
                              </tbody>
                            </table>
                            {metrics.sample_breakdown.length > 15 && (
                              <div className="text-[9px] text-slate-500 text-center py-1 bg-slate-50 border-t border-slate-100 font-medium">
                                Showing 15 of {metrics.sample_breakdown.length} benchmark evaluation samples.
                              </div>
                            )}
                          </div>
                        )}

                        {/* Error Analysis Operational Cards */}
                        {metrics.error_analysis && metrics.error_analysis.length > 0 && (
                          <div className="space-y-1.5 pt-1">
                            <span className="text-[10px] font-bold uppercase tracking-wider text-slate-600 block">
                              Categorized Operational Error Analysis
                            </span>
                            <div className="grid grid-cols-1 gap-1.5">
                              {metrics.error_analysis.map((ea, idx) => (
                                <div key={idx} className="rounded bg-white border border-slate-200 p-2 space-y-0.5">
                                  <span className="text-[10px] font-bold text-slate-800 block">{ea.category}</span>
                                  <p className="text-[10px] text-slate-600 leading-snug">{ea.finding}</p>
                                </div>
                              ))}
                            </div>
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                )}
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

function ContextFactorsPanel({ factors }: { factors: ContextFactor[] }) {
  if (!factors || factors.length === 0) return null;

  return (
    <div className="space-y-1.5">
      <div className="flex items-center justify-between px-1">
        <span className="text-[10px] font-bold uppercase tracking-wider text-slate-500">
          Model Factors &amp; Adjustments
        </span>
        <span className="text-[10px] text-slate-500 font-mono">
          {factors.length} factors evaluated
        </span>
      </div>
      <div className="space-y-1">
        {factors.map((f, idx) => (
          <div key={idx} className="py-1.5 px-2.5 rounded-lg bg-slate-50 border border-slate-200 flex items-start justify-between gap-2">
            <div className="min-w-0 flex-1">
              <div className="flex items-center gap-1.5 flex-wrap">
                <span className="text-[11px] font-bold text-slate-800 truncate">{f.factor}</span>
                <span className="px-1.5 py-0.2 rounded text-[8px] font-extrabold uppercase font-mono bg-blue-100 text-blue-800 border border-blue-300">
                  {f.provenance || 'DERIVED'}
                </span>
                {freshnessBadge(f.freshness, f.data_age_seconds)}
                {classificationBadge(f.impact_classification)}
                {f.relevance_status && (
                  <span
                    className={cn(
                      'px-1.5 py-0.2 rounded text-[8px] font-extrabold uppercase font-mono border',
                      f.relevance_status === 'RELEVANT'
                        ? 'bg-emerald-50 text-emerald-800 border-emerald-300'
                        : 'bg-slate-100 text-slate-600 border-slate-300'
                    )}
                  >
                    {f.relevance_status === 'RELEVANT' ? 'Relevant' : 'Not Relevant'}
                  </span>
                )}
                {f.is_route_relevant === false && !f.relevance_status && (
                  <span className="px-1.5 py-0.2 rounded text-[8px] font-extrabold uppercase font-mono bg-slate-200 text-slate-700" title="Factor is outside route corridor; 0m impact applied">
                    OFF-CORRIDOR
                  </span>
                )}
                {f.distance_to_route_display && (
                  <span className="text-[8.5px] font-mono text-slate-500 bg-slate-100 px-1 py-0.2 rounded border border-slate-200">
                    dist: {f.distance_to_route_display}
                  </span>
                )}
              </div>
              <p className="text-[10px] text-slate-600 mt-0.5">{f.description}</p>
              {f.relevance_reason && (
                <p className="text-[9px] text-slate-500 italic mt-0.5 leading-snug">
                  Why: {f.relevance_reason}
                </p>
              )}
            </div>
            <div className="text-right shrink-0 pt-0.5">
              <span className={cn(
                "font-mono text-xs font-extrabold",
                f.impact_minutes > 0 ? "text-amber-700" : f.impact_minutes < 0 ? "text-emerald-700" : "text-slate-500"
              )}>
                {f.impact_minutes > 0 ? `+${f.impact_minutes}m` : `${f.impact_minutes}m`}
              </span>
            </div>
          </div>
        ))}
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
          Context Data Sources (Telemetry Feeds)
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
