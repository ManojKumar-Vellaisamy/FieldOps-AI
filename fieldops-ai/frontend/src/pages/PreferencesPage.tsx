import { useState } from 'react';
import {
  Sun,
  Moon,
  Bell,
  Volume2,
  CheckCircle2,
  Sliders,
  Check,
  Globe,
  Sparkles,
} from 'lucide-react';
import { useTheme } from '@/hooks/useTheme';
import { useAuth } from '@/contexts/AuthContext';

interface UserPreferences {
  inAppAlerts: boolean;
  soundAlerts: boolean;
  weatherHazardAlerts: boolean;
  timeFormat: 'local' | 'utc';
  dateFormat: 'standard' | 'iso';
}

const DEFAULT_PREFERENCES: UserPreferences = {
  inAppAlerts: true,
  soundAlerts: false,
  weatherHazardAlerts: true,
  timeFormat: 'local',
  dateFormat: 'standard',
};

export default function PreferencesPage() {
  const { isDark, setTheme } = useTheme();
  const { user } = useAuth();

  const storageKey = `fieldops_preferences_${user?.id || 'default'}`;

  const [preferences, setPreferences] = useState<UserPreferences>(() => {
    try {
      const stored = localStorage.getItem(storageKey);
      return stored ? { ...DEFAULT_PREFERENCES, ...JSON.parse(stored) } : DEFAULT_PREFERENCES;
    } catch {
      return DEFAULT_PREFERENCES;
    }
  });

  const [saveNotice, setSaveNotice] = useState<string | null>(null);

  // Sync to localStorage whenever preferences change
  const updatePref = <K extends keyof UserPreferences>(key: K, value: UserPreferences[K]) => {
    setPreferences((prev) => {
      const updated = { ...prev, [key]: value };
      try {
        localStorage.setItem(storageKey, JSON.stringify(updated));
      } catch (err) {
        console.error('Failed to save preference', err);
      }
      return updated;
    });

    setSaveNotice('Preference updated and saved.');
    setTimeout(() => setSaveNotice(null), 3000);
  };

  const detectedTimeZone = Intl.DateTimeFormat().resolvedOptions().timeZone || 'UTC';

  return (
    <div className="space-y-6 animate-fade-in">
      {/* Top Header */}
      <div>
        <h2 className="text-base font-bold text-slate-900">Application Preferences</h2>
        <p className="text-xs text-slate-500 mt-0.5">
          Configure interface appearance, operational notification alerts, and regional telemetry formats.
        </p>
      </div>

      {/* Save Toast Notice */}
      {saveNotice && (
        <div className="flex items-center gap-2 rounded-xl border border-emerald-200 bg-emerald-50 p-3 text-xs text-emerald-800 animate-fade-in">
          <CheckCircle2 className="h-4 w-4 shrink-0 text-emerald-600" />
          <span className="font-semibold">{saveNotice}</span>
        </div>
      )}

      {/* ── Section 1: Appearance & Theme ── */}
      <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-2xs space-y-4">
        <div className="flex items-center gap-2 border-b border-slate-100 pb-3">
          <Sparkles className="h-4 w-4 text-blue-600" />
          <h3 className="text-xs font-bold text-slate-900 uppercase tracking-wider">
            Appearance & Theme
          </h3>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          {/* Light Theme Card */}
          <button
            type="button"
            onClick={() => setTheme('light')}
            className={`flex items-start gap-3.5 rounded-xl border p-4 text-left transition-all cursor-pointer ${
              !isDark
                ? 'border-blue-600 bg-blue-50/40 ring-2 ring-blue-600/20'
                : 'border-slate-200 bg-slate-50/60 hover:bg-slate-100/60 hover:border-slate-300'
            }`}
          >
            <div
              className={`flex h-9 w-9 shrink-0 items-center justify-center rounded-lg border ${
                !isDark
                  ? 'border-blue-200 bg-blue-100 text-blue-700'
                  : 'border-slate-200 bg-white text-slate-600'
              }`}
            >
              <Sun className="h-5 w-5" />
            </div>
            <div className="flex-1">
              <div className="flex items-center justify-between">
                <span className="text-xs font-bold text-slate-900">Light Mode</span>
                {!isDark && (
                  <span className="inline-flex items-center gap-1 rounded-full bg-blue-600 px-2 py-0.5 text-[10px] font-bold text-white">
                    <Check className="h-3 w-3" /> Active
                  </span>
                )}
              </div>
              <p className="text-[11px] text-slate-500 mt-1 leading-normal">
                High-contrast crisp daylight styling recommended for dispatch control rooms.
              </p>
            </div>
          </button>

          {/* Dark Theme Card */}
          <button
            type="button"
            onClick={() => setTheme('dark')}
            className={`flex items-start gap-3.5 rounded-xl border p-4 text-left transition-all cursor-pointer ${
              isDark
                ? 'border-blue-600 bg-blue-50/40 ring-2 ring-blue-600/20'
                : 'border-slate-200 bg-slate-50/60 hover:bg-slate-100/60 hover:border-slate-300'
            }`}
          >
            <div
              className={`flex h-9 w-9 shrink-0 items-center justify-center rounded-lg border ${
                isDark
                  ? 'border-blue-200 bg-blue-100 text-blue-700'
                  : 'border-slate-200 bg-white text-slate-600'
              }`}
            >
              <Moon className="h-5 w-5" />
            </div>
            <div className="flex-1">
              <div className="flex items-center justify-between">
                <span className="text-xs font-bold text-slate-900">Dark Mode</span>
                {isDark && (
                  <span className="inline-flex items-center gap-1 rounded-full bg-blue-600 px-2 py-0.5 text-[10px] font-bold text-white">
                    <Check className="h-3 w-3" /> Active
                  </span>
                )}
              </div>
              <p className="text-[11px] text-slate-500 mt-1 leading-normal">
                Low-glare dark palette optimized for nighttime field operations and reduced eye fatigue.
              </p>
            </div>
          </button>
        </div>
      </div>

      {/* ── Section 2: Operational Notifications ── */}
      <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-2xs space-y-4">
        <div className="flex items-center gap-2 border-b border-slate-100 pb-3">
          <Bell className="h-4 w-4 text-blue-600" />
          <h3 className="text-xs font-bold text-slate-900 uppercase tracking-wider">
            Notifications & Dispatch Alerts
          </h3>
        </div>

        <div className="space-y-3.5 text-xs">
          {/* In-App Alerts Toggle */}
          <div className="flex items-center justify-between p-2 rounded-lg hover:bg-slate-50 transition-colors">
            <div className="flex items-center gap-3">
              <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-slate-100 text-slate-700 border border-slate-200">
                <Bell className="h-4 w-4" />
              </div>
              <div>
                <span className="font-bold text-slate-800 block">In-App Notification Banners</span>
                <span className="text-[11px] text-slate-500">
                  Receive live visual notification toasts for assignment updates and job completions.
                </span>
              </div>
            </div>
            <label className="relative inline-flex items-center cursor-pointer">
              <input
                type="checkbox"
                checked={preferences.inAppAlerts}
                onChange={(e) => updatePref('inAppAlerts', e.target.checked)}
                className="sr-only peer"
              />
              <div className="w-10 h-5 bg-slate-200 peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-slate-300 after:border after:rounded-full after:h-4 after:w-4 after:transition-all peer-checked:bg-blue-600" />
            </label>
          </div>

          {/* Sound Alerts Toggle */}
          <div className="flex items-center justify-between p-2 rounded-lg hover:bg-slate-50 transition-colors">
            <div className="flex items-center gap-3">
              <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-slate-100 text-slate-700 border border-slate-200">
                <Volume2 className="h-4 w-4" />
              </div>
              <div>
                <span className="font-bold text-slate-800 block">Audio Chimes on Priority Events</span>
                <span className="text-[11px] text-slate-500">
                  Play an audible notification when an emergency or critical SLA job is created.
                </span>
              </div>
            </div>
            <label className="relative inline-flex items-center cursor-pointer">
              <input
                type="checkbox"
                checked={preferences.soundAlerts}
                onChange={(e) => updatePref('soundAlerts', e.target.checked)}
                className="sr-only peer"
              />
              <div className="w-10 h-5 bg-slate-200 peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-slate-300 after:border after:rounded-full after:h-4 after:w-4 after:transition-all peer-checked:bg-blue-600" />
            </label>
          </div>

          {/* Weather Hazards Toggle */}
          <div className="flex items-center justify-between p-2 rounded-lg hover:bg-slate-50 transition-colors">
            <div className="flex items-center gap-3">
              <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-slate-100 text-slate-700 border border-slate-200">
                <Sliders className="h-4 w-4" />
              </div>
              <div>
                <span className="font-bold text-slate-800 block">Severe Weather Warnings</span>
                <span className="text-[11px] text-slate-500">
                  Highlight technician routes encountering precipitation or high wind speed warnings.
                </span>
              </div>
            </div>
            <label className="relative inline-flex items-center cursor-pointer">
              <input
                type="checkbox"
                checked={preferences.weatherHazardAlerts}
                onChange={(e) => updatePref('weatherHazardAlerts', e.target.checked)}
                className="sr-only peer"
              />
              <div className="w-10 h-5 bg-slate-200 peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-slate-300 after:border after:rounded-full after:h-4 after:w-4 after:transition-all peer-checked:bg-blue-600" />
            </label>
          </div>
        </div>
      </div>

      {/* ── Section 3: Timezone & Regional Display ── */}
      <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-2xs space-y-4">
        <div className="flex items-center gap-2 border-b border-slate-100 pb-3">
          <Globe className="h-4 w-4 text-blue-600" />
          <h3 className="text-xs font-bold text-slate-900 uppercase tracking-wider">
            Timezone & Regional Telemetry
          </h3>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 text-xs">
          <div>
            <label className="block font-bold text-slate-700 mb-1.5">
              Timestamp Presentation
            </label>
            <select
              value={preferences.timeFormat}
              onChange={(e) => updatePref('timeFormat', e.target.value as 'local' | 'utc')}
              className="w-full rounded-xl border border-slate-200 bg-slate-50/70 p-2.5 text-xs text-slate-900 font-medium focus:bg-white focus:border-blue-600 focus:outline-none focus:ring-2 focus:ring-blue-100 transition-all cursor-pointer"
            >
              <option value="local">Local Browser Time ({detectedTimeZone})</option>
              <option value="utc">Universal Coordinated Time (UTC)</option>
            </select>
            <p className="mt-1 text-[11px] text-slate-400">
              Affects dispatch event timestamps, ETA projections, and audit logs.
            </p>
          </div>

          <div>
            <label className="block font-bold text-slate-700 mb-1.5">
              Calendar Date Format
            </label>
            <select
              value={preferences.dateFormat}
              onChange={(e) => updatePref('dateFormat', e.target.value as 'standard' | 'iso')}
              className="w-full rounded-xl border border-slate-200 bg-slate-50/70 p-2.5 text-xs text-slate-900 font-medium focus:bg-white focus:border-blue-600 focus:outline-none focus:ring-2 focus:ring-blue-100 transition-all cursor-pointer"
            >
              <option value="standard">Standard (e.g. Sep 18, 2026)</option>
              <option value="iso">ISO 8601 (e.g. 2026-09-18)</option>
            </select>
            <p className="mt-1 text-[11px] text-slate-400">
              Format displayed in table headers, filter ranges, and job cards.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
