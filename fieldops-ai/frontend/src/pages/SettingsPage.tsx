import { useState, useEffect } from 'react';
import {
  ShieldCheck,
  Database,
  CloudSun,
  Save,
  Check,
  RotateCcw,
  Key,
  Loader2,
  AlertTriangle,
} from 'lucide-react';
import { useAuth } from '@/contexts/AuthContext';
import { settingsService, type SystemSettings } from '@/services/settings.service';

export default function SettingsPage() {
  const { user } = useAuth();
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const [actionNotice, setActionNotice] = useState<string | null>(null);
  const [errorNotice, setErrorNotice] = useState<string | null>(null);

  // System Configuration State
  const [config, setConfig] = useState({
    jwtExpirationHours: 24,
    maxConcurrentSessions: 5,
    weatherRefreshIntervalMinutes: 15,
    trafficProviderMode: 'REAL_MOCK_FALLBACK',
    baselineEtaSpeedMph: 25.0,
    weatherDelayWeight: 1.25,
    auditLogRetentionDays: 90,
    autoUnassignOnTechInactive: true,
  });

  const triggerNotice = (msg: string) => {
    setActionNotice(msg);
    setTimeout(() => setActionNotice(null), 4000);
  };

  const triggerError = (msg: string) => {
    setErrorNotice(msg);
    setTimeout(() => setErrorNotice(null), 6000);
  };

  // Fetch settings from backend on component mount
  useEffect(() => {
    let isMounted = true;
    const fetchSettings = async () => {
      try {
        setIsLoading(true);
        setErrorNotice(null);
        const data = await settingsService.getSettings();
        if (isMounted) {
          setConfig({
            jwtExpirationHours: data.jwt_expiration_hours,
            maxConcurrentSessions: data.max_concurrent_sessions,
            weatherRefreshIntervalMinutes: data.weather_refresh_interval_minutes,
            trafficProviderMode: data.traffic_provider_mode || 'REAL_MOCK_FALLBACK',
            baselineEtaSpeedMph: data.baseline_eta_speed_mph,
            weatherDelayWeight: data.weather_delay_weight,
            auditLogRetentionDays: data.audit_log_retention_days,
            autoUnassignOnTechInactive: data.auto_unassign_on_tech_inactive,
          });
        }
      } catch (err: unknown) {
        if (isMounted) {
          console.error('Failed to load system settings:', err);
          triggerError('Failed to load system settings from backend. Displaying default values.');
        }
      } finally {
        if (isMounted) {
          setIsLoading(false);
        }
      }
    };

    fetchSettings();
    return () => {
      isMounted = false;
    };
  }, []);

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      setIsSaving(true);
      setErrorNotice(null);
      setActionNotice(null);

      const payload: SystemSettings = {
        jwt_expiration_hours: Number(config.jwtExpirationHours),
        max_concurrent_sessions: Number(config.maxConcurrentSessions),
        weather_refresh_interval_minutes: Number(config.weatherRefreshIntervalMinutes),
        traffic_provider_mode: config.trafficProviderMode,
        baseline_eta_speed_mph: Number(config.baselineEtaSpeedMph),
        weather_delay_weight: Number(config.weatherDelayWeight),
        audit_log_retention_days: Number(config.auditLogRetentionDays),
        auto_unassign_on_tech_inactive: Boolean(config.autoUnassignOnTechInactive),
      };

      const updated = await settingsService.updateSettings(payload);

      setConfig({
        jwtExpirationHours: updated.jwt_expiration_hours,
        maxConcurrentSessions: updated.max_concurrent_sessions,
        weatherRefreshIntervalMinutes: updated.weather_refresh_interval_minutes,
        trafficProviderMode: updated.traffic_provider_mode || 'REAL_MOCK_FALLBACK',
        baselineEtaSpeedMph: updated.baseline_eta_speed_mph,
        weatherDelayWeight: updated.weather_delay_weight,
        auditLogRetentionDays: updated.audit_log_retention_days,
        autoUnassignOnTechInactive: updated.auto_unassign_on_tech_inactive,
      });

      triggerNotice('System settings updated and saved successfully.');
    } catch (err: unknown) {
      console.error('Failed to update system settings:', err);
      let msg = 'Failed to update system settings.';
      if (err && typeof err === 'object' && 'response' in err) {
        const axiosErr = err as { response?: { data?: { detail?: string | Array<{ msg: string }> } } };
        const detail = axiosErr.response?.data?.detail;
        if (typeof detail === 'string') {
          msg = detail;
        } else if (Array.isArray(detail) && detail.length > 0) {
          msg = detail.map((d) => d.msg).join('; ');
        }
      }
      triggerError(msg);
    } finally {
      setIsSaving(false);
    }
  };

  const handleReset = async () => {
    try {
      setIsSaving(true);
      setErrorNotice(null);
      setActionNotice(null);

      const defaults = await settingsService.resetSettings();

      setConfig({
        jwtExpirationHours: defaults.jwt_expiration_hours,
        maxConcurrentSessions: defaults.max_concurrent_sessions,
        weatherRefreshIntervalMinutes: defaults.weather_refresh_interval_minutes,
        trafficProviderMode: defaults.traffic_provider_mode || 'REAL_MOCK_FALLBACK',
        baselineEtaSpeedMph: defaults.baseline_eta_speed_mph,
        weatherDelayWeight: defaults.weather_delay_weight,
        auditLogRetentionDays: defaults.audit_log_retention_days,
        autoUnassignOnTechInactive: defaults.auto_unassign_on_tech_inactive,
      });

      triggerNotice('Restored factory default configuration parameters.');
    } catch (err: unknown) {
      console.error('Failed to reset system settings:', err);
      triggerError('Failed to reset system settings to defaults.');
    } finally {
      setIsSaving(false);
    }
  };

  if (isLoading) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[400px] gap-3">
        <Loader2 className="h-8 w-8 text-purple-600 animate-spin" />
        <p className="text-sm font-medium text-slate-600">Loading system configuration parameters...</p>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-6 py-2 animate-fade-in select-none">
      {/* ── Header ── */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-slate-200 pb-5">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <span className="inline-flex items-center gap-1.5 rounded-full border border-purple-200 bg-purple-50 px-2.5 py-0.5 text-[11px] font-semibold text-purple-700">
              <ShieldCheck className="h-3.5 w-3.5" />
              <span>Administration Workspace</span>
            </span>
            <span className="inline-flex items-center gap-1 rounded-full border border-slate-200 bg-slate-100 px-2.5 py-0.5 text-[11px] font-medium text-slate-700">
              <span>{user?.role || 'Administrator'}</span>
            </span>
          </div>

          <h1 className="text-2xl md:text-3xl font-extrabold tracking-tight text-slate-900">
            Platform Settings & Configuration
          </h1>
          <p className="text-xs md:text-sm text-slate-500 mt-0.5">
            Configure system telemetry parameters, context ETA weights, security policies, and environment parameters.
          </p>
        </div>

        <div className="flex flex-col items-end gap-2">
          {actionNotice && (
            <div className="flex items-center gap-2 text-xs font-semibold text-emerald-800 bg-emerald-50 border border-emerald-200 px-3.5 py-2 rounded-xl animate-fade-in shadow-xs">
              <Check className="h-4 w-4 text-emerald-600" />
              <span>{actionNotice}</span>
            </div>
          )}

          {errorNotice && (
            <div className="flex items-center gap-2 text-xs font-semibold text-rose-800 bg-rose-50 border border-rose-200 px-3.5 py-2 rounded-xl animate-fade-in shadow-xs">
              <AlertTriangle className="h-4 w-4 text-rose-600" />
              <span>{errorNotice}</span>
            </div>
          )}
        </div>
      </div>

      <form onSubmit={handleSave} className="space-y-6">
        {/* ── Section 1: Security & JWT Session Policy ── */}
        <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-xs space-y-4">
          <div className="flex items-center gap-2 border-b border-slate-100 pb-3">
            <Key className="h-5 w-5 text-purple-600" />
            <div>
              <h3 className="text-sm font-bold text-slate-900">Security & Authentication Policy</h3>
              <p className="text-[11px] text-slate-500">JWT token expiration and session security settings</p>
            </div>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 text-xs">
            <div>
              <label className="block font-semibold text-slate-700 mb-1">
                JWT Token Expiration (Hours)
              </label>
              <input
                type="number"
                min={1}
                max={168}
                value={config.jwtExpirationHours}
                onChange={(e) => setConfig({ ...config, jwtExpirationHours: Number(e.target.value) })}
                className="w-full rounded-lg border border-slate-200 bg-slate-50 p-2.5 text-slate-800 font-mono focus:border-purple-500 focus:bg-white focus:outline-none"
                disabled={isSaving}
              />
            </div>

            <div>
              <label className="block font-semibold text-slate-700 mb-1">
                Max Concurrent Sessions Per User
              </label>
              <input
                type="number"
                min={1}
                max={20}
                value={config.maxConcurrentSessions}
                onChange={(e) => setConfig({ ...config, maxConcurrentSessions: Number(e.target.value) })}
                className="w-full rounded-lg border border-slate-200 bg-slate-50 p-2.5 text-slate-800 font-mono focus:border-purple-500 focus:bg-white focus:outline-none"
                disabled={isSaving}
              />
            </div>
          </div>
        </div>

        {/* ── Section 2: Context-Aware ETA Engine Parameters ── */}
        <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-xs space-y-4">
          <div className="flex items-center gap-2 border-b border-slate-100 pb-3">
            <CloudSun className="h-5 w-5 text-amber-600" />
            <div>
              <h3 className="text-sm font-bold text-slate-900">Context-Aware ETA Engine Parameters</h3>
              <p className="text-[11px] text-slate-500">Traffic, weather delays, and baseline transit speed tuning</p>
            </div>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 text-xs">
            <div>
              <label className="block font-semibold text-slate-700 mb-1">
                Baseline Speed (MPH)
              </label>
              <input
                type="number"
                step="0.5"
                min={10}
                max={65}
                value={config.baselineEtaSpeedMph}
                onChange={(e) => setConfig({ ...config, baselineEtaSpeedMph: Number(e.target.value) })}
                className="w-full rounded-lg border border-slate-200 bg-slate-50 p-2.5 text-slate-800 font-mono focus:border-purple-500 focus:bg-white focus:outline-none"
                disabled={isSaving}
              />
            </div>

            <div>
              <label className="block font-semibold text-slate-700 mb-1">
                Weather Delay Weight Multiplier
              </label>
              <input
                type="number"
                step="0.05"
                min={1.0}
                max={3.0}
                value={config.weatherDelayWeight}
                onChange={(e) => setConfig({ ...config, weatherDelayWeight: Number(e.target.value) })}
                className="w-full rounded-lg border border-slate-200 bg-slate-50 p-2.5 text-slate-800 font-mono focus:border-purple-500 focus:bg-white focus:outline-none"
                disabled={isSaving}
              />
            </div>

            <div>
              <label className="block font-semibold text-slate-700 mb-1">
                Weather Cache Refresh (Minutes)
              </label>
              <input
                type="number"
                min={5}
                max={60}
                value={config.weatherRefreshIntervalMinutes}
                onChange={(e) => setConfig({ ...config, weatherRefreshIntervalMinutes: Number(e.target.value) })}
                className="w-full rounded-lg border border-slate-200 bg-slate-50 p-2.5 text-slate-800 font-mono focus:border-purple-500 focus:bg-white focus:outline-none"
                disabled={isSaving}
              />
            </div>
          </div>
        </div>

        {/* ── Section 3: Data Retention & System Diagnostics ── */}
        <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-xs space-y-4">
          <div className="flex items-center gap-2 border-b border-slate-100 pb-3">
            <Database className="h-5 w-5 text-blue-600" />
            <div>
              <h3 className="text-sm font-bold text-slate-900">Audit Trail & Data Retention Policy</h3>
              <p className="text-[11px] text-slate-500">Immutable audit record archiving and cleanup thresholds</p>
            </div>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 text-xs">
            <div>
              <label className="block font-semibold text-slate-700 mb-1">
                Audit Log Retention (Days)
              </label>
              <input
                type="number"
                min={30}
                max={365}
                value={config.auditLogRetentionDays}
                onChange={(e) => setConfig({ ...config, auditLogRetentionDays: Number(e.target.value) })}
                className="w-full rounded-lg border border-slate-200 bg-slate-50 p-2.5 text-slate-800 font-mono focus:border-purple-500 focus:bg-white focus:outline-none"
                disabled={isSaving}
              />
            </div>

            <div className="flex items-center gap-3 pt-4">
              <input
                type="checkbox"
                id="autoUnassign"
                checked={config.autoUnassignOnTechInactive}
                onChange={(e) => setConfig({ ...config, autoUnassignOnTechInactive: e.target.checked })}
                className="h-4 w-4 rounded border-slate-300 text-purple-600 focus:ring-purple-500 cursor-pointer"
                disabled={isSaving}
              />
              <label htmlFor="autoUnassign" className="font-semibold text-slate-700 cursor-pointer">
                Auto-unassign active jobs if technician profile is set to INACTIVE
              </label>
            </div>
          </div>
        </div>

        {/* ── Action Toolbar ── */}
        <div className="flex items-center justify-end gap-3 pt-2">
          <button
            type="button"
            onClick={handleReset}
            disabled={isSaving}
            className="flex items-center gap-1.5 rounded-xl border border-slate-200 bg-white px-4 py-2.5 text-xs font-semibold text-slate-700 hover:bg-slate-50 cursor-pointer shadow-xs disabled:opacity-50 disabled:cursor-not-allowed"
          >
            <RotateCcw className="h-4 w-4 text-slate-500" />
            <span>Reset Defaults</span>
          </button>

          <button
            type="submit"
            disabled={isSaving}
            className="flex items-center gap-2 rounded-xl bg-purple-600 px-5 py-2.5 text-xs font-semibold text-white shadow-xs hover:bg-purple-700 active:scale-[0.98] cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {isSaving ? <Loader2 className="h-4 w-4 animate-spin" /> : <Save className="h-4 w-4" />}
            <span>{isSaving ? 'Saving Configuration...' : 'Save Configuration'}</span>
          </button>
        </div>
      </form>
    </div>
  );
}
