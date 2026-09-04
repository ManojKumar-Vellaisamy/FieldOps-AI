import { useState, useEffect } from 'react';
import { Sparkles, Clock, AlertCircle } from 'lucide-react';
import { etaService } from '@/services/eta.service';
import type { ETAResponse } from '@/types/eta.types';
import { cn } from '@/utils/cn';

interface JobETABadgeProps {
  jobId: string;
  className?: string;
  onClick?: () => void;
}

export function JobETABadge({ jobId, className, onClick }: JobETABadgeProps) {
  const [etaData, setEtaData] = useState<ETAResponse | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(true);

  useEffect(() => {
    let isMounted = true;
    setIsLoading(true);

    etaService
      .getJobEta(jobId)
      .then((data) => {
        if (isMounted) setEtaData(data);
      })
      .catch(() => {
        if (isMounted) setEtaData(null);
      })
      .finally(() => {
        if (isMounted) setIsLoading(false);
      });

    return () => {
      isMounted = false;
    };
  }, [jobId]);

  if (isLoading) {
    return (
      <span className={cn('inline-flex items-center gap-1 text-[11px] text-slate-400 font-mono animate-pulse', className)}>
        <Clock className="h-3 w-3" />
        <span>Calculating...</span>
      </span>
    );
  }

  if (!etaData || !etaData.is_context_sufficient || etaData.context_aware_eta_minutes === null) {
    return (
      <span
        title={etaData?.reason || 'Missing context: unassigned or no telemetry'}
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
      title={`Baseline: ${etaData.baseline_eta_minutes}m • Adjusted: ${etaData.context_aware_eta_minutes}m (${etaData.reason})`}
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
