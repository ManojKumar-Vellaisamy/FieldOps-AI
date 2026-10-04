import { useState, useEffect } from 'react';
import { Cpu, Shield, RefreshCw, Plus } from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '@/contexts/AuthContext';
import { SmartAssignmentSection } from '@/components/dashboard/SmartAssignmentSection';
import { jobService } from '@/services/job.service';
import type { Job } from '@/types/job.types';
import { cn } from '@/utils/cn';

export default function SmartAssignmentPage() {
  const { user } = useAuth();
  const navigate = useNavigate();
  const [unassignedJobs, setUnassignedJobs] = useState<Job[]>([]);
  const [totalJobs, setTotalJobs] = useState<number>(0);
  const [isLoading, setIsLoading] = useState<boolean>(true);

  const loadUnassignedJobs = async () => {
    setIsLoading(true);
    try {
      const [unassignedRes, allJobsRes] = await Promise.all([
        jobService.getJobs({ status: 'NEW', page_size: 50 }),
        jobService.getJobs({ page_size: 1 }).catch(() => ({ total: 0 })),
      ]);
      setUnassignedJobs(unassignedRes.items);
      setTotalJobs(allJobsRes.total);
    } catch (err) {
      console.error('Failed to load unassigned jobs for smart assignment', err);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    loadUnassignedJobs();
  }, []);

  return (
    <div className="flex flex-col gap-6 py-2 animate-fade-in select-none">
      {/* ── Header ── */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-slate-200 pb-5">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <span className="inline-flex items-center gap-1.5 rounded-full border border-purple-200 bg-purple-50 px-2.5 py-0.5 text-[11px] font-semibold text-purple-700">
              <Cpu className="h-3.5 w-3.5 text-purple-600" />
              <span>Smart Assignment Engine</span>
            </span>
            <span className="inline-flex items-center gap-1 rounded-full border border-slate-200 bg-slate-100 px-2.5 py-0.5 text-[11px] font-medium text-slate-700">
              <Shield className="h-3 w-3 text-purple-600" />
              <span>{user?.role || 'Dispatcher'}</span>
            </span>
          </div>

          <h1 className="text-2xl md:text-3xl font-extrabold tracking-tight text-slate-900">
            Smart Technician Assignment
          </h1>
          <p className="text-xs md:text-sm text-slate-500 mt-0.5">
            Rule-based technician eligibility validation, skill certification check, proximity calculation, and 1-click dispatching.
          </p>
        </div>

        <div className="flex items-center gap-2">
          <button
            onClick={() => navigate('/jobs')}
            className="flex items-center gap-2 rounded-xl bg-blue-600 px-4 py-2 text-xs font-bold text-white shadow-xs transition-all hover:bg-blue-700 cursor-pointer"
          >
            <Plus className="h-4 w-4" />
            <span>Create New Job</span>
          </button>
          <button
            onClick={loadUnassignedJobs}
            disabled={isLoading}
            className="flex items-center gap-1.5 rounded-xl border border-slate-200 bg-white px-3 py-2 text-xs font-bold text-slate-700 hover:bg-slate-50 cursor-pointer shadow-xs"
          >
            <RefreshCw className={cn('h-3.5 w-3.5', isLoading && 'animate-spin')} />
            <span>Refresh</span>
          </button>
        </div>
      </div>

      {/* ── Main Smart Assignment Engine Section ── */}
      <SmartAssignmentSection
        unassignedJobs={unassignedJobs}
        totalJobs={totalJobs}
        onAssignmentComplete={loadUnassignedJobs}
      />
    </div>
  );
}
