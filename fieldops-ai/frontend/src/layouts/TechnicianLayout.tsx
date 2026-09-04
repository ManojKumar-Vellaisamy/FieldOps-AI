import { useState } from 'react';
import { Outlet } from 'react-router-dom';
import {
  LayoutDashboard,
  Briefcase,
  Calendar,
  Navigation,
  CheckCircle2,
  User,
} from 'lucide-react';
import { Sidebar, type NavSection } from '@/components/ui/Sidebar';
import { useSidebarState } from '@/hooks/useSidebarState';
import { Navbar } from '@/components/ui/Navbar';
import { RoleGuard } from '@/guards/RoleGuard';
import { cn } from '@/utils/cn';

const TECHNICIAN_NAVIGATION: NavSection[] = [
  {
    title: 'Overview',
    items: [
      { label: 'My Field Workspace', href: '/technician', icon: LayoutDashboard },
    ],
  },
  {
    title: 'My Work',
    items: [
      { label: 'My Jobs', href: '/technician/jobs', icon: Briefcase },
      { label: "Today's Schedule", href: '/technician/schedule', icon: Calendar },
      { label: 'Route Navigation', href: '/technician/route', icon: Navigation },
      { label: 'Update Status', href: '/technician/status', icon: CheckCircle2 },
    ],
  },
  {
    title: 'Account',
    items: [
      { label: 'Profile', href: '/technician/profile', icon: User },
    ],
  },
];

export function TechnicianLayout() {
  const { collapsed, toggle } = useSidebarState();
  const [mobileOpen, setMobileOpen] = useState(false);

  return (
    <RoleGuard allowedRoles={['Technician']}>
      <div className="flex h-screen w-full overflow-hidden bg-slate-50 text-slate-800 antialiased font-sans">
        {/* Desktop Sidebar */}
        <div className="hidden md:flex h-full">
          <Sidebar collapsed={collapsed} onToggle={toggle} sections={TECHNICIAN_NAVIGATION} />
        </div>

        {/* Mobile Drawer */}
        {mobileOpen && (
          <div className="fixed inset-0 z-50 md:hidden flex">
            <div
              className="fixed inset-0 bg-slate-900/40 backdrop-blur-xs transition-opacity"
              onClick={() => setMobileOpen(false)}
            />
            <div className="relative z-10 flex h-full w-64 flex-col bg-white shadow-2xl">
              <Sidebar collapsed={false} onToggle={() => setMobileOpen(false)} sections={TECHNICIAN_NAVIGATION} />
            </div>
          </div>
        )}

        {/* Main Content */}
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
