import { useState, useEffect, useCallback } from 'react';
import {
  Search,
  Filter,
  RotateCw,
  Eye,
  Wrench,
  ChevronLeft,
  ChevronRight,
  Shield,
  Sparkles,
  X,
} from 'lucide-react';
import { useAuth } from '@/contexts/AuthContext';
import { technicianService } from '@/services/technician.service';
import type { Technician, TechnicianQueryParams } from '@/types/technician.types';
import { cn } from '@/utils/cn';
import { formatDate } from '@/utils/format';

export default function TechnicianDirectory() {
  const { user } = useAuth();

  const [technicians, setTechnicians] = useState<Technician[]>([]);
  const [total, setTotal] = useState<number>(0);
  const [totalPages, setTotalPages] = useState<number>(1);
  const [page, setPage] = useState<number>(1);
  const [pageSize] = useState<number>(10);
  const [search, setSearch] = useState<string>('');
  const [statusFilter, setStatusFilter] = useState<string>('ALL');
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [selectedTech, setSelectedTech] = useState<Technician | null>(null);

  const loadDirectory = useCallback(async () => {
    setIsLoading(true);
    try {
      const queryParams: TechnicianQueryParams = {
        sort_by: 'created_at',
        sort_order: 'desc',
        page,
        page_size: pageSize,
      };
      if (search.trim()) {
        queryParams.search = search.trim();
      }
      if (statusFilter !== 'ALL') {
        queryParams.availability_status = statusFilter;
      }

      const data = await technicianService.getTechnicians(queryParams);
      setTechnicians(data.items);
      setTotal(data.total);
      setTotalPages(data.total_pages);
    } catch (err) {
      console.error('Failed to load technician directory', err);
    } finally {
      setIsLoading(false);
    }
  }, [search, statusFilter, page, pageSize]);

  useEffect(() => {
    loadDirectory();
  }, [loadDirectory]);

  return (
    <div className="flex flex-col gap-6 py-2 animate-fade-in select-none">
      {/* ── Header ── */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-slate-200 pb-5">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <span className="inline-flex items-center gap-1 rounded-full border border-blue-200 bg-blue-50 px-2.5 py-0.5 text-[11px] font-semibold text-blue-700">
              <Sparkles className="h-3 w-3 text-blue-600" />
              <span>Dispatch Control Center</span>
            </span>
            <span className="inline-flex items-center gap-1 rounded-full border border-slate-200 bg-slate-100 px-2.5 py-0.5 text-[11px] font-medium text-slate-700">
              <Shield className="h-3 w-3 text-purple-600" />
              <span>{user?.role || 'Dispatcher'}</span>
            </span>
          </div>

          <h1 className="text-2xl md:text-3xl font-extrabold tracking-tight text-slate-900">
            Technician Directory
          </h1>
          <p className="text-xs md:text-sm text-slate-500 mt-0.5">
            Read-only field workforce directory, availability telemetry, and primary skill matrix.
          </p>
        </div>
      </div>

      {/* ── Toolbar: Search & Filters ── */}
      <div className="flex flex-col sm:flex-row items-center justify-between gap-3 bg-white border border-slate-200 p-3.5 rounded-xl shadow-xs">
        <div className="flex flex-1 flex-col sm:flex-row items-center gap-3 w-full sm:w-auto">
          {/* Search Box */}
          <div className="relative w-full sm:w-80">
            <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400 pointer-events-none" />
            <input
              type="search"
              placeholder="Search code, technician name, email..."
              value={search}
              onChange={(e) => {
                setSearch(e.target.value);
                setPage(1);
              }}
              className="w-full rounded-lg border border-slate-300 bg-slate-50 py-2 pl-9 pr-3 text-xs text-slate-800 placeholder:text-slate-400 focus:border-blue-500 focus:bg-white focus:outline-none"
            />
          </div>

          {/* Availability Status Filter */}
          <div className="flex items-center gap-2 w-full sm:w-auto">
            <Filter className="h-4 w-4 text-slate-400 shrink-0" />
            <select
              value={statusFilter}
              onChange={(e) => {
                setStatusFilter(e.target.value);
                setPage(1);
              }}
              className="rounded-lg border border-slate-300 bg-slate-50 py-2 px-3 text-xs text-slate-800 focus:border-blue-500 focus:bg-white focus:outline-none w-full sm:w-auto"
            >
              <option value="ALL">All Availability Statuses</option>
              <option value="AVAILABLE">AVAILABLE</option>
              <option value="ON_JOB">ON_JOB</option>
              <option value="OFF_DUTY">OFF_DUTY</option>
            </select>
          </div>
        </div>

        <button
          onClick={loadDirectory}
          disabled={isLoading}
          className="flex h-9 w-9 items-center justify-center rounded-lg border border-slate-300 bg-slate-50 text-slate-600 hover:bg-slate-100 hover:text-slate-900 transition-all disabled:opacity-50 self-end sm:self-auto"
          title="Refresh directory"
        >
          <RotateCw className={cn('h-4 w-4', isLoading && 'animate-spin text-blue-600')} />
        </button>
      </div>

      {/* ── Data Grid ── */}
      <div className="rounded-xl border border-slate-200 bg-white overflow-hidden shadow-xs">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs text-slate-700">
            <thead className="bg-slate-50 text-[11px] uppercase tracking-wider font-semibold text-slate-500 border-b border-slate-200">
              <tr>
                <th className="px-4 py-3.5">Code</th>
                <th className="px-4 py-3.5">Technician Name</th>
                <th className="px-4 py-3.5">Primary Skill</th>
                <th className="px-4 py-3.5">Experience</th>
                <th className="px-4 py-3.5">Availability</th>
                <th className="px-4 py-3.5 text-right">View</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {isLoading ? (
                <tr>
                  <td colSpan={6} className="px-4 py-8 text-center text-slate-500">
                    <RotateCw className="h-5 w-5 animate-spin mx-auto mb-2 text-blue-600" />
                    <span>Loading directory...</span>
                  </td>
                </tr>
              ) : technicians.length === 0 ? (
                <tr>
                  <td colSpan={6} className="px-4 py-8 text-center text-slate-500">
                    No active technicians found.
                  </td>
                </tr>
              ) : (
                technicians.map((tech) => {
                  const availabilityColor =
                    tech.availability_status === 'AVAILABLE'
                      ? 'bg-emerald-50 text-emerald-700 border-emerald-200'
                      : tech.availability_status === 'ON_JOB'
                      ? 'bg-blue-50 text-blue-700 border-blue-200'
                      : 'bg-amber-50 text-amber-700 border-amber-200';

                  return (
                    <tr key={tech.id} className="hover:bg-slate-50/80 transition-colors">
                      <td className="px-4 py-3.5 font-mono font-bold text-blue-600">{tech.employee_code}</td>
                      <td className="px-4 py-3.5">
                        <div className="font-bold text-slate-900">{tech.user?.full_name || 'N/A'}</div>
                        <div className="text-[11px] text-slate-500">{tech.user?.email || 'N/A'}</div>
                      </td>
                      <td className="px-4 py-3.5">
                        <span className="inline-flex items-center gap-1.5 rounded-md bg-blue-50 border border-blue-200 px-2 py-0.5 text-[11px] font-semibold text-blue-700">
                          <Wrench className="h-3 w-3 text-blue-600" />
                          <span>{tech.primary_skill?.skill_name || 'HVAC Master'}</span>
                        </span>
                      </td>
                      <td className="px-4 py-3.5 font-semibold text-slate-800">{tech.years_experience} yrs</td>
                      <td className="px-4 py-3.5">
                        <span className={cn('inline-flex items-center gap-1.5 rounded-full border px-2.5 py-0.5 text-[10px] font-bold uppercase', availabilityColor)}>
                          <span className="h-1.5 w-1.5 rounded-full bg-current" />
                          <span>{tech.availability_status}</span>
                        </span>
                      </td>
                      <td className="px-4 py-3.5 text-right">
                        <button
                          onClick={() => setSelectedTech(tech)}
                          className="inline-flex items-center gap-1 text-xs font-semibold text-blue-600 hover:text-blue-800"
                        >
                          <Eye className="h-4 w-4" />
                          <span>Details</span>
                        </button>
                      </td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>

        {/* Pagination Bar */}
        <div className="flex flex-col sm:flex-row items-center justify-between gap-3 border-t border-slate-200 px-4 py-3 text-xs text-slate-500 bg-slate-50/50">
          <div>
            Total Technicians: <span className="font-bold text-slate-800">{total}</span>
          </div>

          <div className="flex items-center gap-2">
            <button
              onClick={() => setPage((p) => Math.max(p - 1, 1))}
              disabled={page <= 1}
              className="p-1.5 rounded border border-slate-300 bg-white text-slate-700 hover:bg-slate-100 disabled:opacity-40"
            >
              <ChevronLeft className="h-4 w-4" />
            </button>
            <span className="px-2 font-semibold text-slate-700">
              {page} / {totalPages}
            </span>
            <button
              onClick={() => setPage((p) => Math.min(p + 1, totalPages))}
              disabled={page >= totalPages}
              className="p-1.5 rounded border border-slate-300 bg-white text-slate-700 hover:bg-slate-100 disabled:opacity-40"
            >
              <ChevronRight className="h-4 w-4" />
            </button>
          </div>
        </div>
      </div>

      {/* ── Read-Only Details Modal ── */}
      {selectedTech && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/40 backdrop-blur-xs p-4 animate-fade-in">
          <div className="relative w-full max-w-md rounded-2xl border border-slate-200 bg-white p-6 shadow-xl">
            <div className="flex items-center justify-between border-b border-slate-200 pb-3 mb-4">
              <div>
                <span className="text-[10px] font-bold font-mono text-blue-600">{selectedTech.employee_code}</span>
                <h3 className="text-base font-bold text-slate-900">{selectedTech.user?.full_name}</h3>
              </div>
              <button onClick={() => setSelectedTech(null)} className="text-slate-400 hover:text-slate-600">
                <X className="h-5 w-5" />
              </button>
            </div>

            <div className="space-y-3 text-xs">
              <div className="flex justify-between py-1 border-b border-slate-100">
                <span className="text-slate-500">Email Address:</span>
                <span className="font-semibold text-slate-800">{selectedTech.user?.email}</span>
              </div>
              <div className="flex justify-between py-1 border-b border-slate-100">
                <span className="text-slate-500">Phone:</span>
                <span className="font-semibold text-slate-800">{selectedTech.user?.phone || 'N/A'}</span>
              </div>
              <div className="flex justify-between py-1 border-b border-slate-100">
                <span className="text-slate-500">Primary Skill:</span>
                <span className="font-semibold text-blue-600">{selectedTech.primary_skill?.skill_name || 'HVAC Master'}</span>
              </div>
              <div className="flex justify-between py-1 border-b border-slate-100">
                <span className="text-slate-500">Experience:</span>
                <span className="font-bold text-slate-900">{selectedTech.years_experience} Years</span>
              </div>
              <div className="flex justify-between py-1 border-b border-slate-100">
                <span className="text-slate-500">Current Availability:</span>
                <span className="font-bold text-emerald-600">{selectedTech.availability_status}</span>
              </div>
              <div className="flex justify-between py-1 border-b border-slate-100">
                <span className="text-slate-500">Registered On:</span>
                <span className="font-mono text-slate-500">{formatDate(selectedTech.created_at)}</span>
              </div>
            </div>

            <div className="mt-6 flex justify-end">
              <button
                onClick={() => setSelectedTech(null)}
                className="rounded-lg bg-blue-600 px-4 py-2 text-xs font-semibold text-white hover:bg-blue-700 transition-colors shadow-xs"
              >
                Close Profile
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
