import { useState } from 'react';
import { Plus, UserCheck, RotateCw, Check } from 'lucide-react';
import { cn } from '@/utils/cn';

interface QuickActionsProps {
  onNewJob?: () => void;
  onAssignTechnician?: () => void;
  onRefresh?: () => void;
  className?: string;
}

export function QuickActions({
  onNewJob,
  onAssignTechnician,
  onRefresh,
  className,
}: QuickActionsProps) {
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [actionNotice, setActionNotice] = useState<string | null>(null);

  const triggerNotice = (msg: string) => {
    setActionNotice(msg);
    setTimeout(() => setActionNotice(null), 3000);
  };

  const handleRefresh = () => {
    setIsRefreshing(true);
    onRefresh?.();
    triggerNotice('Dashboard data refreshed.');
    setTimeout(() => setIsRefreshing(false), 800);
  };

  const handleNewJob = () => {
    onNewJob?.();
    triggerNotice('New Job form placeholder triggered.');
  };

  const handleAssign = () => {
    onAssignTechnician?.();
    triggerNotice('Technician Assignment drawer triggered.');
  };

  return (
    <div className={cn('flex flex-col gap-2 select-none', className)}>
      <div className="flex flex-wrap items-center gap-2.5">
        {/* New Job Action */}
        <button
          onClick={handleNewJob}
          className="flex items-center gap-2 rounded-xl bg-blue-600 px-4 py-2.5 text-xs font-bold text-white shadow-xs transition-all hover:bg-blue-700 active:scale-[0.98]"
        >
          <Plus className="h-4 w-4" />
          <span>New Job</span>
        </button>

        {/* Assign Technician Action */}
        <button
          onClick={handleAssign}
          className="flex items-center gap-2 rounded-xl border border-slate-200 bg-white px-4 py-2.5 text-xs font-bold text-slate-800 shadow-2xs transition-all hover:bg-slate-50 active:scale-[0.98]"
        >
          <UserCheck className="h-4 w-4 text-blue-600" />
          <span>Assign Technician</span>
        </button>

        {/* Refresh Dashboard Action */}
        <button
          onClick={handleRefresh}
          disabled={isRefreshing}
          aria-label="Refresh dashboard data"
          className="flex h-9 w-9 items-center justify-center rounded-xl border border-slate-200 bg-white text-slate-600 shadow-2xs transition-all hover:bg-slate-50 hover:text-slate-900 disabled:opacity-50"
        >
          <RotateCw className={cn('h-4 w-4', isRefreshing && 'animate-spin text-blue-600')} />
        </button>
      </div>

      {/* Action Notification Banner */}
      {actionNotice && (
        <div className="flex items-center gap-2 text-xs font-bold text-emerald-800 bg-emerald-50 border border-emerald-200 px-3 py-1.5 rounded-lg animate-fade-in w-fit">
          <Check className="h-3.5 w-3.5 text-emerald-600" />
          <span>{actionNotice}</span>
        </div>
      )}
    </div>
  );
}
