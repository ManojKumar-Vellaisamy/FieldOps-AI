import { useState, useMemo } from 'react';
import { Search, MoreVertical, Eye, UserPlus, Filter } from 'lucide-react';
import type { JobItem, JobPriority, JobStatus } from '@/types/dashboard.types';
import { EmptyState } from './EmptyState';
import { cn } from '@/utils/cn';

interface JobsTableProps {
  jobs: JobItem[];
  onViewJob?: (job: JobItem) => void;
  onAssignJob?: (job: JobItem) => void;
}

export function JobsTable({ jobs, onViewJob, onAssignJob }: JobsTableProps) {
  const [searchTerm, setSearchTerm] = useState('');
  const [selectedPriority, setSelectedPriority] = useState<string>('all');
  const [activeDropdown, setActiveDropdown] = useState<string | null>(null);

  const filteredJobs = useMemo(() => {
    return jobs.filter((job) => {
      const matchesSearch =
        job.id.toLowerCase().includes(searchTerm.toLowerCase()) ||
        job.customer.toLowerCase().includes(searchTerm.toLowerCase()) ||
        job.skill.toLowerCase().includes(searchTerm.toLowerCase()) ||
        job.technician.toLowerCase().includes(searchTerm.toLowerCase());

      const matchesPriority =
        selectedPriority === 'all' || job.priority.toLowerCase() === selectedPriority.toLowerCase();

      return matchesSearch && matchesPriority;
    });
  }, [jobs, searchTerm, selectedPriority]);

  const priorityBadge = (priority: JobPriority) => {
    switch (priority) {
      case 'High':
        return 'bg-rose-50 text-rose-800 border-rose-200';
      case 'Medium':
        return 'bg-amber-50 text-amber-800 border-amber-200';
      case 'Low':
        return 'bg-slate-100 text-slate-700 border-slate-200';
    }
  };

  const statusStyle = (status: JobStatus) => {
    switch (status) {
      case 'In Progress':
        return { dot: 'bg-emerald-500', badge: 'bg-emerald-50 text-emerald-800 border-emerald-200' };
      case 'Assigned':
        return { dot: 'bg-blue-500', badge: 'bg-blue-50 text-blue-800 border-blue-200' };
      case 'Pending':
        return { dot: 'bg-amber-500', badge: 'bg-amber-50 text-amber-800 border-amber-200' };
      case 'Completed':
        return { dot: 'bg-slate-400', badge: 'bg-slate-100 text-slate-700 border-slate-200' };
    }
  };

  return (
    <div className="rounded-xl border border-slate-200 bg-white shadow-xs overflow-hidden select-none">
      {/* ── Table Header Controls ── */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-slate-100 p-4">
        <div>
          <h3 className="text-base font-bold text-slate-900 tracking-tight">Recent Dispatch Jobs</h3>
          <p className="text-xs text-slate-500 mt-0.5">Real-time service ticket status &amp; assignment</p>
        </div>

        <div className="flex items-center gap-2">
          {/* Search Input */}
          <div className="relative">
            <Search className="absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-slate-400 pointer-events-none" />
            <input
              type="text"
              placeholder="Search jobs..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              className="w-36 sm:w-48 rounded-lg border border-slate-200 bg-slate-50 py-1.5 pl-8 pr-3 text-xs text-slate-800 placeholder-slate-400 focus:border-blue-500 focus:bg-white focus:outline-none focus:ring-2 focus:ring-blue-500/20 transition-all"
            />
          </div>

          {/* Priority Filter */}
          <div className="relative flex items-center">
            <Filter className="absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-slate-400 pointer-events-none" />
            <select
              value={selectedPriority}
              onChange={(e) => setSelectedPriority(e.target.value)}
              className="rounded-lg border border-slate-200 bg-slate-50 py-1.5 pl-8 pr-3 text-xs text-slate-800 focus:border-blue-500 focus:bg-white focus:outline-none transition-all appearance-none cursor-pointer"
            >
              <option value="all">All Priorities</option>
              <option value="high">High Priority</option>
              <option value="medium">Medium Priority</option>
              <option value="low">Low Priority</option>
            </select>
          </div>
        </div>
      </div>

      {/* ── Table Content ── */}
      {filteredJobs.length === 0 ? (
        <EmptyState
          title="No jobs match your search"
          description="Try adjusting your search terms or priority filters."
          action={
            <button
              onClick={() => {
                setSearchTerm('');
                setSelectedPriority('all');
              }}
              className="text-xs font-semibold text-blue-600 hover:underline"
            >
              Clear filters
            </button>
          }
        />
      ) : (
        <div className="overflow-x-auto scrollbar-thin">
          <table className="w-full text-left text-xs">
            <thead className="bg-slate-50 text-slate-500 border-b border-slate-200 font-bold uppercase tracking-wider text-[10px]">
              <tr>
                <th className="py-3 px-4">Job ID</th>
                <th className="py-3 px-4">Customer</th>
                <th className="py-3 px-4">Required Skill</th>
                <th className="py-3 px-4">Priority</th>
                <th className="py-3 px-4">Status</th>
                <th className="py-3 px-4">Assigned Tech</th>
                <th className="py-3 px-4">ETA</th>
                <th className="py-3 px-4 text-right">Actions</th>
              </tr>
            </thead>

            <tbody className="divide-y divide-slate-100 text-slate-700">
              {filteredJobs.map((job) => {
                const status = statusStyle(job.status);

                return (
                  <tr key={job.id} className="hover:bg-slate-50/80 transition-colors">
                    {/* Job ID */}
                    <td className="py-3 px-4 font-mono font-bold text-blue-600">{job.id}</td>

                    {/* Customer */}
                    <td className="py-3 px-4">
                      <div className="font-bold text-slate-900">{job.customer}</div>
                      <div className="text-[10px] text-slate-500">{job.location}</div>
                    </td>

                    {/* Required Skill */}
                    <td className="py-3 px-4">
                      <span className="rounded-md bg-purple-50 px-2 py-0.5 text-[11px] font-bold text-purple-700 border border-purple-200">
                        {job.skill}
                      </span>
                    </td>

                    {/* Priority */}
                    <td className="py-3 px-4">
                      <span
                        className={cn(
                          'rounded-full border px-2 py-0.5 text-[10px] font-bold uppercase tracking-wider',
                          priorityBadge(job.priority),
                        )}
                      >
                        {job.priority}
                      </span>
                    </td>

                    {/* Status */}
                    <td className="py-3 px-4">
                      <div className="flex items-center gap-1.5">
                        <span className={cn('h-1.5 w-1.5 rounded-full', status.dot)} />
                        <span
                          className={cn(
                            'rounded-full border px-2 py-0.5 text-[10px] font-bold',
                            status.badge,
                          )}
                        >
                          {job.status}
                        </span>
                      </div>
                    </td>

                    {/* Technician */}
                    <td className="py-3 px-4">
                      <span
                        className={cn(
                          'font-medium',
                          job.technician === 'Unassigned' ? 'text-slate-400 italic' : 'text-slate-800 font-bold',
                        )}
                      >
                        {job.technician}
                      </span>
                    </td>

                    {/* ETA */}
                    <td className="py-3 px-4 font-mono text-[11px] text-slate-700 font-medium">{job.eta}</td>

                    {/* Actions */}
                    <td className="py-3 px-4 text-right relative">
                      <div className="flex items-center justify-end gap-1">
                        <button
                          onClick={() => onViewJob?.(job)}
                          title="View job details"
                          className="p-1 rounded text-slate-400 hover:text-slate-900 hover:bg-slate-100 transition-colors"
                        >
                          <Eye className="h-3.5 w-3.5" />
                        </button>
                        <button
                          onClick={() => onAssignJob?.(job)}
                          title="Assign technician"
                          className="p-1 rounded text-slate-400 hover:text-blue-600 hover:bg-slate-100 transition-colors"
                        >
                          <UserPlus className="h-3.5 w-3.5" />
                        </button>

                        <div className="relative">
                          <button
                            onClick={() => setActiveDropdown(activeDropdown === job.id ? null : job.id)}
                            className="p-1 rounded text-slate-400 hover:text-slate-900 hover:bg-slate-100 transition-colors"
                          >
                            <MoreVertical className="h-3.5 w-3.5" />
                          </button>

                          {activeDropdown === job.id && (
                            <div className="absolute right-0 mt-1 w-36 rounded-lg border border-slate-200 bg-white p-1 shadow-xl z-20 text-left">
                              <button
                                onClick={() => {
                                  onViewJob?.(job);
                                  setActiveDropdown(null);
                                }}
                                className="w-full px-2 py-1 text-[11px] font-medium text-slate-700 hover:bg-slate-50 rounded transition-colors"
                              >
                                View Ticket
                              </button>
                              <button
                                onClick={() => {
                                  onAssignJob?.(job);
                                  setActiveDropdown(null);
                                }}
                                className="w-full px-2 py-1 text-[11px] font-bold text-blue-600 hover:bg-blue-50 rounded transition-colors"
                              >
                                Smart Assign
                              </button>
                            </div>
                          )}
                        </div>
                      </div>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
