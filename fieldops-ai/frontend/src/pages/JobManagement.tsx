import { useState, useEffect, useCallback, useMemo } from 'react';
import {
  Plus,
  Search,
  Filter,
  RotateCw,
  Edit,
  Power,
  UserCheck,
  Shield,
  Briefcase,
  ChevronLeft,
  ChevronRight,
  Check,
  X,
  AlertTriangle,
  MapPin,
  Phone,
  User,
  Wrench,
  Eye,
  Sparkles,
  UserX,
  CheckCircle2,
  ShieldAlert,
  Activity,
  Clock,
  Layers,
} from 'lucide-react';
import { useAuth } from '@/contexts/AuthContext';
import { jobService } from '@/services/job.service';
import { skillService } from '@/services/skill.service';
import { assignmentService } from '@/services/assignment.service';
import type { Job, JobCreatePayload, JobUpdatePayload, Priority } from '@/types/job.types';
import type { Skill } from '@/types/skill.types';
import type { AssignmentRecommendationResponse } from '@/types/assignment.types';
import { cn } from '@/utils/cn';
import { formatDate } from '@/utils/format';
import { parseApiError } from '@/utils/error';
import type { FormErrorState } from '@/utils/error';
import { TechnicianETACard } from '@/components/dashboard/TechnicianETACard';
import { RealtimeConnectionBadge } from '@/components/common/RealtimeConnectionBadge';
import { useRealtimeSync } from '@/hooks/useRealtimeSync';

const PRIORITIES: Priority[] = ['LOW', 'MEDIUM', 'HIGH', 'CRITICAL'];

const LIFECYCLE_STAGES = [
  { key: 'NEW', label: 'NEW', subtext: 'Job Created' },
  { key: 'ASSIGNED', label: 'ASSIGNED', subtext: 'Tech Assigned' },
  { key: 'EN_ROUTE', altKey: 'TRAVELLING', label: 'EN ROUTE', subtext: 'Travelling to Site' },
  { key: 'ARRIVED', label: 'ARRIVED', subtext: 'Arrived On-Site' },
  { key: 'IN_PROGRESS', altKey: 'WORKING', label: 'IN PROGRESS', subtext: 'Work In Progress' },
  { key: 'COMPLETED', label: 'COMPLETED', subtext: 'Service Finished' },
];

export default function JobManagement() {
  const { user } = useAuth();
  const isDispatcher = user?.role === 'Dispatcher';

  // State
  const [jobs, setJobs] = useState<Job[]>([]);
  const [skills, setSkills] = useState<Skill[]>([]);
  const [total, setTotal] = useState<number>(0);
  const [totalPages, setTotalPages] = useState<number>(1);
  const [page, setPage] = useState<number>(1);
  const [pageSize] = useState<number>(10);

  // Filters
  const [search, setSearch] = useState<string>('');
  const [statusFilter, setStatusFilter] = useState<string>('ALL');
  const [assignmentFilter, setAssignmentFilter] = useState<string>('ALL');
  const [priorityFilter, setPriorityFilter] = useState<string>('ALL');
  const [skillFilter, setSkillFilter] = useState<string>('ALL');
  const [dateFilter, setDateFilter] = useState<string>('');
  const [sortBy] = useState<string>('created_at');
  const [sortOrder] = useState<'asc' | 'desc'>('desc');

  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [notice, setNotice] = useState<{ type: 'success' | 'error'; message: string } | null>(null);

  // Modals & Drawer
  const [isAddModalOpen, setIsAddModalOpen] = useState<boolean>(false);
  const [viewJob, setViewJob] = useState<Job | null>(null);
  const [editJob, setEditJob] = useState<Job | null>(null);
  const [cancelJobTarget, setCancelJobTarget] = useState<Job | null>(null);
  const [cancelReason, setCancelReason] = useState<string>('');

  // Smart Assignment Modal state
  const [assignJobTarget, setAssignJobTarget] = useState<Job | null>(null);
  const [recommendation, setRecommendation] = useState<AssignmentRecommendationResponse | null>(null);
  const [isAssignLoading, setIsAssignLoading] = useState<boolean>(false);
  const [isConfirmingTechId, setIsConfirmingTechId] = useState<string | null>(null);
  const [unassignJobTarget, setUnassignJobTarget] = useState<Job | null>(null);

  // Form states
  const [addForm, setAddForm] = useState<JobCreatePayload>({
    customer_name: '',
    customer_phone: '',
    address: '',
    latitude: 37.7749,
    longitude: -122.4194,
    required_skill_id: '',
    priority: 'MEDIUM',
    scheduled_time: '',
    description: '',
    service_instructions: '',
  });

  const [editForm, setEditForm] = useState<JobUpdatePayload>({
    customer_name: '',
    customer_phone: '',
    address: '',
    latitude: 37.7749,
    longitude: -122.4194,
    required_skill_id: '',
    priority: 'MEDIUM',
    scheduled_time: '',
    description: '',
    service_instructions: '',
  });

  const [formError, setFormError] = useState<FormErrorState | null>(null);
  const [isSubmitting, setIsSubmitting] = useState<boolean>(false);

  const triggerNotice = (type: 'success' | 'error', message: string) => {
    setNotice({ type, message });
    setTimeout(() => setNotice(null), 4000);
  };

  // Fetch active skills for dropdowns
  const loadActiveSkills = useCallback(async () => {
    try {
      const res = await skillService.getSkills({ status: 'ACTIVE', page_size: 100 });
      setSkills(res.items);
      if (res.items.length > 0 && !addForm.required_skill_id) {
        setAddForm((prev) => ({ ...prev, required_skill_id: res.items[0]?.id || '' }));
      }
    } catch (err) {
      console.error('Failed to load active skills', err);
    }
  }, [addForm.required_skill_id]);

  const loadJobs = useCallback(async () => {
    setIsLoading(true);
    try {
      const queryParams: Record<string, any> = {
        sort_by: sortBy,
        sort_order: sortOrder,
        page,
        page_size: pageSize,
      };
      if (search.trim()) queryParams.search = search.trim();
      if (statusFilter !== 'ALL') queryParams.status = statusFilter;
      if (priorityFilter !== 'ALL') queryParams.priority = priorityFilter;
      if (skillFilter !== 'ALL') queryParams.required_skill_id = skillFilter;
      if (dateFilter.trim()) queryParams.scheduled_date = dateFilter.trim();
      if (assignmentFilter !== 'ALL') queryParams.assignment_status = assignmentFilter;

      const data = await jobService.getJobs(queryParams);
      setJobs(data.items);
      setTotal(data.total);
      setTotalPages(data.total_pages);
    } catch (err: any) {
      console.error('Failed to load jobs', err);
      triggerNotice('error', 'Failed to fetch job records from server.');
    } finally {
      setIsLoading(false);
    }
  }, [search, statusFilter, priorityFilter, skillFilter, dateFilter, assignmentFilter, sortBy, sortOrder, page, pageSize]);

  useEffect(() => {
    loadActiveSkills();
  }, [loadActiveSkills]);

  useEffect(() => {
    loadJobs();
  }, [loadJobs]);

  // Operational real-time synchronization for dispatch updates
  useRealtimeSync(
    [
      'JOB_ASSIGNED',
      'JOB_UNASSIGNED',
      'JOB_STATUS_CHANGED',
      'JOB_COMPLETED',
      'JOB_CANCELLED',
      'DISPATCH_PLAN_CHANGED',
      'TECHNICIAN_AVAILABILITY_CHANGED',
    ],
    () => {
      loadJobs();
    },
    loadJobs,
  );

  // Derived Operational Summary Metrics
  const summaryMetrics = useMemo(() => {
    const unassignedCount = jobs.filter((j) => j.status === 'NEW' || !j.assigned_technician).length;
    const activeExecutionCount = jobs.filter((j) =>
      ['TRAVELLING', 'EN_ROUTE', 'ARRIVED', 'WORKING', 'IN_PROGRESS'].includes(j.status)
    ).length;
    const completedCount = jobs.filter((j) => j.status === 'COMPLETED').length;
    const attentionCount = jobs.filter((j) => {
      if (j.status === 'COMPLETED' || j.status === 'CANCELLED') return false;
      if (j.status === 'NEW') return true;
      if (j.scheduled_time && new Date(j.scheduled_time).getTime() < Date.now()) return true;
      return false;
    }).length;

    return {
      total,
      unassigned: unassignedCount,
      activeExecution: activeExecutionCount,
      attention: attentionCount,
      completed: completedCount,
    };
  }, [jobs, total]);

  // Open Smart Technician Assignment modal (Module 8 integration)
  const openSmartAssignmentModal = async (job: Job) => {
    setAssignJobTarget(job);
    setRecommendation(null);
    setIsAssignLoading(true);
    setFormError(null);
    try {
      const data = await assignmentService.getRecommendation(job.id);
      setRecommendation(data);
    } catch (err: any) {
      console.error('Failed to load assignment recommendation', err);
      setFormError(parseApiError(err, 'Failed to calculate assignment recommendations.'));
    } finally {
      setIsAssignLoading(false);
    }
  };

  // Confirm Dispatcher assignment selection
  const handleConfirmAssignment = async (technicianId: string) => {
    if (!assignJobTarget) return;
    setIsConfirmingTechId(technicianId);
    setFormError(null);
    try {
      await assignmentService.confirmAssignment(assignJobTarget.id, technicianId);
      triggerNotice('success', 'Technician assigned successfully.');
      setAssignJobTarget(null);
      setRecommendation(null);
      loadJobs();
    } catch (err: any) {
      console.error('Assignment confirmation error', err);
      setFormError(
        parseApiError(err, 'Technician is no longer available. Please refresh recommendations.')
      );
    } finally {
      setIsConfirmingTechId(null);
    }
  };

  // Submit unassign job
  const handleUnassignSubmit = async () => {
    if (!unassignJobTarget) return;
    setFormError(null);
    try {
      await assignmentService.unassignJob(unassignJobTarget.id);
      triggerNotice('success', `Job ${unassignJobTarget.job_number} unassigned successfully.`);
      setUnassignJobTarget(null);
      loadJobs();
    } catch (err: any) {
      console.error('Unassign job error', err);
      const msg =
        err?.response?.data?.error?.message ||
        err?.response?.data?.detail ||
        'Failed to unassign technician.';
      triggerNotice('error', msg);
    }
  };

  // Form Handlers
  const handleAddSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (isSubmitting) return;
    setFormError(null);

    // Client-side validation using existing form state architecture
    const cleanCustomerName = addForm.customer_name.trim();
    if (!cleanCustomerName || cleanCustomerName.length < 2) {
      setFormError({
        title: 'Unable to create job',
        messages: ['Customer name must have at least 2 characters.'],
      });
      return;
    }

    const cleanAddress = addForm.address.trim();
    if (!cleanAddress || cleanAddress.length < 2) {
      setFormError({
        title: 'Unable to create job',
        messages: ['Address must have at least 2 characters.'],
      });
      return;
    }

    const lat = Number(addForm.latitude);
    if (isNaN(lat) || lat < -90 || lat > 90) {
      setFormError({
        title: 'Unable to create job',
        messages: ['Latitude must be between -90 and 90.'],
      });
      return;
    }

    const lng = Number(addForm.longitude);
    if (isNaN(lng) || lng < -180 || lng > 180) {
      setFormError({
        title: 'Unable to create job',
        messages: ['Longitude must be between -180 and 180.'],
      });
      return;
    }

    if (!addForm.required_skill_id || !addForm.required_skill_id.trim()) {
      setFormError({
        title: 'Unable to create job',
        messages: ['Required skill is required.'],
      });
      return;
    }

    let formattedScheduledTime: string | undefined = undefined;
    if (addForm.scheduled_time && addForm.scheduled_time.trim()) {
      const parsedDate = new Date(addForm.scheduled_time);
      if (isNaN(parsedDate.getTime())) {
        setFormError({
          title: 'Unable to create job',
          messages: ['Scheduled time must be a valid date and time.'],
        });
        return;
      }
      formattedScheduledTime = parsedDate.toISOString();
    }

    const rawInstructions = (addForm.service_instructions?.trim() || addForm.description?.trim()) || undefined;

    const payload: JobCreatePayload = {
      customer_name: cleanCustomerName,
      customer_phone: addForm.customer_phone?.trim() || undefined,
      address: cleanAddress,
      latitude: lat,
      longitude: lng,
      required_skill_id: addForm.required_skill_id.trim(),
      priority: addForm.priority || 'MEDIUM',
      scheduled_time: formattedScheduledTime,
      description: rawInstructions,
      service_instructions: rawInstructions,
    };

    setIsSubmitting(true);
    try {
      const created = await jobService.createJob(payload);
      triggerNotice('success', `Job ${created.job_number} created successfully.`);
      setIsAddModalOpen(false);
      setAddForm({
        customer_name: '',
        customer_phone: '',
        address: '',
        latitude: 37.7749,
        longitude: -122.4194,
        required_skill_id: skills.length > 0 ? skills[0]?.id || '' : '',
        priority: 'MEDIUM',
        scheduled_time: '',
        description: '',
        service_instructions: '',
      });
      loadJobs();
    } catch (err: any) {
      setFormError(parseApiError(err, 'Unable to create job'));
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleEditSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!editJob || isSubmitting) return;
    setFormError(null);

    const cleanCustomerName = editForm.customer_name?.trim();
    if (!cleanCustomerName || cleanCustomerName.length < 2) {
      setFormError({
        title: 'Unable to update job',
        messages: ['Customer name must have at least 2 characters.'],
      });
      return;
    }

    const cleanAddress = editForm.address?.trim();
    if (!cleanAddress || cleanAddress.length < 5) {
      setFormError({
        title: 'Unable to update job',
        messages: ['Address must have at least 5 characters.'],
      });
      return;
    }

    const lat = editForm.latitude !== undefined ? Number(editForm.latitude) : undefined;
    if (lat !== undefined && (isNaN(lat) || lat < -90 || lat > 90)) {
      setFormError({
        title: 'Unable to update job',
        messages: ['Latitude must be between -90 and 90.'],
      });
      return;
    }

    const lng = editForm.longitude !== undefined ? Number(editForm.longitude) : undefined;
    if (lng !== undefined && (isNaN(lng) || lng < -180 || lng > 180)) {
      setFormError({
        title: 'Unable to update job',
        messages: ['Longitude must be between -180 and 180.'],
      });
      return;
    }

    if (!editForm.required_skill_id || !editForm.required_skill_id.trim()) {
      setFormError({
        title: 'Unable to update job',
        messages: ['Required skill is required.'],
      });
      return;
    }

    let formattedScheduledTime: string | undefined = undefined;
    if (editForm.scheduled_time && editForm.scheduled_time.trim()) {
      const parsedDate = new Date(editForm.scheduled_time);
      if (isNaN(parsedDate.getTime())) {
        setFormError({
          title: 'Unable to update job',
          messages: ['Scheduled time must be a valid date and time.'],
        });
        return;
      }
      formattedScheduledTime = parsedDate.toISOString();
    }

    const rawInstructions = (editForm.service_instructions?.trim() || editForm.description?.trim()) || undefined;

    const payload: JobUpdatePayload = {
      customer_name: cleanCustomerName,
      customer_phone: editForm.customer_phone?.trim() || undefined,
      address: cleanAddress,
      latitude: lat,
      longitude: lng,
      required_skill_id: editForm.required_skill_id.trim(),
      priority: editForm.priority,
      scheduled_time: formattedScheduledTime,
      description: rawInstructions,
      service_instructions: rawInstructions,
    };

    setIsSubmitting(true);
    try {
      await jobService.updateJob(editJob.id, payload);
      triggerNotice('success', `Job ${editJob.job_number} updated successfully.`);
      setEditJob(null);
      loadJobs();
    } catch (err: any) {
      setFormError(parseApiError(err, 'Unable to update job'));
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleCancelSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!cancelJobTarget || isSubmitting) return;
    if (!cancelReason.trim()) {
      setFormError({
        title: 'Validation Error',
        messages: ['A non-empty cancellation reason is required.'],
      });
      return;
    }
    setFormError(null);
    setIsSubmitting(true);
    try {
      await jobService.cancelJob(cancelJobTarget.id, cancelReason.trim());
      triggerNotice('success', `Job ${cancelJobTarget.job_number} cancelled.`);
      setCancelJobTarget(null);
      setCancelReason('');
      loadJobs();
    } catch (err: any) {
      setFormError(parseApiError(err, 'Failed to cancel job'));
    } finally {
      setIsSubmitting(false);
    }
  };

  const openEditModal = (job: Job) => {
    if (job.status === 'COMPLETED' || job.status === 'CANCELLED') {
      triggerNotice('error', `Cannot edit a ${job.status.toLowerCase()} job order.`);
      return;
    }
    setEditJob(job);
    setEditForm({
      customer_name: job.customer_name,
      customer_phone: job.customer_phone || '',
      address: job.address,
      latitude: job.latitude ?? 37.7749,
      longitude: job.longitude ?? -122.4194,
      required_skill_id: job.required_skill_id || '',
      priority: job.priority,
      scheduled_time: job.scheduled_time ? job.scheduled_time.substring(0, 16) : '',
      description: job.description || job.service_instructions || '',
      service_instructions: job.service_instructions || job.description || '',
    });
    setFormError(null);
  };

  const getPriorityColor = (p: Priority) => {
    switch (p) {
      case 'CRITICAL':
        return 'bg-rose-50 border-rose-200 text-rose-700';
      case 'HIGH':
        return 'bg-amber-50 border-amber-200 text-amber-700';
      case 'MEDIUM':
        return 'bg-blue-50 border-blue-200 text-blue-700';
      case 'LOW':
      default:
        return 'bg-slate-100 border-slate-200 text-slate-700';
    }
  };

  const getStatusColor = (st: string) => {
    switch (st) {
      case 'NEW':
        return 'bg-purple-50 border-purple-200 text-purple-700';
      case 'ASSIGNED':
        return 'bg-blue-50 border-blue-200 text-blue-700';
      case 'EN_ROUTE':
      case 'TRAVELLING':
        return 'bg-sky-50 border-sky-200 text-sky-700';
      case 'ARRIVED':
        return 'bg-amber-50 border-amber-200 text-amber-700';
      case 'IN_PROGRESS':
      case 'WORKING':
        return 'bg-indigo-50 border-indigo-200 text-indigo-700';
      case 'COMPLETED':
        return 'bg-emerald-50 border-emerald-200 text-emerald-700';
      case 'CANCELLED':
        return 'bg-rose-50 border-rose-200 text-rose-700';
      default:
        return 'bg-slate-100 border-slate-200 text-slate-700';
    }
  };

  const getStatusDisplayLabel = (st: string) => {
    switch (st) {
      case 'TRAVELLING':
        return 'EN ROUTE';
      case 'WORKING':
        return 'IN PROGRESS';
      default:
        return st;
    }
  };

  const getActiveStageIndex = (st: string) => {
    switch (st) {
      case 'NEW':
        return 0;
      case 'ASSIGNED':
        return 1;
      case 'TRAVELLING':
      case 'EN_ROUTE':
        return 2;
      case 'ARRIVED':
        return 3;
      case 'WORKING':
      case 'IN_PROGRESS':
        return 4;
      case 'COMPLETED':
        return 5;
      default:
        return -1;
    }
  };

  return (
    <div className="flex flex-col gap-6 py-2 animate-fade-in select-none">
      {/* ── Header ── */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-slate-200 pb-5">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <span className="inline-flex items-center gap-1.5 rounded-full border border-blue-200 bg-blue-50 px-2.5 py-0.5 text-[11px] font-semibold text-blue-700">
              <Briefcase className="h-3.5 w-3.5" />
              <span>Operations Dispatch Control</span>
            </span>
            <span className="inline-flex items-center gap-1 rounded-full border border-slate-200 bg-slate-100 px-2.5 py-0.5 text-[11px] font-medium text-slate-700">
              <Shield className="h-3 w-3 text-purple-600" />
              <span>{user?.role || 'User'}</span>
            </span>
            <RealtimeConnectionBadge />
          </div>

          <h1 className="text-2xl md:text-3xl font-extrabold tracking-tight text-slate-900">
            Jobs & Service Operations
          </h1>
          <p className="text-xs md:text-sm text-slate-500 mt-0.5">
            Operational control point for job lifecycle tracking, unassigned dispatching, and technician assignments.
          </p>
        </div>

        {/* Primary Action Button (Dispatcher Only) */}
        {isDispatcher && (
          <button
            onClick={() => {
              setFormError(null);
              setIsAddModalOpen(true);
            }}
            className="flex items-center gap-2 rounded-xl bg-blue-600 px-4 py-2.5 text-xs font-semibold text-white shadow-xs transition-all hover:bg-blue-700 active:scale-[0.98] self-start md:self-auto cursor-pointer"
          >
            <Plus className="h-4 w-4" />
            <span>Create New Job</span>
          </button>
        )}
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

      {/* ── Operational Attention & KPI Summary Cards ── */}
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-3">
        {/* Card 1: Total Jobs */}
        <div
          onClick={() => {
            setStatusFilter('ALL');
            setAssignmentFilter('ALL');
            setPage(1);
          }}
          className="cursor-pointer rounded-xl border border-slate-200 bg-white p-3.5 shadow-xs transition-all hover:border-slate-300 hover:shadow-md"
        >
          <div className="flex items-center justify-between text-slate-500 text-xs font-semibold">
            <span>Total Operations</span>
            <Layers className="h-4 w-4 text-slate-400" />
          </div>
          <div className="mt-2 text-2xl font-black text-slate-900 font-mono">
            {summaryMetrics.total}
          </div>
          <div className="mt-1 text-[11px] text-slate-500">All registered job orders</div>
        </div>

        {/* Card 2: Unassigned Jobs (Attention Alert) */}
        <div
          onClick={() => {
            setAssignmentFilter('UNASSIGNED');
            setPage(1);
          }}
          className={cn(
            'cursor-pointer rounded-xl border p-3.5 shadow-xs transition-all hover:shadow-md',
            summaryMetrics.unassigned > 0
              ? 'border-amber-200 bg-amber-50/60'
              : 'border-slate-200 bg-white'
          )}
        >
          <div className="flex items-center justify-between text-amber-700 text-xs font-semibold">
            <span>Awaiting Assignment</span>
            <UserX className="h-4 w-4 text-amber-600" />
          </div>
          <div className="mt-2 text-2xl font-black text-amber-700 font-mono">
            {summaryMetrics.unassigned}
          </div>
          <div className="mt-1 text-[11px] text-slate-500">Unassigned new jobs</div>
        </div>

        {/* Card 3: Active Field Execution */}
        <div
          onClick={() => {
            setStatusFilter('ALL');
            setAssignmentFilter('ASSIGNED');
            setPage(1);
          }}
          className="cursor-pointer rounded-xl border border-blue-200 bg-blue-50/50 p-3.5 shadow-xs transition-all hover:shadow-md"
        >
          <div className="flex items-center justify-between text-blue-700 text-xs font-semibold">
            <span>Active Execution</span>
            <Activity className="h-4 w-4 text-blue-600" />
          </div>
          <div className="mt-2 text-2xl font-black text-blue-700 font-mono">
            {summaryMetrics.activeExecution}
          </div>
          <div className="mt-1 text-[11px] text-slate-500">En route / Arrived / Working</div>
        </div>

        {/* Card 4: Operational Attention */}
        <div
          onClick={() => {
            setStatusFilter('NEW');
            setPage(1);
          }}
          className={cn(
            'cursor-pointer rounded-xl border p-3.5 shadow-xs transition-all hover:shadow-md',
            summaryMetrics.attention > 0
              ? 'border-purple-200 bg-purple-50/60'
              : 'border-slate-200 bg-white'
          )}
        >
          <div className="flex items-center justify-between text-purple-700 text-xs font-semibold">
            <span>Requires Attention</span>
            <ShieldAlert className="h-4 w-4 text-purple-600" />
          </div>
          <div className="mt-2 text-2xl font-black text-purple-700 font-mono">
            {summaryMetrics.attention}
          </div>
          <div className="mt-1 text-[11px] text-slate-500">Unassigned or overdue jobs</div>
        </div>

        {/* Card 5: Completed Operations */}
        <div
          onClick={() => {
            setStatusFilter('COMPLETED');
            setPage(1);
          }}
          className="cursor-pointer rounded-xl border border-emerald-200 bg-emerald-50/50 p-3.5 shadow-xs transition-all hover:shadow-md col-span-2 sm:col-span-1"
        >
          <div className="flex items-center justify-between text-emerald-700 text-xs font-semibold">
            <span>Completed Jobs</span>
            <CheckCircle2 className="h-4 w-4 text-emerald-600" />
          </div>
          <div className="mt-2 text-2xl font-black text-emerald-700 font-mono">
            {summaryMetrics.completed}
          </div>
          <div className="mt-1 text-[11px] text-slate-500">Successfully resolved</div>
        </div>
      </div>

      {/* ── Toolbar: Search & Operational Filters ── */}
      <div className="flex flex-col lg:flex-row items-stretch lg:items-center justify-between gap-3 bg-white border border-slate-200 p-3.5 rounded-xl shadow-xs">
        <div className="flex flex-1 flex-col sm:flex-row flex-wrap items-center gap-3">
          {/* Search Box */}
          <div className="relative w-full sm:w-64">
            <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400 pointer-events-none" />
            <input
              type="search"
              placeholder="Search job #, customer, address..."
              value={search}
              onChange={(e) => {
                setSearch(e.target.value);
                setPage(1);
              }}
              className="w-full rounded-lg border border-slate-200 bg-slate-50 py-2 pl-9 pr-3 text-xs text-slate-800 placeholder:text-slate-400 focus:border-blue-500 focus:bg-white focus:outline-none"
            />
          </div>

          {/* Execution Status Filter */}
          <div className="flex items-center gap-1.5 w-full sm:w-auto">
            <Filter className="h-3.5 w-3.5 text-slate-400 shrink-0" />
            <select
              value={statusFilter}
              onChange={(e) => {
                setStatusFilter(e.target.value);
                setPage(1);
              }}
              className="w-full sm:w-40 rounded-lg border border-slate-200 bg-slate-50 py-2 px-3 text-xs text-slate-800 focus:border-blue-500 focus:bg-white focus:outline-none cursor-pointer"
            >
              <option value="ALL">All Statuses</option>
              <option value="NEW">NEW (Created)</option>
              <option value="ASSIGNED">ASSIGNED (Assigned)</option>
              <option value="TRAVELLING">EN ROUTE (Travelling)</option>
              <option value="ARRIVED">ARRIVED (On Site)</option>
              <option value="WORKING">IN PROGRESS (Working)</option>
              <option value="COMPLETED">COMPLETED (Finished)</option>
              <option value="CANCELLED">CANCELLED (Cancelled)</option>
            </select>
          </div>

          {/* Assignment State Filter */}
          <div className="w-full sm:w-auto">
            <select
              value={assignmentFilter}
              onChange={(e) => {
                setAssignmentFilter(e.target.value);
                setPage(1);
              }}
              className="w-full sm:w-36 rounded-lg border border-slate-200 bg-slate-50 py-2 px-3 text-xs text-slate-800 focus:border-blue-500 focus:bg-white focus:outline-none cursor-pointer"
            >
              <option value="ALL">All Assignments</option>
              <option value="ASSIGNED">Assigned Jobs</option>
              <option value="UNASSIGNED">Unassigned Jobs</option>
            </select>
          </div>

          {/* Priority Filter */}
          <div className="w-full sm:w-auto">
            <select
              value={priorityFilter}
              onChange={(e) => {
                setPriorityFilter(e.target.value);
                setPage(1);
              }}
              className="w-full sm:w-32 rounded-lg border border-slate-200 bg-slate-50 py-2 px-3 text-xs text-slate-800 focus:border-blue-500 focus:bg-white focus:outline-none cursor-pointer"
            >
              <option value="ALL">All Priorities</option>
              {PRIORITIES.map((p) => (
                <option key={p} value={p}>
                  {p}
                </option>
              ))}
            </select>
          </div>

          {/* Required Skill Filter */}
          <div className="w-full sm:w-auto">
            <select
              value={skillFilter}
              onChange={(e) => {
                setSkillFilter(e.target.value);
                setPage(1);
              }}
              className="w-full sm:w-40 rounded-lg border border-slate-200 bg-slate-50 py-2 px-3 text-xs text-slate-800 focus:border-blue-500 focus:bg-white focus:outline-none cursor-pointer"
            >
              <option value="ALL">All Skills</option>
              {skills.map((s) => (
                <option key={s.id} value={s.id}>
                  {s.skill_name}
                </option>
              ))}
            </select>
          </div>

          {/* Date Filter */}
          <div className="w-full sm:w-auto">
            <input
              type="date"
              value={dateFilter}
              onChange={(e) => {
                setDateFilter(e.target.value);
                setPage(1);
              }}
              className="w-full sm:w-36 rounded-lg border border-slate-200 bg-slate-50 py-2 px-3 text-xs text-slate-800 focus:border-blue-500 focus:bg-white focus:outline-none"
            />
          </div>
        </div>

        {/* Refresh Button */}
        <button
          onClick={loadJobs}
          title="Refresh Data"
          className="flex items-center justify-center gap-1.5 rounded-lg border border-slate-200 bg-white px-3 py-2 text-xs font-medium text-slate-700 hover:bg-slate-50 active:scale-95 transition-all cursor-pointer"
        >
          <RotateCw className={cn('h-3.5 w-3.5 text-slate-500', isLoading && 'animate-spin')} />
          <span className="hidden sm:inline">Refresh</span>
        </button>
      </div>

      {/* ── Jobs Data Table (Desktop View) ── */}
      <div className="overflow-hidden rounded-xl border border-slate-200 bg-white shadow-xs hidden lg:block">
        <div className="overflow-x-auto scrollbar-thin">
          <table className="w-full text-left text-xs">
            <thead className="border-b border-slate-200 bg-slate-50 text-[11px] font-bold uppercase tracking-wider text-slate-500">
              <tr>
                <th className="py-3.5 px-4">Job ID</th>
                <th className="py-3.5 px-4">Customer</th>
                <th className="py-3.5 px-4">Location</th>
                <th className="py-3.5 px-4">Priority</th>
                <th className="py-3.5 px-4">Required Skill</th>
                <th className="py-3.5 px-4">Technician</th>
                <th className="py-3.5 px-4">Status</th>
                <th className="py-3.5 px-4">Scheduled Time</th>
                <th className="py-3.5 px-4 text-right">Actions</th>
              </tr>
            </thead>

            <tbody className="divide-y divide-slate-100 text-slate-800">
              {isLoading ? (
                <tr>
                  <td colSpan={9} className="py-12 text-center text-slate-500 text-xs">
                    <div className="flex flex-col items-center justify-center gap-2">
                      <RotateCw className="h-6 w-6 text-blue-600 animate-spin" />
                      <span>Loading service operations jobs...</span>
                    </div>
                  </td>
                </tr>
              ) : jobs.length === 0 ? (
                <tr>
                  <td colSpan={9} className="py-12 text-center text-slate-500 text-xs">
                    <div className="flex flex-col items-center justify-center gap-2">
                      <Briefcase className="h-8 w-8 text-slate-400" />
                      <span className="font-semibold text-slate-700">No jobs found</span>
                      <span className="text-[11px] text-slate-400">
                        Try clearing search terms or status filters.
                      </span>
                    </div>
                  </td>
                </tr>
              ) : (
                jobs.map((job) => (
                  <tr key={job.id} className="hover:bg-slate-50 transition-colors">
                    {/* Job ID */}
                    <td className="py-3.5 px-4 font-mono font-bold text-blue-700">
                      {job.job_number}
                    </td>

                    {/* Customer */}
                    <td className="py-3.5 px-4">
                      <div className="font-bold text-slate-900">{job.customer_name}</div>
                      <div className="text-[11px] text-slate-500 flex items-center gap-1">
                        <Phone className="h-3 w-3 text-slate-400" />
                        <span>{job.customer_phone || 'N/A'}</span>
                      </div>
                    </td>

                    {/* Location */}
                    <td className="py-3.5 px-4 max-w-xs truncate text-slate-700">
                      <div className="flex items-center gap-1.5">
                        <MapPin className="h-3.5 w-3.5 text-blue-600 shrink-0" />
                        <span className="truncate">{job.address}</span>
                      </div>
                    </td>

                    {/* Priority */}
                    <td className="py-3.5 px-4">
                      <span
                        className={cn(
                          'inline-flex items-center rounded-md px-2 py-0.5 text-[10px] font-extrabold border',
                          getPriorityColor(job.priority)
                        )}
                      >
                        {job.priority}
                      </span>
                    </td>

                    {/* Required Skill */}
                    <td className="py-3.5 px-4">
                      {job.required_skill ? (
                        <span className="inline-flex items-center gap-1 rounded-md bg-purple-50 px-2 py-0.5 text-[11px] font-semibold text-purple-700 border border-purple-200">
                          <Wrench className="h-3 w-3 text-purple-600" />
                          <span>{job.required_skill.skill_name}</span>
                        </span>
                      ) : (
                        <span className="text-slate-400">—</span>
                      )}
                    </td>

                    {/* Technician */}
                    <td className="py-3.5 px-4">
                      {job.assigned_technician ? (
                        <div className="flex items-center gap-1.5 text-emerald-700 font-semibold">
                          <UserCheck className="h-3.5 w-3.5 shrink-0 text-emerald-600" />
                          <div>
                            <div>{job.assigned_technician.full_name}</div>
                            <div className="text-[10px] text-slate-500 font-mono font-normal">
                              {job.assigned_technician.employee_code}
                            </div>
                          </div>
                        </div>
                      ) : (
                        <span className="inline-flex items-center gap-1 rounded-full bg-amber-50 border border-amber-200 px-2 py-0.5 text-[10px] font-bold text-amber-700">
                          <UserX className="h-3 w-3 text-amber-600" />
                          <span>Unassigned</span>
                        </span>
                      )}
                    </td>

                    {/* Execution Status */}
                    <td className="py-3.5 px-4">
                      <span
                        className={cn(
                          'inline-flex items-center gap-1 rounded-full px-2.5 py-0.5 text-[10px] font-bold border',
                          getStatusColor(job.status)
                        )}
                      >
                        <span>●</span>
                        <span>{getStatusDisplayLabel(job.status)}</span>
                      </span>
                    </td>

                    {/* Scheduled Time */}
                    <td className="py-3.5 px-4 font-mono text-[11px] text-slate-600">
                      {job.scheduled_time ? formatDate(job.scheduled_time) : 'Immediate'}
                    </td>

                    {/* Actions */}
                    <td className="py-3.5 px-4 text-right">
                      <div className="flex items-center justify-end gap-1.5">
                        {/* View Details Drawer */}
                        <button
                          onClick={() => setViewJob(job)}
                          title="View Job Details & Visual Lifecycle"
                          className="flex items-center gap-1 rounded-lg border border-slate-200 bg-white px-2.5 py-1 text-[11px] font-medium text-slate-700 hover:border-blue-500 hover:text-blue-700 transition-colors cursor-pointer"
                        >
                          <Eye className="h-3.5 w-3.5" />
                          <span>View</span>
                        </button>

                        {/* Dispatcher Actions */}
                        {isDispatcher && (
                          <>
                            {/* Smart Assign Button for NEW jobs */}
                            {job.status === 'NEW' && (
                              <button
                                onClick={() => openSmartAssignmentModal(job)}
                                title="Smart Technician Assignment"
                                className="flex items-center gap-1 rounded-lg bg-blue-50 border border-blue-200 px-2.5 py-1 text-[11px] font-bold text-blue-700 hover:bg-blue-600 hover:text-white transition-all shadow-xs active:scale-95 cursor-pointer"
                              >
                                <Sparkles className="h-3.5 w-3.5 text-amber-600" />
                                <span>Assign</span>
                              </button>
                            )}

                            {/* Unassign Button for ASSIGNED jobs */}
                            {job.status === 'ASSIGNED' && (
                              <button
                                onClick={() => setUnassignJobTarget(job)}
                                title="Unassign Technician"
                                className="flex items-center gap-1 rounded-lg bg-amber-50 border border-amber-200 px-2 py-1 text-[11px] font-semibold text-amber-700 hover:bg-amber-100 transition-all cursor-pointer"
                              >
                                <UserX className="h-3.5 w-3.5" />
                                <span>Unassign</span>
                              </button>
                            )}

                            {job.status !== 'CANCELLED' && job.status !== 'COMPLETED' && (
                              <>
                                <button
                                  onClick={() => openEditModal(job)}
                                  title="Edit Job Details"
                                  className="rounded-lg p-1.5 text-slate-400 hover:bg-blue-50 hover:text-blue-700 transition-colors cursor-pointer"
                                >
                                  <Edit className="h-3.5 w-3.5" />
                                </button>

                                <button
                                  onClick={() => {
                                    setCancelJobTarget(job);
                                    setCancelReason('');
                                    setFormError(null);
                                  }}
                                  title="Cancel Job"
                                  className="rounded-lg p-1.5 text-slate-400 hover:bg-rose-50 hover:text-rose-700 transition-colors cursor-pointer"
                                >
                                  <Power className="h-3.5 w-3.5" />
                                </button>
                              </>
                            )}
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
        <div className="flex flex-col sm:flex-row items-center justify-between gap-3 border-t border-slate-200 bg-slate-50 px-4 py-3 text-xs text-slate-500">
          <div>
            Showing <span className="font-bold text-slate-800">{jobs.length}</span> of{' '}
            <span className="font-bold text-slate-800">{total}</span> service jobs
          </div>

          <div className="flex items-center gap-2">
            <button
              disabled={page <= 1}
              onClick={() => setPage((p) => Math.max(p - 1, 1))}
              className="flex items-center gap-1 rounded-lg border border-slate-200 bg-white px-2.5 py-1 text-xs text-slate-700 hover:bg-slate-50 disabled:opacity-50 disabled:pointer-events-none transition-all cursor-pointer"
            >
              <ChevronLeft className="h-3.5 w-3.5" />
              <span>Prev</span>
            </button>
            <span className="px-2 text-slate-500 font-mono text-[11px]">
              Page {page} of {totalPages}
            </span>
            <button
              disabled={page >= totalPages}
              onClick={() => setPage((p) => Math.min(p + 1, totalPages))}
              className="flex items-center gap-1 rounded-lg border border-slate-200 bg-white px-2.5 py-1 text-xs text-slate-700 hover:bg-slate-50 disabled:opacity-50 disabled:pointer-events-none transition-all cursor-pointer"
            >
              <span>Next</span>
              <ChevronRight className="h-3.5 w-3.5" />
            </button>
          </div>
        </div>
      </div>

      {/* ── Mobile & Tablet Responsive List Cards (Mobile View) ── */}
      <div className="block lg:hidden space-y-3">
        {isLoading ? (
          <div className="py-12 text-center text-slate-500 text-xs flex flex-col items-center gap-2">
            <RotateCw className="h-6 w-6 text-blue-600 animate-spin" />
            <span>Loading service operations jobs...</span>
          </div>
        ) : jobs.length === 0 ? (
          <div className="py-12 text-center text-slate-500 text-xs bg-white rounded-xl border border-slate-200 p-6 shadow-xs">
            <Briefcase className="h-8 w-8 text-slate-400 mx-auto mb-2" />
            <div className="font-semibold text-slate-700">No jobs found</div>
          </div>
        ) : (
          jobs.map((job) => (
            <div
              key={job.id}
              className="rounded-xl border border-slate-200 bg-white p-4 space-y-3 shadow-xs"
            >
              <div className="flex items-center justify-between">
                <div className="font-mono font-bold text-blue-700 text-xs">{job.job_number}</div>
                <div className="flex items-center gap-1.5">
                  <span
                    className={cn(
                      'inline-flex items-center rounded-md px-2 py-0.5 text-[10px] font-extrabold border',
                      getPriorityColor(job.priority)
                    )}
                  >
                    {job.priority}
                  </span>
                  <span
                    className={cn(
                      'inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[10px] font-bold border',
                      getStatusColor(job.status)
                    )}
                  >
                    <span>{getStatusDisplayLabel(job.status)}</span>
                  </span>
                </div>
              </div>

              <div>
                <div className="font-bold text-slate-900 text-sm">{job.customer_name}</div>
                <div className="text-xs text-slate-600 flex items-center gap-1 mt-0.5">
                  <MapPin className="h-3.5 w-3.5 text-blue-600 shrink-0" />
                  <span className="truncate">{job.address}</span>
                </div>
              </div>

              <div className="grid grid-cols-2 gap-2 text-xs border-t border-b border-slate-100 py-2">
                <div>
                  <span className="text-[10px] text-slate-400 uppercase font-semibold">
                    Skill Requirement
                  </span>
                  <div className="font-medium text-purple-700">
                    {job.required_skill ? job.required_skill.skill_name : 'N/A'}
                  </div>
                </div>

                <div>
                  <span className="text-[10px] text-slate-400 uppercase font-semibold">
                    Assigned Tech
                  </span>
                  <div className="font-medium">
                    {job.assigned_technician ? (
                      <span className="text-emerald-700 font-semibold">
                        {job.assigned_technician.full_name}
                      </span>
                    ) : (
                      <span className="text-amber-700 font-semibold">Unassigned</span>
                    )}
                  </div>
                </div>
              </div>

              <div className="flex items-center justify-between pt-1">
                <span className="text-[11px] font-mono text-slate-500">
                  {job.scheduled_time ? formatDate(job.scheduled_time) : 'Immediate'}
                </span>

                <div className="flex items-center gap-1.5">
                  <button
                    onClick={() => setViewJob(job)}
                    className="rounded-lg border border-slate-200 bg-white px-2.5 py-1 text-xs font-medium text-slate-700 hover:bg-slate-50 cursor-pointer"
                  >
                    Details
                  </button>

                  {isDispatcher && job.status === 'NEW' && (
                    <button
                      onClick={() => openSmartAssignmentModal(job)}
                      className="rounded-lg bg-blue-600 px-2.5 py-1 text-xs font-bold text-white shadow-xs cursor-pointer"
                    >
                      Assign
                    </button>
                  )}

                  {isDispatcher && job.status === 'ASSIGNED' && (
                    <button
                      onClick={() => setUnassignJobTarget(job)}
                      className="rounded-lg bg-amber-50 text-amber-700 border border-amber-200 px-2 py-1 text-xs font-semibold cursor-pointer"
                    >
                      Unassign
                    </button>
                  )}
                </div>
              </div>
            </div>
          ))
        )}
      </div>

      {/* ── Modal / Drawer: View Job Details & Visual Lifecycle ── */}
      {viewJob && (
        <div className="fixed inset-0 z-50 flex items-center justify-end bg-slate-900/40 backdrop-blur-sm p-0 md:p-4 animate-fade-in">
          <div className="w-full max-w-2xl h-full md:h-auto md:max-h-[90vh] rounded-none md:rounded-2xl border-l md:border border-slate-200 bg-white p-6 shadow-xl space-y-5 overflow-y-auto">
            {/* Drawer Header */}
            <div className="flex items-center justify-between border-b border-slate-100 pb-4">
              <div>
                <div className="flex items-center gap-2">
                  <span className="font-mono text-base font-extrabold text-blue-700">
                    {viewJob.job_number}
                  </span>
                  <span
                    className={cn(
                      'inline-flex items-center gap-1 rounded-full px-2.5 py-0.5 text-[10px] font-bold border',
                      getStatusColor(viewJob.status)
                    )}
                  >
                    <span>●</span>
                    <span>{getStatusDisplayLabel(viewJob.status)}</span>
                  </span>
                  <span
                    className={cn(
                      'inline-flex items-center rounded-md px-2 py-0.5 text-[10px] font-extrabold border',
                      getPriorityColor(viewJob.priority)
                    )}
                  >
                    {viewJob.priority}
                  </span>
                </div>
                <h2 className="text-xl font-black text-slate-900 mt-1">
                  {viewJob.customer_name}
                </h2>
              </div>
              <button
                onClick={() => setViewJob(null)}
                className="text-slate-400 hover:text-slate-700 transition-colors p-1 cursor-pointer"
              >
                <X className="h-6 w-6" />
              </button>
            </div>

            {/* ── Lifecycle Visualization Stepper (Non-Clickable) ── */}
            <div className="rounded-xl border border-slate-200 bg-slate-50 p-4 space-y-3">
              <div className="flex items-center justify-between text-xs border-b border-slate-200 pb-2">
                <span className="font-bold text-slate-800 flex items-center gap-1.5">
                  <Activity className="h-4 w-4 text-blue-600" />
                  <span>Job Execution Lifecycle Tracker</span>
                </span>
                <span className="text-[11px] font-mono text-slate-500">
                  Backend Status: {viewJob.status}
                </span>
              </div>

              {viewJob.status === 'CANCELLED' ? (
                <div className="p-3 rounded-lg bg-rose-50 border border-rose-200 text-rose-800 text-xs">
                  <div className="font-bold flex items-center gap-1.5 mb-1">
                    <AlertTriangle className="h-4 w-4 shrink-0 text-rose-600" />
                    <span>Job Order Cancelled</span>
                  </div>
                  <div className="text-[11px] text-slate-600">
                    This job order was cancelled and cannot be progressed.
                  </div>
                </div>
              ) : (
                <div className="pt-2 pb-1">
                  <div className="grid grid-cols-6 gap-1 relative">
                    {LIFECYCLE_STAGES.map((stage, idx) => {
                      const activeIdx = getActiveStageIndex(viewJob.status);
                      const isCompleted = idx < activeIdx;
                      const isCurrent = idx === activeIdx;

                      return (
                        <div
                          key={stage.key}
                          className="flex flex-col items-center text-center space-y-1.5"
                        >
                          {/* Stage Dot/Badge */}
                          <div
                            className={cn(
                              'h-7 w-7 rounded-full flex items-center justify-center text-xs font-bold transition-all relative',
                              isCompleted
                                ? 'bg-emerald-100 border-2 border-emerald-500 text-emerald-700'
                                : isCurrent
                                ? 'bg-blue-600 border-2 border-blue-400 text-white shadow-md ring-4 ring-blue-100'
                                : 'bg-slate-100 border border-slate-300 text-slate-400'
                            )}
                          >
                            {isCompleted ? (
                              <Check className="h-3.5 w-3.5" />
                            ) : (
                              <span>{idx + 1}</span>
                            )}
                            {isCurrent && (
                              <span className="absolute -top-1 -right-1 flex h-2.5 w-2.5">
                                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-blue-400 opacity-75"></span>
                                <span className="relative inline-flex rounded-full h-2.5 w-2.5 bg-blue-600"></span>
                              </span>
                            )}
                          </div>

                          {/* Stage Title */}
                          <div
                            className={cn(
                              'text-[10px] font-extrabold uppercase tracking-tight',
                              isCompleted
                                ? 'text-emerald-700'
                                : isCurrent
                                ? 'text-blue-700'
                                : 'text-slate-400'
                            )}
                          >
                            {stage.label}
                          </div>
                        </div>
                      );
                    })}
                  </div>
                </div>
              )}
            </div>

            {viewJob.status === 'COMPLETED' ? (
              <div className="p-4 rounded-xl bg-emerald-50 border border-emerald-200 flex flex-col sm:flex-row sm:items-center justify-between gap-3">
                <div className="flex items-center gap-3">
                  <CheckCircle2 className="h-6 w-6 text-emerald-600 shrink-0" />
                  <div>
                    <div className="font-bold text-emerald-900 text-sm flex items-center gap-2">
                      <span>Service Order Completed</span>
                      {viewJob.assigned_technician && (
                        <span className="text-xs font-mono text-emerald-700 font-semibold">
                          ({viewJob.assigned_technician.full_name} • {viewJob.assigned_technician.employee_code})
                        </span>
                      )}
                    </div>
                    <div className="text-xs text-slate-600 flex items-center gap-3 mt-0.5">
                      <span>Service resolved and verified. No further operational dispatch actions required.</span>
                    </div>
                  </div>
                </div>
              </div>
            ) : viewJob.status !== 'CANCELLED' && (
              viewJob.status === 'NEW' || !viewJob.assigned_technician ? (
                <div className="p-4 rounded-xl bg-amber-50 border border-amber-200 flex flex-col sm:flex-row sm:items-center justify-between gap-3">
                  <div className="flex items-center gap-3">
                    <UserX className="h-6 w-6 text-amber-600 shrink-0" />
                    <div>
                      <div className="font-bold text-amber-800 text-xs">
                        Awaiting Technician Assignment
                      </div>
                      <div className="text-[11px] text-slate-600">
                        Job is currently NEW and unassigned in the operational queue.
                      </div>
                    </div>
                  </div>

                  {isDispatcher && (
                    <button
                      onClick={() => {
                        setViewJob(null);
                        openSmartAssignmentModal(viewJob);
                      }}
                      className="flex items-center justify-center gap-1.5 rounded-xl bg-blue-600 px-4 py-2 text-xs font-bold text-white shadow-xs hover:bg-blue-700 active:scale-95 transition-all shrink-0 cursor-pointer"
                    >
                      <Sparkles className="h-4 w-4 text-amber-300" />
                      <span>Smart Assignment</span>
                    </button>
                  )}
                </div>
              ) : (
                <div className="p-4 rounded-xl bg-slate-50 border border-slate-200 flex flex-col sm:flex-row sm:items-center justify-between gap-3">
                  <div className="flex items-center gap-3">
                    <UserCheck className="h-6 w-6 text-emerald-600 shrink-0" />
                    <div>
                      <div className="font-bold text-slate-900 text-sm flex items-center gap-2">
                        <span>{viewJob.assigned_technician.full_name}</span>
                        <span className="text-xs font-mono text-emerald-700 font-semibold">
                          ({viewJob.assigned_technician.employee_code})
                        </span>
                      </div>
                      <div className="text-xs text-slate-600 flex items-center gap-3 mt-0.5">
                        <span>
                          Required Skill:{' '}
                          <strong className="text-purple-700 font-semibold">
                            {viewJob.required_skill?.skill_name || 'Certified'}
                          </strong>
                        </span>
                        <span>•</span>
                        <span>
                          Current Execution:{' '}
                          <strong className="text-blue-700 font-bold">
                            ● {getStatusDisplayLabel(viewJob.status)}
                          </strong>
                        </span>
                      </div>
                    </div>
                  </div>

                  {isDispatcher && viewJob.status === 'ASSIGNED' && (
                    <button
                      onClick={() => {
                        setViewJob(null);
                        setUnassignJobTarget(viewJob);
                      }}
                      className="flex items-center justify-center gap-1 rounded-lg bg-amber-50 border border-amber-200 px-3 py-1.5 text-xs font-semibold text-amber-700 hover:bg-amber-100 transition-all shrink-0 cursor-pointer"
                    >
                      <UserX className="h-3.5 w-3.5" />
                      <span>Unassign</span>
                    </button>
                  )}
                </div>
              )
            )}

            {/* ── Context-Aware ETA Telemetry ── */}
            <TechnicianETACard jobId={viewJob.id} />

            {/* ── Job Specifications Grid ── */}
            <div className="space-y-4 text-xs">
              <div className="grid grid-cols-2 gap-3">
                <div className="p-3 rounded-lg bg-slate-50 border border-slate-200 space-y-1">
                  <span className="text-[10px] font-semibold text-slate-500 uppercase">
                    Contact Phone
                  </span>
                  <div className="font-semibold text-slate-800 flex items-center gap-1">
                    <Phone className="h-3.5 w-3.5 text-slate-400" />
                    <span>{viewJob.customer_phone || 'N/A'}</span>
                  </div>
                </div>

                <div className="p-3 rounded-lg bg-slate-50 border border-slate-200 space-y-1">
                  <span className="text-[10px] font-semibold text-slate-500 uppercase">
                    Priority Urgency
                  </span>
                  <div>
                    <span
                      className={cn(
                        'inline-flex items-center rounded-md px-2 py-0.5 text-[10px] font-extrabold border',
                        getPriorityColor(viewJob.priority)
                      )}
                    >
                      {viewJob.priority}
                    </span>
                  </div>
                </div>

                <div className="p-3 rounded-lg bg-slate-50 border border-slate-200 space-y-1">
                  <span className="text-[10px] font-semibold text-slate-500 uppercase">
                    Required Skill Certification
                  </span>
                  <div className="font-bold text-purple-700 flex items-center gap-1">
                    <Wrench className="h-3.5 w-3.5 text-purple-600" />
                    <span>{viewJob.required_skill ? viewJob.required_skill.skill_name : 'N/A'}</span>
                  </div>
                </div>

                <div className="p-3 rounded-lg bg-slate-50 border border-slate-200 space-y-1">
                  <span className="text-[10px] font-semibold text-slate-500 uppercase">
                    Scheduled Operations Time
                  </span>
                  <div className="font-mono text-slate-700 flex items-center gap-1">
                    <Clock className="h-3.5 w-3.5 text-blue-600" />
                    <span>{viewJob.scheduled_time ? formatDate(viewJob.scheduled_time) : 'Immediate'}</span>
                  </div>
                </div>
              </div>

              <div className="p-3.5 rounded-lg bg-slate-50 border border-slate-200 space-y-1">
                <span className="text-[10px] font-semibold text-slate-500 uppercase">
                  Service Location & Coordinates
                </span>
                <div className="font-semibold text-slate-800 flex items-start gap-1.5">
                  <MapPin className="h-4 w-4 text-blue-600 shrink-0 mt-0.5" />
                  <span>{viewJob.address}</span>
                </div>
                <div className="text-[10px] text-slate-500 font-mono pl-5">
                  GPS: Latitude {viewJob.latitude}, Longitude {viewJob.longitude}
                </div>
              </div>

              {viewJob.description && (
                <div className="p-3.5 rounded-lg bg-slate-50 border border-slate-200 space-y-1">
                  <span className="text-[10px] font-semibold text-slate-500 uppercase">
                    Service Instructions / Scope
                  </span>
                  <p className="text-slate-700 leading-relaxed whitespace-pre-line text-xs">
                    {viewJob.description}
                  </p>
                </div>
              )}

              <div className="flex flex-col sm:flex-row sm:items-center justify-between text-[11px] text-slate-500 font-mono pt-3 border-t border-slate-100 gap-1">
                <span>Dispatcher: {viewJob.creator?.full_name || 'System Dispatcher'}</span>
                <span>Created: {formatDate(viewJob.created_at)}</span>
              </div>
            </div>

            <div className="flex justify-end pt-3 border-t border-slate-100">
              <button
                onClick={() => setViewJob(null)}
                className="rounded-lg border border-slate-200 bg-white px-4 py-2 text-xs text-slate-700 hover:bg-slate-50 font-medium cursor-pointer"
              >
                Close Drawer
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ── Modal: Smart Technician Assignment (Module 8 Integration) ── */}
      {assignJobTarget && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/40 backdrop-blur-sm p-4 animate-fade-in overflow-y-auto">
          <div className="w-full max-w-3xl rounded-2xl border border-slate-200 bg-white p-6 shadow-xl space-y-5 my-8">
            {/* Modal Header */}
            <div className="flex items-center justify-between border-b border-slate-100 pb-4">
              <div>
                <div className="flex items-center gap-2">
                  <span className="inline-flex items-center gap-1 rounded-full border border-purple-200 bg-purple-50 px-2.5 py-0.5 text-[11px] font-bold text-purple-700">
                    <Sparkles className="h-3.5 w-3.5 text-purple-600" />
                    <span>Smart Technician Assignment</span>
                  </span>
                  <span className="font-mono text-xs font-bold text-blue-700">
                    {assignJobTarget.job_number}
                  </span>
                </div>
                <h3 className="text-lg font-extrabold text-slate-900 mt-1">
                  Assign Technician for {assignJobTarget.customer_name}
                </h3>
                <div className="text-xs text-slate-500 flex items-center gap-3 mt-1">
                  <span className="flex items-center gap-1">
                    <MapPin className="h-3.5 w-3.5 text-slate-400" />
                    <span>{assignJobTarget.address}</span>
                  </span>
                  <span className="flex items-center gap-1">
                    <Wrench className="h-3.5 w-3.5 text-purple-600" />
                    <span className="text-purple-700 font-semibold">
                      {assignJobTarget.required_skill?.skill_name || 'Required Skill'}
                    </span>
                  </span>
                </div>
              </div>

              <button
                onClick={() => setAssignJobTarget(null)}
                className="text-slate-400 hover:text-slate-700 transition-colors cursor-pointer"
              >
                <X className="h-5 w-5" />
              </button>
            </div>

            {/* Error Message */}
            {formError && (
              <div className="p-3 rounded-xl bg-rose-50 border border-rose-200 text-rose-800 text-xs flex items-start gap-2.5">
                <AlertTriangle className="h-4 w-4 shrink-0 text-rose-600 mt-0.5" />
                <div className="space-y-1">
                  <div className="font-semibold">{formError.title}</div>
                  {formError.messages.length > 1 ? (
                    <ul className="list-disc list-inside space-y-0.5 pl-0.5">
                      {formError.messages.map((msg, idx) => (
                        <li key={idx}>{msg}</li>
                      ))}
                    </ul>
                  ) : (
                    <div>{formError.messages[0]}</div>
                  )}
                </div>
              </div>
            )}

            {/* Loading State */}
            {isAssignLoading ? (
              <div className="py-12 flex flex-col items-center justify-center gap-3 text-slate-500 text-xs">
                <RotateCw className="h-7 w-7 text-purple-600 animate-spin" />
                <span className="font-semibold text-slate-800">
                  Calculating Smart Technician Recommendations...
                </span>
                <span className="text-[11px] text-slate-500">
                  Evaluating skill certifications, availability status, workload count, and Haversine proximity.
                </span>
              </div>
            ) : recommendation ? (
              <div className="space-y-5 text-xs">
                {/* Top Recommendation Highlight Card */}
                {recommendation.recommended_technician ? (
                  <div className="relative overflow-hidden rounded-xl border border-purple-200 bg-purple-50/60 p-5 shadow-xs">
                    <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
                      <div>
                        <div className="flex items-center gap-2 mb-1.5">
                          <span className="inline-flex items-center gap-1 rounded-full bg-purple-600 text-white px-2.5 py-0.5 text-[10px] font-extrabold uppercase">
                            <Sparkles className="h-3 w-3" />
                            <span>Top Recommendation</span>
                          </span>
                          <span className="text-xs font-mono font-bold text-purple-700">
                            Score: {recommendation.recommendation_score} pts
                          </span>
                        </div>

                        <div className="text-xl font-extrabold text-slate-900 flex items-center gap-2">
                          <span>{recommendation.recommended_technician.full_name}</span>
                          <span className="text-xs font-mono text-slate-500 font-normal">
                            ({recommendation.recommended_technician.employee_code})
                          </span>
                        </div>

                        {/* Explanation Reasons Checklist */}
                        <div className="mt-3 flex flex-wrap gap-2">
                          {recommendation.recommended_technician.explanation_reasons.map((reason, idx) => (
                            <span
                              key={idx}
                              className="inline-flex items-center gap-1 rounded-md bg-white border border-emerald-200 px-2 py-0.5 text-[11px] font-semibold text-emerald-800"
                            >
                              <CheckCircle2 className="h-3 w-3 text-emerald-600 shrink-0" />
                              <span>{reason}</span>
                            </span>
                          ))}
                        </div>
                      </div>

                      {/* Confirm Button */}
                      <button
                        disabled={
                          isConfirmingTechId === recommendation.recommended_technician.technician_id
                        }
                        onClick={() =>
                          handleConfirmAssignment(
                            recommendation.recommended_technician!.technician_id
                          )
                        }
                        className="flex items-center justify-center gap-2 rounded-xl bg-purple-600 px-5 py-3 text-xs font-bold text-white shadow-xs hover:bg-purple-700 active:scale-95 disabled:opacity-50 transition-all shrink-0 cursor-pointer"
                      >
                        {isConfirmingTechId === recommendation.recommended_technician.technician_id ? (
                          <RotateCw className="h-4 w-4 animate-spin" />
                        ) : (
                          <UserCheck className="h-4 w-4" />
                        )}
                        <span>Confirm Assignment</span>
                      </button>
                    </div>

                    <div className="mt-3 text-[11px] text-slate-600 italic border-t border-purple-200/60 pt-2">
                      "{recommendation.explanation}"
                    </div>
                  </div>
                ) : (
                  <div className="p-4 rounded-xl bg-amber-50 border border-amber-200 text-amber-800 text-xs flex items-center gap-3">
                    <ShieldAlert className="h-5 w-5 shrink-0 text-amber-600" />
                    <div>
                      <div className="font-bold">No eligible technician available</div>
                      <div className="text-[11px] text-slate-600">{recommendation.explanation}</div>
                    </div>
                  </div>
                )}

                {/* Ranked Candidates Table */}
                <div className="space-y-2">
                  <div className="font-bold text-slate-800 flex items-center justify-between">
                    <span>Evaluated Candidates ({recommendation.ranked_candidates.length})</span>
                    <span className="text-[11px] font-normal text-slate-500">
                      Ranked deterministically by score
                    </span>
                  </div>

                  <div className="overflow-hidden rounded-xl border border-slate-200 bg-white">
                    <table className="w-full text-left text-xs">
                      <thead className="border-b border-slate-200 bg-slate-50 text-[10px] font-bold uppercase text-slate-500">
                        <tr>
                          <th className="py-2.5 px-3">Rank</th>
                          <th className="py-2.5 px-3">Technician</th>
                          <th className="py-2.5 px-3">Skill Certification</th>
                          <th className="py-2.5 px-3">Status</th>
                          <th className="py-2.5 px-3">Proximity</th>
                          <th className="py-2.5 px-3">Score</th>
                          <th className="py-2.5 px-3 text-right">Action</th>
                        </tr>
                      </thead>

                      <tbody className="divide-y divide-slate-100 text-slate-800">
                        {recommendation.ranked_candidates.map((c) => (
                          <tr
                            key={c.technician_id}
                            className={cn(
                              'transition-colors',
                              c.is_eligible ? 'hover:bg-slate-50' : 'opacity-60 bg-slate-50/50'
                            )}
                          >
                            <td className="py-2.5 px-3 font-mono font-bold text-slate-500">
                              #{c.ranking}
                            </td>

                            <td className="py-2.5 px-3">
                              <div className="font-bold text-slate-900">{c.full_name}</div>
                              <div className="text-[10px] text-slate-500 font-mono">
                                {c.employee_code}
                              </div>
                            </td>

                            <td className="py-2.5 px-3">
                              {c.primary_skill_name ? (
                                <span className="text-purple-700 font-semibold">
                                  {c.primary_skill_name}
                                </span>
                              ) : (
                                <span className="text-slate-400">—</span>
                              )}
                            </td>

                            <td className="py-2.5 px-3">
                              <span
                                className={cn(
                                  'inline-flex items-center rounded-full px-2 py-0.5 text-[10px] font-bold border',
                                  c.availability_status === 'AVAILABLE'
                                    ? 'bg-emerald-50 border-emerald-200 text-emerald-700'
                                    : 'bg-rose-50 border-rose-200 text-rose-700'
                                )}
                              >
                                {c.availability_status}
                              </span>
                            </td>

                            <td className="py-2.5 px-3 font-mono text-[11px] text-slate-600">
                              {c.distance_display}
                            </td>

                            <td className="py-2.5 px-3 font-mono font-bold text-blue-700">
                              {c.recommendation_score} pts
                            </td>

                            <td className="py-2.5 px-3 text-right">
                              {c.is_eligible ? (
                                <button
                                  disabled={isConfirmingTechId === c.technician_id}
                                  onClick={() => handleConfirmAssignment(c.technician_id)}
                                  className="rounded-lg bg-blue-50 border border-blue-200 px-2.5 py-1 text-[11px] font-bold text-blue-700 hover:bg-blue-600 hover:text-white transition-all active:scale-95 disabled:opacity-50 cursor-pointer"
                                >
                                  {isConfirmingTechId === c.technician_id ? 'Assigning...' : 'Assign'}
                                </button>
                              ) : (
                                <span className="inline-flex items-center gap-1 text-[10px] text-rose-600 font-semibold">
                                  <AlertTriangle className="h-3 w-3 shrink-0" />
                                  <span>{c.ineligibility_reason || 'Ineligible'}</span>
                                </span>
                              )}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              </div>
            ) : null}

            <div className="flex justify-end pt-3 border-t border-slate-100">
              <button
                onClick={() => setAssignJobTarget(null)}
                className="rounded-lg border border-slate-200 bg-white px-4 py-2 text-slate-700 hover:bg-slate-50 font-medium text-xs cursor-pointer"
              >
                Close Modal
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ── Modal: Unassign Technician Confirmation ── */}
      {unassignJobTarget && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/40 backdrop-blur-sm p-4 animate-fade-in">
          <div className="w-full max-w-md rounded-2xl border border-slate-200 bg-white p-6 shadow-xl space-y-4">
            <div className="flex items-center gap-3 text-amber-700">
              <UserX className="h-6 w-6 shrink-0 text-amber-600" />
              <h3 className="text-base font-extrabold text-slate-900">
                Unassign Job {unassignJobTarget.job_number}
              </h3>
            </div>

            <p className="text-xs text-slate-600 leading-relaxed">
              Are you sure you want to unassign technician{' '}
              <strong className="text-emerald-700 font-bold">
                {unassignJobTarget.assigned_technician?.full_name || 'Assigned Technician'}
              </strong>{' '}
              from job order{' '}
              <strong className="text-slate-900 font-bold">{unassignJobTarget.job_number}</strong>?
              This will safely revert the job status to{' '}
              <strong className="text-purple-700 font-bold">NEW</strong>.
            </p>

            <div className="flex items-center justify-end gap-2 pt-3 border-t border-slate-100 text-xs">
              <button
                type="button"
                onClick={() => setUnassignJobTarget(null)}
                className="rounded-lg border border-slate-200 bg-white px-3.5 py-1.5 text-slate-700 hover:bg-slate-50 font-medium cursor-pointer"
              >
                Dismiss
              </button>
              <button
                type="button"
                onClick={handleUnassignSubmit}
                className="rounded-lg bg-amber-600 px-4 py-1.5 font-semibold text-white shadow-xs hover:bg-amber-700 cursor-pointer"
              >
                Confirm Unassign
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ── Modal: Create New Job (Dispatcher Only) ── */}
      {isAddModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/40 backdrop-blur-sm p-4 animate-fade-in overflow-y-auto">
          <div className="w-full max-w-xl rounded-2xl border border-slate-200 bg-white p-6 shadow-xl space-y-4 my-8">
            <div className="flex items-center justify-between border-b border-slate-100 pb-3">
              <h3 className="text-lg font-extrabold text-slate-900 flex items-center gap-2">
                <Plus className="h-5 w-5 text-blue-600" />
                <span>Create Service Job Order</span>
              </h3>
              <button
                onClick={() => setIsAddModalOpen(false)}
                className="text-slate-400 hover:text-slate-700 cursor-pointer"
              >
                <X className="h-5 w-5" />
              </button>
            </div>

            {formError && (
              <div className="p-3 rounded-lg bg-rose-50 border border-rose-200 text-rose-800 text-xs flex items-start gap-2.5">
                <AlertTriangle className="h-4 w-4 shrink-0 text-rose-600 mt-0.5" />
                <div className="space-y-1">
                  <div className="font-semibold">{formError.title}</div>
                  {formError.messages.length > 1 ? (
                    <ul className="list-disc list-inside space-y-0.5 pl-0.5">
                      {formError.messages.map((msg, idx) => (
                        <li key={idx}>{msg}</li>
                      ))}
                    </ul>
                  ) : (
                    <div>{formError.messages[0]}</div>
                  )}
                </div>
              </div>
            )}

            <form onSubmit={handleAddSubmit} className="space-y-5 text-xs">
              {/* Section 1: Customer Information */}
              <div className="space-y-3 border-b border-slate-100 pb-4">
                <div className="text-[11px] font-bold uppercase tracking-wider text-blue-700 flex items-center gap-1.5">
                  <User className="h-3.5 w-3.5" />
                  <span>Customer Information</span>
                </div>

                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                  <div>
                    <label className="block text-slate-700 font-semibold mb-1">
                      Customer Name *
                    </label>
                    <input
                      type="text"
                      required
                      placeholder="Acme Industrial Logistics"
                      value={addForm.customer_name}
                      onChange={(e) => setAddForm({ ...addForm, customer_name: e.target.value })}
                      className="w-full rounded-lg border border-slate-200 bg-slate-50 p-2.5 text-slate-800 focus:border-blue-500 focus:bg-white focus:outline-none"
                    />
                  </div>

                  <div>
                    <label className="block text-slate-700 font-semibold mb-1">
                      Contact Phone
                    </label>
                    <input
                      type="tel"
                      placeholder="+1 (555) 019-2834"
                      value={addForm.customer_phone || ''}
                      onChange={(e) => setAddForm({ ...addForm, customer_phone: e.target.value })}
                      className="w-full rounded-lg border border-slate-200 bg-slate-50 p-2.5 text-slate-800 focus:border-blue-500 focus:bg-white focus:outline-none"
                    />
                  </div>
                </div>
              </div>

              {/* Section 2: Service Location */}
              <div className="space-y-3 border-b border-slate-100 pb-4">
                <div className="text-[11px] font-bold uppercase tracking-wider text-blue-700 flex items-center gap-1.5">
                  <MapPin className="h-3.5 w-3.5" />
                  <span>Service Location</span>
                </div>

                <div>
                  <label className="block text-slate-700 font-semibold mb-1">
                    Street Address *
                  </label>
                  <input
                    type="text"
                    required
                    placeholder="742 Evergreen Terrace, Sector 4, Springfield"
                    value={addForm.address}
                    onChange={(e) => setAddForm({ ...addForm, address: e.target.value })}
                    className="w-full rounded-lg border border-slate-200 bg-slate-50 p-2.5 text-slate-800 focus:border-blue-500 focus:bg-white focus:outline-none"
                  />
                </div>

                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="block text-slate-700 font-semibold mb-1">
                      Latitude (-90 to 90) *
                    </label>
                    <input
                      type="number"
                      step="any"
                      required
                      value={addForm.latitude}
                      onChange={(e) =>
                        setAddForm({ ...addForm, latitude: parseFloat(e.target.value) || 0 })
                      }
                      className="w-full rounded-lg border border-slate-200 bg-slate-50 p-2.5 text-slate-800 focus:border-blue-500 focus:bg-white focus:outline-none font-mono"
                    />
                  </div>

                  <div>
                    <label className="block text-slate-700 font-semibold mb-1">
                      Longitude (-180 to 180) *
                    </label>
                    <input
                      type="number"
                      step="any"
                      required
                      value={addForm.longitude}
                      onChange={(e) =>
                        setAddForm({ ...addForm, longitude: parseFloat(e.target.value) || 0 })
                      }
                      className="w-full rounded-lg border border-slate-200 bg-slate-50 p-2.5 text-slate-800 focus:border-blue-500 focus:bg-white focus:outline-none font-mono"
                    />
                  </div>
                </div>
              </div>

              {/* Section 3: Service Requirements */}
              <div className="space-y-3">
                <div className="text-[11px] font-bold uppercase tracking-wider text-blue-700 flex items-center gap-1.5">
                  <Wrench className="h-3.5 w-3.5" />
                  <span>Service Requirements</span>
                </div>

                <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                  <div>
                    <label className="block text-slate-700 font-semibold mb-1">
                      Required Skill *
                    </label>
                    <select
                      required
                      value={addForm.required_skill_id}
                      onChange={(e) => setAddForm({ ...addForm, required_skill_id: e.target.value })}
                      className="w-full rounded-lg border border-slate-200 bg-slate-50 p-2.5 text-slate-800 focus:border-blue-500 focus:bg-white focus:outline-none cursor-pointer"
                    >
                      {skills.length === 0 ? (
                        <option value="">No Active Skills Found</option>
                      ) : (
                        skills.map((s) => (
                          <option key={s.id} value={s.id}>
                            {s.skill_name} ({s.category})
                          </option>
                        ))
                      )}
                    </select>
                  </div>

                  <div>
                    <label className="block text-slate-700 font-semibold mb-1">Priority *</label>
                    <select
                      value={addForm.priority}
                      onChange={(e) =>
                        setAddForm({ ...addForm, priority: e.target.value as Priority })
                      }
                      className="w-full rounded-lg border border-slate-200 bg-slate-50 p-2.5 text-slate-800 focus:border-blue-500 focus:bg-white focus:outline-none cursor-pointer"
                    >
                      {PRIORITIES.map((p) => (
                        <option key={p} value={p}>
                          {p}
                        </option>
                      ))}
                    </select>
                  </div>

                  <div>
                    <label className="block text-slate-700 font-semibold mb-1">
                      Scheduled Time
                    </label>
                    <input
                      type="datetime-local"
                      value={addForm.scheduled_time || ''}
                      onChange={(e) => setAddForm({ ...addForm, scheduled_time: e.target.value })}
                      className="w-full rounded-lg border border-slate-200 bg-slate-50 p-2.5 text-slate-800 focus:border-blue-500 focus:bg-white focus:outline-none font-mono"
                    />
                  </div>
                </div>

                <div>
                  <label className="block text-slate-700 font-semibold mb-1">
                    Service Instructions / Scope
                  </label>
                  <textarea
                    rows={3}
                    placeholder="Detailed problem description, equipment specifications, or safety instructions..."
                    value={addForm.service_instructions || addForm.description || ''}
                    onChange={(e) =>
                      setAddForm({
                        ...addForm,
                        description: e.target.value,
                        service_instructions: e.target.value,
                      })
                    }
                    className="w-full rounded-lg border border-slate-200 bg-slate-50 p-2.5 text-slate-800 focus:border-blue-500 focus:bg-white focus:outline-none"
                  />
                </div>
              </div>

              <div className="flex items-center justify-end gap-2 pt-3 border-t border-slate-100">
                <button
                  type="button"
                  disabled={isSubmitting}
                  onClick={() => setIsAddModalOpen(false)}
                  className="rounded-lg border border-slate-200 bg-white px-4 py-2 text-slate-700 hover:bg-slate-50 font-medium cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={isSubmitting}
                  className="rounded-lg bg-blue-600 px-4 py-2 text-white font-semibold hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed cursor-pointer shadow-xs flex items-center gap-2"
                >
                  {isSubmitting ? (
                    <>
                      <RotateCw className="h-4 w-4 animate-spin" />
                      <span>Creating...</span>
                    </>
                  ) : (
                    <span>Create Job Order</span>
                  )}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* ── Modal: Edit Job (Dispatcher Only) ── */}
      {editJob && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/40 backdrop-blur-sm p-4 animate-fade-in overflow-y-auto">
          <div className="w-full max-w-xl rounded-2xl border border-slate-200 bg-white p-6 shadow-xl space-y-4 my-8">
            <div className="flex items-center justify-between border-b border-slate-100 pb-3">
              <h3 className="text-lg font-extrabold text-slate-900 flex items-center gap-2">
                <Edit className="h-5 w-5 text-blue-600" />
                <span>Edit Job {editJob.job_number}</span>
              </h3>
              <button onClick={() => setEditJob(null)} className="text-slate-400 hover:text-slate-700 cursor-pointer">
                <X className="h-5 w-5" />
              </button>
            </div>

            {formError && (
              <div className="p-3 rounded-lg bg-rose-50 border border-rose-200 text-rose-800 text-xs flex items-start gap-2.5">
                <AlertTriangle className="h-4 w-4 shrink-0 text-rose-600 mt-0.5" />
                <div className="space-y-1">
                  <div className="font-semibold">{formError.title}</div>
                  {formError.messages.length > 1 ? (
                    <ul className="list-disc list-inside space-y-0.5 pl-0.5">
                      {formError.messages.map((msg, idx) => (
                        <li key={idx}>{msg}</li>
                      ))}
                    </ul>
                  ) : (
                    <div>{formError.messages[0]}</div>
                  )}
                </div>
              </div>
            )}

            <form onSubmit={handleEditSubmit} className="space-y-4 text-xs">
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <div>
                  <label className="block text-slate-700 font-semibold mb-1">Customer Name</label>
                  <input
                    type="text"
                    required
                    value={editForm.customer_name || ''}
                    onChange={(e) => setEditForm({ ...editForm, customer_name: e.target.value })}
                    className="w-full rounded-lg border border-slate-200 bg-slate-50 p-2.5 text-slate-800 focus:border-blue-500 focus:bg-white focus:outline-none"
                  />
                </div>

                <div>
                  <label className="block text-slate-700 font-semibold mb-1">Contact Phone</label>
                  <input
                    type="tel"
                    value={editForm.customer_phone || ''}
                    onChange={(e) => setEditForm({ ...editForm, customer_phone: e.target.value })}
                    className="w-full rounded-lg border border-slate-200 bg-slate-50 p-2.5 text-slate-800 focus:border-blue-500 focus:bg-white focus:outline-none"
                  />
                </div>
              </div>

              <div>
                <label className="block text-slate-700 font-semibold mb-1">Street Address</label>
                <input
                  type="text"
                  required
                  value={editForm.address || ''}
                  onChange={(e) => setEditForm({ ...editForm, address: e.target.value })}
                  className="w-full rounded-lg border border-slate-200 bg-slate-50 p-2.5 text-slate-800 focus:border-blue-500 focus:bg-white focus:outline-none"
                />
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                <div>
                  <label className="block text-slate-700 font-semibold mb-1">Required Skill</label>
                  <select
                    value={editForm.required_skill_id || ''}
                    onChange={(e) => setEditForm({ ...editForm, required_skill_id: e.target.value })}
                    className="w-full rounded-lg border border-slate-200 bg-slate-50 p-2.5 text-slate-800 focus:border-blue-500 focus:bg-white focus:outline-none cursor-pointer"
                  >
                    {skills.map((s) => (
                      <option key={s.id} value={s.id}>
                        {s.skill_name}
                      </option>
                    ))}
                  </select>
                </div>

                <div>
                  <label className="block text-slate-700 font-semibold mb-1">Priority</label>
                  <select
                    value={editForm.priority || 'MEDIUM'}
                    onChange={(e) => setEditForm({ ...editForm, priority: e.target.value as Priority })}
                    className="w-full rounded-lg border border-slate-200 bg-slate-50 p-2.5 text-slate-800 focus:border-blue-500 focus:bg-white focus:outline-none cursor-pointer"
                  >
                    {PRIORITIES.map((p) => (
                      <option key={p} value={p}>
                        {p}
                      </option>
                    ))}
                  </select>
                </div>

                <div>
                  <label className="block text-slate-700 font-semibold mb-1">Scheduled Time</label>
                  <input
                    type="datetime-local"
                    value={editForm.scheduled_time || ''}
                    onChange={(e) => setEditForm({ ...editForm, scheduled_time: e.target.value })}
                    className="w-full rounded-lg border border-slate-200 bg-slate-50 p-2.5 text-slate-800 focus:border-blue-500 focus:bg-white focus:outline-none font-mono"
                  />
                </div>
              </div>

              <div>
                <label className="block text-slate-700 font-semibold mb-1">Service Instructions</label>
                <textarea
                  rows={3}
                  value={editForm.service_instructions || editForm.description || ''}
                  onChange={(e) =>
                    setEditForm({
                      ...editForm,
                      description: e.target.value,
                      service_instructions: e.target.value,
                    })
                  }
                  className="w-full rounded-lg border border-slate-200 bg-slate-50 p-2.5 text-slate-800 focus:border-blue-500 focus:bg-white focus:outline-none"
                />
              </div>

              <div className="flex items-center justify-end gap-2 pt-2 border-t border-slate-100">
                <button
                  type="button"
                  disabled={isSubmitting}
                  onClick={() => setEditJob(null)}
                  className="rounded-lg border border-slate-200 bg-white px-4 py-2 text-slate-700 hover:bg-slate-50 font-medium cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={isSubmitting}
                  className="rounded-lg bg-blue-600 px-4 py-2 text-white font-semibold hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed cursor-pointer shadow-xs flex items-center gap-2"
                >
                  {isSubmitting ? (
                    <>
                      <RotateCw className="h-4 w-4 animate-spin" />
                      <span>Updating...</span>
                    </>
                  ) : (
                    <span>Save Changes</span>
                  )}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* ── Modal: Cancel Job ── */}
      {cancelJobTarget && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/40 backdrop-blur-sm p-4 animate-fade-in">
          <div className="w-full max-w-md rounded-2xl border border-slate-200 bg-white p-6 shadow-xl space-y-4">
            <div className="flex items-center gap-3 text-rose-600">
              <AlertTriangle className="h-6 w-6 shrink-0" />
              <h3 className="text-base font-extrabold text-slate-900">
                Cancel Job {cancelJobTarget.job_number}
              </h3>
            </div>

            <p className="text-xs text-slate-600 leading-relaxed">
              Are you sure you want to cancel service job order{' '}
              <strong className="text-slate-900 font-bold">{cancelJobTarget.job_number}</strong>? A
              cancellation reason is required for audit trail tracking.
            </p>

            {formError && (
              <div className="p-2.5 rounded-lg bg-rose-50 border border-rose-200 text-rose-800 text-xs flex items-start gap-2">
                <AlertTriangle className="h-4 w-4 shrink-0 text-rose-600 mt-0.5" />
                <div>
                  <span className="font-semibold">{formError.title}: </span>
                  <span>{formError.messages.join(' ')}</span>
                </div>
              </div>
            )}

            <form onSubmit={handleCancelSubmit} className="space-y-4 text-xs">
              <div>
                <label className="block text-slate-700 font-semibold mb-1">Cancellation Reason *</label>
                <textarea
                  required
                  rows={3}
                  placeholder="Provide detailed cancellation reason (e.g., Customer rescheduled, duplicate entry)..."
                  value={cancelReason}
                  onChange={(e) => setCancelReason(e.target.value)}
                  className="w-full rounded-lg border border-slate-200 bg-slate-50 p-2.5 text-slate-800 focus:border-rose-500 focus:bg-white focus:outline-none"
                />
              </div>

              <div className="flex items-center justify-end gap-2 pt-2 border-t border-slate-100">
                <button
                  type="button"
                  disabled={isSubmitting}
                  onClick={() => setCancelJobTarget(null)}
                  className="rounded-lg border border-slate-200 bg-white px-3.5 py-1.5 text-xs text-slate-700 hover:bg-slate-50 font-medium cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  Dismiss
                </button>
                <button
                  type="submit"
                  disabled={isSubmitting}
                  className="rounded-lg bg-rose-600 px-4 py-1.5 text-xs font-semibold text-white shadow-xs hover:bg-rose-700 disabled:opacity-50 disabled:cursor-not-allowed cursor-pointer flex items-center gap-1.5"
                >
                  {isSubmitting ? (
                    <>
                      <RotateCw className="h-3.5 w-3.5 animate-spin" />
                      <span>Cancelling...</span>
                    </>
                  ) : (
                    <span>Confirm Cancellation</span>
                  )}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}

