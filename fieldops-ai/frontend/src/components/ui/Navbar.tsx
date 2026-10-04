import { useState, useRef, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Bell,
  Sun,
  Moon,
  Search,
  ChevronDown,
  CloudSun,
  Menu,
  User,
  Settings,
  LogOut,
  Shield,
  Activity,
  ShieldCheck,
  UserCheck,
} from 'lucide-react';
import { cn } from '@/utils/cn';
import { useTheme } from '@/hooks/useTheme';
import { useAuth } from '@/contexts/AuthContext';
import { useWeather } from '@/contexts/WeatherContext';

interface NavbarProps {
  title?: string | undefined;
  onMobileToggle?: (() => void) | undefined;
  className?: string | undefined;
}

/**
 * Shared Global Top Bar for Enterprise Application Shell.
 * Contains: FieldOps AI Logo, Role-Specific Global Search, Weather Display,
 * Role-Specific Status Widget, Theme Toggle, Notifications, and User Profile.
 */
export function Navbar({ onMobileToggle, className }: NavbarProps) {
  const navigate = useNavigate();
  const { isDark, toggleTheme } = useTheme();
  const { user, logout } = useAuth();
  const [userMenuOpen, setUserMenuOpen] = useState(false);
  const [notificationsOpen, setNotificationsOpen] = useState(false);
  const { navbarWeather: weather, isLoading: weatherLoading, error: weatherError } = useWeather();

  const userMenuRef = useRef<HTMLDivElement>(null);
  const notifMenuRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (userMenuRef.current && !userMenuRef.current.contains(event.target as Node)) {
        setUserMenuOpen(false);
      }
      if (notifMenuRef.current && !notifMenuRef.current.contains(event.target as Node)) {
        setNotificationsOpen(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);


  const getInitials = (name: string) => {
    return name
      .split(' ')
      .map((n) => n[0])
      .join('')
      .substring(0, 2)
      .toUpperCase();
  };

  const userInitials = user?.full_name ? getInitials(user.full_name) : 'FO';
  const userName = user?.full_name || 'FieldOps User';
  const userEmail = user?.email || 'user@fieldops.ai';
  const userRole = user?.role || 'Dispatcher';

  const getSearchPlaceholder = (role?: string) => {
    switch (role) {
      case 'Administrator':
        return 'Search users, technicians, skills...';
      case 'Technician':
        return 'Search my jobs, locations...';
      case 'Dispatcher':
      default:
        return 'Search jobs, technicians, assignments...';
    }
  };

  const getStatusWidget = (role?: string) => {
    switch (role) {
      case 'Administrator':
        return {
          label: 'System Healthy',
          icon: ShieldCheck,
        };
      case 'Technician':
        return {
          label: 'Available for Assignment',
          icon: UserCheck,
        };
      case 'Dispatcher':
      default:
        return {
          label: 'Operations Active',
          icon: Activity,
        };
    }
  };

  const statusWidget = getStatusWidget(userRole);
  const StatusIcon = statusWidget.icon;

  return (
    <header
      role="banner"
      className={cn(
        'relative z-10 flex h-16 shrink-0 items-center justify-between border-b border-slate-200',
        'bg-white/95 px-4 md:px-6 backdrop-blur-md select-none shadow-xs',
        className,
      )}
    >
      {/* ── Left: Mobile Toggle & Role-Specific Global Search ── */}
      <div className="flex flex-1 items-center gap-3">
        {onMobileToggle && (
          <button
            onClick={onMobileToggle}
            aria-label="Toggle navigation menu"
            className="flex h-9 w-9 items-center justify-center rounded-lg border border-slate-200 bg-slate-50 text-slate-600 md:hidden hover:bg-slate-100 hover:text-slate-900 transition-colors"
          >
            <Menu className="h-4.5 w-4.5" />
          </button>
        )}

        <div className="relative w-full max-w-md">
          <Search
            className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400 pointer-events-none"
            aria-hidden="true"
          />
          <input
            id="global-search"
            type="search"
            placeholder={getSearchPlaceholder(userRole)}
            aria-label="Global search"
            className={cn(
              'w-full rounded-lg border border-slate-200 bg-slate-50 py-2 pl-9 pr-12',
              'text-xs text-slate-800 placeholder:text-slate-400 font-medium',
              'transition-all duration-200',
              'focus:border-blue-500 focus:bg-white focus:outline-none focus:ring-2 focus:ring-blue-500/20',
            )}
          />
          <kbd className="absolute right-2.5 top-1/2 -translate-y-1/2 rounded border border-slate-200 bg-white px-1.5 py-0.5 text-[10px] font-medium text-slate-500 shadow-2xs">
            ⌘K
          </kbd>
        </div>
      </div>

      {/* ── Right: Weather Display, Role Status Widget, Theme & Profile ── */}
      <div className="flex items-center gap-2 md:gap-3">
        {/* Weather Display */}
        <div className="hidden items-center gap-2 rounded-lg border border-slate-200 bg-slate-50 px-2.5 py-1.5 lg:flex">
          <CloudSun className={cn("h-4 w-4", weather ? "text-amber-500" : "text-slate-400")} />
          <div className="flex items-center gap-1.5 text-xs">
            {weather ? (
              <>
                <span className="font-bold text-slate-800">{weather.temperature}</span>
                <span className="text-slate-500">{weather.condition}</span>
                {weather.apparentTemperature && (
                  <span className="text-slate-400 text-[11px] hidden xl:inline font-mono">
                    (Feels {weather.apparentTemperature})
                  </span>
                )}
              </>
            ) : weatherLoading ? (
              <span className="text-slate-400 font-medium">Loading weather...</span>
            ) : (
              <span
                className="text-slate-400 font-medium truncate max-w-[220px]"
                title={weatherError || 'Weather unavailable — location permission required'}
              >
                {weatherError || 'Weather unavailable — location permission required'}
              </span>
            )}
          </div>
        </div>

        {/* Role-Specific Status Widget */}
        <div className="flex items-center gap-2 rounded-full border border-emerald-200 bg-emerald-50 px-3 py-1">
          <span className="relative flex h-2 w-2">
            <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-emerald-400 opacity-75" />
            <span className="relative inline-flex h-2 w-2 rounded-full bg-emerald-500" />
          </span>
          <StatusIcon className="h-3.5 w-3.5 text-emerald-600" />
          <span className="hidden text-xs font-bold text-emerald-700 sm:inline-block">
            {statusWidget.label}
          </span>
        </div>

        {/* Theme Toggle */}
        <button
          id="theme-toggle"
          onClick={toggleTheme}
          aria-label={isDark ? 'Switch to light mode' : 'Switch to dark mode'}
          className={cn(
            'flex h-9 w-9 items-center justify-center rounded-lg border border-slate-200 bg-slate-50 text-slate-600',
            'transition-all duration-200 hover:border-slate-300 hover:bg-slate-100 hover:text-slate-900',
          )}
        >
          {isDark ? <Sun className="h-4 w-4 text-amber-500" /> : <Moon className="h-4 w-4 text-blue-600" />}
        </button>

        {/* Notifications Dropdown */}
        <div ref={notifMenuRef} className="relative">
          <button
            id="notifications-button"
            onClick={() => setNotificationsOpen(!notificationsOpen)}
            aria-label="View notifications"
            className={cn(
              'flex h-9 w-9 items-center justify-center rounded-lg border border-slate-200',
              'text-slate-500 transition-all duration-200 hover:border-slate-300 hover:bg-slate-50 hover:text-slate-700',
              notificationsOpen && 'bg-slate-100 border-slate-300 text-slate-800',
            )}
          >
            <Bell className="h-4 w-4" />
          </button>

          {/* Notifications Dropdown Menu */}
          {notificationsOpen && (
            <div className="absolute right-0 mt-2 w-80 rounded-xl border border-slate-200 bg-white p-4 shadow-xl z-50 animate-fade-in">
              <div className="flex items-center justify-between border-b border-slate-100 pb-2">
                <span className="text-xs font-bold text-slate-900">Notifications</span>
              </div>
              <div className="py-6 text-center text-xs text-slate-400 font-medium">
                No new notifications
              </div>
            </div>
          )}
        </div>

        {/* Divider */}
        <div aria-hidden="true" className="mx-1 h-5 w-px bg-slate-200" />

        {/* User Profile Dropdown */}
        <div ref={userMenuRef} className="relative">
          <button
            id="user-menu-button"
            onClick={() => setUserMenuOpen(!userMenuOpen)}
            aria-label="Open user menu"
            className={cn(
              'flex items-center gap-2.5 rounded-lg border border-slate-200 bg-slate-50 p-1 pr-2.5 cursor-pointer',
              'transition-all duration-200 hover:border-slate-300 hover:bg-slate-100',
              userMenuOpen && 'border-slate-300 bg-slate-100',
            )}
          >
            <div className="flex h-7 w-7 items-center justify-center rounded-md bg-gradient-to-br from-blue-600 to-indigo-600 font-bold text-xs text-white shadow-xs">
              {userInitials}
            </div>
            <div className="hidden flex-col text-left leading-tight lg:flex">
              <span className="text-xs font-bold text-slate-800">{userName}</span>
              <span className="text-[10px] font-medium text-slate-500">{userRole}</span>
            </div>
            <ChevronDown className="h-3.5 w-3.5 text-slate-400 hidden sm:block" />
          </button>

          {/* User Profile Dropdown Menu */}
          {userMenuOpen && (
            <div className="absolute right-0 mt-2 w-56 rounded-xl border border-slate-200 bg-white p-2 shadow-xl z-50 animate-fade-in">
              <div className="px-3 py-2 border-b border-slate-100">
                <p className="text-xs font-bold text-slate-900 truncate">{userName}</p>
                <p className="text-[11px] text-slate-500 truncate">{userEmail}</p>
                <span
                  className={cn(
                    'mt-1.5 inline-block rounded px-2 py-0.5 text-[10px] font-bold border',
                    userRole === 'Administrator' && 'bg-purple-50 text-purple-700 border-purple-200',
                    userRole === 'Technician' && 'bg-emerald-50 text-emerald-700 border-emerald-200',
                    userRole !== 'Administrator' && userRole !== 'Technician' && 'bg-blue-50 text-blue-700 border-blue-200',
                  )}
                >
                  {userRole}
                </span>
              </div>
              <div className="mt-1 flex flex-col gap-0.5 text-xs text-slate-600">
                <button
                  id="menu-profile-settings"
                  type="button"
                  onClick={() => {
                    setUserMenuOpen(false);
                    navigate('/profile');
                  }}
                  className="flex items-center gap-2 rounded-lg px-3 py-2 hover:bg-slate-50 hover:text-slate-900 text-left w-full transition-colors cursor-pointer font-medium"
                >
                  <User className="h-3.5 w-3.5 text-slate-400" /> Profile Settings
                </button>
                <button
                  id="menu-security-access"
                  type="button"
                  onClick={() => {
                    setUserMenuOpen(false);
                    navigate('/profile/security');
                  }}
                  className="flex items-center gap-2 rounded-lg px-3 py-2 hover:bg-slate-50 hover:text-slate-900 text-left w-full transition-colors cursor-pointer font-medium"
                >
                  <Shield className="h-3.5 w-3.5 text-slate-400" /> Security & Access
                </button>
                <button
                  id="menu-preferences"
                  type="button"
                  onClick={() => {
                    setUserMenuOpen(false);
                    navigate('/profile/preferences');
                  }}
                  className="flex items-center gap-2 rounded-lg px-3 py-2 hover:bg-slate-50 hover:text-slate-900 text-left w-full transition-colors cursor-pointer font-medium"
                >
                  <Settings className="h-3.5 w-3.5 text-slate-400" /> Preferences
                </button>
                <div className="my-1 border-t border-slate-100" />
                <button
                  id="menu-sign-out"
                  type="button"
                  onClick={async () => {
                    setUserMenuOpen(false);
                    await logout();
                    navigate('/login', { replace: true });
                  }}
                  className="flex items-center gap-2 rounded-lg px-3 py-2 text-rose-600 hover:bg-rose-50 text-left w-full font-semibold transition-colors cursor-pointer"
                >
                  <LogOut className="h-3.5 w-3.5 text-rose-500" /> Sign Out
                </button>
              </div>
            </div>
          )}
        </div>
      </div>
    </header>
  );
}
