import { useState, useEffect, useRef } from 'react';
import { Sparkles, Clock, AlertCircle } from 'lucide-react';
import { etaService } from '@/services/eta.service';
import type { ETAResponse } from '@/types/eta.types';
import type { ETAUpdatedEventData, RealtimeEvent } from '@/types/realtime.types';
import { useRealtimeSync } from '@/hooks/useRealtimeSync';
import { cn } from '@/utils/cn';

interface JobETABadgeProps {
  jobId: string;
  className?: string;
  onClick?: () => void;
}

export function JobETABadge({ jobId, className, onClick }: JobETABadgeProps) {
  const [etaData, setEtaData] = useState<ETAResponse | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const lastCalculatedAtRef = useRef<number>(0);
  const lastEventKeyRef = useRef<string>('');

  const fetchEta = () => {
    etaService
      .getJobEta(jobId)
      .then((data) => {
        setEtaData(data);
        if (data.calculated_at) {
          lastCalculatedAtRef.current = new Date(data.calculated_at).getTime();
        }
      })
      .catch(() => {
        setEtaData(null);
      })
      .finally(() => {
        setIsLoading(false);
      });
  };

  useEffect(() => {
    setIsLoading(true);
    fetchEta();
  }, [jobId]);

  useRealtimeSync(
    ['ETA_UPDATED'],
    (event: RealtimeEvent<ETAUpdatedEventData>) => {
      const data = event.data;
      if (!data || data.job_id !== jobId) return;

      const eventTimestamp = data.calculated_at || data.updated_at || event.timestamp;
      const eventKey = `${event.event}_${data.job_id}_${eventTimestamp}_${data.context_aware_eta_minutes ?? data.overridden_eta ?? ''}`;
      if (lastEventKeyRef.current === eventKey) return;
      lastEventKeyRef.current = eventKey;

      const incomingTime = new Date(eventTimestamp).getTime();
      if (!isNaN(incomingTime) && lastCalculatedAtRef.current && incomingTime < lastCalculatedAtRef.current) return;
      if (!isNaN(incomingTime)) lastCalculatedAtRef.current = incomingTime;

      if (data.context_aware_eta_minutes !== undefined || data.baseline_eta_minutes !== undefined) {
        setEtaData((prev) => ({
          ...(prev || ({} as ETAResponse)),
          ...(data as unknown as ETAResponse),
          job_id: data.job_id,
          context_aware_eta_minutes: data.context_aware_eta_minutes ?? prev?.context_aware_eta_minutes ?? null,
          baseline_eta_minutes: data.baseline_eta_minutes ?? prev?.baseline_eta_minutes ?? null,
          adjustment_minutes: data.adjustment_minutes ?? prev?.adjustment_minutes ?? null,
          is_context_sufficient: data.is_context_sufficient ?? (prev ? prev.is_context_sufficient : true),
          confidence_level: data.confidence_level ?? prev?.confidence_level ?? 'HIGH',
          confidence_reason: data.confidence_reason ?? prev?.confidence_reason ?? '',
          reliability_status: data.reliability_status ?? prev?.reliability_status ?? 'HIGH',
        }));
        setIsLoading(false);
      } else if (data.overridden_eta !== undefined) {
        setEtaData((prev) => {
          if (!prev) return null;
          return {
            ...prev,
            context_aware_eta_minutes: data.overridden_eta ?? prev.context_aware_eta_minutes,
            final_dispatch_eta_minutes: data.overridden_eta ?? prev.final_dispatch_eta_minutes,
            confidence_level: (data.confidence_level as any) || 'HIGH',
            confidence_reason: data.confidence_reason || 'Dispatcher manual override active',
            reliability_status: (data.reliability_status as any) || 'HIGH',
          };
        });
        setIsLoading(false);
      }
    },
    () => fetchEta(),
  );

  if (isLoading) {
    return (
      <span className={cn('inline-flex items-center gap-1 text-[11px] text-slate-400 font-mono animate-pulse', className)}>
        <Clock className="h-3 w-3" />
        <span>Calculating...</span>
      </span>
    );
  }

  if (etaData && (etaData.is_operationally_realistic === false || etaData.route_validity === 'OUT_OF_SERVICE_AREA')) {
    return (
      <span
        title={etaData.service_range_message || 'Technician location is outside operational service territory'}
        onClick={onClick}
        className={cn(
          'inline-flex items-center gap-1 rounded-md bg-amber-50 border border-amber-300 px-2 py-0.5 text-[11px] text-amber-800 font-semibold cursor-help',
          className,
        )}
      >
        <AlertCircle className="h-3 w-3 text-amber-600" />
        <span>Out of Area</span>
      </span>
    );
  }

  if (!etaData || !etaData.is_context_sufficient || etaData.context_aware_eta_minutes === null) {
    return (
      <span
        title={etaData?.confidence_reason || etaData?.reason || 'Missing context: unassigned or no telemetry'}
        onClick={onClick}
        className={cn(
          'inline-flex items-center gap-1 rounded-md bg-slate-100 border border-slate-200 px-2 py-0.5 text-[11px] text-slate-500 font-semibold cursor-help',
          className,
        )}
      >
        <AlertCircle className="h-3 w-3 text-slate-400" />
        <span>Unavailable</span>
      </span>
    );
  }

  return (
    <span
      title={`Baseline: ${etaData.baseline_eta_minutes}m • Adjusted: ${etaData.context_aware_eta_minutes}m • Route: ${etaData.route_provenance || 'REAL'} • Reliability: ${etaData.confidence_level || 'HIGH'}${etaData.confidence_reason ? ` (${etaData.confidence_reason})` : ` (${etaData.reason})`}`}
      onClick={onClick}
      className={cn(
        'inline-flex items-center gap-1.5 rounded-md border px-2 py-0.5 text-[11px] font-mono font-bold cursor-pointer transition-all shadow-2xs',
        (etaData.adjustment_minutes || 0) > 0
          ? 'bg-amber-50 border-amber-200 text-amber-900 hover:bg-amber-100'
          : 'bg-blue-50 border-blue-200 text-blue-800 hover:bg-blue-100',
        className,
      )}
    >
      <Sparkles className="h-3 w-3 text-blue-600" />
      <span>{etaData.context_aware_eta_minutes} min</span>
      {(etaData.adjustment_minutes || 0) > 0 && (
        <span className="text-[10px] text-amber-700 font-extrabold">+{etaData.adjustment_minutes}m</span>
      )}
    </span>
  );
}
