import { useState, useEffect } from 'react';
import {
  User,
  Mail,
  Phone,
  Shield,
  CheckCircle2,
  AlertCircle,
  Loader2,
  Calendar,
  Lock,
  RotateCcw,
  Save,
} from 'lucide-react';
import { useAuth } from '@/contexts/AuthContext';
import { formatDate } from '@/utils/format';

export default function ProfileSettingsPage() {
  const { user, updateProfile, refreshUser } = useAuth();

  const [fullName, setFullName] = useState(user?.full_name || '');
  const [phone, setPhone] = useState(user?.phone || '');
  const [isSaving, setIsSaving] = useState(false);
  const [successNotice, setSuccessNotice] = useState<string | null>(null);
  const [errorNotice, setErrorNotice] = useState<string | null>(null);

  useEffect(() => {
    if (user) {
      setFullName(user.full_name || '');
      setPhone(user.phone || '');
    }
  }, [user]);

  const hasChanges =
    fullName.trim() !== (user?.full_name || '').trim() ||
    phone.trim() !== (user?.phone || '').trim();

  const handleReset = () => {
    if (user) {
      setFullName(user.full_name || '');
      setPhone(user.phone || '');
      setErrorNotice(null);
      setSuccessNotice(null);
    }
  };

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault();
    setErrorNotice(null);
    setSuccessNotice(null);

    if (fullName.trim().length < 2) {
      setErrorNotice('Full name must be at least 2 characters long.');
      return;
    }

    setIsSaving(true);
    try {
      const payload: { full_name?: string; phone?: string } = {
        full_name: fullName.trim(),
      };
      if (phone.trim()) {
        payload.phone = phone.trim();
      }
      await updateProfile(payload);
      await refreshUser();
      setSuccessNotice('Profile details saved and updated successfully.');
      setTimeout(() => setSuccessNotice(null), 5000);
    } catch (err: any) {
      const msg =
        err?.response?.data?.error?.message ||
        err?.response?.data?.detail ||
        'Failed to save profile changes. Please verify your connection and try again.';
      setErrorNotice(msg);
    } finally {
      setIsSaving(false);
    }
  };

  const getRoleBadge = (role?: string) => {
    switch (role) {
      case 'Administrator':
        return {
          label: 'Administrator',
          className: 'bg-purple-50 text-purple-700 border-purple-200',
          desc: 'Full administrative authority over platform users, technicians, skills, and system parameters.',
        };
      case 'Technician':
        return {
          label: 'Field Technician',
          className: 'bg-emerald-50 text-emerald-700 border-emerald-200',
          desc: 'Authorized for mobile field operations, route navigation, and work order execution.',
        };
      case 'Dispatcher':
      default:
        return {
          label: 'Dispatcher',
          className: 'bg-blue-50 text-blue-700 border-blue-200',
          desc: 'Authorized for job creation, intelligent dispatch recommendations, live map monitoring, and ETA overrides.',
        };
    }
  };

  const roleMeta = getRoleBadge(user?.role);

  return (
    <div className="space-y-6 animate-fade-in">
      {/* Top Banner Notice */}
      <div>
        <h2 className="text-base font-bold text-slate-900">Personal Information</h2>
        <p className="text-xs text-slate-500 mt-0.5">
          Review and update your public name and contact details across FieldOps AI.
        </p>
      </div>

      {/* Success Alert */}
      {successNotice && (
        <div className="flex items-center gap-2 rounded-xl border border-emerald-200 bg-emerald-50 p-3.5 text-xs text-emerald-800 animate-fade-in">
          <CheckCircle2 className="h-4 w-4 shrink-0 text-emerald-600" />
          <span className="font-semibold">{successNotice}</span>
        </div>
      )}

      {/* Error Alert */}
      {errorNotice && (
        <div className="flex items-center gap-2 rounded-xl border border-rose-200 bg-rose-50 p-3.5 text-xs text-rose-800 animate-fade-in">
          <AlertCircle className="h-4 w-4 shrink-0 text-rose-600" />
          <span className="font-semibold">{errorNotice}</span>
        </div>
      )}

      <form onSubmit={handleSave} className="space-y-6">
        <div className="grid grid-cols-1 md:grid-cols-2 gap-5 text-xs">
          {/* Full Name */}
          <div>
            <label htmlFor="fullName" className="block font-bold text-slate-700 mb-1.5">
              Full Name <span className="text-rose-500">*</span>
            </label>
            <div className="relative">
              <div className="pointer-events-none absolute inset-y-0 left-0 flex items-center pl-3 text-slate-400">
                <User className="h-4 w-4" />
              </div>
              <input
                id="fullName"
                type="text"
                required
                minLength={2}
                maxLength={255}
                value={fullName}
                onChange={(e) => setFullName(e.target.value)}
                placeholder="Enter full name"
                className="w-full rounded-xl border border-slate-200 bg-slate-50/60 pl-9 pr-3.5 py-2.5 text-xs text-slate-900 font-medium placeholder-slate-400 focus:bg-white focus:border-blue-600 focus:outline-none focus:ring-2 focus:ring-blue-100 transition-all"
              />
            </div>
            <p className="mt-1 text-[11px] text-slate-400">
              Your name displayed across dispatch logs, assignment records, and navigation.
            </p>
          </div>

          {/* Contact Phone */}
          <div>
            <label htmlFor="phone" className="block font-bold text-slate-700 mb-1.5">
              Contact Phone
            </label>
            <div className="relative">
              <div className="pointer-events-none absolute inset-y-0 left-0 flex items-center pl-3 text-slate-400">
                <Phone className="h-4 w-4" />
              </div>
              <input
                id="phone"
                type="tel"
                maxLength={50}
                value={phone}
                onChange={(e) => setPhone(e.target.value)}
                placeholder="+1 (555) 000-0000"
                className="w-full rounded-xl border border-slate-200 bg-slate-50/60 pl-9 pr-3.5 py-2.5 text-xs text-slate-900 font-medium placeholder-slate-400 focus:bg-white focus:border-blue-600 focus:outline-none focus:ring-2 focus:ring-blue-100 transition-all"
              />
            </div>
            <p className="mt-1 text-[11px] text-slate-400">
              Direct telephone or dispatch mobile contact number.
            </p>
          </div>

          {/* Email Address (Read-only) */}
          <div>
            <div className="flex items-center justify-between mb-1.5">
              <label htmlFor="email" className="block font-bold text-slate-700">
                Email Address
              </label>
              <span className="inline-flex items-center gap-1 text-[10px] text-slate-400 font-medium">
                <Lock className="h-3 w-3" /> Managed by Administrator
              </span>
            </div>
            <div className="relative">
              <div className="pointer-events-none absolute inset-y-0 left-0 flex items-center pl-3 text-slate-400">
                <Mail className="h-4 w-4" />
              </div>
              <input
                id="email"
                type="email"
                readOnly
                disabled
                value={user?.email || ''}
                className="w-full rounded-xl border border-slate-200 bg-slate-100/80 pl-9 pr-3.5 py-2.5 text-xs text-slate-600 font-medium cursor-not-allowed select-all"
              />
            </div>
            <p className="mt-1 text-[11px] text-slate-400">
              Primary login credential and security notifications recipient.
            </p>
          </div>

          {/* Account Role (Read-only) */}
          <div>
            <div className="flex items-center justify-between mb-1.5">
              <label className="block font-bold text-slate-700">
                Security Role
              </label>
              <span className="inline-flex items-center gap-1 text-[10px] text-slate-400 font-medium">
                <Lock className="h-3 w-3" /> RBAC Enforced
              </span>
            </div>
            <div className="flex items-center gap-2 rounded-xl border border-slate-200 bg-slate-100/80 px-3.5 py-2 text-xs">
              <Shield className="h-4 w-4 text-slate-400" />
              <span className={`rounded px-2 py-0.5 text-[11px] font-bold border ${roleMeta.className}`}>
                {roleMeta.label}
              </span>
            </div>
            <p className="mt-1 text-[11px] text-slate-500 leading-normal">
              {roleMeta.desc}
            </p>
          </div>
        </div>

        {/* Account Metadata Cards */}
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 border-t border-slate-100 pt-5 text-xs">
          <div className="rounded-xl border border-slate-200 bg-slate-50/50 p-3.5 flex items-center justify-between">
            <div className="flex items-center gap-2.5">
              <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-emerald-50 text-emerald-600 border border-emerald-100">
                <div className="h-2 w-2 rounded-full bg-emerald-500 animate-pulse" />
              </div>
              <div>
                <span className="font-bold text-slate-800 block">Account Status</span>
                <span className="text-[11px] text-slate-500">System authorization verified</span>
              </div>
            </div>
            <span className="rounded-full bg-emerald-100/80 px-2.5 py-0.5 text-[10px] font-bold text-emerald-700">
              {user?.is_active ? 'ACTIVE' : 'INACTIVE'}
            </span>
          </div>

          <div className="rounded-xl border border-slate-200 bg-slate-50/50 p-3.5 flex items-center justify-between">
            <div className="flex items-center gap-2.5">
              <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-blue-50 text-blue-600 border border-blue-100">
                <Calendar className="h-4 w-4" />
              </div>
              <div>
                <span className="font-bold text-slate-800 block">Member Since</span>
                <span className="text-[11px] text-slate-500">Account provisioned date</span>
              </div>
            </div>
            <span className="text-xs font-semibold text-slate-700">
              {user?.created_at ? formatDate(user.created_at) : 'N/A'}
            </span>
          </div>
        </div>

        {/* Action Controls */}
        <div className="flex items-center justify-end gap-3 border-t border-slate-100 pt-4">
          <button
            type="button"
            onClick={handleReset}
            disabled={!hasChanges || isSaving}
            className="inline-flex items-center gap-1.5 rounded-xl border border-slate-200 bg-white px-4 py-2 text-xs font-semibold text-slate-700 hover:bg-slate-50 disabled:opacity-40 disabled:cursor-not-allowed transition-all cursor-pointer"
          >
            <RotateCcw className="h-3.5 w-3.5 text-slate-400" />
            <span>Discard Changes</span>
          </button>

          <button
            type="submit"
            disabled={!hasChanges || isSaving}
            className="inline-flex items-center gap-2 rounded-xl bg-blue-600 px-5 py-2 text-xs font-semibold text-white shadow-sm hover:bg-blue-700 disabled:opacity-40 disabled:cursor-not-allowed transition-all cursor-pointer shadow-blue-600/20"
          >
            {isSaving ? (
              <>
                <Loader2 className="h-3.5 w-3.5 animate-spin" />
                <span>Saving...</span>
              </>
            ) : (
              <>
                <Save className="h-3.5 w-3.5" />
                <span>Save Profile</span>
              </>
            )}
          </button>
        </div>
      </form>
    </div>
  );
}
