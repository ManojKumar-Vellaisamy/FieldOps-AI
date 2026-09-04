import { useState } from 'react';
import { Outlet } from 'react-router-dom';
import {
  LayoutDashboard,
  Briefcase,
  Cpu,
  MapPin,
  Users,
  BarChart3,
  Gauge,
  History,
} from 'lucide-react';
import { Sidebar, type NavSection } from '@/components/ui/Sidebar';
import { useSidebarState } from '@/hooks/useSidebarState';
import { Navbar } from '@/components/ui/Navbar';
import { RoleGuard } from '@/guards/RoleGuard';
import { cn } from '@/utils/cn';

const DISPATCHER_NAVIGATION: NavSection[] = [
  {
    title: 'Overview',
    items: [
      { label: 'Dispatch Control Center', href: '/dashboard', icon: LayoutDashboard },
    ],
  },
  {
    title: 'Operations',
    items: [
      { label: 'Jobs', href: '/jobs', icon: Briefcase },
      { label: 'Smart Assignment', href: '/smart-assignment', icon: Cpu, badge: 'AI' },
      { label: 'Live Map', href: '/live-map', icon: MapPin },
      { label: 'Technicians', href: '/technicians', icon: Users },
    ],
  },
  {
    title: 'Analytics & Performance',
    items: [
      { label: 'Analytics', href: '/analytics', icon: BarChart3 },
      { label: 'ETA Performance', href: '/eta-performance', icon: Gauge },
    ],
  },
  {
    title: 'Audit',
    items: [
      { label: 'Audit History', href: '/dashboard/audit-history', icon: History },
    ],
  },
];

export function DispatcherLayout() {
  const { collapsed, toggle } = useSidebarState();
  const [mobileOpen, setMobileOpen] = useState(false);

  return (
    <RoleGuard allowedRoles={['Dispatcher']}>
      <div className="flex h-screen w-full overflow-hidden bg-slate-50 text-slate-800 antialiased font-sans">
        {/* Desktop Sidebar */}
        <div className="hidden md:flex h-full">
          <Sidebar collapsed={collapsed} onToggle={toggle} sections={DISPATCHER_NAVIGATION} />
        </div>

        {/* Mobile Drawer */}
        {mobileOpen && (
          <div className="fixed inset-0 z-50 md:hidden flex">
            <div
              className="fixed inset-0 bg-slate-900/40 backdrop-blur-xs transition-opacity"
              onClick={() => setMobileOpen(false)}
            />
            <div className="relative z-10 flex h-full w-64 flex-col bg-white shadow-2xl">
              <Sidebar collapsed={false} onToggle={() => setMobileOpen(false)} sections={DISPATCHER_NAVIGATION} />
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
