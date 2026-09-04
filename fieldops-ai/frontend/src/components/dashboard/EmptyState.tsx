import type { ReactNode } from 'react';
import { SearchX } from 'lucide-react';

interface EmptyStateProps {
  title?: string;
  description?: string;
  action?: ReactNode;
  icon?: ReactNode;
}

export function EmptyState({
  title = 'No records found',
  description = 'No matching data criteria available at this time.',
  action,
  icon,
}: EmptyStateProps) {
  return (
    <div className="flex flex-col items-center justify-center p-8 text-center bg-slate-50/80 rounded-xl border border-dashed border-slate-300 my-4 select-none">
      <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-white text-slate-400 border border-slate-200 shadow-2xs mb-3">
        {icon || <SearchX className="h-6 w-6" />}
      </div>
      <h4 className="text-sm font-bold text-slate-800 mb-1">{title}</h4>
      <p className="text-xs text-slate-500 max-w-sm mb-4 leading-relaxed">{description}</p>
      {action}
    </div>
  );
}
