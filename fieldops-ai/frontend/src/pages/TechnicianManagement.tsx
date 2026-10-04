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
  KeyRound,
  Eye,
  EyeOff,
  UserX,
  CheckCircle2,
  ShieldAlert,
  MapPin,
} from 'lucide-react';
import { useAuth } from '@/contexts/AuthContext';
import { technicianService } from '@/services/technician.service';
import { skillService } from '@/services/skill.service';
import type { Skill } from '@/types/skill.types';
import type {
  Technician,
  TechnicianCreatePayload,
  TechnicianDependencyCheck,
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
  const [activateTech, setActivateTech] = useState<Technician | null>(null);
  const [deleteTech, setDeleteTech] = useState<Technician | null>(null);

  // Password visibility states
  const [showAddPassword, setShowAddPassword] = useState<boolean>(false);
  const [showAddConfirm, setShowAddConfirm] = useState<boolean>(false);

  // Deletion dependency check state
  const [dependencyCheck, setDependencyCheck] = useState<TechnicianDependencyCheck | null>(null);
  const [isCheckingDeps, setIsCheckingDeps] = useState<boolean>(false);
  const [deleteError, setDeleteError] = useState<string | null>(null);

  // Form states
  const [addForm, setAddForm] = useState<TechnicianCreatePayload>({
    employee_code: '',
    full_name: '',
    email: '',
    password: 'Tech@123',
    confirm_password: 'Tech@123',
    phone: '',
    primary_skill_id: '',
    years_experience: 3,
    availability_status: 'AVAILABLE',
    current_latitude: 10.0700,
    current_longitude: 78.7800,
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

    if (addForm.password.length < 8) {
      setFormError('Password must be at least 8 characters long.');
      return;
    }

    if (addForm.password !== addForm.confirm_password) {
      setFormError('Temporary password and confirmation do not match.');
      return;
    }

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
        confirm_password: 'Tech@123',
        phone: '',
        primary_skill_id: availableSkills[0]?.id || '',
        years_experience: 3,
        availability_status: 'AVAILABLE',
        current_latitude: 10.0700,
        current_longitude: 78.7800,
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
      await technicianService.deactivateTechnician(deactivateTech.id);
      triggerNotice('success', `Technician ${deactivateTech.employee_code} deactivated.`);
      setDeactivateTech(null);
      loadTechnicians();
    } catch (err: any) {
      const msg = err?.response?.data?.error?.message || 'Failed to deactivate technician.';
      triggerNotice('error', msg);
    }
  };

  const handleActivate = async () => {
    if (!activateTech) return;
    try {
      await technicianService.activateTechnician(activateTech.id);
      triggerNotice('success', `Technician ${activateTech.employee_code} reactivated.`);
      setActivateTech(null);
      loadTechnicians();
    } catch (err: any) {
      const msg = err?.response?.data?.error?.message || 'Failed to reactivate technician.';
      triggerNotice('error', msg);
    }
  };

  const openDeleteModal = async (tech: Technician) => {
    setDeleteTech(tech);
    setDependencyCheck(null);
    setDeleteError(null);
    setIsCheckingDeps(true);
    try {
      const check = await technicianService.checkDependencies(tech.id);
      setDependencyCheck(check);
    } catch (err: any) {
      setDeleteError('Unable to check operational dependencies. Please try again.');
    } finally {
      setIsCheckingDeps(false);
    }
  };

  const handlePermanentDelete = async () => {
    if (!deleteTech) return;
    setDeleteError(null);
    try {
      await technicianService.permanentDeleteTechnician(deleteTech.id);
      triggerNotice('success', `Technician ${deleteTech.employee_code} permanently removed.`);
      setDeleteTech(null);
      setDependencyCheck(null);
      loadTechnicians();
    } catch (err: any) {
      const msg =
        err?.response?.data?.error?.message ||
        err?.response?.data?.detail ||
        'Failed to permanently delete technician.';
      setDeleteError(msg);
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
      current_latitude: typeof tech.current_latitude === 'number' ? tech.current_latitude : undefined,
      current_longitude: typeof tech.current_longitude === 'number' ? tech.current_longitude : undefined,
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
            Manage field technicians, skill assignments, credentials, activation lifecycle, and account profiles.
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
          {notice.type === 'success' ? (
            <Check className="h-4 w-4 shrink-0 text-emerald-600" />
          ) : (
            <AlertTriangle className="h-4 w-4 shrink-0 text-rose-600" />
          )}
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
                <th className="px-4 py-3.5">Account Status</th>
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
                  <td colSpan={8} className="px-4 py-12 text-center text-slate-500">
                    <p className="font-semibold text-slate-700 text-sm">0 technicians found</p>
                    <p className="text-xs text-slate-400 mt-1">No technicians found. Click &quot;Add Technician&quot; to provision a new technician profile.</p>
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
                  const isUserActive = userStatus === 'ACTIVE';
                  const isTechActive = isUserActive && tech.availability_status !== 'INACTIVE';

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
                            {typeof tech.current_latitude === 'number' && typeof tech.current_longitude === 'number' && (
                              <div className="text-[10px] text-purple-700 font-mono flex items-center gap-1 mt-0.5">
                                <MapPin className="h-2.5 w-2.5 text-purple-500" />
                                <span>{tech.current_latitude.toFixed(4)}°, {tech.current_longitude.toFixed(4)}°</span>
                              </div>
                            )}
                          </div>
                        </div>
                      </td>
                      <td className="px-4 py-3.5">
                        <span className="inline-flex items-center gap-1.5 rounded-md bg-purple-50 border border-purple-200 px-2 py-0.5 text-[11px] font-semibold text-purple-700">
                          <Wrench className="h-3 w-3 text-purple-600" />
                          <span>{tech.primary_skill?.skill_name || 'Unassigned'}</span>
                        </span>
                      </td>
                      <td className="px-4 py-3.5 font-semibold text-slate-700">{tech.years_experience} yrs</td>
                      <td className="px-4 py-3.5">
                        <span
                          className={cn(
                            'inline-flex items-center gap-1.5 rounded-full border px-2.5 py-0.5 text-[10px] font-bold uppercase',
                            availabilityColor,
                          )}
                        >
                          <span className="h-1.5 w-1.5 rounded-full bg-current" />
                          <span>{tech.availability_status}</span>
                        </span>
                      </td>
                      <td className="px-4 py-3.5">
                        <span
                          className={cn(
                            'rounded px-2 py-0.5 text-[10px] font-bold border uppercase inline-flex items-center gap-1',
                            isUserActive
                              ? 'bg-emerald-50 border-emerald-200 text-emerald-700'
                              : 'bg-slate-100 border-slate-300 text-slate-600',
                          )}
                        >
                          <span
                            className={cn(
                              'h-1.5 w-1.5 rounded-full',
                              isUserActive ? 'bg-emerald-500' : 'bg-slate-400',
                            )}
                          />
                          {userStatus}
                        </span>
                      </td>
                      <td className="px-4 py-3.5 font-mono text-[11px] text-slate-500">
                        {formatDate(tech.updated_at)}
                      </td>
                      <td className="px-4 py-3.5 text-right">
                        <div className="flex items-center justify-end gap-1">
                          {/* Edit Details */}
                          <button
                            onClick={() => openEditModal(tech)}
                            className="p-1.5 rounded-lg text-slate-500 hover:text-slate-800 hover:bg-slate-100 transition-colors cursor-pointer"
                            title="Edit Details"
                          >
                            <Edit className="h-4 w-4" />
                          </button>

                          {/* Status Lifecycle Actions */}
                          {isTechActive ? (
                            /* Deactivate */
                            <button
                              onClick={() => setDeactivateTech(tech)}
                              className="p-1.5 rounded-lg text-slate-500 hover:text-rose-600 hover:bg-rose-50 transition-colors cursor-pointer"
                              title="Deactivate Technician"
                            >
                              <UserX className="h-4 w-4" />
                            </button>
                          ) : (
                            /* Activate */
                            <button
                              onClick={() => setActivateTech(tech)}
                              className="p-1.5 rounded-lg text-emerald-600 hover:text-emerald-700 hover:bg-emerald-50 transition-colors cursor-pointer"
                              title="Reactivate Technician"
                            >
                              <CheckCircle2 className="h-4 w-4" />
                            </button>
                          )}

                          {/* Permanent Delete Option (Enabled for inactive / safe technicians) */}
                          {!isTechActive && (
                            <button
                              onClick={() => openDeleteModal(tech)}
                              className="p-1.5 rounded-lg text-rose-600 hover:text-rose-700 hover:bg-rose-50 transition-colors cursor-pointer"
                              title="Permanently Delete"
                            >
                              <Trash2 className="h-4 w-4" />
                            </button>
                          )}
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
          <div className="relative w-full max-w-lg rounded-2xl border border-slate-200 bg-white p-6 shadow-xl max-h-[90vh] overflow-y-auto">
            <div className="flex items-center justify-between border-b border-slate-100 pb-3 mb-4">
              <h3 className="text-base font-bold text-slate-900 flex items-center gap-2">
                <UserCheck className="h-5 w-5 text-purple-600" /> Add New Technician
              </h3>
              <button
                onClick={() => setIsAddModalOpen(false)}
                className="text-slate-400 hover:text-slate-700 cursor-pointer"
              >
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
                    className="w-full rounded-lg border border-slate-200 bg-slate-50 p-2.5 text-slate-800 focus:border-purple-500 focus:bg-white focus:outline-none font-mono"
                  />
                </div>
                <div>
                  <label className="block font-semibold text-slate-700 mb-1">Full Name *</label>
                  <input
                    type="text"
                    required
                    placeholder="e.g. Marcus Vance"
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
                    placeholder="m.vance@fieldops.ai"
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

              {/* Login Credentials Section */}
              <div className="rounded-xl border border-purple-100 bg-purple-50/50 p-3.5 space-y-3">
                <div className="flex items-center gap-2 text-purple-900 font-bold text-xs">
                  <KeyRound className="h-4 w-4 text-purple-600" />
                  <span>Initial Login Credentials</span>
                </div>
                <p className="text-[11px] text-purple-700">
                  Assign a temporary password. The technician will be prompted to change it immediately upon their first login.
                </p>

                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="block font-semibold text-slate-700 mb-1">Temporary Password *</label>
                    <div className="relative">
                      <input
                        type={showAddPassword ? 'text' : 'password'}
                        required
                        minLength={8}
                        placeholder="Min 8 characters"
                        value={addForm.password}
                        onChange={(e) => setAddForm({ ...addForm, password: e.target.value })}
                        className="w-full rounded-lg border border-slate-200 bg-white p-2.5 pr-9 text-slate-800 focus:border-purple-500 focus:outline-none"
                      />
                      <button
                        type="button"
                        onClick={() => setShowAddPassword(!showAddPassword)}
                        className="absolute right-2.5 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600"
                      >
                        {showAddPassword ? <EyeOff className="h-3.5 w-3.5" /> : <Eye className="h-3.5 w-3.5" />}
                      </button>
                    </div>
                  </div>
                  <div>
                    <label className="block font-semibold text-slate-700 mb-1">Confirm Password *</label>
                    <div className="relative">
                      <input
                        type={showAddConfirm ? 'text' : 'password'}
                        required
                        minLength={8}
                        placeholder="Re-enter password"
                        value={addForm.confirm_password}
                        onChange={(e) => setAddForm({ ...addForm, confirm_password: e.target.value })}
                        className="w-full rounded-lg border border-slate-200 bg-white p-2.5 pr-9 text-slate-800 focus:border-purple-500 focus:outline-none"
                      />
                      <button
                        type="button"
                        onClick={() => setShowAddConfirm(!showAddConfirm)}
                        className="absolute right-2.5 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600"
                      >
                        {showAddConfirm ? <EyeOff className="h-3.5 w-3.5" /> : <Eye className="h-3.5 w-3.5" />}
                      </button>
                    </div>
                  </div>
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

              {/* Stationed Base GPS Location */}
              <div className="rounded-xl border border-slate-200 bg-slate-50/70 p-3 space-y-2">
                <div className="flex items-center justify-between">
                  <label className="font-semibold text-slate-700 flex items-center gap-1.5">
                    <MapPin className="h-3.5 w-3.5 text-purple-600" />
                    <span>Stationed Location (Latitude &amp; Longitude)</span>
                  </label>
                  <span className="text-[10px] text-slate-400">Default base location</span>
                </div>
                <div className="grid grid-cols-2 gap-2">
                  <div>
                    <input
                      type="number"
                      step="any"
                      placeholder="Latitude (e.g. 10.0700)"
                      value={addForm.current_latitude ?? ''}
                      onChange={(e) =>
                        setAddForm({
                          ...addForm,
                          current_latitude: e.target.value ? Number(e.target.value) : undefined,
                        })
                      }
                      className="w-full rounded-lg border border-slate-200 bg-white p-2 text-xs font-mono text-slate-800 focus:border-purple-500 focus:outline-none"
                    />
                  </div>
                  <div>
                    <input
                      type="number"
                      step="any"
                      placeholder="Longitude (e.g. 78.7800)"
                      value={addForm.current_longitude ?? ''}
                      onChange={(e) =>
                        setAddForm({
                          ...addForm,
                          current_longitude: e.target.value ? Number(e.target.value) : undefined,
                        })
                      }
                      className="w-full rounded-lg border border-slate-200 bg-white p-2 text-xs font-mono text-slate-800 focus:border-purple-500 focus:outline-none"
                    />
                  </div>
                </div>
                {/* Quick Presets */}
                <div className="flex flex-wrap items-center gap-1.5 pt-1">
                  <span className="text-[10px] text-slate-400 font-semibold">Quick Set:</span>
                  <button
                    type="button"
                    onClick={() =>
                      setAddForm({
                        ...addForm,
                        current_latitude: 10.0700,
                        current_longitude: 78.7800,
                      })
                    }
                    className="rounded bg-white border border-slate-200 px-2 py-0.5 text-[10px] font-bold text-slate-700 hover:border-purple-300 hover:bg-purple-50 transition-colors cursor-pointer"
                  >
                    Karaikudi
                  </button>
                  <button
                    type="button"
                    onClick={() =>
                      setAddForm({
                        ...addForm,
                        current_latitude: 11.0168,
                        current_longitude: 76.9558,
                      })
                    }
                    className="rounded bg-white border border-slate-200 px-2 py-0.5 text-[10px] font-bold text-slate-700 hover:border-purple-300 hover:bg-purple-50 transition-colors cursor-pointer"
                  >
                    Coimbatore
                  </button>
                  <button
                    type="button"
                    onClick={() =>
                      setAddForm({
                        ...addForm,
                        current_latitude: 9.9252,
                        current_longitude: 78.1198,
                      })
                    }
                    className="rounded bg-white border border-slate-200 px-2 py-0.5 text-[10px] font-bold text-slate-700 hover:border-purple-300 hover:bg-purple-50 transition-colors cursor-pointer"
                  >
                    Madurai
                  </button>
                  <button
                    type="button"
                    onClick={() =>
                      setAddForm({
                        ...addForm,
                        current_latitude: 13.0827,
                        current_longitude: 80.2707,
                      })
                    }
                    className="rounded bg-white border border-slate-200 px-2 py-0.5 text-[10px] font-bold text-slate-700 hover:border-purple-300 hover:bg-purple-50 transition-colors cursor-pointer"
                  >
                    Chennai
                  </button>
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
                  Create Technician
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
              <button
                onClick={() => setEditTechnician(null)}
                className="text-slate-400 hover:text-slate-700 cursor-pointer"
              >
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

              {/* Stationed GPS Coordinates */}
              <div className="rounded-xl border border-slate-200 bg-slate-50/70 p-3 space-y-2">
                <div className="flex items-center justify-between">
                  <label className="font-semibold text-slate-700 flex items-center gap-1.5">
                    <MapPin className="h-3.5 w-3.5 text-purple-600" />
                    <span>Stationed Location (Latitude &amp; Longitude)</span>
                  </label>
                  <span className="text-[10px] text-slate-400">Used for dispatch ETA</span>
                </div>
                <div className="grid grid-cols-2 gap-2">
                  <div>
                    <input
                      type="number"
                      step="any"
                      placeholder="Latitude (e.g. 10.0700)"
                      value={editForm.current_latitude ?? ''}
                      onChange={(e) =>
                        setEditForm({
                          ...editForm,
                          current_latitude: e.target.value ? Number(e.target.value) : undefined,
                        })
                      }
                      className="w-full rounded-lg border border-slate-200 bg-white p-2 text-xs font-mono text-slate-800 focus:border-purple-500 focus:outline-none"
                    />
                  </div>
                  <div>
                    <input
                      type="number"
                      step="any"
                      placeholder="Longitude (e.g. 78.7800)"
                      value={editForm.current_longitude ?? ''}
                      onChange={(e) =>
                        setEditForm({
                          ...editForm,
                          current_longitude: e.target.value ? Number(e.target.value) : undefined,
                        })
                      }
                      className="w-full rounded-lg border border-slate-200 bg-white p-2 text-xs font-mono text-slate-800 focus:border-purple-500 focus:outline-none"
                    />
                  </div>
                </div>
                {/* Quick Presets */}
                <div className="flex flex-wrap items-center gap-1.5 pt-1">
                  <span className="text-[10px] text-slate-400 font-semibold">Quick Set:</span>
                  <button
                    type="button"
                    onClick={() =>
                      setEditForm({
                        ...editForm,
                        current_latitude: 10.0700,
                        current_longitude: 78.7800,
                      })
                    }
                    className="rounded bg-white border border-slate-200 px-2 py-0.5 text-[10px] font-bold text-slate-700 hover:border-purple-300 hover:bg-purple-50 transition-colors cursor-pointer"
                  >
                    Karaikudi
                  </button>
                  <button
                    type="button"
                    onClick={() =>
                      setEditForm({
                        ...editForm,
                        current_latitude: 11.0168,
                        current_longitude: 76.9558,
                      })
                    }
                    className="rounded bg-white border border-slate-200 px-2 py-0.5 text-[10px] font-bold text-slate-700 hover:border-purple-300 hover:bg-purple-50 transition-colors cursor-pointer"
                  >
                    Coimbatore
                  </button>
                  <button
                    type="button"
                    onClick={() =>
                      setEditForm({
                        ...editForm,
                        current_latitude: 9.9252,
                        current_longitude: 78.1198,
                      })
                    }
                    className="rounded bg-white border border-slate-200 px-2 py-0.5 text-[10px] font-bold text-slate-700 hover:border-purple-300 hover:bg-purple-50 transition-colors cursor-pointer"
                  >
                    Madurai
                  </button>
                  <button
                    type="button"
                    onClick={() =>
                      setEditForm({
                        ...editForm,
                        current_latitude: 13.0827,
                        current_longitude: 80.2707,
                      })
                    }
                    className="rounded bg-white border border-slate-200 px-2 py-0.5 text-[10px] font-bold text-slate-700 hover:border-purple-300 hover:bg-purple-50 transition-colors cursor-pointer"
                  >
                    Chennai
                  </button>
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


      {/* ── Activate Confirmation Modal ── */}
      {activateTech && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/40 backdrop-blur-sm p-4 animate-fade-in">
          <div className="relative w-full max-w-md rounded-2xl border border-slate-200 bg-white p-6 shadow-xl">
            <div className="flex items-center gap-3 text-emerald-600 mb-3">
              <CheckCircle2 className="h-6 w-6" />
              <h3 className="text-base font-bold text-slate-900">Reactivate Technician?</h3>
            </div>
            <p className="text-xs text-slate-600 leading-relaxed mb-6">
              Are you sure you want to reactivate technician profile{' '}
              <strong className="text-purple-700 font-mono">{activateTech.employee_code}</strong> (
              {activateTech.user?.full_name})? This will restore user account access and reset availability to{' '}
              <strong className="text-emerald-700">AVAILABLE</strong>.
            </p>
            <div className="flex justify-end gap-2">
              <button
                onClick={() => setActivateTech(null)}
                className="rounded-lg border border-slate-200 bg-white px-4 py-2 text-xs font-semibold text-slate-700 hover:bg-slate-50 cursor-pointer"
              >
                Cancel
              </button>
              <button
                onClick={handleActivate}
                className="rounded-lg bg-emerald-600 px-4 py-2 text-xs font-semibold text-white hover:bg-emerald-700 cursor-pointer shadow-xs"
              >
                Confirm Reactivate
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ── Deactivate Confirmation Modal ── */}
      {deactivateTech && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/40 backdrop-blur-sm p-4 animate-fade-in">
          <div className="relative w-full max-w-md rounded-2xl border border-slate-200 bg-white p-6 shadow-xl">
            <div className="flex items-center gap-3 text-amber-600 mb-3">
              <UserX className="h-6 w-6" />
              <h3 className="text-base font-bold text-slate-900">Deactivate Technician?</h3>
            </div>
            <p className="text-xs text-slate-600 leading-relaxed mb-6">
              Are you sure you want to deactivate technician profile{' '}
              <strong className="text-purple-700 font-mono">{deactivateTech.employee_code}</strong> (
              {deactivateTech.user?.full_name})? This will set availability to{' '}
              <strong className="text-rose-700">INACTIVE</strong>, revoke active dispatch eligibility, and deactivate their user account.
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
                className="rounded-lg bg-amber-600 px-4 py-2 text-xs font-semibold text-white hover:bg-amber-700 cursor-pointer shadow-xs"
              >
                Confirm Deactivate
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ── Permanent Delete Modal with Dependency Checking ── */}
      {deleteTech && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/40 backdrop-blur-sm p-4 animate-fade-in">
          <div className="relative w-full max-w-md rounded-2xl border border-slate-200 bg-white p-6 shadow-xl">
            <div className="flex items-center gap-3 text-rose-600 mb-3">
              <Trash2 className="h-6 w-6" />
              <h3 className="text-base font-bold text-slate-900">Permanently Delete Technician</h3>
            </div>

            {deleteError && (
              <div className="mb-4 rounded-lg border border-rose-200 bg-rose-50 p-3 text-xs text-rose-800">
                {deleteError}
              </div>
            )}

            {isCheckingDeps ? (
              <div className="py-6 text-center text-xs text-slate-500">
                <RotateCw className="h-5 w-5 animate-spin mx-auto mb-2 text-purple-600" />
                <span>Checking operational history and dependencies...</span>
              </div>
            ) : dependencyCheck ? (
              dependencyCheck.can_delete ? (
                <div>
                  <div className="mb-4 rounded-xl border border-emerald-200 bg-emerald-50 p-3 text-xs text-emerald-800">
                    <p className="font-semibold mb-1">Safe to delete</p>
                    <p className="text-[11px] text-emerald-700">
                      This technician ({deleteTech.employee_code}) has zero historical job assignments or operational dependencies.
                    </p>
                  </div>
                  <p className="text-xs text-slate-600 mb-6">
                    Permanently deleting will delete this technician profile and user account from the database. This action <strong className="text-rose-600">cannot be undone</strong>.
                  </p>
                  <div className="flex justify-end gap-2">
                    <button
                      onClick={() => setDeleteTech(null)}
                      className="rounded-lg border border-slate-200 bg-white px-4 py-2 text-xs font-semibold text-slate-700 hover:bg-slate-50 cursor-pointer"
                    >
                      Cancel
                    </button>
                    <button
                      onClick={handlePermanentDelete}
                      className="rounded-lg bg-rose-600 px-4 py-2 text-xs font-semibold text-white hover:bg-rose-700 cursor-pointer shadow-xs"
                    >
                      Delete Permanently
                    </button>
                  </div>
                </div>
              ) : (
                <div>
                  <div className="mb-4 rounded-xl border border-rose-200 bg-rose-50 p-3.5 text-xs text-rose-900">
                    <div className="flex items-center gap-2 font-bold mb-1 text-rose-800">
                      <ShieldAlert className="h-4 w-4 shrink-0 text-rose-600" />
                      <span>Cannot Delete: Operational Dependencies Exist</span>
                    </div>
                    <p className="text-[11px] text-rose-700 mb-2">
                      To preserve dispatch records, billing history, and audit compliance, technicians with operational history cannot be permanently deleted.
                    </p>
                    <ul className="list-disc list-inside text-[11px] space-y-0.5 text-rose-800">
                      {dependencyCheck.blockers.map((b, idx) => (
                        <li key={idx}>{b}</li>
                      ))}
                    </ul>
                  </div>
                  <div className="rounded-lg bg-slate-50 border border-slate-200 p-3 text-xs text-slate-600 mb-6">
                    <p className="font-semibold text-slate-800 mb-1">Recommended Action:</p>
                    <p className="text-[11px]">
                      Keep this technician in <strong>INACTIVE</strong> status. This removes them from active dispatch algorithms and live maps while safely preserving historical operational integrity.
                    </p>
                  </div>
                  <div className="flex justify-end">
                    <button
                      onClick={() => setDeleteTech(null)}
                      className="rounded-lg border border-slate-200 bg-white px-4 py-2 text-xs font-semibold text-slate-700 hover:bg-slate-50 cursor-pointer"
                    >
                      Close
                    </button>
                  </div>
                </div>
              )
            ) : null}
          </div>
        </div>
      )}
    </div>
  );
}
