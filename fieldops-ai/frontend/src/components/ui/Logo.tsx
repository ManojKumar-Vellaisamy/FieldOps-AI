import { cn } from '@/utils/cn';

interface LogoProps {
  collapsed?: boolean;
  className?: string;
}

/**
 * Premium FieldOps AI Brand Logo.
 * Combines a modern AI Spark + Route Pin concept with flat SVG design.
 */
export function Logo({ collapsed = false, className }: LogoProps) {
  return (
    <div className={cn('flex items-center gap-3 select-none', className)}>
      {/* Premium Gradient Icon Container */}
      <div className="relative flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-gradient-to-br from-blue-600 to-blue-500 shadow-sm shadow-blue-500/25 ring-1 ring-white/20">
        <svg
          width="20"
          height="20"
          viewBox="0 0 24 24"
          fill="none"
          xmlns="http://www.w3.org/2000/svg"
          className="text-white"
          aria-hidden="true"
        >
          {/* Modern Route Pin Body */}
          <path
            d="M12 2C8.13401 2 5 5.13401 5 9C5 14.25 12 22 12 22C12 22 19 14.25 19 9C19 5.13401 15.866 2 12 2Z"
            fill="currentColor"
            fillOpacity="0.9"
          />
          {/* Central AI Node Circle */}
          <circle cx="12" cy="9" r="2.8" fill="#1D4ED8" />
          {/* AI Node Cross Hair Sparkle */}
          <path
            d="M12 7.2V10.8M10.2 9H13.8"
            stroke="#93C5FD"
            strokeWidth="1.2"
            strokeLinecap="round"
          />
          <circle cx="12" cy="9" r="0.9" fill="#FFFFFF" />
        </svg>
      </div>

      {/* Wordmark & Subtitle */}
      {!collapsed && (
        <div className="flex flex-col justify-center leading-none gap-0.5">
          <span className="text-sm font-bold tracking-tight text-slate-900 leading-none">
            FieldOps <span className="text-blue-600 font-extrabold">AI</span>
          </span>
          <span className="text-[10px] font-medium tracking-tight text-slate-500 leading-none">
            Context-Aware Dispatch Platform
          </span>
        </div>
      )}
    </div>
  );
}
