import { Loader2 } from 'lucide-react';
import { APP_CONSTANTS } from '@/config/constants';
import { Logo } from './Logo';

interface LoadingScreenProps {
  message?: string;
}

/**
 * Full-screen loading screen displayed during app initialisation.
 */
export function LoadingScreen({ message }: LoadingScreenProps) {
  return (
    <div
      role="status"
      aria-label="Loading FieldOps AI"
      className="fixed inset-0 z-50 flex flex-col items-center justify-center gap-8 bg-surface-950"
    >
      {/* Radial glow backdrop */}
      <div
        aria-hidden="true"
        className="pointer-events-none absolute inset-0"
        style={{
          background:
            'radial-gradient(ellipse 60% 40% at 50% 50%, rgba(97,114,243,0.15) 0%, transparent 70%)',
        }}
      />

      <div className="relative flex flex-col items-center gap-6 animate-fade-in">
        {/* Logo */}
        <Logo className="scale-125" />

        {/* Spinner */}
        <Loader2 className="h-8 w-8 animate-spin text-brand-500" aria-hidden="true" />

        {/* Label */}
        <p className="text-sm font-medium text-surface-400 tracking-wide">
          {message || `Loading ${APP_CONSTANTS.APP_NAME}…`}
        </p>
      </div>
    </div>
  );
}

