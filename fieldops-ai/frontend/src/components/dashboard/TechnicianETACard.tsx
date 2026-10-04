import { useState, useEffect, useCallback, useRef } from 'react';
import axios from 'axios';
import { Navigation, Clock, CloudRain, Sparkles, AlertCircle, RefreshCw, MapPin, CalendarClock, Compass } from 'lucide-react';
import { etaService } from '@/services/eta.service';
import type { ETAResponse } from '@/types/eta.types';
import type { ETAUpdatedEventData, RealtimeEvent } from '@/types/realtime.types';
import { useRealtimeSync } from '@/hooks/useRealtimeSync';
import { cn } from '@/utils/cn';

import { TechnicianLocationModal } from '@/components/common/TechnicianLocationModal';

interface TechnicianETACardProps {
  jobId: string;
  className?: string;
  assignedJobLocation?: {
    latitude: number;
    longitude: number;
    address?: string;
  } | null | undefined;
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

export function TechnicianETACard({ jobId, className, assignedJobLocation }: TechnicianETACardProps) {
  const [etaData, setEtaData] = useState<ETAResponse | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [isRefreshing, setIsRefreshing] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [isLocationModalOpen, setIsLocationModalOpen] = useState<boolean>(false);

  // Stale and duplicate event protection refs
  const lastCalculatedAtRef = useRef<number>(0);
  const lastEventKeyRef = useRef<string>('');
  const inFlightAbortRef = useRef<AbortController | null>(null);
  const isFetchingRef = useRef<boolean>(false);

  const fetchEta = useCallback(async (isInitial = false) => {
    // If a background fetch is already in flight and not an initial load, skip duplicate request
    if (isFetchingRef.current && !isInitial) {
      return;
    }

    // Cancel any previous in-flight request
    if (inFlightAbortRef.current) {
      inFlightAbortRef.current.abort();
    }
    const abortController = new AbortController();
    inFlightAbortRef.current = abortController;
    isFetchingRef.current = true;

    if (isInitial) {
      setIsLoading(true);
    } else {
      setIsRefreshing(true);
    }
    setError(null);

    try {
      const data = await etaService.getJobEta(jobId, undefined, undefined, abortController.signal);
      setEtaData(data);
      if (data.calculated_at) {
        lastCalculatedAtRef.current = new Date(data.calculated_at).getTime();
      }
    } catch (err: unknown) {
      // Ignore cleanly aborted in-flight requests
      if (axios.isCancel(err) || (err instanceof Error && err.name === 'CanceledError')) {
        return;
      }
      console.error('Failed to load technician job ETA', err);
      const msg = err instanceof Error ? err.message : 'Could not calculate travel ETA.';
      setError(msg);
      if (isInitial) setEtaData(null);
    } finally {
      if (inFlightAbortRef.current === abortController) {
        inFlightAbortRef.current = null;
        isFetchingRef.current = false;
        if (isInitial) {
          setIsLoading(false);
        }
        setIsRefreshing(false);
      }
    }
  }, [jobId]);

  // Real-time synchronization: update directly from authoritative WebSocket ETA_UPDATED event
  useRealtimeSync(
    ['ETA_UPDATED'],
    (event: RealtimeEvent<ETAUpdatedEventData>) => {
      const data = event.data;
      if (!data || !data.job_id) return;
      // Job identity verification: only update if event matches this card's job
      if (data.job_id !== jobId) return;

      const eventTimestamp = data.calculated_at || data.updated_at || event.timestamp;

      // Duplicate event protection
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

      // Atomic UI state update without loading flash or temporary unavailable state
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
        setIsRefreshing(false);
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
          };
        });
        setIsLoading(false);
        setIsRefreshing(false);
        setError(null);
      }
    },
    () => fetchEta(false),
  );

  useEffect(() => {
    const handleLocationUpdated = () => {
      fetchEta(false);
    };
    window.addEventListener('fieldops:technician_location_updated', handleLocationUpdated);
    return () => {
      window.removeEventListener('fieldops:technician_location_updated', handleLocationUpdated);
    };
  }, [fetchEta]);

  useEffect(() => {
    fetchEta(true);
    return () => {
      if (inFlightAbortRef.current) {
        inFlightAbortRef.current.abort();
      }
    };
  }, [fetchEta]);

  return (
    <div
      className={cn(
        'rounded-xl border border-blue-200 bg-white p-4 space-y-3 shadow-xs select-none',
        className,
      )}
    >
      <div className="flex items-center justify-between border-b border-slate-100 pb-2">
        <div className="flex items-center gap-1.5 flex-wrap">
          <span className="inline-flex items-center gap-1 text-xs font-extrabold uppercase tracking-wider text-blue-700">
            <Navigation className="h-3.5 w-3.5" />
            <span>Transit &amp; ETA Telemetry</span>
          </span>
          {etaData && (
            <>
              <span className={cn(
                "rounded px-1.5 py-0.5 text-[8.5px] font-mono font-bold border",
                etaData.route_provenance === 'REAL'
                  ? 'bg-emerald-50 text-emerald-800 border-emerald-300'
                  : etaData.route_provenance === 'SYSTEM'
                  ? 'bg-purple-50 text-purple-800 border-purple-300'
                  : 'bg-amber-50 text-amber-800 border-amber-300'
              )}>
                Route: {etaData.route_provenance || 'REAL'}
              </span>
              <span
                className={cn(
                  "rounded px-1.5 py-0.5 text-[8.5px] font-mono font-bold border cursor-help",
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
                Reliability: {etaData.confidence_level || etaData.reliability_status || 'HIGH'}
              </span>
            </>
          )}
        </div>

        <div className="flex items-center gap-1.5">
          <button
            type="button"
            onClick={() => setIsLocationModalOpen(true)}
            className="inline-flex items-center gap-1 rounded-md border border-slate-200 bg-slate-50 hover:bg-slate-100 px-2 py-1 text-[10px] font-bold text-slate-700 transition-colors cursor-pointer"
            title="Calibrate technician GPS location"
          >
            <Compass className="h-3 w-3 text-purple-600" />
            <span>Calibrate GPS</span>
          </button>
          <button
            onClick={() => fetchEta(false)}
            disabled={isLoading || isRefreshing}
            title="Refresh Travel ETA"
            className="p-1 rounded text-slate-400 hover:text-slate-700 hover:bg-slate-100 transition-colors disabled:opacity-50 cursor-pointer"
          >
            <RefreshCw className={cn('h-3 w-3', (isLoading || isRefreshing) && 'animate-spin')} />
          </button>
        </div>
      </div>

      {isLoading ? (
        <div className="py-4 text-center text-xs text-slate-500 animate-pulse flex items-center justify-center gap-2 font-medium">
          <Clock className="h-3.5 w-3.5 text-blue-600" />
          <span>Calculating transit route &amp; context conditions...</span>
        </div>
      ) : error ? (
        <div className="py-2 text-center text-xs text-rose-600 flex items-center justify-center gap-1.5 font-bold">
          <AlertCircle className="h-3.5 w-3.5 shrink-0 text-rose-500" />
          <span>{error}</span>
        </div>
      ) : etaData && !etaData.is_context_sufficient ? (
        <div className="rounded-lg bg-amber-50 border border-amber-200 p-3 text-xs text-amber-900 space-y-1">
          <div className="font-bold flex items-center gap-1.5 text-amber-800">
            <AlertCircle className="h-3.5 w-3.5 shrink-0 text-amber-600" />
            <span>ETA Telemetry Unavailable</span>
          </div>
          <p className="text-[11px] text-slate-600">{etaData.reason}</p>
        </div>
      ) : etaData ? (
        <div className="space-y-3">
          {/* Operational Territory Service Radius Guard Notice */}
          {(!etaData.is_operationally_realistic || etaData.route_validity === 'OUT_OF_SERVICE_AREA') && (
            <div className="rounded-lg bg-amber-50 border border-amber-300 p-3 text-xs text-amber-950 space-y-2">
              <div className="font-bold flex items-center justify-between gap-1.5 text-amber-900">
                <div className="flex items-center gap-1.5">
                  <AlertCircle className="h-4 w-4 shrink-0 text-amber-600" />
                  <span className="font-extrabold uppercase text-[10px] tracking-wider">Outside Service Territory</span>
                </div>
                <button
                  type="button"
                  onClick={() => setIsLocationModalOpen(true)}
                  className="inline-flex items-center gap-1 rounded-lg bg-amber-600 hover:bg-amber-700 text-white font-bold px-2.5 py-1 text-[10px] shadow-2xs transition-colors cursor-pointer"
                >
                  <MapPin className="h-3 w-3" />
                  <span>Fix Location</span>
                </button>
              </div>
              <p className="text-[11px] text-slate-700 leading-snug">
                {etaData.service_range_message || 'Technician location is outside viable service radius. Standard driving transit is unserviceable.'}
              </p>
              <div className="pt-0.5 flex items-center gap-2">
                <button
                  type="button"
                  onClick={() => setIsLocationModalOpen(true)}
                  className="inline-flex items-center gap-1.5 rounded-lg border border-amber-400 bg-white hover:bg-amber-100 text-amber-900 font-bold px-2.5 py-1 text-[11px] shadow-2xs transition-colors cursor-pointer"
                >
                  <Compass className="h-3.5 w-3.5 text-amber-700" />
                  <span>Is your location incorrect? Click to Calibrate Location</span>
                </button>
              </div>
            </div>
          )}

          {/* Key Metric Numbers */}
          <div className="grid grid-cols-3 gap-2 text-center">
            <div className="p-2 rounded-lg bg-slate-50 border border-slate-200">
              <span className="text-[9px] uppercase font-bold text-slate-500 block tracking-wider">
                Baseline ETA
              </span>
              <span className="text-base font-black text-slate-900 font-mono">
                {(!etaData.is_operationally_realistic || etaData.route_validity === 'OUT_OF_SERVICE_AREA') ? (
                  <span className="text-xs text-slate-500 font-bold" title={`${etaData.baseline_eta_minutes} min raw baseline`}>
                    — <span className="text-[9px] font-normal text-slate-400">({etaData.baseline_eta_minutes}m)</span>
                  </span>
                ) : (
                  <>
                    {etaData.baseline_eta_minutes}{' '}
                    <span className="text-[10px] text-slate-500 font-normal">min</span>
                  </>
                )}
              </span>
            </div>

            <div className={cn(
              "p-2 rounded-lg border",
              (!etaData.is_operationally_realistic || etaData.route_validity === 'OUT_OF_SERVICE_AREA')
                ? "bg-amber-50 border-amber-300"
                : "bg-blue-50 border-blue-200"
            )}>
              <span className={cn(
                "text-[9px] uppercase font-extrabold block tracking-wider flex items-center justify-center gap-0.5",
                (!etaData.is_operationally_realistic || etaData.route_validity === 'OUT_OF_SERVICE_AREA')
                  ? "text-amber-800"
                  : "text-blue-700"
              )}>
                <Sparkles className="h-2.5 w-2.5" />
                <span>Context ETA</span>
              </span>
              {(!etaData.is_operationally_realistic || etaData.route_validity === 'OUT_OF_SERVICE_AREA') ? (
                <span className="text-xs font-black text-amber-900 font-mono block mt-0.5">
                  Out of Area
                </span>
              ) : (
                <span className="text-base font-black text-blue-700 font-mono">
                  {etaData.context_aware_eta_minutes}{' '}
                  <span className="text-[10px] text-blue-600 font-normal">min</span>
                </span>
              )}
            </div>

            <div className="p-2 rounded-lg bg-slate-50 border border-slate-200">
              <span className="text-[9px] uppercase font-bold text-slate-500 block tracking-wider">
                Adjustment
              </span>
              <span
                className={cn(
                  'text-base font-black font-mono',
                  (etaData.adjustment_minutes || 0) > 0 ? 'text-amber-800' : 'text-slate-700',
                )}
              >
                {(etaData.adjustment_minutes || 0) > 0
                  ? `+${etaData.adjustment_minutes}`
                  : etaData.adjustment_minutes}{' '}
                <span className="text-[10px] text-slate-500 font-normal">min</span>
              </span>
            </div>
          </div>

          {/* Estimated Arrival + Distance */}
          <div className="grid grid-cols-2 gap-2">
            {etaData.estimated_arrival_time && (
              <div className="flex items-center gap-2 p-2 rounded-lg bg-slate-50 border border-slate-200">
                <CalendarClock className="h-3.5 w-3.5 text-blue-600 shrink-0" />
                <div className="min-w-0">
                  <div className="text-[9px] uppercase font-bold text-slate-500 tracking-wider">
                    Est. Arrival
                  </div>
                  <div className="text-xs font-bold text-slate-900 font-mono truncate">
                    {formatArrivalTime(etaData.estimated_arrival_time)}
                  </div>
                </div>
              </div>
            )}

            {etaData.distance_km !== null && (
              <div className="flex items-center gap-2 p-2 rounded-lg bg-slate-50 border border-slate-200">
                <MapPin className="h-3.5 w-3.5 text-emerald-600 shrink-0" />
                <div className="min-w-0">
                  <div className="text-[9px] uppercase font-bold text-slate-500 tracking-wider">
                    Distance
                  </div>
                  <div className="text-xs font-bold text-slate-900 font-mono">
                    {etaData.distance_km} km
                  </div>
                </div>
              </div>
            )}
          </div>

          {/* Operational Transit Explanation */}
          <div className="flex items-center justify-between text-[11px] px-1 text-slate-600">
            <div className="flex items-center gap-1.5 truncate">
              <CloudRain className="h-3.5 w-3.5 text-blue-600 shrink-0" />
              <span className="truncate font-medium">{etaData.reason}</span>
            </div>
          </div>

          {/* Operational Road Restriction Alert Banner */}
          {(() => {
            const roadSource = etaData.data_sources?.find((s) => s.category === 'ROAD' && s.status === 'AVAILABLE');
            if (!roadSource || (!roadSource.is_road_closed && roadSource.impact_minutes <= 0 && !roadSource.active_restriction_name)) {
              return null;
            }
            const isRelevant = roadSource.is_route_relevant !== false && roadSource.relevance_status !== 'NOT_RELEVANT';
            return (
              <div
                className={cn(
                  'p-2 rounded-lg border text-xs flex items-start gap-2',
                  isRelevant && roadSource.is_road_closed
                    ? 'bg-rose-50 border-rose-200 text-rose-900'
                    : isRelevant && roadSource.impact_minutes > 0
                    ? 'bg-amber-50 border-amber-200 text-amber-900'
                    : 'bg-slate-50 border-slate-200 text-slate-800',
                )}
              >
                <AlertCircle
                  className={cn(
                    'h-4 w-4 shrink-0 mt-0.5',
                    isRelevant && roadSource.is_road_closed ? 'text-rose-600' : isRelevant ? 'text-amber-600' : 'text-slate-500',
                  )}
                />
                <div className="min-w-0 flex-1">
                  <div className="font-bold flex items-center gap-1.5 flex-wrap">
                    <span>
                      {isRelevant
                        ? (roadSource.is_road_closed ? 'Road Restriction Ahead: Closure' : 'Road Restriction Ahead')
                        : 'Road Incident Nearby (Off-Corridor)'}
                    </span>
                    {isRelevant && roadSource.impact_minutes > 0 ? (
                      <span className="font-mono text-[10px] px-1 py-0.2 bg-amber-200/80 rounded font-extrabold text-amber-950">
                        ETA impact: +{roadSource.impact_minutes} min {roadSource.detour_seconds && roadSource.detour_seconds > 0 ? '(Detour)' : '(Incident Delay)'}
                      </span>
                    ) : isRelevant && roadSource.detour_seconds && roadSource.detour_seconds > 0 ? (
                      <span className="font-mono text-[9.5px] px-1.5 py-0.2 bg-amber-100 text-amber-900 border border-amber-300 rounded font-bold">
                        {roadSource.detour_display || `${roadSource.detour_seconds}s detour (<1 min)`}
                      </span>
                    ) : (
                      <span className="font-mono text-[9px] px-1 py-0.2 bg-slate-200 text-slate-700 rounded font-bold">
                        0 min impact
                      </span>
                    )}
                  </div>
                  <div className="text-[11px] text-slate-600 mt-0.5">
                    {isRelevant
                      ? `${roadSource.is_road_closed ? 'Major closure' : roadSource.restriction_severity || 'Incident'}${roadSource.active_restriction_name ? ` on ${roadSource.active_restriction_name}` : ''}`
                      : `${roadSource.active_restriction_name || 'Incident'} detected outside selected route corridor — no ETA penalty`}
                  </div>
                  {roadSource.relevance_reason && (
                    <div className="text-[9.5px] text-slate-500 italic mt-0.5">
                      {roadSource.relevance_reason}
                    </div>
                  )}
                </div>
              </div>
            );
          })()}

          {/* Context Data Source Provenance Breakdown */}
          {etaData.data_sources && etaData.data_sources.length > 0 && (
            <div className="border-t border-slate-100 pt-2 space-y-1.5">
              <div className="text-[10px] uppercase font-bold text-slate-400 tracking-wider">
                Context Pipeline &amp; Data Provenance
              </div>
              <div className="space-y-1">
                {etaData.data_sources.map((src) => {
                  const provenance = src.provenance ?? (src.status === 'UNAVAILABLE' ? 'UNAVAILABLE' : 'DERIVED');
                  const isUnavailable = src.status === 'UNAVAILABLE' || provenance === 'UNAVAILABLE';

                  const badgeText = isUnavailable ? 'UNAVAILABLE' : provenance;
                  const badgeClass = isUnavailable
                    ? 'bg-slate-100 text-slate-500 border-slate-200'
                    : provenance === 'REAL'
                      ? 'bg-emerald-100 text-emerald-800 border border-emerald-300'
                      : provenance === 'SYSTEM'
                        ? 'bg-purple-100 text-purple-800 border border-purple-300'
                        : 'bg-blue-100 text-blue-800 border border-blue-300';

                  const relBadge = src.category !== 'WEATHER' && src.relevance_status === 'RELEVANT'
                    ? { text: 'Relevant', cls: 'bg-emerald-100 text-emerald-800' }
                    : src.category !== 'WEATHER' && src.relevance_status === 'NOT_RELEVANT'
                    ? { text: 'Off-Route', cls: 'bg-slate-200 text-slate-600' }
                    : null;

                  return (
                    <div
                      key={src.name}
                      className="flex items-start justify-between gap-2 p-1.5 rounded-md bg-slate-50 border border-slate-200"
                    >
                      <div className="min-w-0 flex-1">
                        <div className="flex items-center gap-1.5 flex-wrap">
                          <span className="font-semibold text-slate-700 text-[10px] truncate">
                            {src.category === 'EVENTS' && src.provenance === 'REAL'
                              ? 'Events (PredictHQ)'
                              : src.category === 'ROAD' && src.provenance === 'REAL'
                              ? 'Road Restrictions (TomTom)'
                              : src.category === 'WEATHER'
                              ? (src.provenance === 'REAL' ? 'Weather Data (Open-Meteo API)' : 'Weather Data (Open-Meteo)')
                              : src.name}
                          </span>
                          {relBadge && (
                            <span className={cn('px-1 py-0.1 rounded text-[7.5px] font-extrabold uppercase font-mono', relBadge.cls)}>
                              {relBadge.text}
                            </span>
                          )}
                          {src.impact_minutes > 0 ? (
                            <span className="font-mono text-[9px] font-extrabold text-amber-700 shrink-0">
                              +{src.impact_minutes}m
                            </span>
                          ) : src.status === 'AVAILABLE' && (src.category === 'ROAD' || src.category === 'EVENTS') ? (
                            <span className="font-mono text-[8.5px] font-bold text-slate-400 shrink-0">
                              0m
                            </span>
                          ) : null}
                        </div>
                        {!isUnavailable && src.description && (
                          <p className="text-[9px] text-slate-500 mt-0.5 leading-tight truncate" title={src.description}>
                            {src.description}
                          </p>
                        )}
                        {!isUnavailable && src.relevance_reason && (
                          <p className="text-[8px] text-slate-500 italic truncate mt-0.5">
                            {src.relevance_reason}
                          </p>
                        )}
                      </div>
                      <span
                        className={cn(
                          'px-1.5 py-0.5 rounded text-[8px] font-extrabold uppercase font-mono shrink-0',
                          badgeClass,
                        )}
                      >
                        {badgeText}
                      </span>
                    </div>
                  );
                })}
              </div>
            </div>
          )}

        </div>
      ) : null}

      <TechnicianLocationModal
        isOpen={isLocationModalOpen}
        onClose={() => setIsLocationModalOpen(false)}
        assignedJobLocation={assignedJobLocation}
        onLocationUpdated={() => fetchEta(true)}
      />
    </div>
  );
}
