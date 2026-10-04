import { useState, useMemo } from 'react';
import { NavLink, Outlet, useLocation } from 'react-router-dom';
import { User, Shield, Settings, ChevronRight } from 'lucide-react';
import { Sidebar } from '@/components/ui/Sidebar';
import { useSidebarState } from '@/hooks/useSidebarState';
import { Navbar } from '@/components/ui/Navbar';
import { useAuth } from '@/contexts/AuthContext';
import { ADMIN_NAVIGATION } from '@/layouts/AdminLayout';
import { DISPATCHER_NAVIGATION } from '@/layouts/DispatcherLayout';
import { TECHNICIAN_NAVIGATION } from '@/layouts/TechnicianLayout';
import { cn } from '@/utils/cn';

const ACCOUNT_TABS = [
  {
    label: 'Profile Settings',
    href: '/profile',
    icon: User,
    exact: true,
  },
  {
    label: 'Security & Access',
    href: '/profile/security',
    icon: Shield,
    exact: false,
  },
  {
    label: 'Preferences',
    href: '/profile/preferences',
    icon: Settings,
    exact: false,
  },
];

export function AccountLayout() {
  const { user } = useAuth();
  const location = useLocation();
  const { collapsed, toggle } = useSidebarState();
  const [mobileOpen, setMobileOpen] = useState(false);

  const navSections = useMemo(() => {
    switch (user?.role) {
      case 'Administrator':
        return ADMIN_NAVIGATION;
      case 'Technician':
        return TECHNICIAN_NAVIGATION;
      case 'Dispatcher':
      default:
        return DISPATCHER_NAVIGATION;
    }
  }, [user?.role]);

  const activeTab = ACCOUNT_TABS.find((t) =>
    t.exact ? location.pathname === t.href : location.pathname.startsWith(t.href),
  ) || ACCOUNT_TABS[0];

  return (
    <div className="flex h-screen w-full overflow-hidden bg-slate-50 text-slate-800 antialiased font-sans">
      {/* Desktop Sidebar */}
      <div className="hidden md:flex h-full">
        <Sidebar collapsed={collapsed} onToggle={toggle} sections={navSections} />
      </div>

      {/* Mobile Drawer */}
      {mobileOpen && (
        <div className="fixed inset-0 z-50 md:hidden flex">
          <div
            className="fixed inset-0 bg-slate-900/40 backdrop-blur-xs transition-opacity"
            onClick={() => setMobileOpen(false)}
          />
          <div className="relative z-10 flex h-full w-64 flex-col bg-white shadow-2xl">
            <Sidebar collapsed={false} onToggle={() => setMobileOpen(false)} sections={navSections} />
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
          <div className="mx-auto max-w-5xl space-y-6">
            {/* Breadcrumb & Header */}
            <div>
              <div className="flex items-center gap-1.5 text-xs text-slate-500 mb-2">
                <span>Account</span>
                <ChevronRight className="h-3 w-3 text-slate-400" />
                <span className="font-semibold text-slate-800">{activeTab?.label || 'Profile Settings'}</span>
              </div>
              <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2">
                <div>
                  <h1 className="text-2xl font-extrabold text-slate-900 tracking-tight">
                    Account & Security
                  </h1>
                  <p className="text-xs text-slate-500 mt-0.5">
                    Manage your identity, security credentials, and application workspace preferences.
                  </p>
                </div>
                {user && (
                  <div className="inline-flex items-center gap-2 self-start sm:self-auto rounded-lg border border-slate-200 bg-white px-3 py-1.5 text-xs shadow-xs">
                    <div className="flex h-6 w-6 items-center justify-center rounded-md bg-gradient-to-br from-blue-600 to-indigo-600 text-white font-bold text-[10px]">
                      {user.full_name ? user.full_name.substring(0, 2).toUpperCase() : 'FO'}
                    </div>
                    <div className="leading-tight">
                      <span className="font-bold text-slate-900 block">{user.full_name}</span>
                      <span className="text-[10px] text-slate-500">{user.role}</span>
                    </div>
                  </div>
                )}
              </div>
            </div>

            {/* Navigation Tabs */}
            <div className="border-b border-slate-200 bg-white rounded-t-xl px-4 pt-2 shadow-2xs">
              <nav className="flex space-x-2 sm:space-x-4" aria-label="Account Tabs">
                {ACCOUNT_TABS.map((tab) => {
                  const Icon = tab.icon;
                  const isActive = tab.exact
                    ? location.pathname === tab.href
                    : location.pathname.startsWith(tab.href);
                  return (
                    <NavLink
                      key={tab.href}
                      to={tab.href}
                      end={tab.exact}
                      className={cn(
                        'flex items-center gap-2 border-b-2 py-3 px-3 text-xs font-semibold transition-all',
                        isActive
                          ? 'border-blue-600 text-blue-600'
                          : 'border-transparent text-slate-500 hover:border-slate-300 hover:text-slate-800',
                      )}
                    >
                      <Icon className={cn('h-4 w-4', isActive ? 'text-blue-600' : 'text-slate-400')} />
                      <span>{tab.label}</span>
                    </NavLink>
                  );
                })}
              </nav>
            </div>

            {/* Tab Sub-Page Content */}
            <div className="rounded-b-xl border border-t-0 border-slate-200 bg-white p-6 shadow-xs">
              <Outlet />
            </div>
          </div>
        </main>
      </div>
    </div>
  );
}
