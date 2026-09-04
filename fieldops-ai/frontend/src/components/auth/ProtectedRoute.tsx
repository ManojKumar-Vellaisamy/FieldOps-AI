import type { ReactNode } from 'react';
import { Navigate, useLocation } from 'react-router-dom';
import { ShieldAlert } from 'lucide-react';
import { useAuth } from '@/contexts/AuthContext';
import { LoadingScreen } from '@/components/ui/LoadingScreen';
import type { UserRole } from '@/types/auth.types';

interface ProtectedRouteProps {
  children?: ReactNode;
  allowedRoles?: UserRole[];
}

export function ProtectedRoute({ children, allowedRoles }: ProtectedRouteProps) {
  const { isAuthenticated, isLoading, user, logout } = useAuth();
  const location = useLocation();

  if (isLoading) {
    return <LoadingScreen message="Verifying session credentials..." />;
  }

  if (!isAuthenticated || !user) {
    return <Navigate to="/login" state={{ from: location }} replace />;
  }

  if (allowedRoles && !allowedRoles.includes(user.role)) {
    return (
      <div className="flex h-screen w-full flex-col items-center justify-center bg-surface-950 px-4 text-center">
        <div className="flex h-16 w-16 items-center justify-center rounded-2xl bg-danger-500/10 text-danger-400 ring-1 ring-danger-500/20 mb-6 animate-pulse">
          <ShieldAlert className="h-8 w-8" />
        </div>
        <h1 className="text-2xl font-bold text-surface-50 mb-2">Access Restricted</h1>
        <p className="max-w-md text-sm text-surface-400 mb-6">
          Your role (<span className="font-semibold text-surface-200">{user.role}</span>) does not have authorization to view this platform area. Contact your administrator to request access.
        </p>
        <div className="flex items-center gap-3">
          <a
            href="/"
            className="rounded-lg bg-surface-800 px-4 py-2 text-sm font-medium text-surface-200 transition-colors hover:bg-surface-700"
          >
            Back to Dashboard
          </a>
          <button
            onClick={() => logout()}
            className="rounded-lg bg-danger-600/20 px-4 py-2 text-sm font-medium text-danger-300 ring-1 ring-danger-500/30 transition-colors hover:bg-danger-600/30"
          >
            Sign Out
          </button>
        </div>
      </div>
    );
  }

  return children ? <>{children}</> : null;
}
