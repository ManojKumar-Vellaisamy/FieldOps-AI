import {
  CloudSun,
  Wind,
  Droplets,
  AlertTriangle,
  RefreshCw,
  CloudRain,
  Clock,
  Umbrella,
} from 'lucide-react';
import type { WeatherData } from '@/types/dashboard.types';
import { useWeather } from '@/contexts/WeatherContext';
import { cn } from '@/utils/cn';

interface WeatherWidgetProps {
  weather?: WeatherData | null;
  isLoading?: boolean;
  className?: string;
}

export function WeatherWidget({
  weather: propWeather,
  isLoading: propIsLoading,
  className,
}: WeatherWidgetProps) {
  const weatherCtx = useWeather();
  const weather = propWeather !== undefined ? propWeather : weatherCtx.weather;
  const isLoading = propIsLoading !== undefined ? propIsLoading : weatherCtx.isLoading;
  const isRefreshing = weatherCtx.isRefreshing;

  // Format observation time string
  const formatObservedTime = (isoString?: string | null) => {
    if (!isoString) return null;
    try {
      const dt = new Date(isoString);
      if (isNaN(dt.getTime())) return isoString;
      return dt.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', timeZoneName: 'short' });
    } catch {
      return isoString;
    }
  };

  if (isLoading && !weather) {
    return (
      <div
        className={cn(
          'rounded-xl border border-slate-200 bg-white p-5 shadow-xs select-none flex flex-col items-center justify-center min-h-[220px]',
          className,
        )}
      >
        <RefreshCw className="h-6 w-6 text-blue-500 animate-spin mb-2" />
        <p className="text-xs text-slate-500 font-semibold">Retrieving Open-Meteo telemetry...</p>
        <p className="text-[11px] text-slate-400 mt-1">Establishing meteorological fix</p>
      </div>
    );
  }

  if (!weather || weather.condition === 'Weather unavailable') {
    return (
      <div
        className={cn(
          'rounded-xl border border-slate-200 bg-white p-5 shadow-xs select-none flex flex-col justify-between min-h-[220px]',
          className,
        )}
      >
        <div>
          <div className="flex items-center justify-between border-b border-slate-100 pb-3 mb-3">
            <div className="flex items-center gap-2.5">
              <CloudSun className="h-5 w-5 text-slate-400" />
              <div>
                <h3 className="text-xs font-bold text-slate-900">Weather Telemetry</h3>
                <p className="text-[10px] text-slate-400 font-medium">Open-Meteo Feed</p>
              </div>
            </div>
            <button
              onClick={() => weatherCtx.refreshWeather(true)}
              className="p-1 rounded-md text-slate-400 hover:text-slate-600 hover:bg-slate-100 transition-colors"
              title="Retry weather retrieval"
            >
              <RefreshCw className={cn('h-3.5 w-3.5', isRefreshing && 'animate-spin text-blue-600')} />
            </button>
          </div>
          <div className="py-6 text-center">
            <p className="text-xs text-slate-500 font-bold">Weather unavailable</p>
            <p className="text-[11px] text-slate-400 mt-1">
              {weatherCtx.error || 'Weather unavailable — location permission required'}
            </p>
          </div>
        </div>
        <div className="pt-2 border-t border-slate-100 text-[10px] text-slate-400 text-center flex items-center justify-center gap-1">
          <span>Provenance: UNAVAILABLE</span>
          <span>•</span>
          <span>No default coordinates substituted</span>
        </div>
      </div>
    );
  }

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

  const observedTimeStr = formatObservedTime(weather.observedAt);

  return (
    <div
      className={cn(
        'rounded-xl border border-slate-200 bg-white p-5 shadow-xs select-none flex flex-col justify-between',
        className,
      )}
    >
      <div>
        {/* Header with Title, Location, and Status */}
        <div className="flex items-start justify-between border-b border-slate-100 pb-3 mb-3">
          <div className="flex items-center gap-2.5">
            <div className="h-9 w-9 rounded-lg bg-amber-50 border border-amber-100 flex items-center justify-center text-amber-500 shrink-0">
              <CloudSun className="h-5 w-5" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h3 className="text-sm font-bold text-slate-900">{weather.condition}</h3>
                <span className="inline-flex items-center gap-1 rounded-full bg-blue-50 border border-blue-200 px-1.5 py-0.2 text-[9px] font-mono font-bold text-blue-700">
                  <span className="h-1.5 w-1.5 rounded-full bg-blue-500 animate-pulse" />
                  REAL
                </span>
              </div>
              <p className="text-[11px] text-slate-500 font-medium truncate max-w-[200px]" title={weather.location}>
                {weather.location}
              </p>
            </div>
          </div>

          {/* Refresh Action & Status */}
          <div className="flex items-center gap-1.5">
            <button
              onClick={() => weatherCtx.refreshWeather(true)}
              disabled={isRefreshing}
              className={cn(
                'p-1.5 rounded-lg border border-slate-200 bg-slate-50 text-slate-600',
                'hover:bg-slate-100 hover:text-slate-900 transition-colors',
                isRefreshing && 'opacity-75 cursor-not-allowed',
              )}
              title="Force weather refresh from Open-Meteo"
            >
              <RefreshCw className={cn('h-3.5 w-3.5', isRefreshing && 'animate-spin text-blue-600')} />
            </button>
          </div>
        </div>

        {/* Hero Temperature Presentation */}
        <div className="flex items-baseline justify-between mb-3 px-1">
          <div>
            <span className="text-3xl font-black text-slate-900 font-mono tracking-tight">
              {weather.temperature}
            </span>
            {weather.apparentTemperature && (
              <span className="ml-2 text-xs text-slate-500 font-medium">
                Feels like <strong className="text-slate-700 font-mono">{weather.apparentTemperature}</strong>
              </span>
            )}
          </div>
          {weather.latitude != null && weather.longitude != null && (
            <span className="text-[10px] font-mono text-slate-400">
              {weather.latitude.toFixed(3)}°, {weather.longitude.toFixed(3)}°
            </span>
          )}
        </div>

        {/* Dense Google-Like Weather Telemetry Grid */}
        <div className="grid grid-cols-2 gap-2 text-xs mb-3 bg-slate-50/80 border border-slate-200/70 rounded-lg p-2.5">
          {/* Humidity */}
          <div className="flex items-center gap-2">
            <Droplets className="h-4 w-4 text-blue-500 shrink-0" />
            <div>
              <span className="text-[10px] text-slate-400 block uppercase font-bold tracking-wider">Humidity</span>
              <span className="font-mono font-bold text-slate-800">{weather.humidity}</span>
            </div>
          </div>

          {/* Wind */}
          <div className="flex items-center gap-2">
            <Wind className="h-4 w-4 text-teal-600 shrink-0" />
            <div>
              <span className="text-[10px] text-slate-400 block uppercase font-bold tracking-wider">Wind</span>
              <span className="font-mono font-bold text-slate-800 truncate block max-w-[110px]" title={weather.windDirection ? `${weather.windSpeed} ${weather.windDirection}` : weather.windSpeed}>
                {weather.windSpeed} {weather.windDirection ? weather.windDirection.split(' ')[0] : ''}
              </span>
            </div>
          </div>

          {/* Precipitation */}
          <div className="flex items-center gap-2">
            <CloudRain className="h-4 w-4 text-indigo-500 shrink-0" />
            <div>
              <span className="text-[10px] text-slate-400 block uppercase font-bold tracking-wider">Precipitation</span>
              <span className="font-mono font-bold text-slate-800">{weather.precipitation}</span>
            </div>
          </div>

          {/* Precipitation Probability */}
          <div className="flex items-center gap-2">
            <Umbrella className="h-4 w-4 text-purple-500 shrink-0" />
            <div>
              <span className="text-[10px] text-slate-400 block uppercase font-bold tracking-wider">Precip Chance</span>
              <span className="font-mono font-bold text-slate-800">
                {weather.precipitationProbability || (weather.precipitationProbabilityPercent != null ? `${weather.precipitationProbabilityPercent.toFixed(0)}% (forecast)` : '--')}
              </span>
            </div>
          </div>
        </div>

        {/* Operational Impact Banner */}
        <div className={cn('rounded-lg border p-2.5 text-xs flex items-start gap-2 mb-2', impactStyle)}>
          <AlertTriangle className="h-4 w-4 shrink-0 mt-0.5" />
          <div className="text-[11px] leading-relaxed flex-1">
            <div className="flex items-center justify-between font-bold mb-0.5">
              <span>Operational Transit Impact</span>
              <span className="font-mono text-[9px] uppercase tracking-wider">{statusText}</span>
            </div>
            <p className="font-medium">
              {weather.etaImpact || 'Clear transit conditions, no weather delay'}
            </p>
          </div>
        </div>
      </div>

      {/* Footer: Open-Meteo Observation Timestamp and Auto-Refresh Info */}
      <div className="flex items-center justify-between text-[10px] text-slate-400 pt-2 border-t border-slate-100">
        <div className="flex items-center gap-1">
          <Clock className="h-3 w-3 text-slate-400" />
          <span>{observedTimeStr ? `Observed: ${observedTimeStr}` : 'Real-time telemetry'}</span>
        </div>
        <span className="font-medium">Auto-refreshed (5m)</span>
      </div>
    </div>
  );
}
