import type { ReactNode } from 'react';
import { Navigate, useLocation } from 'react-router-dom';
import { useAuth } from '@/contexts/AuthContext';
import { LoadingScreen } from '@/components/ui/LoadingScreen';
import { MustChangePasswordModal } from '@/components/auth/MustChangePasswordModal';

interface ProtectedRouteProps {
  children: ReactNode;
}

/**
 * Global authentication guard ensuring a valid active session.
 * Unauthenticated users are redirected to /login.
 * Enforces mandatory password change for users flagged with must_change_password.
 */
export function ProtectedRoute({ children }: ProtectedRouteProps) {
  const { isAuthenticated, isLoading, user } = useAuth();
  const location = useLocation();

  if (isLoading) {
    return <LoadingScreen message="Verifying session credentials..." />;
  }

  if (!isAuthenticated || !user) {
    return <Navigate to="/login" state={{ from: location }} replace />;
  }

  if (user.must_change_password) {
    return <MustChangePasswordModal />;
  }

  return <>{children}</>;
}

