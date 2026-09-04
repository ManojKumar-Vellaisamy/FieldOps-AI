import type { ReactNode } from 'react';
import { Navigate } from 'react-router-dom';
import { useAuth } from '@/contexts/AuthContext';
import { LoadingScreen } from '@/components/ui/LoadingScreen';
import type { UserRole } from '@/types/auth.types';

interface RoleGuardProps {
  children?: ReactNode;
  allowedRoles: UserRole[];
}

/**
 * Enterprise Role Guard:
 * Strictly validates authenticated user.role against allowedRoles array.
 * Dynamically redirects unauthorized users directly to their role workspace.
 */
export function RoleGuard({ children, allowedRoles }: RoleGuardProps) {
  const { user, isLoading } = useAuth();

  if (isLoading) {
    return <LoadingScreen message="Checking role permissions..." />;
  }

  if (!user) {
    return <Navigate to="/login" replace />;
  }

  if (!allowedRoles.includes(user.role)) {
    // Dynamic workspace redirect based on role
    const defaultRoute =
      user.role === 'Administrator'
        ? '/admin'
        : user.role === 'Technician'
        ? '/technician'
        : '/dashboard';

    return <Navigate to={defaultRoute} replace />;
  }

  return children ? <>{children}</> : null;
}
