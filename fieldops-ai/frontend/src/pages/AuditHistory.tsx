import { useState } from 'react';
import { History, Filter, Search, RotateCcw, ShieldCheck, User, Calendar, Tag, CheckCircle2, AlertTriangle, Info } from 'lucide-react';

interface AuditLogEntry {
  id: string;
  timestamp: string;
  user: string;
  action: string;
  jobId: string;
  status: 'Success' | 'Warning' | 'Flagged' | 'Info';
  details: string;
}

const MOCK_AUDIT_LOGS: AuditLogEntry[] = [
  {
    id: 'AUD-901',
    timestamp: '2026-08-07 13:45:12 UTC',
    user: 'Sarah Connor (Admin)',
    action: 'User Role Modified',
    jobId: 'N/A',
    status: 'Success',
    details: 'Updated role permissions for user account (dispatcher@fieldops.ai)',
  },
  {
    id: 'AUD-902',
    timestamp: '2026-08-07 13:35:00 UTC',
    user: 'Priya Nair (Dispatcher)',
    action: 'Manual Dispatch Override',
    jobId: 'JOB-4830',
    status: 'Warning',
    details: 'Manual override applied: Prioritized JOB-4830 over JOB-4834 due to customer SLA',
  },
  {
    id: 'AUD-903',
    timestamp: '2026-08-07 13:22:18 UTC',
    user: 'Priya Nair (Dispatcher)',
    action: 'Service Request Created',
    jobId: 'JOB-4831',
    status: 'Success',
    details: 'Created new high-priority HVAC service job for OmniData Center',
  },
  {
    id: 'AUD-904',
    timestamp: '2026-08-07 13:10:45 UTC',
    user: 'Marcus Vance (Technician)',
    action: 'Technician Status Update',
    jobId: 'JOB-4829',
    status: 'Info',
    details: 'Status updated to In Progress at AeroTech Systems site',
  },
  {
    id: 'AUD-905',
    timestamp: '2026-08-07 12:50:33 UTC',
    user: 'Elena Rostova (Technician)',
    action: 'Job Completion Recorded',
    jobId: 'JOB-4832',
    status: 'Success',
    details: 'Completed precision calibration work order. Customer sign-off obtained',
  },
  {
    id: 'AUD-906',
    timestamp: '2026-08-07 12:30:11 UTC',
    user: 'FieldOps AI Engine',
    action: 'AI Recommendation Generated',
    jobId: 'JOB-4831',
    status: 'Info',
    details: 'Calculated optimal tech match (Marcus Vance) with High Confidence',
  },
  {
    id: 'AUD-907',
    timestamp: '2026-08-07 12:05:00 UTC',
    user: 'System Security',
    action: 'Failed Login Attempt',
    jobId: 'N/A',
    status: 'Flagged',
    details: 'Invalid password attempt recorded for user@fieldops.ai (IP: 192.168.1.45)',
  },
];

export default function AuditHistoryPage() {
  const [selectedUser, setSelectedUser] = useState('All Users');
  const [selectedAction, setSelectedAction] = useState('All Actions');
  const [selectedDate, setSelectedDate] = useState('All Dates');
  const [selectedJobId, setSelectedJobId] = useState('All Job IDs');
  const [selectedStatus, setSelectedStatus] = useState('All Statuses');
  const [searchTerm, setSearchTerm] = useState('');

  const filteredLogs = MOCK_AUDIT_LOGS.filter((log) => {
    const matchesUser = selectedUser === 'All Users' || log.user.includes(selectedUser);
    const matchesAction = selectedAction === 'All Actions' || log.action === selectedAction;
    const matchesJob = selectedJobId === 'All Job IDs' || log.jobId === selectedJobId;
    const matchesStatus = selectedStatus === 'All Statuses' || log.status === selectedStatus;
    const matchesSearch =
      log.details.toLowerCase().includes(searchTerm.toLowerCase()) ||
      log.user.toLowerCase().includes(searchTerm.toLowerCase()) ||
      log.action.toLowerCase().includes(searchTerm.toLowerCase()) ||
      log.jobId.toLowerCase().includes(searchTerm.toLowerCase());

    return matchesUser && matchesAction && matchesJob && matchesStatus && matchesSearch;
  });

  const resetFilters = () => {
    setSelectedUser('All Users');
    setSelectedAction('All Actions');
    setSelectedDate('All Dates');
    setSelectedJobId('All Job IDs');
    setSelectedStatus('All Statuses');
    setSearchTerm('');
  };

  const getStatusBadge = (status: AuditLogEntry['status']) => {
    switch (status) {
      case 'Success':
        return (
          <span className="inline-flex items-center gap-1 rounded-full border border-emerald-200 bg-emerald-50 px-2 py-0.5 text-[10px] font-bold text-emerald-700">
            <CheckCircle2 className="h-3 w-3 text-emerald-600" /> Success
          </span>
        );
      case 'Warning':
        return (
          <span className="inline-flex items-center gap-1 rounded-full border border-amber-200 bg-amber-50 px-2 py-0.5 text-[10px] font-bold text-amber-700">
            <AlertTriangle className="h-3 w-3 text-amber-600" /> Warning
          </span>
        );
      case 'Flagged':
        return (
          <span className="inline-flex items-center gap-1 rounded-full border border-rose-200 bg-rose-50 px-2 py-0.5 text-[10px] font-bold text-rose-700">
            <AlertTriangle className="h-3 w-3 text-rose-600" /> Flagged
          </span>
        );
      case 'Info':
      default:
        return (
          <span className="inline-flex items-center gap-1 rounded-full border border-blue-200 bg-blue-50 px-2 py-0.5 text-[10px] font-bold text-blue-700">
            <Info className="h-3 w-3 text-blue-600" /> Info
          </span>
        );
    }
  };

  return (
    <div className="flex flex-col gap-6 py-2 animate-fade-in select-none">
      {/* ── Page Header ── */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-slate-200 pb-5">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <span className="inline-flex items-center gap-1.5 rounded-full border border-blue-200 bg-blue-50 px-2.5 py-0.5 text-[11px] font-semibold text-blue-700">
              <History className="h-3.5 w-3.5 text-blue-600" />
              <span>Audit Trail & Security Telemetry</span>
            </span>
            <span className="inline-flex items-center gap-1 rounded-full border border-slate-200 bg-slate-100 px-2.5 py-0.5 text-[11px] font-medium text-slate-700">
              <ShieldCheck className="h-3 w-3 text-emerald-600" />
              <span>Immutable System Log</span>
            </span>
          </div>

          <h1 className="text-2xl md:text-3xl font-extrabold tracking-tight text-slate-900">
            Audit History
          </h1>
          <p className="text-xs md:text-sm text-slate-500 mt-0.5">
            Complete traceability of user operations, dispatch overrides, system recommendations, and security events.
          </p>
        </div>
      </div>

      {/* ── Filter Placeholders Toolbar (User, Action, Date, Job ID, Status) ── */}
      <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-xs space-y-4">
        <div className="flex items-center justify-between border-b border-slate-200 pb-3">
          <div className="flex items-center gap-2">
            <Filter className="h-4 w-4 text-blue-600" />
            <h3 className="text-xs font-bold text-slate-900 uppercase tracking-wider">Audit Log Filters</h3>
          </div>
          <button
            onClick={resetFilters}
            className="flex items-center gap-1 text-[11px] font-semibold text-slate-500 hover:text-blue-600 transition-colors"
          >
            <RotateCcw className="h-3 w-3" /> Reset Filters
          </button>
        </div>

        {/* Filter Grid */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-3 text-xs">
          {/* 1. User Filter */}
          <div className="space-y-1">
            <label className="text-[10px] font-bold text-slate-500 uppercase tracking-wider flex items-center gap-1">
              <User className="h-3 w-3 text-blue-600" /> User
            </label>
            <select
              value={selectedUser}
              onChange={(e) => setSelectedUser(e.target.value)}
              className="w-full rounded-lg border border-slate-300 bg-slate-50 py-2 px-2.5 text-xs text-slate-800 focus:border-blue-500 focus:bg-white focus:outline-none"
            >
              <option value="All Users">All Users</option>
              <option value="Sarah Connor">Sarah Connor (Admin)</option>
              <option value="Priya Nair">Priya Nair (Dispatcher)</option>
              <option value="Marcus Vance">Marcus Vance (Tech)</option>
              <option value="Elena Rostova">Elena Rostova (Tech)</option>
              <option value="FieldOps AI">FieldOps AI Engine</option>
            </select>
          </div>

          {/* 2. Action Filter */}
          <div className="space-y-1">
            <label className="text-[10px] font-bold text-slate-500 uppercase tracking-wider flex items-center gap-1">
              <Tag className="h-3 w-3 text-purple-600" /> Action
            </label>
            <select
              value={selectedAction}
              onChange={(e) => setSelectedAction(e.target.value)}
              className="w-full rounded-lg border border-slate-300 bg-slate-50 py-2 px-2.5 text-xs text-slate-800 focus:border-blue-500 focus:bg-white focus:outline-none"
            >
              <option value="All Actions">All Actions</option>
              <option value="User Role Modified">User Role Modified</option>
              <option value="Manual Dispatch Override">Manual Dispatch Override</option>
              <option value="Service Request Created">Service Request Created</option>
              <option value="Technician Status Update">Technician Status Update</option>
              <option value="Job Completion Recorded">Job Completion Recorded</option>
              <option value="AI Recommendation Generated">AI Recommendation Generated</option>
            </select>
          </div>

          {/* 3. Date Filter */}
          <div className="space-y-1">
            <label className="text-[10px] font-bold text-slate-500 uppercase tracking-wider flex items-center gap-1">
              <Calendar className="h-3 w-3 text-emerald-600" /> Date Range
            </label>
            <select
              value={selectedDate}
              onChange={(e) => setSelectedDate(e.target.value)}
              className="w-full rounded-lg border border-slate-300 bg-slate-50 py-2 px-2.5 text-xs text-slate-800 focus:border-blue-500 focus:bg-white focus:outline-none"
            >
              <option value="All Dates">All Dates</option>
              <option value="Today">Today</option>
              <option value="Yesterday">Yesterday</option>
              <option value="Last 7 Days">Last 7 Days</option>
              <option value="Last 30 Days">Last 30 Days</option>
            </select>
          </div>

          {/* 4. Job ID Filter */}
          <div className="space-y-1">
            <label className="text-[10px] font-bold text-slate-500 uppercase tracking-wider flex items-center gap-1">
              <Tag className="h-3 w-3 text-amber-600" /> Job ID
            </label>
            <select
              value={selectedJobId}
              onChange={(e) => setSelectedJobId(e.target.value)}
              className="w-full rounded-lg border border-slate-300 bg-slate-50 py-2 px-2.5 text-xs text-slate-800 focus:border-blue-500 focus:bg-white focus:outline-none"
            >
              <option value="All Job IDs">All Job IDs</option>
              <option value="JOB-4829">JOB-4829</option>
              <option value="JOB-4830">JOB-4830</option>
              <option value="JOB-4831">JOB-4831</option>
              <option value="JOB-4832">JOB-4832</option>
            </select>
          </div>

          {/* 5. Status Filter */}
          <div className="space-y-1">
            <label className="text-[10px] font-bold text-slate-500 uppercase tracking-wider flex items-center gap-1">
              <ShieldCheck className="h-3 w-3 text-rose-600" /> Status
            </label>
            <select
              value={selectedStatus}
              onChange={(e) => setSelectedStatus(e.target.value)}
              className="w-full rounded-lg border border-slate-300 bg-slate-50 py-2 px-2.5 text-xs text-slate-800 focus:border-blue-500 focus:bg-white focus:outline-none"
            >
              <option value="All Statuses">All Statuses</option>
              <option value="Success">Success</option>
              <option value="Warning">Warning</option>
              <option value="Flagged">Flagged</option>
              <option value="Info">Info</option>
            </select>
          </div>
        </div>

        {/* Text Filter Input */}
        <div className="pt-2 border-t border-slate-200 flex items-center gap-2">
          <div className="relative flex-1">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-slate-400" />
            <input
              type="text"
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              placeholder="Search audit details, users, actions..."
              className="w-full rounded-lg border border-slate-300 bg-slate-50 py-1.5 pl-9 pr-3 text-xs text-slate-800 placeholder:text-slate-400 focus:border-blue-500 focus:bg-white focus:outline-none"
            />
          </div>
          <span className="text-[11px] text-slate-500 font-mono">
            Showing {filteredLogs.length} of {MOCK_AUDIT_LOGS.length} records
          </span>
        </div>
      </div>

      {/* ── Audit Log Table ── */}
      <div className="rounded-xl border border-slate-200 bg-white overflow-hidden shadow-xs">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead className="bg-slate-50 border-b border-slate-200 text-[10px] uppercase tracking-wider text-slate-500 font-bold">
              <tr>
                <th className="py-3 px-4">Log ID</th>
                <th className="py-3 px-4">Timestamp</th>
                <th className="py-3 px-4">User</th>
                <th className="py-3 px-4">Action</th>
                <th className="py-3 px-4">Job ID</th>
                <th className="py-3 px-4">Status</th>
                <th className="py-3 px-4">Details</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100 text-slate-700">
              {filteredLogs.length > 0 ? (
                filteredLogs.map((log) => (
                  <tr key={log.id} className="hover:bg-slate-50/80 transition-colors">
                    <td className="py-3 px-4 font-mono font-bold text-blue-600">{log.id}</td>
                    <td className="py-3 px-4 font-mono text-slate-500 whitespace-nowrap">{log.timestamp}</td>
                    <td className="py-3 px-4 font-semibold text-slate-900 whitespace-nowrap">{log.user}</td>
                    <td className="py-3 px-4 font-medium text-slate-800 whitespace-nowrap">{log.action}</td>
                    <td className="py-3 px-4 font-mono text-amber-700 font-semibold">{log.jobId}</td>
                    <td className="py-3 px-4">{getStatusBadge(log.status)}</td>
                    <td className="py-3 px-4 text-slate-600 max-w-md truncate">{log.details}</td>
                  </tr>
                ))
              ) : (
                <tr>
                  <td colSpan={7} className="py-8 text-center text-slate-500">
                    No audit records match the selected filter criteria.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
