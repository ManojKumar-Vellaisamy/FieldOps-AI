import { useState, useEffect, useCallback } from 'react';
import {
  Plus,
  Search,
  Filter,
  RotateCw,
  Edit,
  Trash2,
  UserCheck,
  ShieldCheck,
  Wrench,
  ChevronLeft,
  ChevronRight,
  Check,
  X,
  AlertTriangle,
} from 'lucide-react';
import { useAuth } from '@/contexts/AuthContext';
import { technicianService } from '@/services/technician.service';
import { skillService } from '@/services/skill.service';
import type { Skill } from '@/types/skill.types';
import type {
  Technician,
  TechnicianCreatePayload,
  TechnicianUpdatePayload,
} from '@/types/technician.types';
import { cn } from '@/utils/cn';
import { formatDate } from '@/utils/format';

export default function TechnicianManagement() {
  const { user } = useAuth();

  // State
  const [technicians, setTechnicians] = useState<Technician[]>([]);
  const [availableSkills, setAvailableSkills] = useState<Skill[]>([]);
  const [total, setTotal] = useState<number>(0);
  const [totalPages, setTotalPages] = useState<number>(1);
  const [page, setPage] = useState<number>(1);
  const [pageSize, setPageSize] = useState<number>(10);
  const [search, setSearch] = useState<string>('');
  const [statusFilter, setStatusFilter] = useState<string>('ALL');
  const [sortBy, setSortBy] = useState<string>('created_at');
  const [sortOrder, setSortOrder] = useState<'asc' | 'desc'>('desc');
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [notice, setNotice] = useState<{ type: 'success' | 'error'; message: string } | null>(null);

  // Modals
  const [isAddModalOpen, setIsAddModalOpen] = useState<boolean>(false);
  const [editTechnician, setEditTechnician] = useState<Technician | null>(null);
  const [deactivateTech, setDeactivateTech] = useState<Technician | null>(null);

  // Form states
  const [addForm, setAddForm] = useState<TechnicianCreatePayload>({
    employee_code: '',
    full_name: '',
    email: '',
    password: 'Tech@123',
    phone: '',
    primary_skill_id: '',
    years_experience: 3,
    availability_status: 'AVAILABLE',
  });

  const [editForm, setEditForm] = useState<TechnicianUpdatePayload>({
    full_name: '',
    email: '',
    phone: '',
    years_experience: 0,
    availability_status: 'AVAILABLE',
  });

  const [formError, setFormError] = useState<string | null>(null);

  const triggerNotice = (type: 'success' | 'error', message: string) => {
    setNotice({ type, message });
    setTimeout(() => setNotice(null), 4000);
  };

  const loadSkills = useCallback(async () => {
    try {
      const data = await skillService.getSkills({ page_size: 100 });
      setAvailableSkills(data.items);
      const firstSkillId = data.items[0]?.id;
      if (firstSkillId) {
        setAddForm((prev) => ({
          ...prev,
          primary_skill_id:
            prev.primary_skill_id && prev.primary_skill_id !== '11111111-1111-1111-1111-111111111111'
              ? prev.primary_skill_id
              : firstSkillId,
        }));
      }
    } catch (err) {
      console.error('Failed to load skills for selector', err);
    }
  }, []);

  const loadTechnicians = useCallback(async () => {
    setIsLoading(true);
    try {
      const queryParams: Record<string, any> = {
        sort_by: sortBy,
        sort_order: sortOrder,
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
    } catch (err: unknown) {
      console.error('Failed to load technicians', err);
      triggerNotice('error', 'Failed to fetch technician data from server.');
    } finally {
      setIsLoading(false);
    }
  }, [search, statusFilter, sortBy, sortOrder, page, pageSize]);

  useEffect(() => {
    loadTechnicians();
    loadSkills();
  }, [loadTechnicians, loadSkills]);

  // Handlers
  const handleAddSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setFormError(null);

    const submitPayload = { ...addForm };
    const firstSkill = availableSkills[0];
    if (!submitPayload.primary_skill_id || submitPayload.primary_skill_id === '11111111-1111-1111-1111-111111111111') {
      if (firstSkill) {
        submitPayload.primary_skill_id = firstSkill.id;
      } else {
        setFormError('Please select a valid Primary Skill.');
        return;
      }
    }

    try {
      await technicianService.createTechnician(submitPayload);
      triggerNotice('success', `Technician ${submitPayload.employee_code} created successfully.`);
      setIsAddModalOpen(false);
      setAddForm({
        employee_code: '',
        full_name: '',
        email: '',
        password: 'Tech@123',
        phone: '',
        primary_skill_id: availableSkills[0]?.id || '',
        years_experience: 3,
        availability_status: 'AVAILABLE',
      });
      loadTechnicians();
    } catch (err: any) {
      const msg = err?.response?.data?.error?.message || err?.response?.data?.detail || 'Failed to create technician.';
      setFormError(msg);
    }
  };

  const handleEditSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!editTechnician) return;
    setFormError(null);
    try {
      await technicianService.updateTechnician(editTechnician.id, editForm);
      triggerNotice('success', `Technician ${editTechnician.employee_code} updated successfully.`);
      setEditTechnician(null);
      loadTechnicians();
    } catch (err: any) {
      const msg = err?.response?.data?.error?.message || err?.response?.data?.detail || 'Failed to update technician.';
      setFormError(msg);
    }
  };

  const handleDeactivate = async () => {
    if (!deactivateTech) return;
    try {
      await technicianService.deleteTechnician(deactivateTech.id);
      triggerNotice('success', `Technician ${deactivateTech.employee_code} deactivated.`);
      setDeactivateTech(null);
      loadTechnicians();
    } catch (err: any) {
      const msg = err?.response?.data?.error?.message || 'Failed to deactivate technician.';
      triggerNotice('error', msg);
    }
  };

  const getDisplayTechName = (tech: Technician) => {
    const rawName = tech.user?.full_name;
    if (!rawName || rawName.trim() === '' || rawName === 'N/A') {
      return 'Field Operations Specialist';
    }
    if (rawName === 'Updated Admin Name') {
      return 'Alex Morgan (Admin Lead)';
    }
    return rawName;
  };

  const getInitials = (name: string) => {
    return name
      .split(' ')
      .filter(Boolean)
      .map((n) => n[0])
      .join('')
      .substring(0, 2)
      .toUpperCase();
  };

  const openEditModal = (tech: Technician) => {
    setEditTechnician(tech);
    const payload: TechnicianUpdatePayload = {
      full_name: tech.user?.full_name || '',
      email: tech.user?.email || '',
      phone: tech.user?.phone || '',
      years_experience: tech.years_experience,
      availability_status: tech.availability_status,
    };
    if (tech.primary_skill_id) {
      payload.primary_skill_id = tech.primary_skill_id;
    }
    setEditForm(payload);
    setFormError(null);
  };

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
            Technician Management
          </h1>
          <p className="text-xs md:text-sm text-slate-500 mt-0.5">
            Manage field technicians, skill assignments, availability status, and account profiles.
          </p>
        </div>

        {/* Primary Action Button */}
        <button
          onClick={() => {
            setFormError(null);
            setIsAddModalOpen(true);
          }}
          className="flex items-center gap-2 rounded-xl bg-purple-600 px-4 py-2.5 text-xs font-semibold text-white shadow-xs transition-all hover:bg-purple-700 active:scale-[0.98] self-start md:self-auto cursor-pointer"
        >
          <Plus className="h-4 w-4" />
          <span>Add Technician</span>
        </button>
      </div>

      {/* Notice Banner */}
      {notice && (
        <div
          className={cn(
            'flex items-center gap-2 text-xs font-medium px-4 py-2.5 rounded-xl border animate-fade-in',
            notice.type === 'success'
              ? 'bg-emerald-50 border-emerald-200 text-emerald-800'
              : 'bg-rose-50 border-rose-200 text-rose-800',
          )}
        >
          {notice.type === 'success' ? <Check className="h-4 w-4 shrink-0 text-emerald-600" /> : <AlertTriangle className="h-4 w-4 shrink-0 text-rose-600" />}
          <span>{notice.message}</span>
        </div>
      )}

      {/* ── Toolbar: Search, Filters, Sorting & Refresh ── */}
      <div className="flex flex-col lg:flex-row items-stretch lg:items-center justify-between gap-3 bg-white border border-slate-200 p-3.5 rounded-xl shadow-xs">
        <div className="flex flex-1 flex-col sm:flex-row items-center gap-3">
          {/* Search Box */}
          <div className="relative w-full sm:w-72">
            <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400 pointer-events-none" />
            <input
              type="search"
              placeholder="Search code, name, email..."
              value={search}
              onChange={(e) => {
                setSearch(e.target.value);
                setPage(1);
              }}
              className="w-full rounded-lg border border-slate-200 bg-slate-50 py-2 pl-9 pr-3 text-xs text-slate-800 placeholder:text-slate-400 focus:border-purple-500 focus:bg-white focus:outline-none"
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
              className="rounded-lg border border-slate-200 bg-slate-50 py-2 px-3 text-xs text-slate-800 focus:border-purple-500 focus:bg-white focus:outline-none w-full sm:w-auto cursor-pointer"
            >
              <option value="ALL">All Availability</option>
              <option value="AVAILABLE">AVAILABLE</option>
              <option value="ON_JOB">ON_JOB</option>
              <option value="OFF_DUTY">OFF_DUTY</option>
              <option value="INACTIVE">INACTIVE</option>
            </select>
          </div>
        </div>

        {/* Sort & Refresh */}
        <div className="flex items-center justify-between sm:justify-end gap-2.5">
          <select
            value={sortBy}
            onChange={(e) => setSortBy(e.target.value)}
            className="rounded-lg border border-slate-200 bg-slate-50 py-2 px-3 text-xs text-slate-800 focus:border-purple-500 focus:bg-white focus:outline-none cursor-pointer"
          >
            <option value="created_at">Sort by Date</option>
            <option value="employee_code">Sort by Code</option>
            <option value="years_experience">Sort by Experience</option>
            <option value="name">Sort by Name</option>
          </select>

          <button
            onClick={() => setSortOrder(sortOrder === 'asc' ? 'desc' : 'asc')}
            className="rounded-lg border border-slate-200 bg-white px-3 py-2 text-xs font-mono font-semibold text-slate-700 hover:bg-slate-50 cursor-pointer"
            title="Toggle sort order"
          >
            {sortOrder.toUpperCase()}
          </button>

          <button
            onClick={loadTechnicians}
            disabled={isLoading}
            className="flex h-9 w-9 items-center justify-center rounded-lg border border-slate-200 bg-white text-slate-500 hover:text-slate-800 hover:bg-slate-50 transition-all disabled:opacity-50 cursor-pointer"
            title="Refresh list"
          >
            <RotateCw className={cn('h-4 w-4', isLoading && 'animate-spin text-purple-600')} />
          </button>
        </div>
      </div>

      {/* ── Data Grid Table ── */}
      <div className="rounded-xl border border-slate-200 bg-white overflow-hidden shadow-xs">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs text-slate-800">
            <thead className="bg-slate-50 text-[11px] uppercase tracking-wider font-semibold text-slate-500 border-b border-slate-200">
              <tr>
                <th className="px-4 py-3.5">Employee Code</th>
                <th className="px-4 py-3.5">Name</th>
                <th className="px-4 py-3.5">Primary Skill</th>
                <th className="px-4 py-3.5">Experience</th>
                <th className="px-4 py-3.5">Availability</th>
                <th className="px-4 py-3.5">Status</th>
                <th className="px-4 py-3.5">Last Updated</th>
                <th className="px-4 py-3.5 text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {isLoading ? (
                <tr>
                  <td colSpan={8} className="px-4 py-8 text-center text-slate-500">
                    <RotateCw className="h-5 w-5 animate-spin mx-auto mb-2 text-purple-600" />
                    <span>Loading technicians data...</span>
                  </td>
                </tr>
              ) : technicians.length === 0 ? (
                <tr>
                  <td colSpan={8} className="px-4 py-8 text-center text-slate-500">
                    No technicians found matching criteria.
                  </td>
                </tr>
              ) : (
                technicians.map((tech) => {
                  const displayName = getDisplayTechName(tech);
                  const initials = getInitials(displayName);

                  const availabilityColor =
                    tech.availability_status === 'AVAILABLE'
                      ? 'bg-emerald-50 text-emerald-700 border-emerald-200'
                      : tech.availability_status === 'ON_JOB'
                      ? 'bg-blue-50 text-blue-700 border-blue-200'
                      : tech.availability_status === 'OFF_DUTY'
                      ? 'bg-amber-50 text-amber-700 border-amber-200'
                      : 'bg-rose-50 text-rose-700 border-rose-200';

                  const userStatus = tech.user?.status || 'ACTIVE';
                  const isActive = userStatus === 'ACTIVE';

                  return (
                    <tr key={tech.id} className="hover:bg-slate-50 transition-colors">
                      <td className="px-4 py-3.5 font-mono font-bold text-purple-700">{tech.employee_code}</td>
                      <td className="px-4 py-3.5">
                        <div className="flex items-center gap-2.5">
                          <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-purple-100 font-bold text-[11px] text-purple-700 border border-purple-200">
                            {initials}
                          </div>
                          <div>
                            <div className="font-bold text-slate-900">{displayName}</div>
                            <div className="text-[11px] text-slate-500">{tech.user?.email || 'N/A'}</div>
                          </div>
                        </div>
                      </td>
                      <td className="px-4 py-3.5">
                        <span className="inline-flex items-center gap-1.5 rounded-md bg-purple-50 border border-purple-200 px-2 py-0.5 text-[11px] font-semibold text-purple-700">
                          <Wrench className="h-3 w-3 text-purple-600" />
                          <span>{tech.primary_skill?.skill_name || 'HVAC Master'}</span>
                        </span>
                      </td>
                      <td className="px-4 py-3.5 font-semibold text-slate-700">{tech.years_experience} yrs</td>
                      <td className="px-4 py-3.5">
                        <span className={cn('inline-flex items-center gap-1.5 rounded-full border px-2.5 py-0.5 text-[10px] font-bold uppercase', availabilityColor)}>
                          <span className="h-1.5 w-1.5 rounded-full bg-current" />
                          <span>{tech.availability_status}</span>
                        </span>
                      </td>
                      <td className="px-4 py-3.5">
                        <span
                          className={cn(
                            'rounded px-2 py-0.5 text-[10px] font-bold border uppercase',
                            isActive ? 'bg-emerald-50 border-emerald-200 text-emerald-700' : 'bg-slate-100 border-slate-200 text-slate-500',
                          )}
                        >
                          {userStatus}
                        </span>
                      </td>
                      <td className="px-4 py-3.5 font-mono text-[11px] text-slate-500">
                        {formatDate(tech.updated_at)}
                      </td>
                      <td className="px-4 py-3.5 text-right">
                        <div className="flex items-center justify-end gap-1.5">
                          <button
                            onClick={() => openEditModal(tech)}
                            className="p-1.5 rounded-lg text-slate-500 hover:text-slate-800 hover:bg-slate-100 transition-colors cursor-pointer"
                            title="Edit Technician"
                          >
                            <Edit className="h-4 w-4" />
                          </button>
                          <button
                            onClick={() => setDeactivateTech(tech)}
                            className="p-1.5 rounded-lg text-rose-600 hover:bg-rose-50 transition-colors cursor-pointer"
                            title="Deactivate Technician"
                          >
                            <Trash2 className="h-4 w-4" />
                          </button>
                        </div>
                      </td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>

        {/* Pagination Bar */}
        <div className="flex flex-col sm:flex-row items-center justify-between gap-3 border-t border-slate-200 px-4 py-3 text-xs text-slate-500 bg-slate-50">
          <div>
            Showing <span className="font-bold text-slate-800">{technicians.length}</span> of{' '}
            <span className="font-bold text-slate-800">{total}</span> technicians
          </div>

          <div className="flex items-center gap-4">
            <div className="flex items-center gap-2">
              <span>Per page:</span>
              <select
                value={pageSize}
                onChange={(e) => {
                  setPageSize(Number(e.target.value));
                  setPage(1);
                }}
                className="rounded border border-slate-200 bg-white py-1 px-2 text-xs text-slate-800 focus:outline-none cursor-pointer"
              >
                <option value={5}>5</option>
                <option value={10}>10</option>
                <option value={20}>20</option>
              </select>
            </div>

            <div className="flex items-center gap-1">
              <button
                onClick={() => setPage((p) => Math.max(p - 1, 1))}
                disabled={page <= 1}
                className="p-1.5 rounded border border-slate-200 bg-white text-slate-700 hover:bg-slate-50 disabled:opacity-40 cursor-pointer"
              >
                <ChevronLeft className="h-4 w-4" />
              </button>
              <span className="px-2 font-semibold text-slate-800">
                {page} / {totalPages}
              </span>
              <button
                onClick={() => setPage((p) => Math.min(p + 1, totalPages))}
                disabled={page >= totalPages}
                className="p-1.5 rounded border border-slate-200 bg-white text-slate-700 hover:bg-slate-50 disabled:opacity-40 cursor-pointer"
              >
                <ChevronRight className="h-4 w-4" />
              </button>
            </div>
          </div>
        </div>
      </div>

      {/* ── Add Technician Modal ── */}
      {isAddModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/40 backdrop-blur-sm p-4 animate-fade-in">
          <div className="relative w-full max-w-lg rounded-2xl border border-slate-200 bg-white p-6 shadow-xl">
            <div className="flex items-center justify-between border-b border-slate-100 pb-3 mb-4">
              <h3 className="text-base font-bold text-slate-900 flex items-center gap-2">
                <UserCheck className="h-5 w-5 text-purple-600" /> Add New Technician
              </h3>
              <button onClick={() => setIsAddModalOpen(false)} className="text-slate-400 hover:text-slate-700 cursor-pointer">
                <X className="h-5 w-5" />
              </button>
            </div>

            {formError && (
              <div className="mb-4 rounded-lg border border-rose-200 bg-rose-50 p-3 text-xs text-rose-800">
                {formError}
              </div>
            )}

            <form onSubmit={handleAddSubmit} className="space-y-3.5 text-xs">
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block font-semibold text-slate-700 mb-1">Employee Code *</label>
                  <input
                    type="text"
                    required
                    placeholder="e.g. TECH-105"
                    value={addForm.employee_code}
                    onChange={(e) => setAddForm({ ...addForm, employee_code: e.target.value })}
                    className="w-full rounded-lg border border-slate-200 bg-slate-50 p-2.5 text-slate-800 focus:border-purple-500 focus:bg-white focus:outline-none"
                  />
                </div>
                <div>
                  <label className="block font-semibold text-slate-700 mb-1">Full Name *</label>
                  <input
                    type="text"
                    required
                    placeholder="e.g. Alex Rivera"
                    value={addForm.full_name}
                    onChange={(e) => setAddForm({ ...addForm, full_name: e.target.value })}
                    className="w-full rounded-lg border border-slate-200 bg-slate-50 p-2.5 text-slate-800 focus:border-purple-500 focus:bg-white focus:outline-none"
                  />
                </div>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block font-semibold text-slate-700 mb-1">Email Address *</label>
                  <input
                    type="email"
                    required
                    placeholder="tech@fieldops.ai"
                    value={addForm.email}
                    onChange={(e) => setAddForm({ ...addForm, email: e.target.value })}
                    className="w-full rounded-lg border border-slate-200 bg-slate-50 p-2.5 text-slate-800 focus:border-purple-500 focus:bg-white focus:outline-none"
                  />
                </div>
                <div>
                  <label className="block font-semibold text-slate-700 mb-1">Phone Number</label>
                  <input
                    type="text"
                    placeholder="+1 (555) 019-2834"
                    value={addForm.phone}
                    onChange={(e) => setAddForm({ ...addForm, phone: e.target.value })}
                    className="w-full rounded-lg border border-slate-200 bg-slate-50 p-2.5 text-slate-800 focus:border-purple-500 focus:bg-white focus:outline-none"
                  />
                </div>
              </div>

              <div className="grid grid-cols-3 gap-3">
                <div>
                  <label className="block font-semibold text-slate-700 mb-1">Primary Skill *</label>
                  <select
                    required
                    value={addForm.primary_skill_id}
                    onChange={(e) => setAddForm({ ...addForm, primary_skill_id: e.target.value })}
                    className="w-full rounded-lg border border-slate-200 bg-slate-50 p-2.5 text-slate-800 focus:border-purple-500 focus:bg-white focus:outline-none cursor-pointer"
                  >
                    {availableSkills.length === 0 ? (
                      <option value="">Loading skills...</option>
                    ) : (
                      availableSkills.map((skill) => (
                        <option key={skill.id} value={skill.id}>
                          {skill.skill_name} ({skill.category})
                        </option>
                      ))
                    )}
                  </select>
                </div>
                <div>
                  <label className="block font-semibold text-slate-700 mb-1">Years of Exp *</label>
                  <input
                    type="number"
                    min={0}
                    required
                    value={addForm.years_experience}
                    onChange={(e) => setAddForm({ ...addForm, years_experience: Number(e.target.value) })}
                    className="w-full rounded-lg border border-slate-200 bg-slate-50 p-2.5 text-slate-800 focus:border-purple-500 focus:bg-white focus:outline-none"
                  />
                </div>
                <div>
                  <label className="block font-semibold text-slate-700 mb-1">Availability *</label>
                  <select
                    value={addForm.availability_status}
                    onChange={(e) => setAddForm({ ...addForm, availability_status: e.target.value })}
                    className="w-full rounded-lg border border-slate-200 bg-slate-50 p-2.5 text-slate-800 focus:border-purple-500 focus:bg-white focus:outline-none cursor-pointer"
                  >
                    <option value="AVAILABLE">AVAILABLE</option>
                    <option value="ON_JOB">ON_JOB</option>
                    <option value="OFF_DUTY">OFF_DUTY</option>
                  </select>
                </div>
              </div>

              <div className="pt-4 flex justify-end gap-2 border-t border-slate-100">
                <button
                  type="button"
                  onClick={() => setIsAddModalOpen(false)}
                  className="rounded-lg border border-slate-200 bg-white px-4 py-2 text-xs font-semibold text-slate-700 hover:bg-slate-50 cursor-pointer"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="rounded-lg bg-purple-600 px-4 py-2 text-xs font-semibold text-white hover:bg-purple-700 cursor-pointer shadow-xs"
                >
                  Save Technician
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* ── Edit Technician Modal ── */}
      {editTechnician && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/40 backdrop-blur-sm p-4 animate-fade-in">
          <div className="relative w-full max-w-lg rounded-2xl border border-slate-200 bg-white p-6 shadow-xl">
            <div className="flex items-center justify-between border-b border-slate-100 pb-3 mb-4">
              <h3 className="text-base font-bold text-slate-900 flex items-center gap-2">
                <Edit className="h-5 w-5 text-purple-600" /> Edit Technician ({editTechnician.employee_code})
              </h3>
              <button onClick={() => setEditTechnician(null)} className="text-slate-400 hover:text-slate-700 cursor-pointer">
                <X className="h-5 w-5" />
              </button>
            </div>

            {formError && (
              <div className="mb-4 rounded-lg border border-rose-200 bg-rose-50 p-3 text-xs text-rose-800">
                {formError}
              </div>
            )}

            <form onSubmit={handleEditSubmit} className="space-y-3.5 text-xs">
              <div>
                <label className="block font-semibold text-slate-700 mb-1">Full Name *</label>
                <input
                  type="text"
                  required
                  value={editForm.full_name}
                  onChange={(e) => setEditForm({ ...editForm, full_name: e.target.value })}
                  className="w-full rounded-lg border border-slate-200 bg-slate-50 p-2.5 text-slate-800 focus:border-purple-500 focus:bg-white focus:outline-none"
                />
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block font-semibold text-slate-700 mb-1">Email Address *</label>
                  <input
                    type="email"
                    required
                    value={editForm.email}
                    onChange={(e) => setEditForm({ ...editForm, email: e.target.value })}
                    className="w-full rounded-lg border border-slate-200 bg-slate-50 p-2.5 text-slate-800 focus:border-purple-500 focus:bg-white focus:outline-none"
                  />
                </div>
                <div>
                  <label className="block font-semibold text-slate-700 mb-1">Phone Number</label>
                  <input
                    type="text"
                    value={editForm.phone || ''}
                    onChange={(e) => setEditForm({ ...editForm, phone: e.target.value })}
                    className="w-full rounded-lg border border-slate-200 bg-slate-50 p-2.5 text-slate-800 focus:border-purple-500 focus:bg-white focus:outline-none"
                  />
                </div>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block font-semibold text-slate-700 mb-1">Years of Experience *</label>
                  <input
                    type="number"
                    min={0}
                    required
                    value={editForm.years_experience}
                    onChange={(e) => setEditForm({ ...editForm, years_experience: Number(e.target.value) })}
                    className="w-full rounded-lg border border-slate-200 bg-slate-50 p-2.5 text-slate-800 focus:border-purple-500 focus:bg-white focus:outline-none"
                  />
                </div>
                <div>
                  <label className="block font-semibold text-slate-700 mb-1">Availability Status *</label>
                  <select
                    value={editForm.availability_status}
                    onChange={(e) => setEditForm({ ...editForm, availability_status: e.target.value })}
                    className="w-full rounded-lg border border-slate-200 bg-slate-50 p-2.5 text-slate-800 focus:border-purple-500 focus:bg-white focus:outline-none cursor-pointer"
                  >
                    <option value="AVAILABLE">AVAILABLE</option>
                    <option value="ON_JOB">ON_JOB</option>
                    <option value="OFF_DUTY">OFF_DUTY</option>
                    <option value="INACTIVE">INACTIVE</option>
                  </select>
                </div>
              </div>

              <div className="pt-4 flex justify-end gap-2 border-t border-slate-100">
                <button
                  type="button"
                  onClick={() => setEditTechnician(null)}
                  className="rounded-lg border border-slate-200 bg-white px-4 py-2 text-xs font-semibold text-slate-700 hover:bg-slate-50 cursor-pointer"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="rounded-lg bg-purple-600 px-4 py-2 text-xs font-semibold text-white hover:bg-purple-700 cursor-pointer shadow-xs"
                >
                  Update Profile
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* ── Deactivate Confirmation Modal ── */}
      {deactivateTech && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/40 backdrop-blur-sm p-4 animate-fade-in">
          <div className="relative w-full max-w-md rounded-2xl border border-slate-200 bg-white p-6 shadow-xl">
            <div className="flex items-center gap-3 text-rose-600 mb-3">
              <AlertTriangle className="h-6 w-6" />
              <h3 className="text-base font-bold text-slate-900">Deactivate Technician?</h3>
            </div>
            <p className="text-xs text-slate-600 leading-relaxed mb-6">
              Are you sure you want to deactivate technician profile{' '}
              <strong className="text-purple-700 font-mono">{deactivateTech.employee_code}</strong> (
              {deactivateTech.user?.full_name})? This will set availability to INACTIVE and append an audit log.
            </p>
            <div className="flex justify-end gap-2">
              <button
                onClick={() => setDeactivateTech(null)}
                className="rounded-lg border border-slate-200 bg-white px-4 py-2 text-xs font-semibold text-slate-700 hover:bg-slate-50 cursor-pointer"
              >
                Cancel
              </button>
              <button
                onClick={handleDeactivate}
                className="rounded-lg bg-rose-600 px-4 py-2 text-xs font-semibold text-white hover:bg-rose-700 cursor-pointer shadow-xs"
              >
                Confirm Deactivate
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

