import { Briefcase, Users, Clock, AlertCircle, Cpu, Gauge, TrendingUp, TrendingDown, Minus } from 'lucide-react';
import type { KPIStat } from '@/types/dashboard.types';
import { cn } from '@/utils/cn';

interface StatCardProps {
  stat: KPIStat;
  className?: string;
}

const iconMap = {
  Briefcase,
  Users,
  Clock,
  AlertCircle,
  Cpu,
  Gauge,
};

export function StatCard({ stat, className }: StatCardProps) {
  const Icon = iconMap[stat.iconName] || Briefcase;

  const trendIcon =
    stat.trend === 'increase' ? (
      <TrendingUp className="h-3.5 w-3.5 text-emerald-600" />
    ) : stat.trend === 'decrease' ? (
      <TrendingDown className="h-3.5 w-3.5 text-blue-600" />
    ) : (
      <Minus className="h-3.5 w-3.5 text-slate-400" />
    );

  const trendBadgeStyle =
    stat.trend === 'increase'
      ? 'bg-emerald-50 text-emerald-700 border-emerald-200'
      : stat.trend === 'decrease'
      ? 'bg-blue-50 text-blue-700 border-blue-200'
      : 'bg-slate-100 text-slate-600 border-slate-200';

  return (
    <div
      className={cn(
        'group relative flex flex-col justify-between rounded-xl border border-slate-200 bg-white p-5 shadow-xs',
        'transition-all duration-200 hover:border-slate-300 hover:shadow-sm select-none',
        className,
      )}
    >
      <div>
        <div className="flex items-center justify-between">
          <div className="flex h-10 w-10 items-center justify-center rounded-lg border border-blue-100 bg-blue-50 text-blue-600 transition-transform duration-200 group-hover:scale-105">
            <Icon className="h-5 w-5" />
          </div>

          <div
            className={cn(
              'flex items-center gap-1 rounded-full border px-2 py-0.5 text-xs font-bold',
              trendBadgeStyle,
            )}
          >
            {trendIcon}
            <span>{stat.change}</span>
          </div>
        </div>

        <div className="mt-4">
          <span className="text-2xl sm:text-3xl font-extrabold tracking-tight text-slate-900 font-mono">
            {stat.value}
          </span>
          <h3 className="mt-1 text-xs font-bold text-slate-500 uppercase tracking-wider">
            {stat.title}
          </h3>
        </div>
      </div>

      <div className="mt-4 border-t border-slate-100 pt-2.5">
        <span className="text-[11px] font-medium text-slate-500">{stat.subtitle}</span>
      </div>
    </div>
  );
}
