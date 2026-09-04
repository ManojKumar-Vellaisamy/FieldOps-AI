import { Sparkles, Cpu } from 'lucide-react';
import type { Recommendation } from '@/types/dashboard.types';
import { cn } from '@/utils/cn';

interface RecommendationCardProps {
  recommendation?: Recommendation;
  onApplyRecommendation?: (rec: Recommendation) => void;
  className?: string;
}

export function RecommendationCard({
  className,
}: RecommendationCardProps) {
  return (
    <div
      className={cn(
        'relative overflow-hidden rounded-xl border border-slate-200 bg-white p-5 shadow-xs select-none flex flex-col justify-between',
        className,
      )}
    >
      {/* Header Badge */}
      <div className="flex items-center justify-between mb-4">
        <div className="inline-flex items-center gap-1.5 rounded-full border border-purple-200 bg-purple-50 px-2.5 py-1 text-xs font-bold text-purple-700">
          <Sparkles className="h-3.5 w-3.5" />
          <span>Smart Assignment Engine</span>
        </div>

        <div className="flex items-center gap-1.5 rounded-md border border-slate-200 bg-slate-100 px-2.5 py-0.5 text-[11px] font-bold text-slate-500">
          <span>Awaiting context analysis</span>
        </div>
      </div>

      {/* State Banner */}
      <div className="rounded-lg border border-slate-200 bg-slate-50 p-4 space-y-2 text-center my-auto">
        <div className="flex justify-center">
          <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-purple-100 text-purple-700 border border-purple-200">
            <Cpu className="h-5 w-5" />
          </div>
        </div>
        <div className="text-xs font-bold text-slate-900">Smart Assignment & AI Dispatch</div>
        <p className="text-[11px] text-slate-600 max-w-xs mx-auto leading-relaxed">
          AI recommendations and automated technician match scoring will become operational in subsequent modules.
        </p>
        <span className="inline-block rounded-full bg-white px-2.5 py-0.5 text-[10px] font-mono text-slate-500 border border-slate-200">
          Not available yet
        </span>
      </div>
    </div>
  );
}
