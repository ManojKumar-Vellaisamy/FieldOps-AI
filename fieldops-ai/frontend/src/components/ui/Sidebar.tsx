import type { ComponentType } from 'react';
import { NavLink } from 'react-router-dom';
import {
  LayoutDashboard,
  Briefcase,
  Cpu,
  MapPin,
  Users,
  BarChart3,
  Gauge,
  History,
  UserCog,
  Wrench,
  Settings,
  HelpCircle,
  ChevronLeft,
  ChevronRight,
} from 'lucide-react';
import { cn } from '@/utils/cn';
import { APP_CONSTANTS } from '@/config/constants';
import { Logo } from './Logo';

export interface SidebarNavItem {
  label: string;
  href: string;
  icon: ComponentType<{ className?: string }>;
  badge?: string;
}

export interface NavSection {
  title?: string;
  items: SidebarNavItem[];
}

const NAVIGATION_SECTIONS: NavSection[] = [
  {
    title: 'Overview',
    items: [{ label: 'Dashboard', href: '/', icon: LayoutDashboard }],
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
    title: 'Analytics',
    items: [
      { label: 'Dashboard Analytics', href: '/analytics', icon: BarChart3 },
      { label: 'ETA Performance', href: '/eta-performance', icon: Gauge },
    ],
  },
  {
    title: 'Audit',
    items: [{ label: 'Audit History', href: '/audit-history', icon: History }],
  },
  {
    title: 'Administration',
    items: [
      { label: 'User Management', href: '/users', icon: UserCog },
      { label: 'Skills', href: '/skills', icon: Wrench },
      { label: 'Settings', href: '/settings', icon: Settings },
    ],
  },
];

const SUPPORT_NAV: SidebarNavItem[] = [
  { label: 'Help & Support', href: '/help', icon: HelpCircle },
];

interface SidebarProps {
  collapsed: boolean;
  onToggle: () => void;
  sections?: NavSection[];
  className?: string | undefined;
}

export function Sidebar({ collapsed, onToggle, sections, className }: SidebarProps) {
  const sidebarWidth = collapsed
    ? APP_CONSTANTS.SIDEBAR.COLLAPSED_WIDTH
    : APP_CONSTANTS.SIDEBAR.EXPANDED_WIDTH;

  const navSections = sections || NAVIGATION_SECTIONS;

  return (
    <aside
      role="navigation"
      aria-label="Primary navigation"
      aria-expanded={!collapsed}
      style={{ width: sidebarWidth }}
      className={cn(
        'relative flex h-full flex-col border-r border-slate-200 bg-white shadow-xs',
        'transition-[width] duration-300 cubic-bezier(0.4, 0, 0.2, 1) shrink-0 select-none z-20 overflow-visible',
        className,
      )}
    >
      {/* ── Brand Logo Header ── */}
      <div className="flex h-16 shrink-0 items-center justify-between border-b border-slate-200 px-4 overflow-hidden">
        <Logo collapsed={collapsed} />
      </div>

      {/* ── Main Navigation Sections ── */}
      <nav className="flex flex-1 flex-col gap-6 overflow-y-auto px-3 py-5 scrollbar-thin overflow-x-hidden">
        {navSections.map((section, idx) => (
          <div key={section.title || idx} className="flex flex-col gap-1">
            {!collapsed && section.title && (
              <p className="mb-1.5 px-3 text-[10px] font-bold uppercase tracking-wider text-slate-400 select-none">
                {section.title}
              </p>
            )}
            {section.items.map((item) => (
              <NavItem key={item.href} item={item} collapsed={collapsed} />
            ))}
          </div>
        ))}
      </nav>

      {/* ── Footer & Support Navigation ── */}
      <div className="shrink-0 border-t border-slate-200 px-3 py-3 overflow-hidden">
        {!collapsed && (
          <p className="mb-1.5 px-3 text-[10px] font-bold uppercase tracking-wider text-slate-400 select-none">
            Support
          </p>
        )}
        <div className="flex flex-col gap-1">
          {SUPPORT_NAV.map((item) => (
            <NavItem key={item.href} item={item} collapsed={collapsed} />
          ))}
        </div>

        {/* Footer info: Version & Copyright */}
        {!collapsed ? (
          <div className="mt-3 border-t border-slate-100 pt-2.5 px-3 flex flex-col gap-0.5 text-xs text-slate-500 transition-opacity duration-200">
            <div className="flex items-center justify-between font-mono text-[11px]">
              <span>Version</span>
              <span className="font-semibold text-slate-700">v1.0.0</span>
            </div>
            <p className="text-[11px] text-slate-400">© FieldOps AI</p>
          </div>
        ) : (
          <div
            className="mt-2 text-center text-[10px] font-mono text-slate-400"
            title="v1.0.0 • © FieldOps AI"
            aria-label="Version 1.0.0"
          >
            v1.0
          </div>
        )}
      </div>

      {/* ── Collapse Toggle Button ── */}
      <button
        type="button"
        onClick={onToggle}
        title={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
        aria-label={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
        className={cn(
          'absolute -right-[17px] top-16 z-30 flex h-[34px] w-[34px] items-center justify-center rounded-full',
          'bg-white text-slate-800 border border-slate-300 shadow-md',
          'transition-all duration-200 hover:bg-slate-50 hover:text-blue-700 hover:border-blue-500 hover:scale-105 active:scale-95',
          'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-600 focus-visible:ring-offset-2 focus-visible:ring-offset-white',
        )}
      >
        {collapsed ? (
          <ChevronRight className="h-4 w-4 text-slate-800 stroke-[2.5]" aria-hidden="true" />
        ) : (
          <ChevronLeft className="h-4 w-4 text-slate-800 stroke-[2.5]" aria-hidden="true" />
        )}
      </button>
    </aside>
  );
}

// ── Individual Nav Item Component ──────────────────────────────────────────
interface NavItemProps {
  item: SidebarNavItem;
  collapsed: boolean;
}

function NavItem({ item, collapsed }: NavItemProps) {
  const Icon = item.icon;

  return (
    <NavLink
      to={item.href}
      end={item.href === '/'}
      title={collapsed ? item.label : undefined}
      aria-label={item.label}
      className={({ isActive }) =>
        cn(
          'group relative flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium',
          'transition-all duration-200 ease-in-out select-none',
          'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-500 focus-visible:ring-offset-1 focus-visible:ring-offset-white',
          isActive
            ? 'bg-blue-50 text-blue-700 font-bold shadow-2xs border border-blue-200/60'
            : 'text-slate-600 hover:bg-slate-100 hover:text-slate-900',
          collapsed && 'justify-center px-2',
        )
      }
    >
      {({ isActive }) => (
        <>
          {/* Active Highlight Left Bar */}
          {isActive && (
            <span
              aria-hidden="true"
              className="absolute left-0 top-1/2 h-5 w-1 -translate-y-1/2 rounded-r-full bg-blue-600 shadow-2xs transition-all duration-200"
            />
          )}

          {/* Lucide Icon */}
          <Icon
            aria-hidden="true"
            className={cn(
              'h-5 w-5 shrink-0 transition-transform duration-200 group-hover:scale-105',
              isActive ? 'text-blue-600' : 'text-slate-400 group-hover:text-slate-700',
            )}
          />

          {!collapsed && (
            <span className="truncate text-sm tracking-tight transition-opacity duration-200">
              {item.label}
            </span>
          )}

          {!collapsed && item.badge && (
            <span className="ml-auto rounded-full bg-blue-100 px-2 py-0.5 text-[10px] font-extrabold text-blue-700 border border-blue-200">
              {item.badge}
            </span>
          )}
        </>
      )}
    </NavLink>
  );
}

