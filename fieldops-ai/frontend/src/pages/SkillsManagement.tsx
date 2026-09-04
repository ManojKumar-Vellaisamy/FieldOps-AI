import { useState, useEffect, useCallback } from 'react';
import {
  Plus,
  Search,
  Filter,
  RotateCw,
  Edit,
  Power,
  Users,
  ShieldCheck,
  Shield,
  Wrench,
  ChevronLeft,
  ChevronRight,
  Check,
  X,
  AlertTriangle,
  Sparkles,
  Info,
} from 'lucide-react';
import { useAuth } from '@/contexts/AuthContext';
import { skillService } from '@/services/skill.service';
import type {
  Skill,
  SkillCreatePayload,
  SkillUpdatePayload,
  SkillWithTechniciansResponse,
} from '@/types/skill.types';
import { cn } from '@/utils/cn';
import { formatDate } from '@/utils/format';

const CATEGORIES = ['ALL', 'HVAC', 'Electrical', 'Telecommunications', 'Network', 'Calibration'];

export default function SkillsManagement() {
  const { user } = useAuth();
  const isAdmin = user?.role === 'Administrator';

  // State
  const [skills, setSkills] = useState<Skill[]>([]);
  const [total, setTotal] = useState<number>(0);
  const [totalActive, setTotalActive] = useState<number>(0);
  const [totalInactive, setTotalInactive] = useState<number>(0);
  const [totalPages, setTotalPages] = useState<number>(1);
  const [page, setPage] = useState<number>(1);
  const [pageSize] = useState<number>(10);
  const [search, setSearch] = useState<string>('');
  const [categoryFilter, setCategoryFilter] = useState<string>('ALL');
  const [statusFilter, setStatusFilter] = useState<string>('ALL');
  const [sortBy] = useState<string>('created_at');
  const [sortOrder] = useState<'asc' | 'desc'>('desc');
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [notice, setNotice] = useState<{ type: 'success' | 'error'; message: string } | null>(null);

  // Modals
  const [isAddModalOpen, setIsAddModalOpen] = useState<boolean>(false);
  const [editSkill, setEditSkill] = useState<Skill | null>(null);
  const [statusToggleSkill, setStatusToggleSkill] = useState<Skill | null>(null);
  const [techViewSkill, setTechViewSkill] = useState<SkillWithTechniciansResponse | null>(null);
  const [isTechModalOpen, setIsTechModalOpen] = useState<boolean>(false);

  // Form states
  const [addForm, setAddForm] = useState<SkillCreatePayload>({
    skill_name: '',
    category: 'HVAC',
    description: '',
    status: 'ACTIVE',
  });

  const [editForm, setEditForm] = useState<SkillUpdatePayload>({
    skill_name: '',
    category: 'HVAC',
    description: '',
  });

  const [formError, setFormError] = useState<string | null>(null);

  const triggerNotice = (type: 'success' | 'error', message: string) => {
    setNotice({ type, message });
    setTimeout(() => setNotice(null), 4000);
  };

  const loadSkills = useCallback(async () => {
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
      if (categoryFilter !== 'ALL') {
        queryParams.category = categoryFilter;
      }
      if (statusFilter !== 'ALL') {
        queryParams.status = statusFilter;
      }

      const data = await skillService.getSkills(queryParams);
      setSkills(data.items);
      setTotal(data.total);
      setTotalPages(data.total_pages);
      setTotalActive(data.total_active);
      setTotalInactive(data.total_inactive);
    } catch (err: unknown) {
      console.error('Failed to load skills', err);
      triggerNotice('error', 'Failed to fetch skill taxonomy from server.');
    } finally {
      setIsLoading(false);
    }
  }, [search, categoryFilter, statusFilter, sortBy, sortOrder, page, pageSize]);

  useEffect(() => {
    loadSkills();
  }, [loadSkills]);

  // Handlers
  const handleAddSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setFormError(null);
    try {
      await skillService.createSkill(addForm);
      triggerNotice('success', `Skill '${addForm.skill_name}' created successfully.`);
      setIsAddModalOpen(false);
      setAddForm({
        skill_name: '',
        category: 'HVAC',
        description: '',
        status: 'ACTIVE',
      });
      loadSkills();
    } catch (err: any) {
      const msg = err?.response?.data?.error?.message || err?.response?.data?.detail || 'Failed to create skill.';
      setFormError(msg);
    }
  };

  const handleEditSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!editSkill) return;
    setFormError(null);
    try {
      await skillService.updateSkill(editSkill.id, editForm);
      triggerNotice('success', `Skill '${editSkill.skill_name}' updated successfully.`);
      setEditSkill(null);
      loadSkills();
    } catch (err: any) {
      const msg = err?.response?.data?.error?.message || err?.response?.data?.detail || 'Failed to update skill.';
      setFormError(msg);
    }
  };

  const handleToggleStatus = async () => {
    if (!statusToggleSkill) return;
    const newStatus = statusToggleSkill.status === 'ACTIVE' ? 'INACTIVE' : 'ACTIVE';
    try {
      await skillService.updateSkillStatus(statusToggleSkill.id, newStatus);
      triggerNotice(
        'success',
        `Skill '${statusToggleSkill.skill_name}' status changed to ${newStatus}.`,
      );
      setStatusToggleSkill(null);
      loadSkills();
    } catch (err: any) {
      const msg = err?.response?.data?.error?.message || 'Failed to update skill status.';
      triggerNotice('error', msg);
    }
  };

  const handleViewTechnicians = async (skillId: string) => {
    try {
      const res = await skillService.getSkillTechnicians(skillId);
      setTechViewSkill(res);
      setIsTechModalOpen(true);
    } catch (err: any) {
      triggerNotice('error', 'Failed to load qualified technician list.');
    }
  };

  const openEditModal = (skill: Skill) => {
    setEditSkill(skill);
    setEditForm({
      skill_name: skill.skill_name,
      category: skill.category,
      description: skill.description || '',
    });
    setFormError(null);
  };

  return (
    <div className="flex flex-col gap-6 py-2 animate-fade-in select-none">
      {/* ── Header ── */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-slate-200 pb-5">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <span className="inline-flex items-center gap-1.5 rounded-full border border-purple-200 bg-purple-50 px-2.5 py-0.5 text-[11px] font-semibold text-purple-700">
              {isAdmin ? <ShieldCheck className="h-3.5 w-3.5 text-purple-600" /> : <Shield className="h-3.5 w-3.5 text-purple-600" />}
              <span>{isAdmin ? 'Administration Workspace' : 'Dispatch Control Center'}</span>
            </span>
            <span className="inline-flex items-center gap-1 rounded-full border border-slate-200 bg-slate-100 px-2.5 py-0.5 text-[11px] font-medium text-slate-700">
              <span>{user?.role || 'User'}</span>
            </span>
          </div>

          <h1 className="text-2xl md:text-3xl font-extrabold tracking-tight text-slate-900">
            Skills Management
          </h1>
          <p className="text-xs md:text-sm text-slate-500 mt-0.5">
            Maintain technician skill taxonomy, track certified qualification counts, and manage availability status.
          </p>
        </div>

        {/* Primary Action Button (Admin Only) */}
        {isAdmin && (
          <button
            onClick={() => {
              setFormError(null);
              setIsAddModalOpen(true);
            }}
            className="flex items-center gap-2 rounded-xl bg-purple-600 px-4 py-2.5 text-xs font-semibold text-white shadow-xs transition-all hover:bg-purple-700 active:scale-[0.98] self-start md:self-auto"
          >
            <Plus className="h-4 w-4" />
            <span>Create Skill</span>
          </button>
        )}
      </div>

      {/* ── Summary Metric Cards ── */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-xs">
          <div className="flex items-center justify-between text-slate-500 text-xs font-semibold uppercase tracking-wider">
            <span>Total Skills</span>
            <Wrench className="h-4 w-4 text-purple-600" />
          </div>
          <div className="text-2xl font-black text-slate-900 mt-2">{total}</div>
          <div className="text-[11px] text-slate-500 mt-1">Taxonomy skill definitions</div>
        </div>

        <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-xs">
          <div className="flex items-center justify-between text-slate-500 text-xs font-semibold uppercase tracking-wider">
            <span>Active Skills</span>
            <Sparkles className="h-4 w-4 text-emerald-600" />
          </div>
          <div className="text-2xl font-black text-emerald-700 mt-2">{totalActive}</div>
          <div className="text-[11px] text-slate-500 mt-1">Available for dispatch & assignment</div>
        </div>

        <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-xs">
          <div className="flex items-center justify-between text-slate-500 text-xs font-semibold uppercase tracking-wider">
            <span>Inactive Skills</span>
            <Power className="h-4 w-4 text-amber-600" />
          </div>
          <div className="text-2xl font-black text-amber-700 mt-2">{totalInactive}</div>
          <div className="text-[11px] text-slate-500 mt-1">Deactivated taxonomy skills</div>
        </div>
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

      {/* ── Toolbar: Search & Filters ── */}
      <div className="flex flex-col lg:flex-row items-stretch lg:items-center justify-between gap-3 bg-white border border-slate-200 p-3.5 rounded-xl shadow-xs">
        <div className="flex flex-1 flex-col sm:flex-row items-center gap-3">
          {/* Search Box */}
          <div className="relative w-full sm:w-72">
            <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400 pointer-events-none" />
            <input
              type="search"
              placeholder="Search skill name, description..."
              value={search}
              onChange={(e) => {
                setSearch(e.target.value);
                setPage(1);
              }}
              className="w-full rounded-lg border border-slate-300 bg-slate-50 py-2 pl-9 pr-3 text-xs text-slate-800 placeholder:text-slate-400 focus:border-purple-500 focus:bg-white focus:outline-none"
            />
          </div>

          {/* Category Filter */}
          <div className="flex items-center gap-2 w-full sm:w-auto">
            <Filter className="h-4 w-4 text-slate-400 shrink-0" />
            <select
              value={categoryFilter}
              onChange={(e) => {
                setCategoryFilter(e.target.value);
                setPage(1);
              }}
              className="w-full sm:w-44 rounded-lg border border-slate-300 bg-slate-50 py-2 px-3 text-xs text-slate-800 focus:border-purple-500 focus:bg-white focus:outline-none"
            >
              <option value="ALL">All Categories</option>
              {CATEGORIES.filter((c) => c !== 'ALL').map((c) => (
                <option key={c} value={c}>{c}</option>
              ))}
            </select>
          </div>

          {/* Status Filter */}
          <div className="flex items-center gap-2 w-full sm:w-auto">
            <select
              value={statusFilter}
              onChange={(e) => {
                setStatusFilter(e.target.value);
                setPage(1);
              }}
              className="w-full sm:w-36 rounded-lg border border-slate-300 bg-slate-50 py-2 px-3 text-xs text-slate-800 focus:border-purple-500 focus:bg-white focus:outline-none"
            >
              <option value="ALL">All Statuses</option>
              <option value="ACTIVE">Active Only</option>
              <option value="INACTIVE">Inactive Only</option>
            </select>
          </div>
        </div>

        {/* Refresh Button */}
        <button
          onClick={loadSkills}
          title="Refresh Data"
          className="flex items-center justify-center gap-1.5 rounded-lg border border-slate-300 bg-slate-50 px-3 py-2 text-xs font-medium text-slate-700 hover:bg-slate-100 hover:text-slate-900 active:scale-95 transition-all"
        >
          <RotateCw className={cn('h-3.5 w-3.5 text-slate-600', isLoading && 'animate-spin text-purple-600')} />
          <span className="hidden sm:inline">Refresh</span>
        </button>
      </div>

      {/* ── Skills Data Table ── */}
      <div className="overflow-hidden rounded-xl border border-slate-200 bg-white shadow-xs">
        <div className="overflow-x-auto scrollbar-thin">
          <table className="w-full text-left text-xs">
            <thead className="border-b border-slate-200 bg-slate-50 text-[11px] font-bold uppercase tracking-wider text-slate-500">
              <tr>
                <th className="py-3.5 px-4">Skill Name</th>
                <th className="py-3.5 px-4">Category</th>
                <th className="py-3.5 px-4">Description</th>
                <th className="py-3.5 px-4 text-center">Qualified Techs</th>
                <th className="py-3.5 px-4">Status</th>
                <th className="py-3.5 px-4">Last Updated</th>
                <th className="py-3.5 px-4 text-right">Actions</th>
              </tr>
            </thead>

            <tbody className="divide-y divide-slate-100 text-slate-700">
              {isLoading ? (
                <tr>
                  <td colSpan={7} className="py-12 text-center text-slate-500 text-xs">
                    <span>Loading skill taxonomy...</span>
                  </td>
                </tr>
              ) : skills.length === 0 ? (
                <tr>
                  <td colSpan={7} className="py-12 text-center text-slate-500 text-xs">
                    <div className="flex flex-col items-center justify-center gap-2">
                      <Wrench className="h-8 w-8 text-slate-300" />
                      <span className="font-semibold text-slate-700">No skills found</span>
                      <span className="text-[11px] text-slate-400">
                        Try adjusting search terms or status filters.
                      </span>
                    </div>
                  </td>
                </tr>
              ) : (
                skills.map((skill) => (
                  <tr key={skill.id} className="hover:bg-slate-50/80 transition-colors">
                    {/* Skill Name */}
                    <td className="py-3.5 px-4">
                      <div className="flex items-center gap-2">
                        <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-purple-50 text-purple-700 font-bold border border-purple-200">
                          <Wrench className="h-3.5 w-3.5 text-purple-600" />
                        </div>
                        <span className="font-bold text-slate-900">{skill.skill_name}</span>
                      </div>
                    </td>

                    {/* Category */}
                    <td className="py-3.5 px-4">
                      <span className="inline-flex items-center rounded-md bg-slate-100 px-2 py-0.5 text-[11px] font-semibold text-slate-700 border border-slate-200">
                        {skill.category}
                      </span>
                    </td>

                    {/* Description */}
                    <td className="py-3.5 px-4 max-w-xs truncate text-slate-500">
                      {skill.description || '—'}
                    </td>

                    {/* Technician Count */}
                    <td className="py-3.5 px-4 text-center">
                      <button
                        onClick={() => handleViewTechnicians(skill.id)}
                        className="inline-flex items-center gap-1.5 rounded-full bg-purple-50 border border-purple-200 px-2.5 py-0.5 text-[11px] font-bold text-purple-700 hover:bg-purple-100 transition-all"
                      >
                        <Users className="h-3 w-3 text-purple-600" />
                        <span>{skill.technician_count} Techs</span>
                      </button>
                    </td>

                    {/* Status */}
                    <td className="py-3.5 px-4">
                      <span
                        className={cn(
                          'inline-flex items-center gap-1 rounded-full px-2.5 py-0.5 text-[10px] font-bold border',
                          skill.status === 'ACTIVE'
                            ? 'bg-emerald-50 border-emerald-200 text-emerald-700'
                            : 'bg-amber-50 border-amber-200 text-amber-700',
                        )}
                      >
                        <span
                          className={cn(
                            'h-1.5 w-1.5 rounded-full',
                            skill.status === 'ACTIVE' ? 'bg-emerald-600 animate-pulse' : 'bg-amber-600',
                          )}
                        />
                        <span>{skill.status}</span>
                      </span>
                    </td>

                    {/* Last Updated */}
                    <td className="py-3.5 px-4 font-mono text-[11px] text-slate-500">
                      {formatDate(skill.updated_at || skill.created_at)}
                    </td>

                    {/* Actions Menu */}
                    <td className="py-3.5 px-4 text-right">
                      <div className="flex items-center justify-end gap-1.5">
                        <button
                          onClick={() => handleViewTechnicians(skill.id)}
                          title="View Qualified Technicians"
                          className="rounded-lg p-1.5 text-slate-500 hover:bg-slate-100 hover:text-slate-900 transition-colors"
                        >
                          <Users className="h-3.5 w-3.5" />
                        </button>

                        {isAdmin && (
                          <>
                            <button
                              onClick={() => openEditModal(skill)}
                              title="Edit Skill Details"
                              className="rounded-lg p-1.5 text-slate-500 hover:bg-purple-50 hover:text-purple-700 transition-colors"
                            >
                              <Edit className="h-3.5 w-3.5" />
                            </button>

                            <button
                              onClick={() => setStatusToggleSkill(skill)}
                              title={skill.status === 'ACTIVE' ? 'Deactivate Skill' : 'Activate Skill'}
                              className={cn(
                                'rounded-lg p-1.5 transition-colors',
                                skill.status === 'ACTIVE'
                                  ? 'text-amber-600 hover:bg-amber-50'
                                  : 'text-emerald-600 hover:bg-emerald-50',
                              )}
                            >
                              <Power className="h-3.5 w-3.5" />
                            </button>
                          </>
                        )}
                      </div>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>

        {/* Pagination Footer */}
        <div className="flex flex-col sm:flex-row items-center justify-between gap-3 border-t border-slate-200 bg-slate-50/50 px-4 py-3 text-xs text-slate-500">
          <div>
            Showing <span className="font-bold text-slate-800">{skills.length}</span> of{' '}
            <span className="font-bold text-slate-800">{total}</span> skills
          </div>

          <div className="flex items-center gap-2">
            <button
              disabled={page <= 1}
              onClick={() => setPage((p) => Math.max(p - 1, 1))}
              className="flex items-center gap-1 rounded-lg border border-slate-300 bg-white px-2.5 py-1 text-xs text-slate-700 hover:bg-slate-100 disabled:opacity-50 disabled:pointer-events-none transition-all"
            >
              <ChevronLeft className="h-3.5 w-3.5" />
              <span>Prev</span>
            </button>
            <span className="px-2 text-slate-600 font-mono text-[11px]">
              Page {page} of {totalPages}
            </span>
            <button
              disabled={page >= totalPages}
              onClick={() => setPage((p) => Math.min(p + 1, totalPages))}
              className="flex items-center gap-1 rounded-lg border border-slate-300 bg-white px-2.5 py-1 text-xs text-slate-700 hover:bg-slate-100 disabled:opacity-50 disabled:pointer-events-none transition-all"
            >
              <span>Next</span>
              <ChevronRight className="h-3.5 w-3.5" />
            </button>
          </div>
        </div>
      </div>

      {/* ── Modal: Create Skill ── */}
      {isAddModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/40 backdrop-blur-xs p-4 animate-fade-in">
          <div className="w-full max-w-md rounded-2xl border border-slate-200 bg-white p-6 shadow-xl space-y-4">
            <div className="flex items-center justify-between border-b border-slate-200 pb-3">
              <h3 className="text-lg font-extrabold text-slate-900 flex items-center gap-2">
                <Wrench className="h-5 w-5 text-purple-600" />
                <span>Create New Skill</span>
              </h3>
              <button
                onClick={() => setIsAddModalOpen(false)}
                className="text-slate-400 hover:text-slate-600"
              >
                <X className="h-5 w-5" />
              </button>
            </div>

            {formError && (
              <div className="p-3 rounded-lg bg-rose-50 border border-rose-200 text-rose-700 text-xs flex items-center gap-2">
                <AlertTriangle className="h-4 w-4 shrink-0 text-rose-600" />
                <span>{formError}</span>
              </div>
            )}

            <form onSubmit={handleAddSubmit} className="space-y-4 text-xs">
              <div>
                <label className="block text-slate-700 font-semibold mb-1">Skill Name *</label>
                <input
                  type="text"
                  required
                  placeholder="e.g. Fiber Optics Specialist"
                  value={addForm.skill_name}
                  onChange={(e) => setAddForm({ ...addForm, skill_name: e.target.value })}
                  className="w-full rounded-lg border border-slate-300 bg-slate-50 p-2.5 text-slate-800 focus:border-purple-500 focus:bg-white focus:outline-none"
                />
              </div>

              <div>
                <label className="block text-slate-700 font-semibold mb-1">Category *</label>
                <select
                  value={addForm.category}
                  onChange={(e) => setAddForm({ ...addForm, category: e.target.value })}
                  className="w-full rounded-lg border border-slate-300 bg-slate-50 p-2.5 text-slate-800 focus:border-purple-500 focus:bg-white focus:outline-none"
                >
                  {CATEGORIES.filter((c) => c !== 'ALL').map((c) => (
                    <option key={c} value={c}>{c}</option>
                  ))}
                </select>
              </div>

              <div>
                <label className="block text-slate-700 font-semibold mb-1">Description</label>
                <textarea
                  rows={3}
                  placeholder="Detailed qualification scope and technical certification criteria..."
                  value={addForm.description || ''}
                  onChange={(e) => setAddForm({ ...addForm, description: e.target.value })}
                  className="w-full rounded-lg border border-slate-300 bg-slate-50 p-2.5 text-slate-800 focus:border-purple-500 focus:bg-white focus:outline-none"
                />
              </div>

              <div className="flex items-center justify-end gap-2 pt-2 border-t border-slate-200">
                <button
                  type="button"
                  onClick={() => setIsAddModalOpen(false)}
                  className="rounded-lg border border-slate-300 bg-white px-4 py-2 text-slate-700 hover:bg-slate-100 font-medium"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="rounded-lg bg-purple-600 px-4 py-2 text-white font-semibold hover:bg-purple-700 shadow-xs"
                >
                  Create Skill
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* ── Modal: Edit Skill ── */}
      {editSkill && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/40 backdrop-blur-xs p-4 animate-fade-in">
          <div className="w-full max-w-md rounded-2xl border border-slate-200 bg-white p-6 shadow-xl space-y-4">
            <div className="flex items-center justify-between border-b border-slate-200 pb-3">
              <h3 className="text-lg font-extrabold text-slate-900 flex items-center gap-2">
                <Edit className="h-5 w-5 text-purple-600" />
                <span>Edit Skill Taxonomy</span>
              </h3>
              <button
                onClick={() => setEditSkill(null)}
                className="text-slate-400 hover:text-slate-600"
              >
                <X className="h-5 w-5" />
              </button>
            </div>

            {formError && (
              <div className="p-3 rounded-lg bg-rose-50 border border-rose-200 text-rose-700 text-xs flex items-center gap-2">
                <AlertTriangle className="h-4 w-4 shrink-0 text-rose-600" />
                <span>{formError}</span>
              </div>
            )}

            <form onSubmit={handleEditSubmit} className="space-y-4 text-xs">
              <div>
                <label className="block text-slate-700 font-semibold mb-1">Skill Name</label>
                <input
                  type="text"
                  required
                  value={editForm.skill_name || ''}
                  onChange={(e) => setEditForm({ ...editForm, skill_name: e.target.value })}
                  className="w-full rounded-lg border border-slate-300 bg-slate-50 p-2.5 text-slate-800 focus:border-purple-500 focus:bg-white focus:outline-none"
                />
              </div>

              <div>
                <label className="block text-slate-700 font-semibold mb-1">Category</label>
                <select
                  value={editForm.category || 'HVAC'}
                  onChange={(e) => setEditForm({ ...editForm, category: e.target.value })}
                  className="w-full rounded-lg border border-slate-300 bg-slate-50 p-2.5 text-slate-800 focus:border-purple-500 focus:bg-white focus:outline-none"
                >
                  {CATEGORIES.filter((c) => c !== 'ALL').map((c) => (
                    <option key={c} value={c}>{c}</option>
                  ))}
                </select>
              </div>

              <div>
                <label className="block text-slate-700 font-semibold mb-1">Description</label>
                <textarea
                  rows={3}
                  value={editForm.description || ''}
                  onChange={(e) => setEditForm({ ...editForm, description: e.target.value })}
                  className="w-full rounded-lg border border-slate-300 bg-slate-50 p-2.5 text-slate-800 focus:border-purple-500 focus:bg-white focus:outline-none"
                />
              </div>

              <div className="flex items-center justify-end gap-2 pt-2 border-t border-slate-200">
                <button
                  type="button"
                  onClick={() => setEditSkill(null)}
                  className="rounded-lg border border-slate-300 bg-white px-4 py-2 text-slate-700 hover:bg-slate-100 font-medium"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="rounded-lg bg-purple-600 px-4 py-2 text-white font-semibold hover:bg-purple-700 shadow-xs"
                >
                  Save Changes
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* ── Confirmation Modal: Status Change (Soft Deactivation) ── */}
      {statusToggleSkill && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/40 backdrop-blur-xs p-4 animate-fade-in">
          <div className="w-full max-w-sm rounded-2xl border border-slate-200 bg-white p-6 shadow-xl space-y-4">
            <div className="flex items-center gap-3 text-amber-600">
              <AlertTriangle className="h-6 w-6 shrink-0 text-amber-600" />
              <h3 className="text-base font-extrabold text-slate-900">
                Confirm Skill {statusToggleSkill.status === 'ACTIVE' ? 'Deactivation' : 'Activation'}
              </h3>
            </div>

            <p className="text-xs text-slate-600 leading-relaxed">
              Are you sure you want to change the status of skill{' '}
              <strong className="text-slate-900 font-bold">{statusToggleSkill.skill_name}</strong> to{' '}
              <strong className="text-amber-700 font-bold">
                {statusToggleSkill.status === 'ACTIVE' ? 'INACTIVE' : 'ACTIVE'}
              </strong>?
            </p>

            <div className="p-3 rounded-lg bg-slate-50 border border-slate-200 text-[11px] text-slate-500 flex items-start gap-2">
              <Info className="h-4 w-4 text-purple-600 shrink-0 mt-0.5" />
              <span>
                Existing technician skill associations will remain safely preserved in historical records.
              </span>
            </div>

            <div className="flex items-center justify-end gap-2 pt-2 border-t border-slate-200">
              <button
                type="button"
                onClick={() => setStatusToggleSkill(null)}
                className="rounded-lg border border-slate-300 bg-white px-3.5 py-1.5 text-xs text-slate-700 hover:bg-slate-100 font-medium"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={handleToggleStatus}
                className={cn(
                  'rounded-lg px-4 py-1.5 text-xs font-semibold text-white shadow-xs transition-all',
                  statusToggleSkill.status === 'ACTIVE'
                    ? 'bg-amber-600 hover:bg-amber-700'
                    : 'bg-emerald-600 hover:bg-emerald-700',
                )}
              >
                Confirm
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ── Modal: View Qualified Technicians ── */}
      {isTechModalOpen && techViewSkill && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/40 backdrop-blur-xs p-4 animate-fade-in">
          <div className="w-full max-w-lg rounded-2xl border border-slate-200 bg-white p-6 shadow-xl space-y-4">
            <div className="flex items-center justify-between border-b border-slate-200 pb-3">
              <div>
                <h3 className="text-base font-extrabold text-slate-900 flex items-center gap-2">
                  <Users className="h-5 w-5 text-purple-600" />
                  <span>{techViewSkill.skill.skill_name}</span>
                </h3>
                <span className="text-[11px] text-slate-500">
                  Qualified Field Workforce ({techViewSkill.technician_count})
                </span>
              </div>
              <button
                onClick={() => setIsTechModalOpen(false)}
                className="text-slate-400 hover:text-slate-600"
              >
                <X className="h-5 w-5" />
              </button>
            </div>

            <div className="max-h-64 overflow-y-auto space-y-2.5 scrollbar-thin">
              {techViewSkill.technicians.length === 0 ? (
                <div className="py-8 text-center text-xs text-slate-500">
                  No field technicians currently hold this primary skill certification.
                </div>
              ) : (
                techViewSkill.technicians.map((t) => (
                  <div
                    key={t.id}
                    className="flex items-center justify-between p-3 rounded-xl border border-slate-200 bg-slate-50 text-xs"
                  >
                    <div className="flex items-center gap-3">
                      <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-purple-50 text-purple-700 font-bold border border-purple-200 text-xs">
                        {t.employee_code}
                      </div>
                      <div>
                        <div className="font-bold text-slate-900">{t.full_name}</div>
                        <div className="text-[11px] text-slate-500">{t.email}</div>
                      </div>
                    </div>

                    <div className="text-right space-y-0.5">
                      <span className="inline-flex rounded-full bg-emerald-50 border border-emerald-200 px-2 py-0.5 text-[10px] font-bold text-emerald-700">
                        {t.availability_status}
                      </span>
                      <div className="text-[10px] text-slate-500">{t.years_experience} yrs exp</div>
                    </div>
                  </div>
                ))
              )}
            </div>

            <div className="flex justify-end pt-2 border-t border-slate-200">
              <button
                onClick={() => setIsTechModalOpen(false)}
                className="rounded-lg border border-slate-300 bg-white px-4 py-1.5 text-xs text-slate-700 hover:bg-slate-100 font-medium"
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
