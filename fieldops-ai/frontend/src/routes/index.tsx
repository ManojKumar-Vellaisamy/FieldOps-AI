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
const UserManagement = lazy(() => import('@/pages/UserManagement'));
const SettingsPage = lazy(() => import('@/pages/SettingsPage'));
const DispatcherDashboard = lazy(() => import('@/pages/DispatcherDashboard'));
const SmartAssignmentPage = lazy(() => import('@/pages/SmartAssignmentPage'));
const LiveMapPage = lazy(() => import('@/pages/LiveMapPage'));
const AnalyticsPage = lazy(() => import('@/pages/AnalyticsPage'));
const ETAPerformancePage = lazy(() => import('@/pages/ETAPerformancePage'));
const TechnicianDashboard = lazy(() => import('@/pages/TechnicianDashboard'));
const TechnicianJobsPage = lazy(() => import('@/pages/TechnicianJobsPage'));
const TechnicianSchedulePage = lazy(() => import('@/pages/TechnicianSchedulePage'));
const TechnicianRoutePage = lazy(() => import('@/pages/TechnicianRoutePage'));
const TechnicianStatusPage = lazy(() => import('@/pages/TechnicianStatusPage'));
const TechnicianManagement = lazy(() => import('@/pages/TechnicianManagement'));
const TechnicianDirectory = lazy(() => import('@/pages/TechnicianDirectory'));
const TechnicianProfile = lazy(() => import('@/pages/TechnicianProfile'));
const SkillsManagement = lazy(() => import('@/pages/SkillsManagement'));
const JobManagement = lazy(() => import('@/pages/JobManagement'));
const AuditHistoryPage = lazy(() => import('@/pages/AuditHistory'));
const NotFoundPage = lazy(() => import('@/pages/NotFound'));

// ── Account & Security Pages ──────────────────────────────────────────────────
const AccountLayout = lazy(() =>
  import('@/layouts/AccountLayout').then((m) => ({ default: m.AccountLayout })),
);
const ProfileSettingsPage = lazy(() => import('@/pages/ProfileSettingsPage'));
const SecuritySettingsPage = lazy(() => import('@/pages/SecuritySettingsPage'));
const PreferencesPage = lazy(() => import('@/pages/PreferencesPage'));

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
        path: 'users',
        element: <UserManagement />,
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
      {
        path: 'settings',
        element: <SettingsPage />,
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
        path: 'smart-assignment',
        element: <SmartAssignmentPage />,
      },
      {
        path: 'live-map',
        element: <LiveMapPage />,
      },
      {
        path: 'technicians',
        element: <TechnicianDirectory />,
      },
      {
        path: 'analytics',
        element: <AnalyticsPage />,
      },
      {
        path: 'eta-performance',
        element: <ETAPerformancePage />,
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
    path: '/smart-assignment',
    element: (
      <ProtectedRoute>
        <DispatcherLayout />
      </ProtectedRoute>
    ),
    children: [
      {
        index: true,
        element: <SmartAssignmentPage />,
      },
    ],
  },
  {
    path: '/live-map',
    element: (
      <ProtectedRoute>
        <DispatcherLayout />
      </ProtectedRoute>
    ),
    children: [
      {
        index: true,
        element: <LiveMapPage />,
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
    path: '/analytics',
    element: (
      <ProtectedRoute>
        <DispatcherLayout />
      </ProtectedRoute>
    ),
    children: [
      {
        index: true,
        element: <AnalyticsPage />,
      },
    ],
  },
  {
    path: '/eta-performance',
    element: (
      <ProtectedRoute>
        <DispatcherLayout />
      </ProtectedRoute>
    ),
    children: [
      {
        index: true,
        element: <ETAPerformancePage />,
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
        path: 'jobs',
        element: <TechnicianJobsPage />,
      },
      {
        path: 'schedule',
        element: <TechnicianSchedulePage />,
      },
      {
        path: 'route',
        element: <TechnicianRoutePage />,
      },
      {
        path: 'status',
        element: <TechnicianStatusPage />,
      },
      {
        path: 'profile',
        element: <TechnicianProfile />,
      },
    ],
  },
  {
    path: '/profile',
    element: (
      <ProtectedRoute>
        <AccountLayout />
      </ProtectedRoute>
    ),
    children: [
      {
        index: true,
        element: <ProfileSettingsPage />,
      },
      {
        path: 'security',
        element: <SecuritySettingsPage />,
      },
      {
        path: 'preferences',
        element: <PreferencesPage />,
      },
    ],
  },
  {
    path: '/security',
    element: <Navigate to="/profile/security" replace />,
  },
  {
    path: '/preferences',
    element: <Navigate to="/profile/preferences" replace />,
  },
  {
    path: '*',
    element: <NotFoundPage />,
  },
];
