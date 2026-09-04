import { useState } from 'react';
import { Outlet } from 'react-router-dom';
import { Sidebar } from '@/components/ui/Sidebar';
import { useSidebarState } from '@/hooks/useSidebarState';
import { Navbar } from '@/components/ui/Navbar';
import { cn } from '@/utils/cn';

interface SidebarLayoutProps {
  className?: string;
}

/**
 * Enterprise Application Shell Layout:
 *  - Collapsible desktop sidebar & drawer mobile sidebar
 *  - Top header navbar with global search and tools
 *  - Scrollable main workspace area
 */
export function SidebarLayout({}: SidebarLayoutProps = {}) {
  const { collapsed, toggle } = useSidebarState();
  const [mobileOpen, setMobileOpen] = useState(false);

  return (
    <div className="flex h-screen w-full overflow-hidden bg-slate-50 text-slate-800 antialiased font-sans">
      {/* ── Desktop Sidebar ── */}
      <div className="hidden md:flex h-full">
        <Sidebar collapsed={collapsed} onToggle={toggle} />
      </div>

      {/* ── Mobile Drawer Overlay & Sidebar ── */}
      {mobileOpen && (
        <div className="fixed inset-0 z-50 md:hidden flex">
          <div
            className="fixed inset-0 bg-slate-900/40 backdrop-blur-xs transition-opacity"
            onClick={() => setMobileOpen(false)}
          />
          <div className="relative z-10 flex h-full w-64 flex-col bg-white shadow-2xl">
            <Sidebar collapsed={false} onToggle={() => setMobileOpen(false)} />
          </div>
        </div>
      )}

      {/* ── Main Content Area ── */}
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
  );
}
