import { Suspense, type ReactNode } from 'react';
import { LoadingScreen } from '@/components/ui/LoadingScreen';

interface AppLayoutProps {
  children: ReactNode;
}

/**
 * Top-level app layout wrapper.
 * Provides a Suspense boundary with a full-screen loading fallback.
 */
export function AppLayout({ children }: AppLayoutProps) {
  return (
    <Suspense fallback={<LoadingScreen />}>
      <div id="app-root" className="min-h-screen bg-surface-950 font-sans antialiased">
        {children}
      </div>
    </Suspense>
  );
}
