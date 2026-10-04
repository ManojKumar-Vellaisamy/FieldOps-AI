import { useState, useEffect } from 'react';
import {
  Navigation,
  MapPin,
  Compass,
  ExternalLink,
  Shield,
  CheckCircle2,
  AlertCircle,
  Clock,
  RefreshCw,
} from 'lucide-react';
import { useAuth } from '@/contexts/AuthContext';
import { jobService } from '@/services/job.service';
import { technicianService } from '@/services/technician.service';
import type { Job } from '@/types/job.types';
import type { Technician } from '@/types/technician.types';
import { TechnicianETACard } from '@/components/dashboard/TechnicianETACard';
import { formatDate } from '@/utils/format';
import { RealtimeConnectionBadge } from '@/components/common/RealtimeConnectionBadge';
import { GeolocationStatusBadge } from '@/components/common/GeolocationStatusBadge';
import { useRealtimeSync } from '@/hooks/useRealtimeSync';
import { useTechnicianGeolocation } from '@/hooks/useTechnicianGeolocation';
import { TechnicianLocationModal } from '@/components/common/TechnicianLocationModal';

function formatCoordinate(lat?: number | null, lon?: number | null): string {
  if (typeof lat !== 'number' || typeof lon !== 'number') return '—';
  const latDir = lat >= 0 ? 'N' : 'S';
  const lonDir = lon >= 0 ? 'E' : 'W';
  return `${Math.abs(lat).toFixed(4)}° ${latDir}, ${Math.abs(lon).toFixed(4)}° ${lonDir}`;
}

export default function TechnicianRoutePage() {
  const { user } = useAuth();
  const [activeJob, setActiveJob] = useState<Job | null>(null);
  const [techProfile, setTechProfile] = useState<Technician | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [isRefreshing, setIsRefreshing] = useState<boolean>(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [lastUpdated, setLastUpdated] = useState<string | null>(null);
  const [isLocationModalOpen, setIsLocationModalOpen] = useState<boolean>(false);

  const loadData = async (isInitial = false) => {
    if (isInitial) {
      setIsLoading(true);
    } else {
      setIsRefreshing(true);
    }
    setErrorMessage(null);

    try {
      const [jobs, profile] = await Promise.all([
        jobService.getMyJobs(),
        technicianService.getMyProfile().catch(() => null),
      ]);

      const active = jobs.find((j) => j.status !== 'COMPLETED' && j.status !== 'CANCELLED');
      setActiveJob(active || null);
      setTechProfile(profile);
      setLastUpdated(new Date().toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit', second: '2-digit' }));
    } catch (err: unknown) {
      console.error('Failed to load route navigation data', err);
      const msg = err instanceof Error ? err.message : 'Failed to load route telemetry.';
      setErrorMessage(msg);
    } finally {
      if (isInitial) {
        setIsLoading(false);
      }
      setIsRefreshing(false);
    }
  };

  // Real browser geolocation telemetry tracking
  const geo = useTechnicianGeolocation({
    enabled: !!activeJob,
    onLocationSent: (coords) => {
      setTechProfile((prev) =>
        prev
          ? {
              ...prev,
              current_latitude: coords.latitude,
              current_longitude: coords.longitude,
            }
          : prev,
      );
    },
  });

  // Real-time synchronization without screen blinking
  useRealtimeSync(
    ['JOB_STATUS_CHANGED', 'ETA_UPDATED', 'JOB_CANCELLED', 'JOB_ASSIGNED', 'TECHNICIAN_LOCATION_UPDATED'],
    () => {
      loadData(false);
    },
    () => loadData(false),
  );

  useEffect(() => {
    loadData(true);
    // Silent background interval relaxed to 60 seconds fallback
    const interval = setInterval(() => {
      loadData(false);
    }, 60000);
    return () => clearInterval(interval);
  }, []);

  const hasJobCoords = activeJob && typeof activeJob.latitude === 'number' && typeof activeJob.longitude === 'number';
  const techLat = geo.coordinates?.latitude ?? techProfile?.current_latitude;
  const techLng = geo.coordinates?.longitude ?? techProfile?.current_longitude;
  const hasTechCoords =
    typeof techLat === 'number' &&
    typeof techLng === 'number' &&
    !isNaN(techLat) &&
    !isNaN(techLng);

  const openGoogleMaps = () => {
    if (!hasJobCoords) return;
    // Prefer authoritative technician telemetry:
    // 1. Live browser GPS or manually calibrated position from useTechnicianGeolocation hook
    // 2. Fallback to technician server profile stationed coordinates
    const originParam = hasTechCoords ? `&origin=${techLat},${techLng}` : '';
    const url = `https://www.google.com/maps/dir/?api=1${originParam}&destination=${activeJob!.latitude},${activeJob!.longitude}&travelmode=driving`;
    window.open(url, '_blank', 'noopener,noreferrer');
  };

  return (
    <div className="flex flex-col gap-6 py-2 animate-fade-in select-none max-w-5xl mx-auto">
      {/* ── Page Header ── */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-slate-200 pb-5">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <span className="inline-flex items-center gap-1.5 rounded-full border border-blue-200 bg-blue-50 px-2.5 py-0.5 text-[11px] font-semibold text-blue-700">
              <Navigation className="h-3.5 w-3.5 text-blue-600 animate-pulse" />
              <span>Field Transit Telemetry</span>
            </span>
            <span className="inline-flex items-center gap-1 rounded-full border border-slate-200 bg-slate-100 px-2.5 py-0.5 text-[11px] font-medium text-slate-700">
              <Shield className="h-3 w-3 text-purple-600" />
              <span>{user?.role || 'Technician'}</span>
            </span>
            <RealtimeConnectionBadge />
            <GeolocationStatusBadge geo={geo} />
          </div>

          <h1 className="text-2xl md:text-3xl font-extrabold tracking-tight text-slate-900">
            Route Navigation
          </h1>
          <p className="text-xs md:text-sm text-slate-500 mt-0.5">
            Real-time GPS coordinates, route telemetry, and external map directions for active work orders.
          </p>
        </div>

        <div className="flex items-center gap-3">
          {lastUpdated && (
            <div className="flex items-center gap-1.5 text-[11px] font-mono text-slate-500 bg-slate-100 border border-slate-200 px-2.5 py-1.5 rounded-xl">
              <Clock className="h-3 w-3 text-blue-600" />
              <span>Ping: {lastUpdated}</span>
              {isRefreshing && <RefreshCw className="h-3 w-3 text-blue-600 animate-spin ml-1" />}
            </div>
          )}

          {hasJobCoords && (
            <button
              onClick={openGoogleMaps}
              className="flex items-center gap-2 rounded-xl bg-blue-600 px-5 py-2.5 text-xs font-extrabold text-white shadow-xs hover:bg-blue-700 active:scale-[0.98] transition-all cursor-pointer"
            >
              <ExternalLink className="h-4 w-4" />
              <span>Open Google Maps</span>
            </button>
          )}
        </div>
      </div>

      {geo.permissionState === 'denied' && (
        <div className="flex items-center gap-3 rounded-xl border border-amber-200 bg-amber-50 p-4 text-xs font-semibold text-amber-900 animate-fade-in shadow-xs">
          <AlertCircle className="h-5 w-5 shrink-0 text-amber-600" />
          <span>Location permission required for live navigation. Please allow GPS access in your browser settings.</span>
        </div>
      )}

      {geo.freshness === 'STALE' && geo.permissionState !== 'denied' && (
        <div className="flex items-center gap-3 rounded-xl border border-amber-200/80 bg-amber-50/70 p-3.5 text-xs font-medium text-amber-800 animate-fade-in">
          <AlertCircle className="h-4 w-4 shrink-0 text-amber-600" />
          <span>GPS signal is stale. Navigation is using the last known location telemetry fix.</span>
        </div>
      )}

      {errorMessage && (
        <div className="flex items-center gap-3 rounded-xl border border-rose-200 bg-rose-50 p-4 text-xs font-semibold text-rose-800 animate-shake">
          <AlertCircle className="h-5 w-5 shrink-0 text-rose-600" />
          <span>{errorMessage}</span>
        </div>
      )}

      {/* Primary Content Render - Preserves DOM structure on background refresh */}
      {isLoading ? (
        <div className="rounded-2xl border border-slate-200 bg-white p-12 text-center text-xs text-slate-500 flex flex-col items-center gap-2">
          <RefreshCw className="h-6 w-6 text-blue-600 animate-spin" />
          <span>Initializing route telemetry...</span>
        </div>
      ) : activeJob ? (
        <div className="space-y-6">
          {/* Active Job Target Banner */}
          <div className="rounded-2xl border border-blue-200 bg-white p-6 shadow-xs space-y-4">
            <div className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-100 pb-3">
              <div>
                <div className="flex items-center gap-2 mb-1">
                  <span className="font-mono text-xs font-extrabold text-blue-700 bg-blue-50 px-2.5 py-0.5 rounded border border-blue-200">
                    {activeJob.job_number}
                  </span>
                  <span className="text-[10px] uppercase font-extrabold px-2.5 py-0.5 rounded-full bg-purple-50 text-purple-700 border border-purple-200">
                    STATUS: {activeJob.status}
                  </span>
                  <span className="text-[10px] uppercase font-extrabold px-2.5 py-0.5 rounded-full bg-amber-50 text-amber-700 border border-amber-200">
                    {activeJob.priority} PRIORITY
                  </span>
                </div>
                <h2 className="text-xl font-extrabold text-slate-900">{activeJob.customer_name}</h2>
              </div>

              {activeJob.scheduled_time && (
                <div className="text-right text-xs font-mono text-slate-600">
                  <span className="text-[10px] uppercase font-bold text-slate-400 block">Scheduled Time</span>
                  <span>{formatDate(activeJob.scheduled_time)}</span>
                </div>
              )}
            </div>

            {/* Coordinates & Location Info */}
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 text-xs">
              <div className="rounded-xl border border-slate-200 bg-slate-50 p-4 space-y-2">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2 text-slate-500 font-bold uppercase text-[10px]">
                    <Compass className="h-4 w-4 text-emerald-600" />
                    <span>Technician Current GPS Location</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <GeolocationStatusBadge geo={geo} />
                    <button
                      type="button"
                      onClick={() => setIsLocationModalOpen(true)}
                      className="inline-flex items-center gap-1 rounded-md border border-slate-200 bg-white hover:bg-slate-100 px-2 py-0.5 text-[10px] font-bold text-slate-700 shadow-2xs transition-colors cursor-pointer"
                      title="Calibrate technician GPS location"
                    >
                      <MapPin className="h-3 w-3 text-purple-600" />
                      <span>Calibrate</span>
                    </button>
                  </div>
                </div>
                {geo.coordinates ? (
                  <div>
                    <div className="font-mono font-bold text-slate-800 text-sm">
                      {formatCoordinate(geo.coordinates.latitude, geo.coordinates.longitude)}
                    </div>
                    <div className="text-[11px] text-slate-500 mt-0.5">
                      Telemetry Source:{' '}
                      <strong className={geo.isManualOverride ? 'text-purple-700 font-extrabold' : 'text-emerald-700 font-extrabold'}>
                        {geo.isManualOverride
                          ? `Calibrated Location (${geo.manualLabel || 'Manual'})`
                          : 'Device Browser GPS API'}
                      </strong>
                    </div>
                  </div>
                ) : hasTechCoords ? (
                  <div>
                    <div className="font-mono font-bold text-slate-800 text-sm">
                      {formatCoordinate(techProfile!.current_latitude, techProfile!.current_longitude)}
                    </div>
                    <div className="text-[11px] text-slate-500 mt-0.5">
                      Status: <strong className="text-emerald-700 font-extrabold">Server Telemetry Recorded</strong>
                    </div>
                  </div>
                ) : (
                  <div className="text-slate-600 bg-amber-50 border border-amber-200 rounded-lg p-2 text-[11px] space-y-1">
                    <div className="font-bold text-amber-800 flex items-center gap-1">
                      <AlertCircle className="h-3.5 w-3.5 text-amber-600 shrink-0" />
                      <span>Location Telemetry Pending</span>
                    </div>
                    <p className="text-[10px] text-slate-600">
                      Grant browser GPS permission or wait for device satellite acquisition.
                    </p>
                  </div>
                )}
              </div>

              <div className="rounded-xl border border-slate-200 bg-slate-50 p-4 space-y-2">
                <div className="flex items-center gap-2 text-slate-500 font-bold uppercase text-[10px]">
                  <MapPin className="h-4 w-4 text-blue-600" />
                  <span>Destination Customer Site</span>
                </div>
                <p className="font-semibold text-slate-800 leading-relaxed">{activeJob.address}</p>
                {hasJobCoords ? (
                  <div className="font-mono text-[11px] text-slate-500">
                    Coords: {formatCoordinate(activeJob.latitude, activeJob.longitude)}
                  </div>
                ) : (
                  <div className="text-slate-500 italic text-[11px]">
                    Destination coordinates pending dispatcher geocoding.
                  </div>
                )}
              </div>
            </div>

            {/* Visual Route Vector Representation */}
            <div className="rounded-2xl border border-slate-200 bg-slate-900 p-6 text-white space-y-4 shadow-inner relative overflow-hidden">
              <div className="flex items-center justify-between text-xs border-b border-slate-800 pb-3">
                <span className="font-mono font-bold text-emerald-400 flex items-center gap-2">
                  <span className="h-2 w-2 rounded-full bg-emerald-400 animate-ping" />
                  LIVE TRANSIT VECTOR
                </span>
                <span className="font-mono text-slate-400 text-[11px]">
                  Target: {activeJob.job_number}
                </span>
              </div>

              <div className="flex items-center justify-between gap-4 py-4 px-2">
                <div className="flex flex-col items-center gap-1.5 text-center">
                  <div className="flex h-10 w-10 items-center justify-center rounded-full bg-emerald-500/20 text-emerald-400 border border-emerald-500/30">
                    <Compass className="h-5 w-5" />
                  </div>
                  <span className="text-[11px] font-bold text-slate-300">My Location</span>
                  <span className="font-mono text-[10px] text-slate-400">
                    {hasTechCoords ? `${Math.abs(techLat!).toFixed(2)}° ${techLat! >= 0 ? 'N' : 'S'}` : 'Origin'}
                  </span>
                </div>

                {/* Animated Line Vector */}
                <div className="flex-1 flex flex-col items-center gap-1 px-4">
                  <span className="text-[10px] font-mono text-blue-400 uppercase tracking-widest font-bold">
                    In Transit
                  </span>
                  <div className="w-full h-1 bg-slate-800 rounded-full overflow-hidden relative">
                    <div className="h-full bg-gradient-to-r from-emerald-500 via-blue-500 to-amber-500 animate-pulse w-full" />
                  </div>
                </div>

                <div className="flex flex-col items-center gap-1.5 text-center">
                  <div className="flex h-10 w-10 items-center justify-center rounded-full bg-blue-500/20 text-blue-400 border border-blue-500/30">
                    <MapPin className="h-5 w-5" />
                  </div>
                  <span className="text-[11px] font-bold text-slate-300">Destination</span>
                  <span className="font-mono text-[10px] text-slate-400">
                    {hasJobCoords ? `${Math.abs(activeJob.latitude || 0).toFixed(2)}° ${(activeJob.latitude || 0) >= 0 ? 'N' : 'S'}` : 'Site'}
                  </span>
                </div>
              </div>
            </div>

            {/* Context-Aware Travel ETA Telemetry Card */}
            <TechnicianETACard
              jobId={activeJob.id}
              assignedJobLocation={
                typeof activeJob.latitude === 'number' && typeof activeJob.longitude === 'number'
                  ? {
                      latitude: activeJob.latitude,
                      longitude: activeJob.longitude,
                      address: activeJob.address,
                    }
                  : null
              }
            />

            {/* Navigation Lifecycle Actions */}
            <div className="border-t border-slate-100 pt-4">
              {activeJob.status === 'ASSIGNED' && (
                <button
                  onClick={async () => {
                    try {
                      const updated = await jobService.updateJobStatus(activeJob.id, 'EN_ROUTE');
                      setActiveJob(updated);
                    } catch (e) {
                      console.error('Status transition error:', e);
                    }
                  }}
                  className="w-full flex items-center justify-center gap-2 rounded-xl bg-blue-600 px-5 py-3 text-xs font-extrabold text-white shadow-xs hover:bg-blue-700 transition-all cursor-pointer"
                >
                  <Navigation className="h-4 w-4 animate-pulse" />
                  <span>START NAVIGATION (EN ROUTE)</span>
                </button>
              )}

              {(activeJob.status === 'EN_ROUTE' || activeJob.status === 'TRAVELLING') && (
                <button
                  onClick={async () => {
                    try {
                      const updated = await jobService.updateJobStatus(activeJob.id, 'ARRIVED');
                      setActiveJob(updated);
                    } catch (e) {
                      console.error('Status transition error:', e);
                    }
                  }}
                  className="w-full flex items-center justify-center gap-2 rounded-xl bg-amber-600 px-5 py-3 text-xs font-extrabold text-white shadow-xs hover:bg-amber-700 transition-all cursor-pointer"
                >
                  <MapPin className="h-4 w-4" />
                  <span>MARK ARRIVED AT SITE</span>
                </button>
              )}

              {activeJob.status === 'ARRIVED' && (
                <button
                  onClick={async () => {
                    try {
                      const updated = await jobService.updateJobStatus(activeJob.id, 'IN_PROGRESS');
                      setActiveJob(updated);
                    } catch (e) {
                      console.error('Status transition error:', e);
                    }
                  }}
                  className="w-full flex items-center justify-center gap-2 rounded-xl bg-purple-600 px-5 py-3 text-xs font-extrabold text-white shadow-xs hover:bg-purple-700 transition-all cursor-pointer"
                >
                  <CheckCircle2 className="h-4 w-4" />
                  <span>START WORK (IN PROGRESS)</span>
                </button>
              )}
            </div>
          </div>
        </div>
      ) : (
        <div className="rounded-2xl border border-slate-200 bg-white p-12 text-center text-xs text-slate-500 flex flex-col items-center gap-3 shadow-xs">
          <CheckCircle2 className="h-10 w-10 text-emerald-500" />
          <span className="text-base font-extrabold text-slate-800">No active job assigned</span>
          <span className="text-slate-500 max-w-md">
            You currently have no active assigned service order requiring travel navigation.
          </span>
        </div>
      )}

      <TechnicianLocationModal
        isOpen={isLocationModalOpen}
        onClose={() => setIsLocationModalOpen(false)}
        assignedJobLocation={
          activeJob && typeof activeJob.latitude === 'number' && typeof activeJob.longitude === 'number'
            ? {
                latitude: activeJob.latitude,
                longitude: activeJob.longitude,
                address: activeJob.address,
              }
            : null
        }
        onLocationUpdated={() => loadData(false)}
      />
    </div>
  );
}
