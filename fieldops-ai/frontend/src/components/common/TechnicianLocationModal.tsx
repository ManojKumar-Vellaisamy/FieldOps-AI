import React, { useState } from 'react';
import {
  MapPin,
  Compass,
  Navigation,
  RotateCcw,
  Check,
  AlertCircle,
  X,
  Sparkles,
  Building,
  Info,
} from 'lucide-react';
import { useTechnicianGeolocation } from '@/hooks/useTechnicianGeolocation';

interface TechnicianLocationModalProps {
  isOpen: boolean;
  onClose: () => void;
  assignedJobLocation?: {
    latitude: number;
    longitude: number;
    address?: string;
  } | null | undefined;
  onLocationUpdated?: (coords: { latitude: number; longitude: number }) => void;
}

interface PresetLocation {
  name: string;
  region: string;
  latitude: number;
  longitude: number;
}

const REGIONAL_PRESETS: PresetLocation[] = [
  { name: 'Karaikudi (Center)', region: 'Sivaganga', latitude: 10.0700, longitude: 78.7800 },
  { name: 'Coimbatore (Gandhipuram)', region: 'Coimbatore', latitude: 11.0168, longitude: 76.9558 },
  { name: 'Madurai (Mattuthavani)', region: 'Madurai', latitude: 9.9252, longitude: 78.1198 },
  { name: 'Tiruchirappalli (Trichy)', region: 'Central TN', latitude: 10.7905, longitude: 78.7047 },
  { name: 'Chennai (Guindy / Central)', region: 'Chennai', latitude: 13.0067, longitude: 80.2022 },
];

export const TechnicianLocationModal: React.FC<TechnicianLocationModalProps> = ({
  isOpen,
  onClose,
  assignedJobLocation,
  onLocationUpdated,
}) => {
  const geo = useTechnicianGeolocation({ enabled: false });

  const [customLat, setCustomLat] = useState<string>(
    geo.coordinates ? geo.coordinates.latitude.toFixed(6) : '',
  );
  const [customLon, setCustomLon] = useState<string>(
    geo.coordinates ? geo.coordinates.longitude.toFixed(6) : '',
  );
  const [isSubmitting, setIsSubmitting] = useState<boolean>(false);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  if (!isOpen) return null;

  const handleApplyPreset = async (lat: number, lon: number, label: string) => {
    setIsSubmitting(true);
    setErrorMessage(null);
    setSuccessMessage(null);
    try {
      await geo.setManualLocation(lat, lon, label);
      setSuccessMessage(`Location updated to ${label}!`);
      if (onLocationUpdated) {
        onLocationUpdated({ latitude: lat, longitude: lon });
      }
      setTimeout(() => {
        onClose();
      }, 700);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Failed to update location.';
      setErrorMessage(msg);
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleApplyCustom = async (e: React.FormEvent) => {
    e.preventDefault();
    const lat = parseFloat(customLat);
    const lon = parseFloat(customLon);

    if (isNaN(lat) || lat < -90 || lat > 90) {
      setErrorMessage('Please enter a valid latitude between -90 and 90.');
      return;
    }
    if (isNaN(lon) || lon < -180 || lon > 180) {
      setErrorMessage('Please enter a valid longitude between -180 and 180.');
      return;
    }

    setIsSubmitting(true);
    setErrorMessage(null);
    try {
      await geo.setManualLocation(lat, lon, 'Custom Coordinates');
      setSuccessMessage('Custom coordinates applied successfully!');
      if (onLocationUpdated) {
        onLocationUpdated({ latitude: lat, longitude: lon });
      }
      setTimeout(() => {
        onClose();
      }, 700);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Failed to apply custom coordinates.';
      setErrorMessage(msg);
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleResetToGps = async () => {
    setIsSubmitting(true);
    setErrorMessage(null);
    try {
      await geo.clearManualOverride();
      setSuccessMessage('Reset to live device browser GPS!');
      setTimeout(() => {
        onClose();
      }, 700);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Failed to reset GPS.';
      setErrorMessage(msg);
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/50 backdrop-blur-xs p-4 animate-fade-in select-none">
      <div className="relative w-full max-w-lg rounded-2xl border border-slate-200 bg-white p-6 shadow-2xl space-y-4 max-h-[90vh] overflow-y-auto">
        {/* Header */}
        <div className="flex items-start justify-between border-b border-slate-100 pb-3">
          <div className="flex items-center gap-2.5">
            <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-purple-50 text-purple-600 border border-purple-200">
              <Compass className="h-5 w-5" />
            </div>
            <div>
              <h3 className="text-base font-extrabold text-slate-900">
                Calibrate Technician Location
              </h3>
              <p className="text-xs text-slate-500">
                Set active coordinates for realistic dispatch distance &amp; ETA calculation.
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="rounded-lg p-1 text-slate-400 hover:bg-slate-100 hover:text-slate-600 cursor-pointer transition-colors"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        {/* Informational Banner */}
        <div className="rounded-xl border border-blue-100 bg-blue-50/70 p-3 text-xs text-blue-900 flex items-start gap-2.5">
          <Info className="h-4 w-4 text-blue-600 shrink-0 mt-0.5" />
          <div className="text-[11px] leading-relaxed">
            <span className="font-bold">Hardware Note:</span> Laptops &amp; PCs lack satellite GPS chips and rely on Wi-Fi router databases (which often report your previous location like Coimbatore). Use the presets below to simulate your genuine location.
          </div>
        </div>

        {/* Current State */}
        <div className="rounded-xl border border-slate-200 bg-slate-50 p-3 flex items-center justify-between text-xs">
          <div>
            <span className="text-[10px] uppercase font-bold text-slate-400 block tracking-wider">
              Current Registered Position
            </span>
            <span className="font-mono font-bold text-slate-800 text-sm">
              {geo.coordinates
                ? `${geo.coordinates.latitude.toFixed(4)}°, ${geo.coordinates.longitude.toFixed(4)}°`
                : 'Unavailable'}
            </span>
            <span className="block text-[10px] text-slate-500 mt-0.5">
              Source:{' '}
              <strong className={geo.isManualOverride ? 'text-purple-700' : 'text-emerald-700'}>
                {geo.isManualOverride
                  ? `Manual (${geo.manualLabel || 'Calibrated'})`
                  : 'Device Browser GPS'}
              </strong>
            </span>
          </div>

          {geo.isManualOverride && (
            <button
              onClick={handleResetToGps}
              disabled={isSubmitting}
              className="inline-flex items-center gap-1 rounded-lg border border-slate-200 bg-white hover:bg-slate-100 px-2.5 py-1.5 text-xs font-semibold text-slate-700 shadow-2xs transition-colors cursor-pointer"
              title="Clear manual calibration and return to device browser GPS"
            >
              <RotateCcw className="h-3.5 w-3.5 text-slate-500" />
              <span>Reset to GPS</span>
            </button>
          )}
        </div>

        {/* Alerts */}
        {successMessage && (
          <div className="flex items-center gap-2 rounded-xl border border-emerald-200 bg-emerald-50 p-3 text-xs font-bold text-emerald-800 animate-fade-in">
            <Check className="h-4 w-4 text-emerald-600 shrink-0" />
            <span>{successMessage}</span>
          </div>
        )}
        {errorMessage && (
          <div className="flex items-center gap-2 rounded-xl border border-rose-200 bg-rose-50 p-3 text-xs font-bold text-rose-800 animate-shake">
            <AlertCircle className="h-4 w-4 text-rose-600 shrink-0" />
            <span>{errorMessage}</span>
          </div>
        )}

        {/* ── SECTION 1: ASSIGNED JOB PROXIMITY SHORTCUT ── */}
        {assignedJobLocation && (
          <div className="rounded-xl border border-emerald-200 bg-emerald-50/60 p-3.5 space-y-2">
            <div className="flex items-center gap-1.5 text-xs font-bold text-emerald-900">
              <Sparkles className="h-3.5 w-3.5 text-emerald-600" />
              <span>Quick Match: Assigned Service Order</span>
            </div>
            <p className="text-[11px] text-emerald-800">
              Service Address: <strong className="font-bold">{assignedJobLocation.address || 'Assigned Job'}</strong>
            </p>
            <div className="grid grid-cols-2 gap-2 pt-1">
              <button
                type="button"
                onClick={() =>
                  handleApplyPreset(
                    assignedJobLocation.latitude + 0.015,
                    assignedJobLocation.longitude + 0.012,
                    `In Transit (~2 km from ${assignedJobLocation.address || 'Job'})`,
                  )
                }
                disabled={isSubmitting}
                className="flex items-center justify-center gap-1.5 rounded-lg border border-emerald-300 bg-white hover:bg-emerald-100 p-2 text-xs font-bold text-emerald-800 shadow-2xs transition-colors cursor-pointer text-center"
              >
                <Navigation className="h-3.5 w-3.5 text-emerald-600" />
                <span>Near Job (~2 km transit)</span>
              </button>
              <button
                type="button"
                onClick={() =>
                  handleApplyPreset(
                    assignedJobLocation.latitude,
                    assignedJobLocation.longitude,
                    `At Customer Site (${assignedJobLocation.address || 'Job'})`,
                  )
                }
                disabled={isSubmitting}
                className="flex items-center justify-center gap-1.5 rounded-lg border border-emerald-300 bg-white hover:bg-emerald-100 p-2 text-xs font-bold text-emerald-800 shadow-2xs transition-colors cursor-pointer text-center"
              >
                <MapPin className="h-3.5 w-3.5 text-emerald-600" />
                <span>At Customer Site (0 km)</span>
              </button>
            </div>
          </div>
        )}

        {/* ── SECTION 2: REGIONAL CITY PRESETS ── */}
        <div className="space-y-2">
          <label className="text-[11px] font-bold uppercase tracking-wider text-slate-500 block">
            Regional Service Hubs (1-Click)
          </label>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
            {REGIONAL_PRESETS.map((p) => (
              <button
                key={p.name}
                type="button"
                onClick={() => handleApplyPreset(p.latitude, p.longitude, p.name)}
                disabled={isSubmitting}
                className="flex items-center justify-between rounded-xl border border-slate-200 bg-white hover:border-purple-300 hover:bg-purple-50/50 p-2.5 text-left transition-all cursor-pointer shadow-2xs group"
              >
                <div>
                  <div className="text-xs font-extrabold text-slate-800 group-hover:text-purple-900">
                    {p.name}
                  </div>
                  <div className="text-[10px] text-slate-400">
                    {p.latitude.toFixed(4)}°, {p.longitude.toFixed(4)}°
                  </div>
                </div>
                <Building className="h-4 w-4 text-slate-300 group-hover:text-purple-600" />
              </button>
            ))}
          </div>
        </div>

        {/* ── SECTION 3: CUSTOM LATITUDE / LONGITUDE INPUT ── */}
        <form onSubmit={handleApplyCustom} className="space-y-2.5 border-t border-slate-100 pt-3">
          <label className="text-[11px] font-bold uppercase tracking-wider text-slate-500 block">
            Custom Coordinates
          </label>
          <div className="grid grid-cols-2 gap-2.5">
            <div>
              <span className="text-[10px] font-bold text-slate-400 mb-1 block">Latitude</span>
              <input
                type="number"
                step="any"
                required
                placeholder="10.0700"
                value={customLat}
                onChange={(e) => setCustomLat(e.target.value)}
                className="w-full rounded-lg border border-slate-200 bg-slate-50 px-2.5 py-1.5 text-xs font-mono text-slate-800 focus:border-purple-500 focus:bg-white focus:outline-none"
              />
            </div>
            <div>
              <span className="text-[10px] font-bold text-slate-400 mb-1 block">Longitude</span>
              <input
                type="number"
                step="any"
                required
                placeholder="78.7800"
                value={customLon}
                onChange={(e) => setCustomLon(e.target.value)}
                className="w-full rounded-lg border border-slate-200 bg-slate-50 px-2.5 py-1.5 text-xs font-mono text-slate-800 focus:border-purple-500 focus:bg-white focus:outline-none"
              />
            </div>
          </div>
          <div className="flex justify-end gap-2 pt-2">
            <button
              type="button"
              onClick={onClose}
              className="rounded-lg border border-slate-200 bg-white px-3 py-1.5 text-xs font-semibold text-slate-700 hover:bg-slate-50 cursor-pointer"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={isSubmitting}
              className="rounded-lg bg-purple-600 hover:bg-purple-700 px-4 py-1.5 text-xs font-bold text-white shadow-xs transition-colors cursor-pointer"
            >
              {isSubmitting ? 'Updating...' : 'Set Custom Coordinates'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};
