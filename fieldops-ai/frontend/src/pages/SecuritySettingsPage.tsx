import { useState } from 'react';
import {
  KeyRound,
  Eye,
  EyeOff,
  ShieldCheck,
  AlertCircle,
  CheckCircle2,
  Loader2,
  Lock,
  ShieldAlert,
  Info,
} from 'lucide-react';
import { authService } from '@/services/auth.service';
import { useAuth } from '@/contexts/AuthContext';

export default function SecuritySettingsPage() {
  const { user, refreshUser } = useAuth();

  const [currentPassword, setCurrentPassword] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');

  const [showCurrent, setShowCurrent] = useState(false);
  const [showNew, setShowNew] = useState(false);
  const [showConfirm, setShowConfirm] = useState(false);

  const [isSubmitting, setIsSubmitting] = useState(false);
  const [successNotice, setSuccessNotice] = useState<string | null>(null);
  const [errorNotice, setErrorNotice] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setErrorNotice(null);
    setSuccessNotice(null);

    if (newPassword.length < 8) {
      setErrorNotice('New password must be at least 8 characters in length.');
      return;
    }

    if (newPassword !== confirmPassword) {
      setErrorNotice('New password and confirmation password do not match.');
      return;
    }

    if (currentPassword === newPassword) {
      setErrorNotice('New password must be different from your current password.');
      return;
    }

    setIsSubmitting(true);
    try {
      const response = await authService.changePassword({
        current_password: currentPassword,
        new_password: newPassword,
        confirm_password: confirmPassword,
      });

      setSuccessNotice(response.message || 'Password changed successfully. Your permanent credentials are now updated.');
      setCurrentPassword('');
      setNewPassword('');
      setConfirmPassword('');
      await refreshUser();
    } catch (err: any) {
      const status = err?.response?.status;
      if (status === 401) {
        setErrorNotice('Current password is incorrect. Please verify your existing password and retry.');
      } else {
        const msg =
          err?.response?.data?.error?.message ||
          err?.response?.data?.detail ||
          'Failed to change password. Please ensure requirements are satisfied.';
        setErrorNotice(msg);
      }
    } finally {
      setIsSubmitting(false);
    }
  };

  const passwordRules = [
    { label: 'At least 8 characters long', met: newPassword.length >= 8 },
    { label: 'Passwords match', met: Boolean(newPassword && newPassword === confirmPassword) },
    { label: 'Different from current password', met: Boolean(newPassword && currentPassword && newPassword !== currentPassword) },
  ];

  return (
    <div className="space-y-6 animate-fade-in">
      {/* Top Description */}
      <div>
        <h2 className="text-base font-bold text-slate-900">Security & Credentials</h2>
        <p className="text-xs text-slate-500 mt-0.5">
          Establish and update your secret personal password for account authentication.
        </p>
      </div>

      {/* Success Notification */}
      {successNotice && (
        <div className="flex items-start gap-2.5 rounded-xl border border-emerald-200 bg-emerald-50 p-4 text-xs text-emerald-800 animate-fade-in">
          <CheckCircle2 className="h-4 w-4 shrink-0 mt-0.5 text-emerald-600" />
          <div>
            <p className="font-bold">Credential Updated Successfully</p>
            <p className="mt-0.5 text-emerald-700">{successNotice}</p>
          </div>
        </div>
      )}

      {/* Error Notification */}
      {errorNotice && (
        <div className="flex items-start gap-2.5 rounded-xl border border-rose-200 bg-rose-50 p-4 text-xs text-rose-800 animate-fade-in">
          <AlertCircle className="h-4 w-4 shrink-0 mt-0.5 text-rose-600" />
          <div>
            <p className="font-bold">Password Change Rejected</p>
            <p className="mt-0.5 text-rose-700">{errorNotice}</p>
          </div>
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Change Password Form (Left 2 cols) */}
        <div className="lg:col-span-2 space-y-4">
          <form onSubmit={handleSubmit} className="space-y-4 text-xs">
            {/* Current Password */}
            <div>
              <label htmlFor="currentPassword" className="block font-bold text-slate-700 mb-1.5">
                Current Password <span className="text-rose-500">*</span>
              </label>
              <div className="relative">
                <div className="pointer-events-none absolute inset-y-0 left-0 flex items-center pl-3 text-slate-400">
                  <KeyRound className="h-4 w-4" />
                </div>
                <input
                  id="currentPassword"
                  type={showCurrent ? 'text' : 'password'}
                  required
                  value={currentPassword}
                  onChange={(e) => setCurrentPassword(e.target.value)}
                  placeholder="Enter current password"
                  autoComplete="current-password"
                  className="w-full rounded-xl border border-slate-200 bg-slate-50/60 pl-9 pr-10 py-2.5 text-xs text-slate-900 font-medium placeholder-slate-400 focus:bg-white focus:border-blue-600 focus:outline-none focus:ring-2 focus:ring-blue-100 transition-all"
                />
                <button
                  type="button"
                  onClick={() => setShowCurrent(!showCurrent)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600"
                  aria-label={showCurrent ? 'Hide password' : 'Show password'}
                >
                  {showCurrent ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                </button>
              </div>
            </div>

            {/* New Password */}
            <div>
              <label htmlFor="newPassword" className="block font-bold text-slate-700 mb-1.5">
                New Password <span className="text-rose-500">*</span>
              </label>
              <div className="relative">
                <div className="pointer-events-none absolute inset-y-0 left-0 flex items-center pl-3 text-slate-400">
                  <Lock className="h-4 w-4" />
                </div>
                <input
                  id="newPassword"
                  type={showNew ? 'text' : 'password'}
                  required
                  minLength={8}
                  value={newPassword}
                  onChange={(e) => setNewPassword(e.target.value)}
                  placeholder="Enter minimum 8 characters"
                  autoComplete="new-password"
                  className="w-full rounded-xl border border-slate-200 bg-slate-50/60 pl-9 pr-10 py-2.5 text-xs text-slate-900 font-medium placeholder-slate-400 focus:bg-white focus:border-blue-600 focus:outline-none focus:ring-2 focus:ring-blue-100 transition-all"
                />
                <button
                  type="button"
                  onClick={() => setShowNew(!showNew)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600"
                  aria-label={showNew ? 'Hide password' : 'Show password'}
                >
                  {showNew ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                </button>
              </div>
            </div>

            {/* Confirm New Password */}
            <div>
              <label htmlFor="confirmPassword" className="block font-bold text-slate-700 mb-1.5">
                Confirm New Password <span className="text-rose-500">*</span>
              </label>
              <div className="relative">
                <div className="pointer-events-none absolute inset-y-0 left-0 flex items-center pl-3 text-slate-400">
                  <Lock className="h-4 w-4" />
                </div>
                <input
                  id="confirmPassword"
                  type={showConfirm ? 'text' : 'password'}
                  required
                  minLength={8}
                  value={confirmPassword}
                  onChange={(e) => setConfirmPassword(e.target.value)}
                  placeholder="Re-enter new password to confirm"
                  autoComplete="new-password"
                  className="w-full rounded-xl border border-slate-200 bg-slate-50/60 pl-9 pr-10 py-2.5 text-xs text-slate-900 font-medium placeholder-slate-400 focus:bg-white focus:border-blue-600 focus:outline-none focus:ring-2 focus:ring-blue-100 transition-all"
                />
                <button
                  type="button"
                  onClick={() => setShowConfirm(!showConfirm)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600"
                  aria-label={showConfirm ? 'Hide password' : 'Show password'}
                >
                  {showConfirm ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                </button>
              </div>
            </div>

            {/* Password Validation Checklist */}
            <div className="rounded-xl border border-slate-200 bg-slate-50/70 p-3.5 space-y-1.5">
              <span className="text-[11px] font-bold text-slate-700 block mb-1">
                Password Requirements
              </span>
              {passwordRules.map((rule, idx) => (
                <div key={idx} className="flex items-center gap-2 text-[11px]">
                  <div
                    className={`h-2 w-2 rounded-full ${
                      rule.met ? 'bg-emerald-500' : 'bg-slate-300'
                    }`}
                  />
                  <span className={rule.met ? 'text-slate-800 font-medium' : 'text-slate-500'}>
                    {rule.label}
                  </span>
                </div>
              ))}
            </div>

            <div className="pt-2">
              <button
                type="submit"
                disabled={isSubmitting || !currentPassword || !newPassword || !confirmPassword}
                className="inline-flex items-center gap-2 rounded-xl bg-blue-600 px-5 py-2.5 text-xs font-semibold text-white shadow-sm hover:bg-blue-700 disabled:opacity-40 disabled:cursor-not-allowed transition-all cursor-pointer shadow-blue-600/20"
              >
                {isSubmitting ? (
                  <>
                    <Loader2 className="h-4 w-4 animate-spin" />
                    <span>Verifying & Updating...</span>
                  </>
                ) : (
                  <>
                    <ShieldCheck className="h-4 w-4" />
                    <span>Update Permanent Password</span>
                  </>
                )}
              </button>
            </div>
          </form>
        </div>

        {/* Security Policy Panel (Right 1 col) */}
        <div className="space-y-4 text-xs">
          <div className="rounded-xl border border-blue-200 bg-blue-50/40 p-4 space-y-3">
            <div className="flex items-center gap-2 text-blue-900 font-bold">
              <ShieldAlert className="h-4 w-4 text-blue-600" />
              <span>Security & Privacy Guarantee</span>
            </div>
            <p className="text-slate-600 leading-relaxed text-[11px]">
              FieldOps AI enforces irreversible cryptographic hashing using bcrypt. Your permanent password is known exclusively to you.
            </p>
            <div className="border-t border-blue-200/60 pt-2.5 space-y-2 text-[11px] text-slate-600">
              <div className="flex items-start gap-2">
                <Info className="h-3.5 w-3.5 shrink-0 text-blue-500 mt-0.5" />
                <span>Administrators cannot retrieve or inspect your password.</span>
              </div>
              <div className="flex items-start gap-2">
                <Info className="h-3.5 w-3.5 shrink-0 text-blue-500 mt-0.5" />
                <span>Onboarding or reset passwords are strictly temporary.</span>
              </div>
              <div className="flex items-start gap-2">
                <Info className="h-3.5 w-3.5 shrink-0 text-blue-500 mt-0.5" />
                <span>All password change actions are recorded in immutable audit logs.</span>
              </div>
            </div>
          </div>

          <div className="rounded-xl border border-slate-200 bg-white p-4 space-y-2">
            <span className="font-bold text-slate-800 block text-xs">Session Identity</span>
            <div className="text-[11px] text-slate-500 space-y-1">
              <div>
                Account: <span className="font-semibold text-slate-700">{user?.email}</span>
              </div>
              <div>
                Role: <span className="font-semibold text-slate-700">{user?.role}</span>
              </div>
              <div>
                Status:{' '}
                <span className="inline-flex items-center gap-1 font-semibold text-emerald-600">
                  <span className="h-1.5 w-1.5 rounded-full bg-emerald-500" /> Active Session
                </span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
