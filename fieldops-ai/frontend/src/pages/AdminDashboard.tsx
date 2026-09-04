import { useState } from 'react';
import { Users, UserCheck, Wrench, ShieldCheck, Activity, Server, Database, CheckCircle2, Plus, UserPlus, Check } from 'lucide-react';
import { useAuth } from '@/contexts/AuthContext';

export default function AdminDashboard() {
  const { user } = useAuth();
  const [actionNotice, setActionNotice] = useState<string | null>(null);

  const triggerNotice = (msg: string) => {
    setActionNotice(msg);
    setTimeout(() => setActionNotice(null), 3000);
  };

  const ADMIN_STATS = [
    {
      id: 'stat-users',
      title: 'Total Users',
      value: '24',
      subtitle: '3 Administrators • 5 Dispatchers',
      icon: Users,
      color: 'text-blue-600',
      bgColor: 'bg-blue-50 border-blue-200',
    },
    {
      id: 'stat-techs',
      title: 'Total Technicians',
      value: '16',
      subtitle: 'Active field workforce',
      icon: UserCheck,
      color: 'text-purple-600',
      bgColor: 'bg-purple-50 border-purple-200',
    },
    {
      id: 'stat-available-techs',
      title: 'Available Technicians',
      value: '12 / 16',
      subtitle: '75% ready for assignment',
      icon: CheckCircle2,
      color: 'text-emerald-600',
      bgColor: 'bg-emerald-50 border-emerald-200',
    },
    {
      id: 'stat-skills',
      title: 'Configured Skills',
      value: '8 Categories',
      subtitle: 'HVAC, Fiber, High Voltage & Precision',
      icon: Wrench,
      color: 'text-amber-600',
      bgColor: 'bg-amber-50 border-amber-200',
    },
  ];

  const SKILL_DISTRIBUTION = [
    { name: 'HVAC Master', count: 5, percentage: 31 },
    { name: 'Fiber Optics & Telecom', count: 4, percentage: 25 },
    { name: 'High Voltage Electrical', count: 3, percentage: 19 },
    { name: 'Precision Calibration', count: 2, percentage: 13 },
    { name: 'Medical Equipment Repair', count: 2, percentage: 12 },
  ];

  const RECENT_USER_ACTIVITY = [
    {
      id: 'usr-act-1',
      action: 'Role Modified',
      details: 'User Marcus Vance role changed to Dispatcher',
      time: '15m ago',
      actor: 'Sarah Connor (Admin)',
    },
    {
      id: 'usr-act-2',
      action: 'New Account Created',
      details: 'Created technician user account for Elena Rostova',
      time: '1h ago',
      actor: 'Sarah Connor (Admin)',
    },
    {
      id: 'usr-act-3',
      action: 'Skill Certified',
      details: 'Added High Voltage Certification to Alex Rivera',
      time: '3h ago',
      actor: 'Sarah Connor (Admin)',
    },
    {
      id: 'usr-act-4',
      action: 'Password Reset',
      details: 'Initiated secure reset token for tech@fieldops.ai',
      time: '5h ago',
      actor: 'System Security',
    },
  ];

  const SYSTEM_HEALTH = [
    { component: 'FastAPI Backend Core', status: 'Operational', latency: '24ms', icon: Server, color: 'text-emerald-600' },
    { component: 'PostgreSQL Async Database', status: 'Healthy', latency: '12ms', icon: Database, color: 'text-emerald-600' },
    { component: 'Auth & JWT Security Engine', status: 'Operational', latency: '8ms', icon: ShieldCheck, color: 'text-emerald-600' },
  ];

  return (
    <div className="flex flex-col gap-6 py-2 animate-fade-in select-none">
      {/* ── Workspace Header ── */}
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
            Administration Workspace
          </h1>
          <p className="text-xs md:text-sm text-slate-500 mt-0.5">
            Manage users, technicians, skills, audit records and platform configuration.
          </p>
        </div>

        {/* Primary Actions Toolbar (+ Add User, + Add Technician, Manage Skills) */}
        <div className="flex flex-col gap-2">
          <div className="flex flex-wrap items-center gap-2.5">
            <button
              onClick={() => triggerNotice('Add User modal triggered.')}
              className="flex items-center gap-2 rounded-xl bg-purple-600 px-4 py-2 text-xs font-semibold text-white shadow-xs transition-all hover:bg-purple-700 active:scale-[0.98] cursor-pointer"
            >
              <Plus className="h-4 w-4" />
              <span>Add User</span>
            </button>

            <button
              onClick={() => triggerNotice('Add Technician form triggered.')}
              className="flex items-center gap-2 rounded-xl border border-slate-200 bg-white px-4 py-2 text-xs font-semibold text-slate-700 shadow-xs transition-all hover:bg-slate-50 hover:border-slate-300 active:scale-[0.98] cursor-pointer"
            >
              <UserPlus className="h-4 w-4 text-purple-600" />
              <span>Add Technician</span>
            </button>

            <button
              onClick={() => triggerNotice('Manage Skills taxonomy opened.')}
              className="flex items-center gap-2 rounded-xl border border-slate-200 bg-white px-4 py-2 text-xs font-semibold text-slate-700 shadow-xs transition-all hover:bg-slate-50 hover:border-slate-300 active:scale-[0.98] cursor-pointer"
            >
              <Wrench className="h-4 w-4 text-amber-600" />
              <span>Manage Skills</span>
            </button>
          </div>

          {actionNotice && (
            <div className="flex items-center gap-2 text-xs font-medium text-emerald-700 bg-emerald-50 border border-emerald-200 px-3 py-1.5 rounded-lg animate-fade-in w-fit self-start md:self-end">
              <Check className="h-3.5 w-3.5 text-emerald-600" />
              <span>{actionNotice}</span>
            </div>
          )}
        </div>
      </div>

      {/* ── Top KPI Stat Cards Grid (4 Cards) ── */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {ADMIN_STATS.map((stat) => {
          const Icon = stat.icon;
          return (
            <div
              key={stat.id}
              className="flex flex-col justify-between rounded-xl border border-slate-200 bg-white p-5 shadow-xs transition-all hover:border-slate-300 hover:shadow-md"
            >
              <div>
                <div className="flex items-center justify-between">
                  <div className={`flex h-10 w-10 items-center justify-center rounded-lg border ${stat.bgColor}`}>
                    <Icon className={`h-5 w-5 ${stat.color}`} />
                  </div>
                </div>
                <div className="mt-3.5">
                  <h3 className="text-[11px] font-bold uppercase tracking-wider text-slate-400 leading-none mb-1">
                    {stat.title}
                  </h3>
                  <div className="text-2xl sm:text-3xl font-extrabold tracking-tight text-slate-900 leading-none">
                    {stat.value}
                  </div>
                </div>
              </div>
              <div className="mt-3.5 border-t border-slate-100 pt-2.5">
                <span className="text-[11px] font-medium text-slate-500 leading-snug">{stat.subtitle}</span>
              </div>
            </div>
          );
        })}
      </div>

      {/* ── Middle Grid: Skill Distribution & System Health ── */}
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        {/* Left 2 Cols: Skill Distribution & System Telemetry */}
        <div className="lg:col-span-2 flex flex-col gap-6">
          {/* Skill Taxonomy Distribution */}
          <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-xs">
            <div className="flex items-center justify-between border-b border-slate-100 pb-3 mb-4">
              <div>
                <h3 className="text-sm font-bold text-slate-900 tracking-tight leading-snug">Skill Distribution</h3>
                <p className="text-[11px] font-medium text-slate-500 leading-snug mt-0.5">Technician workforce capability breakdown</p>
              </div>
              <span className="inline-flex items-center gap-1 rounded-full border border-amber-200 bg-amber-50 px-2.5 py-0.5 text-[11px] font-semibold text-amber-700">
                <Wrench className="h-3 w-3" />
                <span>5 Active Skill Matrix</span>
              </span>
            </div>

            <div className="space-y-4">
              {SKILL_DISTRIBUTION.map((item) => (
                <div key={item.name} className="space-y-1.5">
                  <div className="flex justify-between text-xs font-semibold">
                    <span className="text-slate-800">{item.name}</span>
                    <span className="text-slate-500 font-mono">{item.count} Techs ({item.percentage}%)</span>
                  </div>
                  <div className="h-2 w-full overflow-hidden rounded-full bg-slate-100 border border-slate-200">
                    <div
                      className="h-full rounded-full bg-gradient-to-r from-blue-600 to-purple-600 transition-all duration-500"
                      style={{ width: `${item.percentage * 3}%` }}
                    />
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* System Health */}
          <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-xs">
            <div className="flex items-center justify-between border-b border-slate-100 pb-3 mb-4">
              <div>
                <h3 className="text-sm font-bold text-slate-900 tracking-tight leading-snug">System Health & Infrastructure</h3>
                <p className="text-[11px] font-medium text-slate-500 leading-snug mt-0.5">Real-time core backend service diagnostics</p>
              </div>
              <span className="flex h-2.5 w-2.5 rounded-full bg-emerald-500 animate-pulse" title="System Operational" />
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
              {SYSTEM_HEALTH.map((sys) => {
                const Icon = sys.icon;
                return (
                  <div key={sys.component} className="rounded-lg border border-slate-200 bg-slate-50 p-3.5 flex flex-col justify-between">
                    <div className="flex items-center gap-2 mb-2">
                      <Icon className="h-4 w-4 text-blue-600 shrink-0" />
                      <span className="text-xs font-bold text-slate-800 truncate">{sys.component}</span>
                    </div>
                    <div className="flex items-center justify-between text-[11px]">
                      <span className={`font-semibold ${sys.color}`}>{sys.status}</span>
                      <span className="font-mono text-slate-500">{sys.latency}</span>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        </div>

        {/* Right Col: Recent User Activity Feed */}
        <div className="lg:col-span-1">
          <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-xs h-full flex flex-col">
            <div className="flex items-center justify-between border-b border-slate-100 pb-3 mb-4">
              <div>
                <h3 className="text-sm font-bold text-slate-900 tracking-tight leading-snug">Recent User Activity</h3>
                <p className="text-[11px] font-medium text-slate-500 leading-snug mt-0.5">User management audit stream</p>
              </div>
              <Activity className="h-4 w-4 text-slate-400" />
            </div>

            <div className="space-y-4 flex-1">
              {RECENT_USER_ACTIVITY.map((act) => (
                <div key={act.id} className="rounded-lg border border-slate-200 bg-slate-50 p-3 text-xs space-y-1">
                  <div className="flex justify-between items-center">
                    <span className="font-bold text-slate-800">{act.action}</span>
                    <span className="text-[10px] font-mono text-slate-400">{act.time}</span>
                  </div>
                  <p className="text-[11px] text-slate-600 leading-relaxed">{act.details}</p>
                  <span className="inline-block text-[10px] font-semibold text-purple-700">By {act.actor}</span>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

