import React from 'react';
import { Wifi, WifiOff, RefreshCw } from 'lucide-react';
import { useRealtime } from '@/contexts/RealtimeContext';
import { cn } from '@/utils/cn';

interface RealtimeConnectionBadgeProps {
  className?: string;
  compact?: boolean;
}

export const RealtimeConnectionBadge: React.FC<RealtimeConnectionBadgeProps> = ({
  className,
  compact = false,
}) => {
  const { status, reconnect } = useRealtime();

  if (status === 'CONNECTED') {
    return (
      <div
        className={cn(
          'inline-flex items-center gap-1.5 rounded-full border border-emerald-200 bg-emerald-50 px-2.5 py-1 text-[11px] font-bold text-emerald-700 shadow-xs select-none transition-all',
          className,
        )}
        title="Real-time WebSocket event synchronization active"
      >
        <span className="relative flex h-2 w-2">
          <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75" />
          <span className="relative inline-flex rounded-full h-2 w-2 bg-emerald-500" />
        </span>
        <Wifi className="h-3 w-3 text-emerald-600" />
        {!compact && <span>Live Real-Time Sync</span>}
      </div>
    );
  }

  if (status === 'RECONNECTING') {
    return (
      <button
        onClick={reconnect}
        className={cn(
          'inline-flex items-center gap-1.5 rounded-full border border-amber-200 bg-amber-50 px-2.5 py-1 text-[11px] font-bold text-amber-700 shadow-xs select-none transition-all hover:bg-amber-100 cursor-pointer',
          className,
        )}
        title="Connection interrupted. Automatically reconnecting..."
      >
        <RefreshCw className="h-3 w-3 text-amber-600 animate-spin" />
        {!compact && <span>Reconnecting...</span>}
      </button>
    );
  }

  // DISCONNECTED
  return (
    <button
      onClick={reconnect}
      className={cn(
        'inline-flex items-center gap-1.5 rounded-full border border-slate-300 bg-slate-100 px-2.5 py-1 text-[11px] font-semibold text-slate-600 shadow-xs select-none transition-all hover:bg-slate-200 cursor-pointer',
        className,
      )}
      title="Live real-time offline. Click to manually reconnect."
    >
      <WifiOff className="h-3 w-3 text-slate-500" />
      {!compact && <span>Sync Offline (Click Reconnect)</span>}
    </button>
  );
};
