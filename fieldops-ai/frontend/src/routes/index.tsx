import { lazy } from 'react';
import { Navigate } from 'react-router-dom';
import type { RouteObject } from 'react-router-dom';
import { ProtectedRoute } from '@/guards/ProtectedRoute';
import { AdminLayout } from '@/layouts/AdminLayout';
import { DispatcherLayout } from '@/layouts/DispatcherLayout';
import { TechnicianLayout } from '@/layouts/TechnicianLayout';
import { useAuth } from '@/contexts/AuthContext';
import { LoadingScreen } from '@/components/ui/LoadingScreen';

// ── Lazy-loaded pages (code-split per route) ─────────────────────────────────
const LoginPage = lazy(() => import('@/pages/Login'));
const AdminDashboard = lazy(() => import('@/pages/AdminDashboard'));
const DispatcherDashboard = lazy(() => import('@/pages/DispatcherDashboard'));
const TechnicianDashboard = lazy(() => import('@/pages/TechnicianDashboard'));
const TechnicianManagement = lazy(() => import('@/pages/TechnicianManagement'));
const TechnicianDirectory = lazy(() => import('@/pages/TechnicianDirectory'));
const TechnicianProfile = lazy(() => import('@/pages/TechnicianProfile'));
const SkillsManagement = lazy(() => import('@/pages/SkillsManagement'));
const JobManagement = lazy(() => import('@/pages/JobManagement'));
const AuditHistoryPage = lazy(() => import('@/pages/AuditHistory'));
const NotFoundPage = lazy(() => import('@/pages/NotFound'));

/**
 * Root Redirector Component:
 * Evaluates authenticated user.role and dynamically redirects to the correct role workspace.
 */
function RootRedirect() {
  const { isAuthenticated, user, isLoading } = useAuth();

  if (isLoading) {
    return <LoadingScreen message="Resolving workspace..." />;
  }

  if (!isAuthenticated || !user) {
    return <Navigate to="/login" replace />;
  }

  switch (user.role) {
    case 'Administrator':
      return <Navigate to="/admin" replace />;
    case 'Technician':
      return <Navigate to="/technician" replace />;
    case 'Dispatcher':
    default:
      return <Navigate to="/dashboard" replace />;
  }
}

// ── Role-Based Enterprise Route Definitions ───────────────────────────────────
export const routes: RouteObject[] = [
  {
    path: '/login',
    element: <LoginPage />,
  },
  {
    path: '/',
    element: (
      <ProtectedRoute>
        <RootRedirect />
      </ProtectedRoute>
    ),
  },
  {
    path: '/admin',
    element: (
      <ProtectedRoute>
        <AdminLayout />
      </ProtectedRoute>
    ),
    children: [
      {
        index: true,
        element: <AdminDashboard />,
      },
      {
        path: 'technicians',
        element: <TechnicianManagement />,
      },
      {
        path: 'skills',
        element: <SkillsManagement />,
      },
      {
        path: 'audit-history',
        element: <AuditHistoryPage />,
      },
    ],
  },
  {
    path: '/dashboard',
    element: (
      <ProtectedRoute>
        <DispatcherLayout />
      </ProtectedRoute>
    ),
    children: [
      {
        index: true,
        element: <DispatcherDashboard />,
      },
      {
        path: 'jobs',
        element: <JobManagement />,
      },
      {
        path: 'technicians',
        element: <TechnicianDirectory />,
      },
      {
        path: 'skills',
        element: <SkillsManagement />,
      },
      {
        path: 'audit-history',
        element: <AuditHistoryPage />,
      },
    ],
  },
  {
    path: '/jobs',
    element: (
      <ProtectedRoute>
        <DispatcherLayout />
      </ProtectedRoute>
    ),
    children: [
      {
        index: true,
        element: <JobManagement />,
      },
    ],
  },
  {
    path: '/technicians',
    element: (
      <ProtectedRoute>
        <DispatcherLayout />
      </ProtectedRoute>
    ),
    children: [
      {
        index: true,
        element: <TechnicianDirectory />,
      },
    ],
  },
  {
    path: '/skills',
    element: (
      <ProtectedRoute>
        <AdminLayout />
      </ProtectedRoute>
    ),
    children: [
      {
        index: true,
        element: <SkillsManagement />,
      },
    ],
  },
  {
    path: '/audit-history',
    element: <Navigate to="/dashboard/audit-history" replace />,
  },
  {
    path: '/technician',
    element: (
      <ProtectedRoute>
        <TechnicianLayout />
      </ProtectedRoute>
    ),
    children: [
      {
        index: true,
        element: <TechnicianDashboard />,
      },
      {
        path: 'profile',
        element: <TechnicianProfile />,
      },
    ],
  },
  {
    path: '*',
    element: <NotFoundPage />,
  },
];
