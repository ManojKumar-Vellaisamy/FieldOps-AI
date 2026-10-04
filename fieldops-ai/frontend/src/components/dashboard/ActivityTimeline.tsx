import {
  Sparkles,
  PlusCircle,
  UserCheck,
  ShieldAlert,
  Server,
  Activity,
} from 'lucide-react';
import type { ActivityItem, ActivityType } from '@/types/dashboard.types';
import { cn } from '@/utils/cn';

interface ActivityTimelineProps {
  activities: ActivityItem[];
  className?: string;
  isLoading?: boolean;
  error?: string | null;
}

const activityIconMap: Record<ActivityType, { icon: typeof Activity; style: string }> = {
  recommendation: { icon: Sparkles, style: 'bg-purple-50 text-purple-700 border-purple-200' },
  dispatcher: { icon: PlusCircle, style: 'bg-blue-50 text-blue-700 border-blue-200' },
  create: { icon: PlusCircle, style: 'bg-blue-50 text-blue-700 border-blue-200' },
  technician: { icon: UserCheck, style: 'bg-emerald-50 text-emerald-700 border-emerald-200' },
  assign: { icon: UserCheck, style: 'bg-emerald-50 text-emerald-700 border-emerald-200' },
  availability: { icon: UserCheck, style: 'bg-emerald-50 text-emerald-700 border-emerald-200' },
  warning: { icon: ShieldAlert, style: 'bg-amber-50 text-amber-800 border-amber-200' },
  override: { icon: ShieldAlert, style: 'bg-amber-50 text-amber-800 border-amber-200' },
  system: { icon: Server, style: 'bg-slate-100 text-slate-600 border-slate-200' },
};

export function ActivityTimeline({
  activities,
  className,
  isLoading = false,
  error = null,
}: ActivityTimelineProps) {
  return (
    <div
      className={cn(
        'rounded-xl border border-slate-200 bg-white p-5 shadow-xs select-none',
        className,
      )}
    >
      <div className="flex items-center justify-between border-b border-slate-100 pb-3 mb-4">
        <div>
          <h3 className="text-sm font-bold text-slate-900 tracking-tight">Recent Activity</h3>
          <p className="text-[11px] text-slate-500 font-medium">Live operational telemetry feed</p>
        </div>
        <span
          className={cn(
            'flex h-2 w-2 rounded-full',
            error ? 'bg-amber-400' : 'bg-emerald-500 animate-pulse',
          )}
          title={error ? 'Telemetry Unavailable' : 'Live Stream Active'}
        />
      </div>

      {isLoading ? (
        <div className="py-8 text-center text-xs text-slate-400 font-medium">
          Loading operational telemetry...
        </div>
      ) : error ? (
        <div className="py-8 text-center text-xs text-slate-500 font-medium">
          {error}
        </div>
      ) : activities.length === 0 ? (
        <div className="py-8 text-center text-xs text-slate-400 font-medium">
          No recent operational activity recorded
        </div>
      ) : (
        <div className="relative pl-3 space-y-4 before:absolute before:left-5 before:top-2 before:bottom-2 before:w-0.5 before:bg-slate-200">
          {activities.map((act) => {
            const config = activityIconMap[act.type] || activityIconMap.create;
            const Icon = config.icon;

            return (
              <div key={act.id} className="relative flex items-start gap-3 group">
                <div
                  className={cn(
                    'relative z-10 flex h-7 w-7 shrink-0 items-center justify-center rounded-full border shadow-2xs transition-transform duration-200 group-hover:scale-110',
                    config.style,
                  )}
                >
                  <Icon className="h-3.5 w-3.5" />
                </div>

                <div className="flex-1 min-w-0 pt-0.5">
                  <div className="flex items-center justify-between gap-2">
                    <h4 className="text-xs font-bold text-slate-800 truncate">{act.title}</h4>
                    <span className="text-[10px] font-mono text-slate-400 shrink-0 font-medium">{act.timestamp}</span>
                  </div>
                  <p className="text-[11px] text-slate-600 leading-relaxed mt-0.5">{act.description}</p>
                  <span className="inline-block mt-1 text-[10px] font-medium text-slate-400">
                    By <span className="text-slate-700 font-semibold">{act.actor}</span>
                  </span>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
