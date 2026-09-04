import { CloudSun, Wind, Droplets, AlertTriangle } from 'lucide-react';
import type { WeatherData } from '@/types/dashboard.types';
import { cn } from '@/utils/cn';

interface WeatherWidgetProps {
  weather: WeatherData;
  className?: string;
}

export function WeatherWidget({ weather, className }: WeatherWidgetProps) {
  const impactStyle =
    weather.impactSeverity === 'high'
      ? 'bg-rose-50 text-rose-800 border-rose-200'
      : weather.impactSeverity === 'moderate'
      ? 'bg-amber-50 text-amber-900 border-amber-200'
      : 'bg-emerald-50 text-emerald-800 border-emerald-200';

  const statusText =
    weather.impactSeverity === 'high'
      ? 'High Impact'
      : weather.impactSeverity === 'moderate'
      ? 'Medium Impact'
      : 'Low Impact';

  return (
    <div
      className={cn(
        'rounded-xl border border-slate-200 bg-white p-5 shadow-xs select-none flex flex-col justify-between',
        className,
      )}
    >
      <div>
        {/* Header */}
        <div className="flex items-center justify-between border-b border-slate-100 pb-3 mb-3">
          <div className="flex items-center gap-2.5">
            <CloudSun className="h-5 w-5 text-amber-500" />
            <div>
              <div className="flex items-center gap-2">
                <h3 className="text-xs font-bold text-slate-900">Weather: {weather.condition}</h3>
              </div>
              <p className="text-[10px] text-slate-500 font-medium">{weather.location}</p>
            </div>
          </div>

          <div className="text-right">
            <span className="text-lg font-bold text-slate-900 font-mono">{weather.temperature}</span>
          </div>
        </div>

        {/* Operational Impact Section */}
        <div className={cn('rounded-lg border p-3 text-xs flex items-start gap-2.5 mb-3', impactStyle)}>
          <AlertTriangle className="h-4 w-4 shrink-0 mt-0.5" />
          <div className="text-[11px] leading-relaxed flex-1">
            <div className="flex items-center justify-between font-bold mb-0.5">
              <span>Operational Impact</span>
              <span className="font-mono text-[10px] uppercase tracking-wider">{statusText}</span>
            </div>
            <p className="font-medium">
              {weather.etaImpact || 'Estimated ETA increase: +5 minutes'}
            </p>
          </div>
        </div>
      </div>

      {/* Telemetry Footer */}
      <div className="grid grid-cols-2 gap-2 text-[11px] text-slate-500 pt-2 border-t border-slate-100">
        <div className="flex items-center gap-1.5">
          <Wind className="h-3.5 w-3.5 text-slate-400 shrink-0" />
          <span>Wind: <strong className="text-slate-800 font-mono">{weather.windSpeed}</strong></span>
        </div>
        <div className="flex items-center gap-1.5">
          <Droplets className="h-3.5 w-3.5 text-slate-400 shrink-0" />
          <span>Humidity: <strong className="text-slate-800 font-mono">{weather.humidity}</strong></span>
        </div>
      </div>
    </div>
  );
}
