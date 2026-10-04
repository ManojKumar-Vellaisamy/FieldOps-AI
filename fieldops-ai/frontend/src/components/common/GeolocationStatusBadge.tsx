import React from 'react';
import { Navigation, Clock, AlertCircle, Compass, MapPin } from 'lucide-react';
import type { GeolocationState } from '@/hooks/useTechnicianGeolocation';
import { cn } from '@/utils/cn';

interface GeolocationStatusBadgeProps {
  geo: GeolocationState;
  className?: string;
  showCoordinates?: boolean;
}

export const GeolocationStatusBadge: React.FC<GeolocationStatusBadgeProps> = ({
  geo,
  className,
  showCoordinates = false,
}) => {
  const { freshness, coordinates, permissionState, requestPermission, lastUpdated, isManualOverride, manualLabel } = geo;

  const timeString = lastUpdated
    ? lastUpdated.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit', second: '2-digit' })
    : null;

  // Manual Override / Calibrated Location
  if (isManualOverride && coordinates) {
    return (
      <div className={cn('flex flex-wrap items-center gap-2', className)}>
        <div
          className="inline-flex items-center gap-1.5 rounded-full border border-purple-200 bg-purple-50 px-2.5 py-1 text-[11px] font-bold text-purple-700 shadow-xs select-none"
          title={`Manually calibrated location: ${manualLabel || 'Custom'}`}
        >
          <span className="relative flex h-2 w-2">
            <span className="relative inline-flex rounded-full h-2 w-2 bg-purple-500" />
          </span>
          <MapPin className="h-3 w-3 text-purple-600" />
          <span>CALIBRATED</span>
          {manualLabel && <span className="font-mono text-[10px] text-purple-700/80">({manualLabel})</span>}
        </div>
        {showCoordinates && (
          <span className="font-mono text-[11px] text-purple-700 bg-purple-50/70 border border-purple-200 px-2 py-0.5 rounded-lg flex items-center gap-1">
            <Compass className="h-3 w-3 text-purple-600" />
            {coordinates.latitude.toFixed(4)}°, {coordinates.longitude.toFixed(4)}°
          </span>
        )}
      </div>
    );
  }

  if (freshness === 'LIVE') {
    return (
      <div className={cn('flex flex-wrap items-center gap-2', className)}>
        <div
          className="inline-flex items-center gap-1.5 rounded-full border border-emerald-200 bg-emerald-50 px-2.5 py-1 text-[11px] font-bold text-emerald-700 shadow-xs select-none"
          title={`Active browser GPS lock (updated at ${timeString || 'now'})`}
        >
          <span className="relative flex h-2 w-2">
            <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75" />
            <span className="relative inline-flex rounded-full h-2 w-2 bg-emerald-500" />
          </span>
          <Navigation className="h-3 w-3 text-emerald-600" />
          <span>GPS LIVE</span>
          {timeString && <span className="font-mono text-[10px] text-emerald-600/80">({timeString})</span>}
        </div>
        {showCoordinates && coordinates && (
          <span className="font-mono text-[11px] text-slate-600 bg-slate-100 border border-slate-200 px-2 py-0.5 rounded-lg flex items-center gap-1">
            <Compass className="h-3 w-3 text-emerald-600" />
            {coordinates.latitude.toFixed(4)}°, {coordinates.longitude.toFixed(4)}°
          </span>
        )}
      </div>
    );
  }

  if (freshness === 'STALE') {
    return (
      <div className={cn('flex flex-wrap items-center gap-2', className)}>
        <div
          className="inline-flex items-center gap-1.5 rounded-full border border-amber-200 bg-amber-50 px-2.5 py-1 text-[11px] font-bold text-amber-700 shadow-xs select-none"
          title={`GPS fix older than 60 seconds (last fix at ${timeString || 'unknown'})`}
        >
          <Clock className="h-3 w-3 text-amber-600" />
          <span>GPS STALE</span>
          {timeString && <span className="font-mono text-[10px]">({timeString})</span>}
        </div>
        {showCoordinates && coordinates && (
          <span className="font-mono text-[11px] text-slate-500 bg-slate-100 border border-slate-200 px-2 py-0.5 rounded-lg">
            {coordinates.latitude.toFixed(4)}°, {coordinates.longitude.toFixed(4)}°
          </span>
        )}
      </div>
    );
  }

  // UNAVAILABLE
  return (
    <div className={cn('flex flex-wrap items-center gap-2', className)}>
      <div
        className="inline-flex items-center gap-1.5 rounded-full border border-slate-200 bg-slate-100 px-2.5 py-1 text-[11px] font-semibold text-slate-600 shadow-xs select-none"
        title="GPS signal unavailable or permission pending"
      >
        <AlertCircle className="h-3 w-3 text-slate-400" />
        <span>GPS UNAVAILABLE</span>
      </div>

      {permissionState === 'prompt' && (
        <button
          onClick={requestPermission}
          className="rounded-lg bg-blue-50 border border-blue-200 px-2 py-0.5 text-[10px] font-extrabold text-blue-700 hover:bg-blue-100 cursor-pointer shadow-xs transition-colors"
        >
          Enable Device GPS
        </button>
      )}
      {permissionState === 'denied' && (
        <span className="text-[10px] text-rose-600 font-medium">
          Permission blocked in browser
        </span>
      )}
    </div>
  );
};
