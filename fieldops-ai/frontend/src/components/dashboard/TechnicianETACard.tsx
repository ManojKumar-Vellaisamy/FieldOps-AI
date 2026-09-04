import { useState, useEffect } from 'react';
import { Navigation, Clock, CloudRain, Sparkles, AlertCircle, RefreshCw, MapPin, CalendarClock } from 'lucide-react';
import { etaService } from '@/services/eta.service';
import type { ETAResponse } from '@/types/eta.types';
import { cn } from '@/utils/cn';

interface TechnicianETACardProps {
  jobId: string;
  className?: string;
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

export function TechnicianETACard({ jobId, className }: TechnicianETACardProps) {
  const [etaData, setEtaData] = useState<ETAResponse | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  const fetchEta = async () => {
    setIsLoading(true);
    setError(null);
    try {
      const data = await etaService.getJobEta(jobId);
      setEtaData(data);
    } catch (err: unknown) {
      console.error('Failed to load technician job ETA', err);
      const msg = err instanceof Error ? err.message : 'Could not calculate travel ETA.';
      setError(msg);
      setEtaData(null);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchEta();
  }, [jobId]);

  return (
    <div
      className={cn(
        'rounded-xl border border-blue-200 bg-white p-4 space-y-3 shadow-xs select-none',
        className,
      )}
    >
      <div className="flex items-center justify-between border-b border-slate-100 pb-2">
        <div className="flex items-center gap-2">
          <span className="inline-flex items-center gap-1 text-xs font-extrabold uppercase tracking-wider text-blue-700">
            <Navigation className="h-3.5 w-3.5" />
            <span>Transit &amp; ETA Telemetry</span>
          </span>
          <span className="rounded bg-blue-50 border border-blue-200 px-1.5 py-0.5 text-[9px] font-mono font-bold text-blue-700">
            Live
          </span>
        </div>

        <button
          onClick={fetchEta}
          disabled={isLoading}
          title="Refresh Travel ETA"
          className="p-1 rounded text-slate-400 hover:text-slate-700 hover:bg-slate-100 transition-colors disabled:opacity-50"
        >
          <RefreshCw className={cn('h-3 w-3', isLoading && 'animate-spin')} />
        </button>
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
            <span>ETA Unavailable</span>
          </div>
          <p className="text-[11px] text-slate-600">{etaData.reason}</p>
        </div>
      ) : etaData ? (
        <div className="space-y-3">
          {/* Key Metric Numbers */}
          <div className="grid grid-cols-3 gap-2 text-center">
            <div className="p-2 rounded-lg bg-slate-50 border border-slate-200">
              <span className="text-[9px] uppercase font-bold text-slate-500 block tracking-wider">
                Baseline ETA
              </span>
              <span className="text-base font-black text-slate-900 font-mono">
                {etaData.baseline_eta_minutes}{' '}
                <span className="text-[10px] text-slate-500 font-normal">min</span>
              </span>
            </div>

            <div className="p-2 rounded-lg bg-blue-50 border border-blue-200">
              <span className="text-[9px] uppercase font-extrabold text-blue-700 block tracking-wider flex items-center justify-center gap-0.5">
                <Sparkles className="h-2.5 w-2.5 text-blue-600" />
                <span>Context ETA</span>
              </span>
              <span className="text-base font-black text-blue-700 font-mono">
                {etaData.context_aware_eta_minutes}{' '}
                <span className="text-[10px] text-blue-600 font-normal">min</span>
              </span>
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
        </div>
      ) : null}
    </div>
  );
}
