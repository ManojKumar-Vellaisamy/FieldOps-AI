import { useState, useEffect, useCallback, useMemo, useRef } from 'react';
import {
  MapPin,
  Shield,
  RefreshCw,
  Compass,
  ZoomIn,
  ZoomOut,
  RotateCcw,
  Radio,
  ExternalLink,
  ChevronRight,
  X,
} from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '@/contexts/AuthContext';
import { jobService } from '@/services/job.service';
import { technicianService } from '@/services/technician.service';
import { analyticsService } from '@/services/analytics.service';
import { etaService } from '@/services/eta.service';
import type { Job } from '@/types/job.types';
import type { Technician } from '@/types/technician.types';
import type { ETAResponse } from '@/types/eta.types';
import { cn } from '@/utils/cn';
import { RealtimeConnectionBadge } from '@/components/common/RealtimeConnectionBadge';
import { useRealtimeSync } from '@/hooks/useRealtimeSync';
import type {
  RealtimeEvent,
  TechnicianLocationUpdatedEventData,
  TechnicianAvailabilityChangedEventData,
  JobStatusChangedEventData,
} from '@/types/realtime.types';

// GPS Freshness helper reusing Module 17 thresholds
function getGpsFreshness(
  updatedAt: string | null | undefined,
  hasCoords: boolean,
): 'LIVE' | 'STALE' | 'UNAVAILABLE' {
  if (!hasCoords || !updatedAt) return 'UNAVAILABLE';
  const lastTime = new Date(updatedAt).getTime();
  if (isNaN(lastTime)) return 'UNAVAILABLE';
  const diffSec = (Date.now() - lastTime) / 1000;
  if (diffSec <= 30) return 'LIVE';
  return 'STALE';
}

export default function LiveMapPage() {
  const { user } = useAuth();
  const navigate = useNavigate();

  // Primary Entities State
  const [jobs, setJobs] = useState<Job[]>([]);
  const [technicians, setTechnicians] = useState<Technician[]>([]);
  const [isLoading, setIsLoading] = useState<boolean>(true);

  // Authoritative Operational Counts (from PostgreSQL)
  const [summaryCounts, setSummaryCounts] = useState({
    activeJobs: 0,
    totalTechnicians: 0,
    techsWithLiveGps: 0,
    unassignedJobs: 0,
    jobsTravelling: 0,
    jobsWorking: 0,
  });

  // Selection & Inspector State
  const [selectedEntity, setSelectedEntity] = useState<{
    type: 'technician' | 'job';
    id: string;
  } | null>(null);
  const [selectedEta, setSelectedEta] = useState<ETAResponse | null>(null);
  const [isEtaLoading, setIsEtaLoading] = useState<boolean>(false);

  // Map Filter & Display State
  const [filterMode, setFilterMode] = useState<'all' | 'jobs' | 'techs'>('all');
  const [gpsOnlyFilter, setGpsOnlyFilter] = useState<boolean>(false);
  const [viewMode, setViewMode] = useState<'map' | 'list'>('map');

  // Canvas Pan & Zoom
  const [zoom, setZoom] = useState<number>(1);
  const [pan, setPan] = useState<{ x: number; y: number }>({ x: 0, y: 0 });
  const [isDragging, setIsDragging] = useState<boolean>(false);
  const dragStartRef = useRef<{ x: number; y: number }>({ x: 0, y: 0 });

  // Telemetry Heartbeat Timestamp
  const [lastTelemetryTimestamp, setLastTelemetryTimestamp] = useState<string | null>(null);

  // Load Authoritative State from REST
  const loadMapData = useCallback(async () => {
    setIsLoading(true);
    try {
      const [jobsRes, techsRes, analyticsRes] = await Promise.all([
        jobService.getJobs({ page_size: 100 }),
        technicianService.getTechnicians({ page_size: 100 }),
        analyticsService.getOperationalAnalytics().catch(() => null),
      ]);

      setJobs(jobsRes.items);
      setTechnicians(techsRes.items);

      if (analyticsRes) {
        const travellingCount =
          analyticsRes.status_distribution.find((s) => s.status === 'TRAVELLING')?.count || 0;
        const workingCount =
          analyticsRes.status_distribution.find((s) => s.status === 'WORKING')?.count || 0;

        // Evaluate live GPS technicians (updated <= 30s)
        const liveGpsCount = techsRes.items.filter((t) => {
          const hasCoords = typeof t.current_latitude === 'number' && typeof t.current_longitude === 'number';
          return getGpsFreshness(t.updated_at, hasCoords) === 'LIVE';
        }).length;

        setSummaryCounts({
          activeJobs: analyticsRes.active_jobs,
          totalTechnicians: analyticsRes.total_technicians,
          techsWithLiveGps: liveGpsCount,
          unassignedJobs: analyticsRes.unassigned_jobs,
          jobsTravelling: travellingCount,
          jobsWorking: workingCount,
        });
      } else {
        // Fallback local calculations if analytics endpoint fails
        const active = jobsRes.items.filter((j) => j.status !== 'COMPLETED' && j.status !== 'CANCELLED');
        const liveGps = techsRes.items.filter((t) => {
          const hasCoords = typeof t.current_latitude === 'number' && typeof t.current_longitude === 'number';
          return getGpsFreshness(t.updated_at, hasCoords) === 'LIVE';
        }).length;

        setSummaryCounts({
          activeJobs: active.length,
          totalTechnicians: techsRes.total,
          techsWithLiveGps: liveGps,
          unassignedJobs: jobsRes.items.filter((j) => j.status === 'NEW').length,
          jobsTravelling: jobsRes.items.filter((j) => j.status === 'TRAVELLING').length,
          jobsWorking: jobsRes.items.filter((j) => j.status === 'WORKING').length,
        });
      }

      setLastTelemetryTimestamp(
        new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' }),
      );
    } catch (err) {
      console.error('Failed to load authoritative live map data', err);
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    loadMapData();
  }, [loadMapData]);

  // Handle Real-Time WebSocket Operational Events (In-place updates by entity ID)
  const handleRealtimeEvent = useCallback((event: RealtimeEvent) => {
    const { event: eventType, data } = event;

    if (eventType === 'TECHNICIAN_LOCATION_UPDATED') {
      const payload = data as TechnicianLocationUpdatedEventData;
      setTechnicians((prev) =>
        prev.map((t) =>
          t.id === payload.technician_id
            ? {
                ...t,
                current_latitude: payload.latitude,
                current_longitude: payload.longitude,
                updated_at: payload.updated_at || new Date().toISOString(),
              }
            : t,
        ),
      );

      setLastTelemetryTimestamp(
        new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' }),
      );
    } else if (eventType === 'TECHNICIAN_AVAILABILITY_CHANGED') {
      const payload = data as TechnicianAvailabilityChangedEventData;
      setTechnicians((prev) =>
        prev.map((t) =>
          t.id === payload.technician_id ? { ...t, availability_status: payload.new_status } : t,
        ),
      );
    } else if (eventType === 'JOB_STATUS_CHANGED' || eventType === 'JOB_COMPLETED') {
      const payload = data as JobStatusChangedEventData;
      setJobs((prev) =>
        prev.map((j) =>
          j.id === payload.job_id ? { ...j, status: payload.new_status as any } : j,
        ),
      );
    } else if (
      eventType === 'JOB_ASSIGNED' ||
      eventType === 'JOB_UNASSIGNED' ||
      eventType === 'JOB_CANCELLED' ||
      eventType === 'DISPATCH_PLAN_CHANGED'
    ) {
      // Refresh authoritative relations for assignment updates
      jobService
        .getJobs({ page_size: 100 })
        .then((res) => setJobs(res.items))
        .catch(() => null);
    }
  }, []);

  // Subscribe to real-time events with authoritative resync on reconnect
  useRealtimeSync(
    [
      'TECHNICIAN_LOCATION_UPDATED',
      'TECHNICIAN_AVAILABILITY_CHANGED',
      'JOB_ASSIGNED',
      'JOB_UNASSIGNED',
      'JOB_STATUS_CHANGED',
      'JOB_COMPLETED',
      'JOB_CANCELLED',
      'DISPATCH_PLAN_CHANGED',
      'ETA_UPDATED',
    ],
    handleRealtimeEvent,
    loadMapData,
  );

  // Selected Entity Details
  const selectedTech = useMemo(() => {
    if (selectedEntity?.type !== 'technician') return null;
    return technicians.find((t) => t.id === selectedEntity.id) || null;
  }, [selectedEntity, technicians]);

  const selectedJob = useMemo(() => {
    if (selectedEntity?.type !== 'job') return null;
    return jobs.find((j) => j.id === selectedEntity.id) || null;
  }, [selectedEntity, jobs]);

  // Load ETA for selected job
  useEffect(() => {
    if (selectedJob) {
      setIsEtaLoading(true);
      etaService
        .getJobEta(selectedJob.id)
        .then((eta) => setSelectedEta(eta))
        .catch(() => setSelectedEta(null))
        .finally(() => setIsEtaLoading(false));
    } else {
      setSelectedEta(null);
    }
  }, [selectedJob]);

  // Bounding Box & Coordinate Normalization for Spatial Canvas
  const validTechs = useMemo(
    () =>
      technicians.filter(
        (t) => typeof t.current_latitude === 'number' && typeof t.current_longitude === 'number',
      ),
    [technicians],
  );

  const validJobs = useMemo(
    () =>
      jobs.filter(
        (j) =>
          typeof j.latitude === 'number' &&
          typeof j.longitude === 'number' &&
          j.status !== 'COMPLETED' &&
          j.status !== 'CANCELLED',
      ),
    [jobs],
  );

  const bounds = useMemo(() => {
    const lats = [
      ...validTechs.map((t) => t.current_latitude!),
      ...validJobs.map((j) => j.latitude!),
    ];
    const lngs = [
      ...validTechs.map((t) => t.current_longitude!),
      ...validJobs.map((j) => j.longitude!),
    ];

    if (lats.length === 0 || lngs.length === 0) {
      // Default San Francisco bounding box
      return { minLat: 37.70, maxLat: 37.82, minLng: -122.52, maxLng: -122.36 };
    }

    const minLat = Math.min(...lats);
    const maxLat = Math.max(...lats);
    const minLng = Math.min(...lngs);
    const maxLng = Math.max(...lngs);

    const latPad = Math.max((maxLat - minLat) * 0.15, 0.02);
    const lngPad = Math.max((maxLng - minLng) * 0.15, 0.02);

    return {
      minLat: minLat - latPad,
      maxLat: maxLat + latPad,
      minLng: minLng - lngPad,
      maxLng: maxLng + lngPad,
    };
  }, [validTechs, validJobs]);

  // Project geographic lat/lng into [0..100]% spatial canvas coordinates
  const projectCoord = useCallback(
    (lat: number, lng: number) => {
      const latRange = bounds.maxLat - bounds.minLat || 0.001;
      const lngRange = bounds.maxLng - bounds.minLng || 0.001;

      const x = ((lng - bounds.minLng) / lngRange) * 100;
      const y = ((bounds.maxLat - lat) / latRange) * 100; // Inverted Y for map layout

      return {
        x: Math.max(5, Math.min(95, x)),
        y: Math.max(5, Math.min(95, y)),
      };
    },
    [bounds],
  );

  // Find assignments for drawing connection vectors
  const activeTransitVectors = useMemo(() => {
    const vectors: {
      id: string;
      techName: string;
      jobNumber: string;
      techPos: { x: number; y: number };
      jobPos: { x: number; y: number };
      status: string;
    }[] = [];

    validJobs.forEach((j) => {
      if (j.assigned_technician?.id) {
        const tech = validTechs.find((t) => t.id === j.assigned_technician!.id);
        if (tech && tech.current_latitude && tech.current_longitude && j.latitude && j.longitude) {
          vectors.push({
            id: `vector-${tech.id}-${j.id}`,
            techName: tech.user?.full_name || tech.employee_code,
            jobNumber: j.job_number,
            techPos: projectCoord(tech.current_latitude, tech.current_longitude),
            jobPos: projectCoord(j.latitude, j.longitude),
            status: j.status,
          });
        }
      }
    });

    return vectors;
  }, [validJobs, validTechs, projectCoord]);

  // Canvas Pan handlers
  const handleMouseDown = (e: React.MouseEvent) => {
    if (e.button !== 0) return;
    setIsDragging(true);
    dragStartRef.current = { x: e.clientX - pan.x, y: e.clientY - pan.y };
  };

  const handleMouseMove = (e: React.MouseEvent) => {
    if (!isDragging) return;
    setPan({
      x: e.clientX - dragStartRef.current.x,
      y: e.clientY - dragStartRef.current.y,
    });
  };

  const handleMouseUp = () => {
    setIsDragging(false);
  };

  const resetViewport = () => {
    setZoom(1);
    setPan({ x: 0, y: 0 });
  };

  return (
    <div className="flex flex-col gap-5 py-2 animate-fade-in select-none">
      {/* ── Page Header ── */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-slate-200 pb-4">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <span className="inline-flex items-center gap-1.5 rounded-full border border-blue-200 bg-blue-50 px-2.5 py-0.5 text-[11px] font-bold text-blue-700">
              <MapPin className="h-3.5 w-3.5 text-blue-600" />
              <span>Live Field Operations Map</span>
            </span>
            <span className="inline-flex items-center gap-1 rounded-full border border-slate-200 bg-slate-100 px-2.5 py-0.5 text-[11px] font-bold text-slate-700">
              <Shield className="h-3 w-3 text-purple-600" />
              <span>{user?.role || 'Dispatcher'}</span>
            </span>
            <RealtimeConnectionBadge />
          </div>

          <h1 className="text-2xl md:text-3xl font-extrabold tracking-tight text-slate-900">
            Live Field Operations Map
          </h1>
          <p className="text-xs md:text-sm text-slate-500 mt-0.5 font-medium">
            Real-time geospatial field dispatch overview, technician browser GPS telemetry, and active transit vectors.
          </p>
        </div>

        <div className="flex items-center gap-2.5 self-start md:self-auto">
          <button
            onClick={loadMapData}
            disabled={isLoading}
            className="flex items-center gap-1.5 rounded-xl border border-slate-200 bg-white px-3.5 py-2 text-xs font-bold text-slate-700 hover:bg-slate-50 transition-colors shadow-2xs cursor-pointer"
          >
            <RefreshCw className={cn('h-3.5 w-3.5', isLoading && 'animate-spin')} />
            <span>Refresh Map</span>
          </button>
        </div>
      </div>

      {/* ── Top Summary Operational Counters (Calculated strictly from PostgreSQL) ── */}
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3">
        {/* Active Jobs */}
        <div className="rounded-xl border border-slate-200 bg-white p-3.5 shadow-2xs">
          <div className="text-[11px] font-bold uppercase tracking-wider text-slate-500">Active Jobs</div>
          <div className="mt-1 text-2xl font-black text-slate-900 font-mono">
            {summaryCounts.activeJobs.toLocaleString()}
          </div>
          <div className="text-[10px] text-slate-400 font-medium mt-0.5">In-flight work</div>
        </div>

        {/* Technicians */}
        <div className="rounded-xl border border-slate-200 bg-white p-3.5 shadow-2xs">
          <div className="text-[11px] font-bold uppercase tracking-wider text-slate-500">Technicians</div>
          <div className="mt-1 text-2xl font-black text-slate-900 font-mono">
            {summaryCounts.totalTechnicians.toLocaleString()}
          </div>
          <div className="text-[10px] text-slate-400 font-medium mt-0.5">Field workforce</div>
        </div>

        {/* Technicians with Live GPS */}
        <div className="rounded-xl border border-emerald-200 bg-emerald-50/40 p-3.5 shadow-2xs">
          <div className="text-[11px] font-bold uppercase tracking-wider text-emerald-800 flex items-center gap-1">
            <span className="h-2 w-2 rounded-full bg-emerald-500 animate-pulse" />
            <span>Live GPS Units</span>
          </div>
          <div className="mt-1 text-2xl font-black text-emerald-700 font-mono">
            {summaryCounts.techsWithLiveGps.toLocaleString()}
          </div>
          <div className="text-[10px] text-emerald-600 font-medium mt-0.5">≤30s telemetry</div>
        </div>

        {/* Unassigned Jobs */}
        <div className="rounded-xl border border-purple-200 bg-purple-50/40 p-3.5 shadow-2xs">
          <div className="text-[11px] font-bold uppercase tracking-wider text-purple-800">Unassigned</div>
          <div className="mt-1 text-2xl font-black text-purple-700 font-mono">
            {summaryCounts.unassignedJobs.toLocaleString()}
          </div>
          <div className="text-[10px] text-purple-600 font-medium mt-0.5">Pending matching</div>
        </div>

        {/* Jobs Travelling */}
        <div className="rounded-xl border border-amber-200 bg-amber-50/40 p-3.5 shadow-2xs">
          <div className="text-[11px] font-bold uppercase tracking-wider text-amber-800">Travelling</div>
          <div className="mt-1 text-2xl font-black text-amber-700 font-mono">
            {summaryCounts.jobsTravelling.toLocaleString()}
          </div>
          <div className="text-[10px] text-amber-600 font-medium mt-0.5">En route to site</div>
        </div>

        {/* Jobs Working */}
        <div className="rounded-xl border border-blue-200 bg-blue-50/40 p-3.5 shadow-2xs">
          <div className="text-[11px] font-bold uppercase tracking-wider text-blue-800">Working</div>
          <div className="mt-1 text-2xl font-black text-blue-700 font-mono">
            {summaryCounts.jobsWorking.toLocaleString()}
          </div>
          <div className="text-[10px] text-blue-600 font-medium mt-0.5">On-site execution</div>
        </div>
      </div>

      {/* ── Main Workspace: Spatial Map Canvas + Detail Inspector Drawer ── */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-5">
        {/* Left/Center Canvas: Spatial Coordinate Map (8 cols) */}
        <div
          className={cn(
            'rounded-2xl border border-slate-300 bg-slate-950 p-4 shadow-lg relative overflow-hidden flex flex-col justify-between transition-all select-none',
            selectedEntity ? 'lg:col-span-8' : 'lg:col-span-12',
            'min-h-[580px]',
          )}
        >
          {/* Spatial Grid Background */}
          <div className="absolute inset-0 bg-[linear-gradient(to_right,#1e293b_1px,transparent_1px),linear-gradient(to_bottom,#1e293b_1px,transparent_1px)] bg-[size:32px_32px] opacity-35 pointer-events-none" />

          {/* Top Canvas Controls Bar */}
          <div className="relative z-20 flex flex-wrap items-center justify-between gap-3 bg-slate-900/90 border border-slate-800 backdrop-blur-md p-2.5 rounded-xl text-xs text-white">
            {/* View Mode & Entity Filters */}
            <div className="flex items-center gap-1.5">
              <button
                onClick={() => setFilterMode('all')}
                className={cn(
                  'px-2.5 py-1 rounded-lg text-xs font-bold transition-all cursor-pointer',
                  filterMode === 'all'
                    ? 'bg-blue-600 text-white shadow-xs'
                    : 'text-slate-400 hover:text-white',
                )}
              >
                All Nodes
              </button>
              <button
                onClick={() => setFilterMode('jobs')}
                className={cn(
                  'px-2.5 py-1 rounded-lg text-xs font-bold transition-all cursor-pointer flex items-center gap-1',
                  filterMode === 'jobs'
                    ? 'bg-blue-600 text-white shadow-xs'
                    : 'text-slate-400 hover:text-white',
                )}
              >
                <MapPin className="h-3 w-3" />
                <span>Jobs ({validJobs.length})</span>
              </button>
              <button
                onClick={() => setFilterMode('techs')}
                className={cn(
                  'px-2.5 py-1 rounded-lg text-xs font-bold transition-all cursor-pointer flex items-center gap-1',
                  filterMode === 'techs'
                    ? 'bg-emerald-600 text-white shadow-xs'
                    : 'text-slate-400 hover:text-white',
                )}
              >
                <Compass className="h-3 w-3" />
                <span>Techs ({validTechs.length})</span>
              </button>
            </div>

            {/* GPS Telemetry Filter & View Toggle */}
            <div className="flex items-center gap-2">
              <button
                onClick={() => setGpsOnlyFilter(!gpsOnlyFilter)}
                className={cn(
                  'px-2.5 py-1 rounded-lg text-[11px] font-bold border transition-all cursor-pointer flex items-center gap-1',
                  gpsOnlyFilter
                    ? 'bg-emerald-900/80 text-emerald-300 border-emerald-700'
                    : 'bg-slate-800 text-slate-400 border-slate-700 hover:text-white',
                )}
              >
                <Radio className="h-3 w-3" />
                <span>Live GPS Only</span>
              </button>

              <button
                onClick={() => setViewMode(viewMode === 'map' ? 'list' : 'map')}
                className="px-2.5 py-1 rounded-lg text-[11px] font-bold bg-slate-800 text-slate-300 border border-slate-700 hover:bg-slate-700 cursor-pointer"
              >
                {viewMode === 'map' ? 'Matrix View' : 'Map View'}
              </button>

              {/* Pan & Zoom Controls */}
              <div className="flex items-center gap-1 bg-slate-800 rounded-lg p-0.5 border border-slate-700">
                <button
                  onClick={() => setZoom((z) => Math.min(z + 0.25, 2.5))}
                  title="Zoom In"
                  className="p-1 hover:text-white text-slate-400 cursor-pointer"
                >
                  <ZoomIn className="h-3.5 w-3.5" />
                </button>
                <button
                  onClick={() => setZoom((z) => Math.max(z - 0.25, 0.75))}
                  title="Zoom Out"
                  className="p-1 hover:text-white text-slate-400 cursor-pointer"
                >
                  <ZoomOut className="h-3.5 w-3.5" />
                </button>
                <button
                  onClick={resetViewport}
                  title="Reset View"
                  className="p-1 hover:text-white text-slate-400 cursor-pointer"
                >
                  <RotateCcw className="h-3.5 w-3.5" />
                </button>
              </div>
            </div>
          </div>

          {/* Interactive Canvas Plane */}
          {viewMode === 'map' ? (
            <div
              className="relative flex-1 w-full overflow-hidden my-3 cursor-grab active:cursor-grabbing min-h-[440px]"
              onMouseDown={handleMouseDown}
              onMouseMove={handleMouseMove}
              onMouseUp={handleMouseUp}
              onMouseLeave={handleMouseUp}
            >
              <div
                className="absolute inset-0 transition-transform duration-75 origin-center"
                style={{
                  transform: `translate(${pan.x}px, ${pan.y}px) scale(${zoom})`,
                }}
              >
                {/* SVG Active Transit Connection Vectors */}
                <svg className="absolute inset-0 w-full h-full pointer-events-none z-10">
                  {activeTransitVectors.map((v) => (
                    <g key={v.id}>
                      <line
                        x1={`${v.techPos.x}%`}
                        y1={`${v.techPos.y}%`}
                        x2={`${v.jobPos.x}%`}
                        y2={`${v.jobPos.y}%`}
                        stroke={
                          v.status === 'TRAVELLING'
                            ? '#f59e0b'
                            : v.status === 'WORKING'
                            ? '#3b82f6'
                            : '#10b981'
                        }
                        strokeWidth="2"
                        strokeDasharray="4 4"
                        className="animate-pulse opacity-70"
                      />
                    </g>
                  ))}
                </svg>

                {/* Job Markers */}
                {(filterMode === 'all' || filterMode === 'jobs') &&
                  validJobs.map((j) => {
                    const pos = projectCoord(j.latitude!, j.longitude!);
                    const isSelected = selectedEntity?.type === 'job' && selectedEntity.id === j.id;

                    return (
                      <div
                        key={`map-job-${j.id}`}
                        onClick={(e) => {
                          e.stopPropagation();
                          setSelectedEntity({ type: 'job', id: j.id });
                        }}
                        style={{ left: `${pos.x}%`, top: `${pos.y}%` }}
                        className={cn(
                          'absolute -translate-x-1/2 -translate-y-1/2 z-20 cursor-pointer group transition-all',
                          isSelected && 'z-30 scale-125',
                        )}
                      >
                        <div
                          className={cn(
                            'h-7 w-7 rounded-xl border flex items-center justify-center shadow-lg transition-transform hover:scale-110',
                            isSelected
                              ? 'bg-blue-600 border-white text-white ring-4 ring-blue-400/50'
                              : j.priority === 'CRITICAL'
                              ? 'bg-rose-600 border-rose-400 text-white'
                              : j.priority === 'HIGH'
                              ? 'bg-amber-600 border-amber-400 text-white'
                              : j.status === 'NEW'
                              ? 'bg-purple-600 border-purple-400 text-white'
                              : 'bg-blue-800 border-blue-500 text-blue-100',
                          )}
                          title={`${j.job_number}: ${j.customer_name} (${j.status})`}
                        >
                          <MapPin className="h-3.5 w-3.5" />
                        </div>

                        {/* Tooltip on hover */}
                        <div className="pointer-events-none absolute left-1/2 -translate-x-1/2 bottom-full mb-1.5 hidden group-hover:block whitespace-nowrap rounded-lg bg-slate-900/95 border border-slate-700 px-2.5 py-1 text-[11px] font-medium text-white shadow-xl z-40">
                          <div className="font-bold text-blue-400 font-mono">{j.job_number}</div>
                          <div className="text-[10px] text-slate-300">{j.customer_name}</div>
                          <div className="text-[9px] uppercase font-bold text-slate-400">{j.status}</div>
                        </div>
                      </div>
                    );
                  })}

                {/* Technician Markers */}
                {(filterMode === 'all' || filterMode === 'techs') &&
                  validTechs.map((t) => {
                    const hasCoords =
                      typeof t.current_latitude === 'number' &&
                      typeof t.current_longitude === 'number';
                    const freshness = getGpsFreshness(t.updated_at, hasCoords);

                    if (gpsOnlyFilter && freshness !== 'LIVE') return null;

                    const pos = projectCoord(t.current_latitude!, t.current_longitude!);
                    const isSelected =
                      selectedEntity?.type === 'technician' && selectedEntity.id === t.id;

                    return (
                      <div
                        key={`map-tech-${t.id}`}
                        onClick={(e) => {
                          e.stopPropagation();
                          setSelectedEntity({ type: 'technician', id: t.id });
                        }}
                        style={{ left: `${pos.x}%`, top: `${pos.y}%` }}
                        className={cn(
                          'absolute -translate-x-1/2 -translate-y-1/2 z-20 cursor-pointer group transition-all',
                          isSelected && 'z-30 scale-125',
                        )}
                      >
                        {/* Live GPS Pulse Ring */}
                        {freshness === 'LIVE' && (
                          <span className="absolute inset-0 rounded-full bg-emerald-400/40 animate-ping" />
                        )}

                        <div
                          className={cn(
                            'h-8 w-8 rounded-full border flex items-center justify-center shadow-lg transition-transform hover:scale-110 relative',
                            isSelected
                              ? 'bg-emerald-600 border-white text-white ring-4 ring-emerald-400/60'
                              : freshness === 'LIVE'
                              ? 'bg-emerald-600 border-emerald-300 text-white'
                              : freshness === 'STALE'
                              ? 'bg-amber-600 border-amber-300 text-white'
                              : 'bg-slate-700 border-slate-500 text-slate-300',
                          )}
                          title={`${t.user?.full_name || t.employee_code} (${t.availability_status}) [GPS: ${freshness}]`}
                        >
                          <Compass className="h-4 w-4" />
                        </div>

                        {/* Hover Tooltip */}
                        <div className="pointer-events-none absolute left-1/2 -translate-x-1/2 bottom-full mb-1.5 hidden group-hover:block whitespace-nowrap rounded-lg bg-slate-900/95 border border-slate-700 px-2.5 py-1 text-[11px] font-medium text-white shadow-xl z-40">
                          <div className="font-bold text-emerald-400">
                            {t.user?.full_name || t.employee_code}
                          </div>
                          <div className="text-[10px] text-slate-300 font-mono">
                            {t.employee_code} • {t.availability_status}
                          </div>
                          <div
                            className={cn(
                              'text-[9px] uppercase font-bold',
                              freshness === 'LIVE' ? 'text-emerald-400' : 'text-amber-400',
                            )}
                          >
                            GPS {freshness}
                          </div>
                        </div>
                      </div>
                    );
                  })}
              </div>
            </div>
          ) : (
            /* Matrix View */
            <div className="flex-1 overflow-y-auto max-h-[440px] my-3 rounded-xl border border-slate-800 bg-slate-900/90 p-3">
              <div className="text-xs font-bold uppercase text-slate-400 border-b border-slate-800 pb-2 mb-3">
                Live Field Entities Directory
              </div>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                {validTechs.map((t) => {
                  const freshness = getGpsFreshness(
                    t.updated_at,
                    typeof t.current_latitude === 'number',
                  );
                  return (
                    <div
                      key={`list-t-${t.id}`}
                      onClick={() => setSelectedEntity({ type: 'technician', id: t.id })}
                      className="p-3 rounded-xl border border-slate-800 bg-slate-950/60 hover:border-slate-700 cursor-pointer transition-colors"
                    >
                      <div className="flex items-center justify-between text-[11px] mb-1">
                        <span className="font-bold text-emerald-400">{t.employee_code}</span>
                        <span
                          className={cn(
                            'px-1.5 py-0.2 rounded text-[9px] font-bold uppercase',
                            freshness === 'LIVE'
                              ? 'bg-emerald-950 text-emerald-300 border border-emerald-800'
                              : 'bg-amber-950 text-amber-300 border border-amber-800',
                          )}
                        >
                          GPS {freshness}
                        </span>
                      </div>
                      <div className="font-bold text-white text-xs">{t.user?.full_name}</div>
                      <div className="text-[10px] text-slate-400 font-mono mt-1">
                        {t.current_latitude?.toFixed(4)}°, {t.current_longitude?.toFixed(4)}°
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          )}

          {/* Bottom Telemetry Legend & Coordinates Info */}
          <div className="relative z-20 flex flex-wrap items-center justify-between gap-3 text-[11px] text-slate-400 font-mono border-t border-slate-800/80 pt-3">
            <div className="flex items-center gap-3">
              <span className="flex items-center gap-1 text-emerald-400 font-bold">
                <span className="h-2 w-2 rounded-full bg-emerald-400 animate-pulse" />
                Live GPS (&le;30s)
              </span>
              <span className="flex items-center gap-1 text-amber-400">
                <span className="h-2 w-2 rounded-full bg-amber-400" />
                Stale GPS (&gt;30s)
              </span>
              <span className="flex items-center gap-1 text-blue-400">
                <span className="h-2 w-2 rounded-full bg-blue-400" />
                Active Work Order
              </span>
            </div>

            <span>
              Telemetry Heartbeat:{' '}
              <strong className="text-white">{lastTelemetryTimestamp || 'Synchronized'}</strong>
            </span>
          </div>
        </div>

        {/* Right Drawer: Operational Entity Detail Inspector (4 cols when open) */}
        {selectedEntity && (
          <div className="lg:col-span-4 rounded-2xl border border-slate-200 bg-white p-5 shadow-lg flex flex-col justify-between animate-fade-in">
            {/* Technician Detail Panel */}
            {selectedTech && (
              <div>
                <div className="flex items-center justify-between border-b border-slate-200 pb-3 mb-4">
                  <div className="flex items-center gap-2">
                    <Compass className="h-5 w-5 text-emerald-600" />
                    <div>
                      <h3 className="font-bold text-slate-900 text-sm">
                        {selectedTech.user?.full_name || 'Technician'}
                      </h3>
                      <div className="text-[11px] text-slate-500 font-mono">
                        {selectedTech.employee_code}
                      </div>
                    </div>
                  </div>
                  <button
                    onClick={() => setSelectedEntity(null)}
                    className="p-1 rounded-lg hover:bg-slate-100 text-slate-400 hover:text-slate-700 cursor-pointer"
                  >
                    <X className="h-4 w-4" />
                  </button>
                </div>

                <div className="space-y-3.5 text-xs">
                  {/* Status & GPS Freshness */}
                  <div className="flex items-center justify-between p-2.5 rounded-xl bg-slate-50 border border-slate-100">
                    <span className="text-slate-600 font-medium">Availability</span>
                    <span
                      className={cn(
                        'px-2 py-0.5 rounded text-[10px] font-bold uppercase',
                        selectedTech.availability_status === 'AVAILABLE'
                          ? 'bg-emerald-100 text-emerald-800'
                          : 'bg-amber-100 text-amber-800',
                      )}
                    >
                      {selectedTech.availability_status}
                    </span>
                  </div>

                  <div className="flex items-center justify-between p-2.5 rounded-xl bg-slate-50 border border-slate-100">
                    <span className="text-slate-600 font-medium">GPS Freshness</span>
                    {(() => {
                      const freshness = getGpsFreshness(
                        selectedTech.updated_at,
                        typeof selectedTech.current_latitude === 'number',
                      );
                      return (
                        <span
                          className={cn(
                            'px-2 py-0.5 rounded text-[10px] font-bold uppercase flex items-center gap-1',
                            freshness === 'LIVE'
                              ? 'bg-emerald-100 text-emerald-800'
                              : freshness === 'STALE'
                              ? 'bg-amber-100 text-amber-800'
                              : 'bg-slate-100 text-slate-700',
                          )}
                        >
                          {freshness === 'LIVE' && (
                            <span className="h-1.5 w-1.5 rounded-full bg-emerald-600 animate-ping" />
                          )}
                          {freshness}
                        </span>
                      );
                    })()}
                  </div>

                  {/* Coordinates */}
                  <div className="p-3 rounded-xl border border-slate-200 bg-slate-50/70 font-mono text-[11px]">
                    <div className="text-[10px] font-sans font-bold uppercase text-slate-500 mb-1">
                      Browser GPS Telemetry
                    </div>
                    <div>Lat: {selectedTech.current_latitude?.toFixed(5) ?? 'N/A'}</div>
                    <div>Lng: {selectedTech.current_longitude?.toFixed(5) ?? 'N/A'}</div>
                    <div className="text-[10px] text-slate-400 mt-1">
                      Last Update: {new Date(selectedTech.updated_at).toLocaleTimeString()}
                    </div>
                  </div>

                  {/* Current Active Assignment */}
                  {(() => {
                    const currentJob = jobs.find(
                      (j) =>
                        j.assigned_technician?.id === selectedTech.id &&
                        j.status !== 'COMPLETED' &&
                        j.status !== 'CANCELLED',
                    );

                    return (
                      <div className="p-3 rounded-xl border border-blue-200 bg-blue-50/50">
                        <div className="text-[10px] font-bold uppercase text-blue-700 mb-1.5 flex items-center justify-between">
                          <span>Current Assigned Job</span>
                          {currentJob && (
                            <span className="px-1.5 py-0.2 rounded bg-blue-200 text-blue-900 text-[9px]">
                              {currentJob.status}
                            </span>
                          )}
                        </div>

                        {currentJob ? (
                          <div className="space-y-1">
                            <div className="font-bold text-slate-900 text-xs">
                              {currentJob.job_number}: {currentJob.customer_name}
                            </div>
                            <div className="text-[11px] text-slate-600 truncate">
                              {currentJob.address}
                            </div>
                            <button
                              onClick={() => setSelectedEntity({ type: 'job', id: currentJob.id })}
                              className="mt-2 text-[11px] font-bold text-blue-700 hover:text-blue-800 flex items-center gap-1 cursor-pointer"
                            >
                              <span>Inspect Work Order</span>
                              <ChevronRight className="h-3 w-3" />
                            </button>
                          </div>
                        ) : (
                          <div className="text-[11px] text-slate-500 italic">
                            No active job currently assigned.
                          </div>
                        )}
                      </div>
                    );
                  })()}
                </div>

                <div className="mt-5 pt-3 border-t border-slate-100 flex justify-end">
                  <button
                    onClick={() => navigate('/technicians')}
                    className="flex items-center gap-1 text-xs font-bold text-slate-700 hover:text-blue-600 cursor-pointer"
                  >
                    <span>View in Technicians Directory</span>
                    <ExternalLink className="h-3.5 w-3.5" />
                  </button>
                </div>
              </div>
            )}

            {/* Job Detail Panel */}
            {selectedJob && (
              <div>
                <div className="flex items-center justify-between border-b border-slate-200 pb-3 mb-4">
                  <div className="flex items-center gap-2">
                    <MapPin className="h-5 w-5 text-blue-600" />
                    <div>
                      <h3 className="font-bold text-slate-900 text-sm">{selectedJob.job_number}</h3>
                      <div className="text-[11px] text-slate-500">{selectedJob.customer_name}</div>
                    </div>
                  </div>
                  <button
                    onClick={() => setSelectedEntity(null)}
                    className="p-1 rounded-lg hover:bg-slate-100 text-slate-400 hover:text-slate-700 cursor-pointer"
                  >
                    <X className="h-4 w-4" />
                  </button>
                </div>

                <div className="space-y-3.5 text-xs">
                  {/* Status & Priority */}
                  <div className="flex items-center justify-between p-2.5 rounded-xl bg-slate-50 border border-slate-100">
                    <span className="text-slate-600 font-medium">Work Order Status</span>
                    <span className="px-2 py-0.5 rounded text-[10px] font-bold uppercase bg-blue-100 text-blue-800">
                      {selectedJob.status}
                    </span>
                  </div>

                  <div className="flex items-center justify-between p-2.5 rounded-xl bg-slate-50 border border-slate-100">
                    <span className="text-slate-600 font-medium">Priority</span>
                    <span
                      className={cn(
                        'px-2 py-0.5 rounded text-[10px] font-bold uppercase',
                        selectedJob.priority === 'CRITICAL'
                          ? 'bg-rose-100 text-rose-800'
                          : selectedJob.priority === 'HIGH'
                          ? 'bg-amber-100 text-amber-800'
                          : 'bg-slate-100 text-slate-700',
                      )}
                    >
                      {selectedJob.priority}
                    </span>
                  </div>

                  {/* Location & Address */}
                  <div className="p-3 rounded-xl border border-slate-200 bg-slate-50/70">
                    <div className="text-[10px] font-bold uppercase text-slate-500 mb-1">
                      Service Location
                    </div>
                    <div className="text-slate-800 font-medium">{selectedJob.address}</div>
                    <div className="text-[10px] text-slate-400 font-mono mt-1">
                      {selectedJob.latitude?.toFixed(4)}°, {selectedJob.longitude?.toFixed(4)}°
                    </div>
                  </div>

                  {/* Assigned Technician */}
                  <div className="p-3 rounded-xl border border-emerald-200 bg-emerald-50/50">
                    <div className="text-[10px] font-bold uppercase text-emerald-800 mb-1">
                      Assigned Field Technician
                    </div>
                    {selectedJob.assigned_technician ? (
                      <div className="space-y-1">
                        <div className="font-bold text-slate-900 text-xs">
                          {selectedJob.assigned_technician.full_name}
                        </div>
                        <div className="text-[10px] text-slate-500 font-mono">
                          {selectedJob.assigned_technician.employee_code}
                        </div>
                        <button
                          onClick={() =>
                            setSelectedEntity({
                              type: 'technician',
                              id: selectedJob.assigned_technician!.id,
                            })
                          }
                          className="mt-1 text-[11px] font-bold text-emerald-700 hover:text-emerald-800 flex items-center gap-1 cursor-pointer"
                        >
                          <span>Inspect Field Technician</span>
                          <ChevronRight className="h-3 w-3" />
                        </button>
                      </div>
                    ) : (
                      <div className="text-[11px] text-slate-500 italic">
                        Unassigned (Awaiting dispatcher assignment)
                      </div>
                    )}
                  </div>

                  {/* Context-Aware ETA Telemetry */}
                  <div className="p-3 rounded-xl border border-blue-200 bg-blue-50/60">
                    <div className="text-[10px] font-bold uppercase text-blue-800 mb-1 flex items-center justify-between">
                      <span>Context-Aware ETA</span>
                      {selectedEta && (
                        <span className="text-[9px] font-mono font-bold text-blue-700">
                          {selectedEta.is_context_sufficient ? 'Sufficient' : 'Partial'}
                        </span>
                      )}
                    </div>

                    {isEtaLoading ? (
                      <div className="text-[11px] text-slate-400 animate-pulse">
                        Calculating live transit ETA...
                      </div>
                    ) : selectedEta && selectedEta.context_aware_eta_minutes !== null ? (
                      <div className="space-y-1">
                        <div className="text-xl font-black text-blue-700 font-mono">
                          {selectedEta.context_aware_eta_minutes}{' '}
                          <span className="text-xs font-normal text-slate-500">minutes</span>
                        </div>
                        <div className="text-[10px] text-slate-500 font-medium">
                          Baseline: {selectedEta.baseline_eta_minutes}m • Adjustment: +
                          {selectedEta.adjustment_minutes || 0}m
                        </div>
                      </div>
                    ) : (
                      <div className="text-[11px] text-slate-500 italic">
                        ETA not calculated for current operational state.
                      </div>
                    )}
                  </div>
                </div>

                <div className="mt-5 pt-3 border-t border-slate-100 flex justify-end">
                  <button
                    onClick={() => navigate('/jobs')}
                    className="flex items-center gap-1 text-xs font-bold text-slate-700 hover:text-blue-600 cursor-pointer"
                  >
                    <span>View in Job Management</span>
                    <ExternalLink className="h-3.5 w-3.5" />
                  </button>
                </div>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
