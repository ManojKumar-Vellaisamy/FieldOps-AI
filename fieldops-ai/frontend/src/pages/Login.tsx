import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import {
  Eye,
  EyeOff,
  Lock,
  Mail,
  ArrowRight,
  Shield,
  Activity,
  Cpu,
  CheckCircle2,
  AlertCircle,
  X,
  Sparkles,
  LockKeyhole,
} from 'lucide-react';
import { useAuth } from '@/contexts/AuthContext';
import { Logo } from '@/components/ui/Logo';
import { env } from '@/config/env';
import type { UserRole } from '@/types/auth.types';

// ── Form Validation Schema using Zod ──────────────────────────────────────────
const loginSchema = z.object({
  email: z
    .string()
    .min(1, 'Email address is required')
    .email('Please enter a valid email address'),
  password: z
    .string()
    .min(1, 'Password is required')
    .min(8, 'Password must be at least 8 characters'),
  remember_me: z.boolean(),
});

type LoginFormData = z.infer<typeof loginSchema>;

export default function LoginPage() {
  const navigate = useNavigate();
  const { login, isAuthenticated, user } = useAuth();

  const [showPassword, setShowPassword] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [isForgotModalOpen, setIsForgotModalOpen] = useState(false);
  const [forgotEmail, setForgotEmail] = useState('');
  const [forgotSubmitted, setForgotSubmitted] = useState(false);

  const getRoleDefaultRoute = (role?: UserRole): string => {
    switch (role) {
      case 'Administrator':
        return '/admin';
      case 'Technician':
        return '/technician';
      case 'Dispatcher':
      default:
        return '/dashboard';
    }
  };

  // Redirect directly to role workspace upon successful authentication
  useEffect(() => {
    if (isAuthenticated && user) {
      const targetRoute = getRoleDefaultRoute(user.role);
      navigate(targetRoute, { replace: true });
    }
  }, [isAuthenticated, user, navigate]);

  const {
    register,
    handleSubmit,
    setValue,
    formState: { errors, isSubmitting },
  } = useForm<LoginFormData>({
    resolver: zodResolver(loginSchema),
    defaultValues: {
      email: '',
      password: '',
      remember_me: false,
    },
  });

  const onSubmit = async (data: LoginFormData) => {
    setErrorMessage(null);
    try {
      await login(data);
      // AuthContext sets active user synchronously upon completion
    } catch (err: any) {
      const msg =
        err?.response?.data?.error?.message ||
        err?.response?.data?.detail ||
        'Invalid credentials.';
      setErrorMessage(msg);
    }
  };

  // Autofill demo credentials ONLY (Does NOT bypass authentication or auto-submit)
  const handleAutofillDemo = (email: string, pass: string) => {
    setValue('email', email, { shouldValidate: true });
    setValue('password', pass, { shouldValidate: true });
    setErrorMessage(null);
  };

  return (
    <div className="flex min-h-screen w-full bg-slate-50 text-slate-800 antialiased font-sans">
      {/* ── Left Side Panel (Branding & Enterprise Technical Overview) ─────── */}
      <div className="hidden lg:flex lg:w-1/2 relative flex-col justify-between overflow-hidden border-r border-slate-200 bg-gradient-to-br from-slate-50 via-blue-50/30 to-slate-100/60 p-12 select-none">
        {/* Subtle Ambient Background Accent */}
        <div className="absolute -top-32 -left-32 h-96 w-96 rounded-full bg-blue-100/50 blur-3xl pointer-events-none" />
        <div className="absolute -bottom-32 -right-32 h-96 w-96 rounded-full bg-indigo-100/40 blur-3xl pointer-events-none" />

        {/* Top Logo */}
        <div className="relative z-10">
          <Logo collapsed={false} />
        </div>

        {/* Center Technical Description & Feature Cards */}
        <div className="relative z-10 my-auto max-w-lg">
          <div className="mb-5 inline-flex items-center gap-2 rounded-full border border-blue-200 bg-blue-50 px-3 py-1 text-xs font-bold text-blue-700 shadow-2xs">
            <Sparkles className="h-3.5 w-3.5 text-blue-600" />
            <span>Enterprise Field Operations</span>
          </div>

          <h1 className="text-3xl xl:text-4xl font-extrabold tracking-tight text-slate-900 leading-[1.25] mb-4">
            Context-Aware Technician Dispatch & Real-Time ETA Prediction
          </h1>

          <p className="text-sm xl:text-base text-slate-600 leading-relaxed mb-8">
            Optimize technician assignment through skill matching, context-aware ETA prediction and intelligent dispatch recommendations.
          </p>

          {/* Enterprise Technical Cards */}
          <div className="grid grid-cols-2 gap-4">
            <div className="rounded-xl border border-slate-200 bg-white/90 p-4 shadow-xs transition-all hover:border-slate-300 hover:shadow-md">
              <div className="flex items-center gap-3 mb-2.5">
                <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-blue-50 border border-blue-100 text-blue-600">
                  <Cpu className="h-4.5 w-4.5" />
                </div>
                <div className="text-xs font-bold text-slate-900">Context-Aware ETA</div>
              </div>
              <p className="text-[11px] text-slate-500 leading-relaxed">
                ETA prediction using weather, road restrictions and event-aware routing.
              </p>
            </div>

            <div className="rounded-xl border border-slate-200 bg-white/90 p-4 shadow-xs transition-all hover:border-slate-300 hover:shadow-md">
              <div className="flex items-center gap-3 mb-2.5">
                <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-emerald-50 border border-emerald-100 text-emerald-600">
                  <Activity className="h-4.5 w-4.5" />
                </div>
                <div className="text-xs font-bold text-slate-900">Technician Status</div>
              </div>
              <p className="text-[11px] text-slate-500 leading-relaxed">
                Monitor technician assignment and work progress throughout the service lifecycle.
              </p>
            </div>
          </div>
        </div>

        {/* Footer info */}
        <div className="relative z-10 flex items-center justify-between text-xs text-slate-500 border-t border-slate-200/80 pt-4">
          <span className="font-medium text-slate-600">FieldOps AI • Enterprise Platform</span>
          <div className="flex items-center gap-2">
            <span className="h-2 w-2 rounded-full bg-emerald-500 animate-pulse" />
            <span className="font-medium text-slate-600">Development Authentication</span>
          </div>
        </div>
      </div>

      {/* ── Right Side Panel (Login Form & Demo Controls) ─────────────────── */}
      <div className="flex w-full lg:w-1/2 flex-col justify-center px-6 py-12 sm:px-12 xl:px-20 bg-slate-50/50">
        <div className="mx-auto w-full max-w-md bg-white p-8 sm:p-10 rounded-2xl border border-slate-200 shadow-sm">
          {/* Mobile Logo Header */}
          <div className="mb-8 lg:hidden">
            <Logo collapsed={false} />
          </div>

          {/* Form Header */}
          <div className="mb-7">
            <h2 className="text-2xl sm:text-3xl font-extrabold tracking-tight text-slate-900">
              Sign in to your account
            </h2>
            <p className="mt-1.5 text-xs sm:text-sm text-slate-500">
              Enter your corporate credentials to access your workspace.
            </p>
          </div>

          {/* Error Banner */}
          {errorMessage && (
            <div className="mb-6 flex items-start gap-3 rounded-xl border border-rose-200 bg-rose-50 p-4 text-xs font-medium text-rose-800 animate-fade-in">
              <AlertCircle className="h-4.5 w-4.5 shrink-0 text-rose-600 mt-0.5" />
              <div className="flex-1">
                <span className="font-bold block mb-0.5">Authentication Error</span>
                <span>{errorMessage}</span>
              </div>
            </div>
          )}

          {/* Login Form */}
          <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
            {/* Email Field with Auto-Focus */}
            <div>
              <label htmlFor="email" className="block text-xs font-bold text-slate-700 mb-1.5">
                Email address
              </label>
              <div className="relative">
                <div className="pointer-events-none absolute inset-y-0 left-0 flex items-center pl-3.5 text-slate-400">
                  <Mail className="h-4 w-4" />
                </div>
                <input
                  id="email"
                  type="email"
                  autoFocus
                  placeholder="name@company.com"
                  autoComplete="email"
                  {...register('email')}
                  className={`w-full rounded-xl border bg-slate-50/70 pl-10 pr-4 py-2.5 text-xs text-slate-900 font-medium placeholder-slate-400 transition-all focus:bg-white focus:outline-none focus:ring-2 ${
                    errors.email
                      ? 'border-rose-300 focus:ring-rose-200'
                      : 'border-slate-200 focus:border-blue-600 focus:ring-blue-100'
                  }`}
                />
              </div>
              {errors.email && (
                <p className="mt-1 text-xs text-rose-600 font-medium">{errors.email.message}</p>
              )}
            </div>

            {/* Password Field */}
            <div>
              <div className="flex items-center justify-between mb-1.5">
                <label htmlFor="password" className="block text-xs font-bold text-slate-700">
                  Password
                </label>
                <button
                  type="button"
                  onClick={() => setIsForgotModalOpen(true)}
                  className="text-xs font-semibold text-blue-600 hover:text-blue-800 transition-colors"
                >
                  Forgot password?
                </button>
              </div>
              <div className="relative">
                <div className="pointer-events-none absolute inset-y-0 left-0 flex items-center pl-3.5 text-slate-400">
                  <Lock className="h-4 w-4" />
                </div>
                <input
                  id="password"
                  type={showPassword ? 'text' : 'password'}
                  placeholder="••••••••"
                  autoComplete="current-password"
                  {...register('password')}
                  className={`w-full rounded-xl border bg-slate-50/70 pl-10 pr-11 py-2.5 text-xs text-slate-900 font-medium placeholder-slate-400 transition-all focus:bg-white focus:outline-none focus:ring-2 ${
                    errors.password
                      ? 'border-rose-300 focus:ring-rose-200'
                      : 'border-slate-200 focus:border-blue-600 focus:ring-blue-100'
                  }`}
                />
                <button
                  type="button"
                  onClick={() => setShowPassword(!showPassword)}
                  aria-label={showPassword ? 'Hide password' : 'Show password'}
                  className="absolute inset-y-0 right-0 flex items-center pr-3.5 text-slate-400 hover:text-slate-600 transition-colors"
                >
                  {showPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                </button>
              </div>
              {errors.password && (
                <p className="mt-1 text-xs text-rose-600 font-medium">{errors.password.message}</p>
              )}
            </div>

            {/* Remember Me Checkbox */}
            <div className="flex items-center justify-between pt-0.5">
              <label className="flex items-center gap-2 cursor-pointer">
                <input
                  type="checkbox"
                  {...register('remember_me')}
                  className="h-4 w-4 rounded border-slate-300 bg-slate-50 text-blue-600 focus:ring-2 focus:ring-blue-200"
                />
                <span className="text-xs text-slate-600 font-medium">Remember me for 7 days</span>
              </label>
            </div>

            {/* Submit Button */}
            <button
              type="submit"
              disabled={isSubmitting}
              className="relative flex w-full items-center justify-center gap-2 rounded-xl bg-blue-600 py-3 text-xs sm:text-sm font-bold text-white shadow-xs transition-all hover:bg-blue-700 active:scale-[0.99] disabled:opacity-60 focus:outline-none focus:ring-2 focus:ring-blue-500 cursor-pointer"
            >
              {isSubmitting ? (
                <>
                  <div className="h-4 w-4 rounded-full border-2 border-white/30 border-t-white animate-spin" />
                  <span>Authenticating...</span>
                </>
              ) : (
                <>
                  <span>Sign In</span>
                  <ArrowRight className="h-4 w-4" />
                </>
              )}
            </button>
          </form>

          {/* Demo Accounts Panel (Development Autofill Controls) */}
          <div className="mt-7 border-t border-slate-200/80 pt-5">
            <div className="mb-3">
              <div className="flex items-center justify-between">
                <span className="text-[11px] font-bold uppercase tracking-wider text-slate-400">
                  Demo Accounts (Development Mode)
                </span>
              </div>
              <p className="text-[11px] text-slate-500 mt-0.5">
                Click any profile below to autofill credentials for testing.
              </p>
            </div>

            <div className="flex flex-col gap-2">
              {/* Optional Administrator Access Button */}
              {env.showAdminDemo && (
                <button
                  type="button"
                  onClick={() => handleAutofillDemo('admin@fieldops.ai', 'Admin@123')}
                  className="flex items-center justify-between rounded-xl border border-slate-200 bg-slate-50/70 p-2.5 text-left transition-all hover:border-slate-300 hover:bg-slate-100/80 group cursor-pointer"
                >
                  <div className="flex items-center gap-2.5">
                    <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-slate-200/70 text-slate-700 group-hover:text-slate-900 border border-slate-300/60">
                      <LockKeyhole className="h-4 w-4" />
                    </div>
                    <div>
                      <div className="flex items-center gap-2">
                        <span className="text-xs font-bold text-slate-800">Administrator</span>
                        <span className="rounded bg-amber-50 px-1.5 py-0.5 text-[9px] font-bold uppercase tracking-wider text-amber-700 border border-amber-200">
                          Restricted
                        </span>
                      </div>
                      <p className="text-[10px] text-slate-500">admin@fieldops.ai • Admin@123</p>
                    </div>
                  </div>
                  <span className="text-[10px] font-bold text-blue-600 opacity-0 group-hover:opacity-100 transition-opacity pr-1">
                    Autofill
                  </span>
                </button>
              )}

              {/* Standard Operations Roles: Dispatcher & Technician */}
              <div className="grid grid-cols-2 gap-2">
                <button
                  type="button"
                  onClick={() => handleAutofillDemo('dispatcher@fieldops.ai', 'Dispatch@123')}
                  className="flex items-center gap-2.5 rounded-xl border border-slate-200 bg-slate-50/70 p-2.5 text-left text-xs font-medium text-slate-700 hover:border-blue-300 hover:bg-blue-50/40 transition-all group cursor-pointer"
                >
                  <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-lg bg-purple-50 text-purple-600 border border-purple-100">
                    <Shield className="h-3.5 w-3.5" />
                  </div>
                  <div className="overflow-hidden">
                    <div className="font-bold text-slate-900 truncate">Dispatcher</div>
                    <div className="text-[10px] text-slate-500 truncate">dispatcher@fieldops.ai</div>
                  </div>
                </button>

                <button
                  type="button"
                  onClick={() => handleAutofillDemo('technician@fieldops.ai', 'Tech@123')}
                  className="flex items-center gap-2.5 rounded-xl border border-slate-200 bg-slate-50/70 p-2.5 text-left text-xs font-medium text-slate-700 hover:border-emerald-300 hover:bg-emerald-50/40 transition-all group cursor-pointer"
                >
                  <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-lg bg-emerald-50 text-emerald-600 border border-emerald-100">
                    <Activity className="h-3.5 w-3.5" />
                  </div>
                  <div className="overflow-hidden">
                    <div className="font-bold text-slate-900 truncate">Technician</div>
                    <div className="text-[10px] text-slate-500 truncate">technician@fieldops.ai</div>
                  </div>
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* ── Forgot Password Modal Placeholder ────────────────────────────── */}
      {isForgotModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/40 backdrop-blur-xs p-4 animate-fade-in">
          <div className="relative w-full max-w-md rounded-2xl border border-slate-200 bg-white p-6 shadow-xl">
            <button
              onClick={() => {
                setIsForgotModalOpen(false);
                setForgotSubmitted(false);
              }}
              className="absolute right-4 top-4 text-slate-400 hover:text-slate-600 transition-colors"
            >
              <X className="h-5 w-5" />
            </button>

            {!forgotSubmitted ? (
              <>
                <h3 className="text-lg font-bold text-slate-900 mb-2">Reset Password</h3>
                <p className="text-sm text-slate-500 mb-4">
                  Enter your registered corporate email address and we will send you instructions to reset your security credentials.
                </p>
                <form
                  onSubmit={(e) => {
                    e.preventDefault();
                    if (forgotEmail) setForgotSubmitted(true);
                  }}
                  className="space-y-4"
                >
                  <div>
                    <label htmlFor="forgot-email" className="block text-xs font-medium text-slate-700 mb-1">
                      Email address
                    </label>
                    <input
                      id="forgot-email"
                      type="email"
                      required
                      value={forgotEmail}
                      onChange={(e) => setForgotEmail(e.target.value)}
                      placeholder="name@company.com"
                      className="w-full rounded-xl border border-slate-300 bg-slate-50 px-3.5 py-2 text-sm text-slate-800 placeholder-slate-400 focus:border-blue-500 focus:bg-white focus:outline-none"
                    />
                  </div>
                  <div className="flex justify-end gap-2 pt-2">
                    <button
                      type="button"
                      onClick={() => setIsForgotModalOpen(false)}
                      className="rounded-lg px-4 py-2 text-sm text-slate-600 hover:bg-slate-100 transition-colors"
                    >
                      Cancel
                    </button>
                    <button
                      type="submit"
                      className="rounded-lg bg-blue-600 px-4 py-2 text-sm font-semibold text-white hover:bg-blue-700 transition-colors shadow-xs"
                    >
                      Send Reset Instructions
                    </button>
                  </div>
                </form>
              </>
            ) : (
              <div className="text-center py-4">
                <div className="mx-auto mb-3 flex h-12 w-12 items-center justify-center rounded-full bg-emerald-50 text-emerald-600">
                  <CheckCircle2 className="h-6 w-6" />
                </div>
                <h3 className="text-lg font-bold text-slate-900 mb-1">Check your inbox</h3>
                <p className="text-sm text-slate-500 mb-6">
                  If an account exists for <span className="font-semibold text-slate-800">{forgotEmail}</span>, password reset instructions have been dispatched.
                </p>
                <button
                  type="button"
                  onClick={() => {
                    setIsForgotModalOpen(false);
                    setForgotSubmitted(false);
                    setForgotEmail('');
                  }}
                  className="rounded-xl bg-slate-100 px-6 py-2.5 text-sm font-semibold text-slate-800 hover:bg-slate-200 transition-colors"
                >
                  Done
                </button>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
