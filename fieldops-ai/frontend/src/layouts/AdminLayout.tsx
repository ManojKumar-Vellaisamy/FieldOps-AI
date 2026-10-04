import { useState } from 'react';
import { Outlet } from 'react-router-dom';
import {
  LayoutDashboard,
  UserCog,
  Users,
  Wrench,
  History,
  Settings,
} from 'lucide-react';
import { Sidebar, type NavSection } from '@/components/ui/Sidebar';
import { useSidebarState } from '@/hooks/useSidebarState';
import { Navbar } from '@/components/ui/Navbar';
import { RoleGuard } from '@/guards/RoleGuard';
import { cn } from '@/utils/cn';

export const ADMIN_NAVIGATION: NavSection[] = [
  {
    title: 'Overview',
    items: [
      { label: 'Administration Workspace', href: '/admin', icon: LayoutDashboard },
    ],
  },
  {
    title: 'Administration',
    items: [
      { label: 'User Management', href: '/admin/users', icon: UserCog },
      { label: 'Technician Management', href: '/admin/technicians', icon: Users },
      { label: 'Skills Management', href: '/admin/skills', icon: Wrench },
    ],
  },
  {
    title: 'System & Audit',
    items: [
      { label: 'Audit History', href: '/admin/audit-history', icon: History },
      { label: 'Settings', href: '/admin/settings', icon: Settings },
    ],
  },
];

export function AdminLayout() {
  const { collapsed, toggle } = useSidebarState();
  const [mobileOpen, setMobileOpen] = useState(false);

  return (
    <RoleGuard allowedRoles={['Administrator']}>
      <div className="flex h-screen w-full overflow-hidden bg-slate-50 text-slate-800 antialiased font-sans">
        {/* Desktop Sidebar */}
        <div className="hidden md:flex h-full">
          <Sidebar collapsed={collapsed} onToggle={toggle} sections={ADMIN_NAVIGATION} />
        </div>

        {/* Mobile Drawer */}
        {mobileOpen && (
          <div className="fixed inset-0 z-50 md:hidden flex">
            <div
              className="fixed inset-0 bg-slate-900/40 backdrop-blur-xs transition-opacity"
              onClick={() => setMobileOpen(false)}
            />
            <div className="relative z-10 flex h-full w-64 flex-col bg-white shadow-2xl">
              <Sidebar collapsed={false} onToggle={() => setMobileOpen(false)} sections={ADMIN_NAVIGATION} />
            </div>
          </div>
        )}

        {/* Main Area */}
        <div className="flex flex-1 flex-col overflow-hidden min-w-0">
          <Navbar onMobileToggle={() => setMobileOpen(true)} />
          <main
            id="main-content"
            role="main"
            className={cn(
              'flex-1 overflow-y-auto p-4 md:p-8',
              'animate-fade-in scrollbar-thin',
            )}
          >
            <div className="mx-auto max-w-7xl">
              <Outlet />
            </div>
          </main>
        </div>
      </div>
    </RoleGuard>
  );
}
