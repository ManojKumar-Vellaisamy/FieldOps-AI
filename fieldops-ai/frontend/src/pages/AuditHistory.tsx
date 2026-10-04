import { useState, useEffect, useCallback, useMemo } from 'react';
import {
  History,
  Filter,
  Search,
  RotateCcw,
  ShieldCheck,
  User,
  Calendar,
  Tag,
  CheckCircle2,
  AlertTriangle,
  Info,
} from 'lucide-react';
import apiClient from '@/services/api';

interface AuditLogEntry {
  id: string;
  timestamp: string;
  rawTimestamp?: string;
  user: string;
  action: string;
  jobId: string;
  status: 'Success' | 'Warning' | 'Flagged' | 'Info';
  details: string;
}

export default function AuditHistoryPage() {
  const [logs, setLogs] = useState<AuditLogEntry[]>([]);
  const [totalCount, setTotalCount] = useState<number>(0);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  const [selectedUser, setSelectedUser] = useState('All Users');
  const [selectedAction, setSelectedAction] = useState('All Actions');
  const [selectedDate, setSelectedDate] = useState('All Dates');
  const [selectedJobId, setSelectedJobId] = useState('All Job IDs');
  const [selectedStatus, setSelectedStatus] = useState('All Statuses');
  const [searchTerm, setSearchTerm] = useState('');

  const fetchAuditLogs = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      // Use the correct API endpoint path without double /api/v1 prefix
      const response = await apiClient.get('/audit-logs?page_size=50');
      if (response.data && Array.isArray(response.data.items)) {
        const mapped: AuditLogEntry[] = response.data.items.map((item: {
          id?: string;
          created_at?: string;
          user_full_name?: string | null;
          action?: string;
          entity?: string;
          entity_id?: string | null;
          reason?: string | null;
        }) => {
          let statusVal: AuditLogEntry['status'] = 'Success';
          const actionUpper = (item.action || '').toUpperCase();
          if (
            actionUpper.includes('OVERRIDE') ||
            actionUpper.includes('UNASSIGNED') ||
            actionUpper.includes('CANCELLED')
          ) {
            statusVal = 'Warning';
          } else if (actionUpper.includes('FAILED') || actionUpper.includes('DENIED')) {
            statusVal = 'Flagged';
          } else if (
            actionUpper.includes('GET') ||
            actionUpper.includes('VIEW') ||
            actionUpper.includes('RECOMMENDATION')
          ) {
            statusVal = 'Info';
          }

          const rawId = item.id ? String(item.id) : '';
          const entityIdStr = item.entity_id ? String(item.entity_id) : '';

          return {
            id: rawId.length > 8 ? rawId.substring(0, 8).toUpperCase() : rawId || 'AUD-LOG',
            timestamp: item.created_at ? new Date(item.created_at).toLocaleString() : 'N/A',
            rawTimestamp: item.created_at || '',
            user: item.user_full_name || 'System / Automated',
            action: item.action || 'Operational Event',
            jobId: entityIdStr
              ? entityIdStr.length > 12
                ? entityIdStr.substring(0, 8).toUpperCase()
                : entityIdStr
              : 'N/A',
            status: statusVal,
            details: item.reason || `${item.action || 'Event'} on ${item.entity || 'System'}`,
          };
        });

        setLogs(mapped);
        setTotalCount(typeof response.data.total === 'number' ? response.data.total : mapped.length);
      } else {
        setLogs([]);
        setTotalCount(0);
      }
    } catch (err: unknown) {
      console.error('[AuditHistory] Failed to fetch live audit logs:', err);
      setError('Audit service temporarily unavailable. Unable to load live records.');
      setLogs([]);
      setTotalCount(0);
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchAuditLogs();
  }, [fetchAuditLogs]);

  // Derive unique filter options dynamically from real audit records
  const uniqueUsers = useMemo(() => {
    const set = new Set<string>();
    logs.forEach((l) => {
      if (l.user) set.add(l.user);
    });
    return Array.from(set).sort();
  }, [logs]);

  const uniqueActions = useMemo(() => {
    const set = new Set<string>();
    logs.forEach((l) => {
      if (l.action) set.add(l.action);
    });
    return Array.from(set).sort();
  }, [logs]);

  const uniqueJobIds = useMemo(() => {
    const set = new Set<string>();
    logs.forEach((l) => {
      if (l.jobId && l.jobId !== 'N/A') set.add(l.jobId);
    });
    return Array.from(set).sort();
  }, [logs]);

  const filteredLogs = logs.filter((log) => {
    const matchesUser = selectedUser === 'All Users' || log.user === selectedUser;
    const matchesAction = selectedAction === 'All Actions' || log.action === selectedAction;
    const matchesJob = selectedJobId === 'All Job IDs' || log.jobId === selectedJobId;
    const matchesStatus = selectedStatus === 'All Statuses' || log.status === selectedStatus;

    let matchesDate = true;
    if (selectedDate !== 'All Dates' && log.rawTimestamp) {
      const logDate = new Date(log.rawTimestamp);
      const now = new Date();
      const diffDays = (now.getTime() - logDate.getTime()) / (1000 * 3600 * 24);
      if (selectedDate === 'Today') {
        matchesDate = logDate.toDateString() === now.toDateString();
      } else if (selectedDate === 'Yesterday') {
        const yesterday = new Date(now);
        yesterday.setDate(now.getDate() - 1);
        matchesDate = logDate.toDateString() === yesterday.toDateString();
      } else if (selectedDate === 'Last 7 Days') {
        matchesDate = diffDays <= 7;
      } else if (selectedDate === 'Last 30 Days') {
        matchesDate = diffDays <= 30;
      }
    }

    const matchesSearch =
      !searchTerm ||
      log.details.toLowerCase().includes(searchTerm.toLowerCase()) ||
      log.user.toLowerCase().includes(searchTerm.toLowerCase()) ||
      log.action.toLowerCase().includes(searchTerm.toLowerCase()) ||
      log.jobId.toLowerCase().includes(searchTerm.toLowerCase());

    return matchesUser && matchesAction && matchesDate && matchesJob && matchesStatus && matchesSearch;
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

        <button
          onClick={fetchAuditLogs}
          disabled={isLoading}
          className="flex items-center gap-1.5 rounded-lg border border-slate-200 bg-white px-3 py-1.5 text-xs font-semibold text-slate-700 shadow-2xs hover:bg-slate-50 disabled:opacity-50 transition-colors self-start md:self-auto"
        >
          <RotateCcw className={`h-3.5 w-3.5 ${isLoading ? 'animate-spin text-blue-600' : 'text-slate-500'}`} />
          <span>Refresh Records</span>
        </button>
      </div>

      {/* ── Filter Toolbar (User, Action, Date, Job ID, Status) ── */}
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
              {uniqueUsers.map((u) => (
                <option key={u} value={u}>
                  {u}
                </option>
              ))}
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
              {uniqueActions.map((a) => (
                <option key={a} value={a}>
                  {a}
                </option>
              ))}
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
              {uniqueJobIds.map((j) => (
                <option key={j} value={j}>
                  {j}
                </option>
              ))}
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
          <span className="text-[11px] text-slate-500 font-mono whitespace-nowrap">
            Showing {filteredLogs.length} of {totalCount} records
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
              {isLoading ? (
                <tr>
                  <td colSpan={7} className="py-12 text-center text-slate-500">
                    <div className="flex flex-col items-center justify-center gap-2">
                      <RotateCcw className="h-5 w-5 animate-spin text-blue-600" />
                      <span className="font-medium text-xs">Loading real audit records...</span>
                    </div>
                  </td>
                </tr>
              ) : error ? (
                <tr>
                  <td colSpan={7} className="py-12 text-center text-rose-700 bg-rose-50/50">
                    <div className="flex flex-col items-center justify-center gap-2">
                      <AlertTriangle className="h-5 w-5 text-rose-600" />
                      <span className="font-semibold text-xs">{error}</span>
                      <button
                        onClick={fetchAuditLogs}
                        className="mt-1 text-xs text-blue-600 hover:text-blue-800 underline font-medium cursor-pointer"
                      >
                        Retry Connection
                      </button>
                    </div>
                  </td>
                </tr>
              ) : filteredLogs.length > 0 ? (
                filteredLogs.map((log) => (
                  <tr key={log.id} className="hover:bg-slate-50/80 transition-colors">
                    <td className="py-3 px-4 font-mono font-bold text-blue-600">{log.id}</td>
                    <td className="py-3 px-4 font-mono text-slate-500 whitespace-nowrap">{log.timestamp}</td>
                    <td className="py-3 px-4 font-semibold text-slate-900 whitespace-nowrap">{log.user}</td>
                    <td className="py-3 px-4 font-medium text-slate-800 whitespace-nowrap">{log.action}</td>
                    <td className="py-3 px-4 font-mono text-amber-700 font-semibold">{log.jobId}</td>
                    <td className="py-3 px-4">{getStatusBadge(log.status)}</td>
                    <td className="py-3 px-4 text-slate-600 max-w-md truncate" title={log.details}>
                      {log.details}
                    </td>
                  </tr>
                ))
              ) : (
                <tr>
                  <td colSpan={7} className="py-12 text-center text-slate-500 font-medium">
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
