import { useState, useEffect } from 'react';
import { Wrench, Shield, Mail, Phone, Calendar, Award, CheckCircle2, Sparkles } from 'lucide-react';
import { useAuth } from '@/contexts/AuthContext';
import { technicianService } from '@/services/technician.service';
import { skillService } from '@/services/skill.service';
import type { Technician } from '@/types/technician.types';
import type { Skill } from '@/types/skill.types';
import { formatDate } from '@/utils/format';

export default function TechnicianProfile() {
  const { user } = useAuth();
  const [profile, setProfile] = useState<Technician | null>(null);
  const [mySkills, setMySkills] = useState<Skill[]>([]);
  const [isLoading, setIsLoading] = useState<boolean>(true);

  useEffect(() => {
    async function loadData() {
      setIsLoading(true);
      try {
        const [profData, skillsData] = await Promise.all([
          technicianService.getMyProfile(),
          skillService.getMySkills().catch(() => []),
        ]);
        setProfile(profData);
        setMySkills(skillsData);
      } catch (err) {
        console.error('Failed to load technician profile', err);
      } finally {
        setIsLoading(false);
      }
    }
    loadData();
  }, []);

  return (
    <div className="flex flex-col gap-6 py-2 animate-fade-in select-none">
      {/* ── Workspace Header ── */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-slate-200 pb-5">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <span className="inline-flex items-center gap-1.5 rounded-full border border-emerald-200 bg-emerald-50 px-2.5 py-0.5 text-[11px] font-semibold text-emerald-700">
              <Wrench className="h-3.5 w-3.5 text-emerald-600" />
              <span>My Field Workspace</span>
            </span>
            <span className="inline-flex items-center gap-1 rounded-full border border-slate-200 bg-slate-100 px-2.5 py-0.5 text-[11px] font-medium text-slate-700">
              <Shield className="h-3 w-3 text-purple-600" />
              <span>{user?.role || 'Technician'}</span>
            </span>
          </div>

          <h1 className="text-2xl md:text-3xl font-extrabold tracking-tight text-slate-900">
            My Technician Profile
          </h1>
          <p className="text-xs md:text-sm text-slate-500 mt-0.5">
            View employee credential details, certified skills taxonomy, and assignment telemetry.
          </p>
        </div>
      </div>

      {/* ── Main Profile Card ── */}
      <div className="max-w-3xl rounded-xl border border-slate-200 bg-white p-6 shadow-xs space-y-6">
        {isLoading ? (
          <div className="py-12 text-center text-xs text-slate-500">
            <span>Loading profile telemetry...</span>
          </div>
        ) : (
          <>
            {/* Header summary */}
            <div className="flex flex-wrap items-center justify-between gap-4 border-b border-slate-200 pb-5">
              <div className="flex items-center gap-4">
                <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-gradient-to-br from-emerald-600 to-emerald-500 text-white font-extrabold text-xl shadow-md">
                  {user?.full_name ? user.full_name.substring(0, 2).toUpperCase() : 'AR'}
                </div>
                <div>
                  <div className="flex items-center gap-2">
                    <span className="font-mono text-xs font-bold text-emerald-700 bg-emerald-50 px-2 py-0.5 rounded border border-emerald-200">
                      {profile?.employee_code || 'TECH-001'}
                    </span>
                    <span className="rounded-full bg-emerald-50 border border-emerald-200 px-2.5 py-0.5 text-[10px] font-bold text-emerald-700">
                      {profile?.availability_status || 'AVAILABLE'}
                    </span>
                  </div>
                  <h2 className="text-xl font-bold text-slate-900 mt-1">{profile?.user?.full_name || user?.full_name}</h2>
                </div>
              </div>
            </div>

            {/* Profile Fields Read-Only Grid */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-xs">
              <div className="rounded-lg border border-slate-200 bg-slate-50/70 p-4 space-y-1">
                <div className="flex items-center gap-2 text-slate-500 mb-1">
                  <Mail className="h-4 w-4 text-emerald-600" />
                  <span className="font-semibold uppercase tracking-wider text-[10px]">Email Address</span>
                </div>
                <div className="font-semibold text-slate-800">{profile?.user?.email || user?.email}</div>
              </div>

              <div className="rounded-lg border border-slate-200 bg-slate-50/70 p-4 space-y-1">
                <div className="flex items-center gap-2 text-slate-500 mb-1">
                  <Phone className="h-4 w-4 text-emerald-600" />
                  <span className="font-semibold uppercase tracking-wider text-[10px]">Contact Phone</span>
                </div>
                <div className="font-semibold text-slate-800">{profile?.user?.phone || '+1 (555) 019-2834'}</div>
              </div>

              <div className="rounded-lg border border-slate-200 bg-slate-50/70 p-4 space-y-1">
                <div className="flex items-center gap-2 text-slate-500 mb-1">
                  <Wrench className="h-4 w-4 text-emerald-600" />
                  <span className="font-semibold uppercase tracking-wider text-[10px]">Primary Certified Skill</span>
                </div>
                <div className="font-bold text-emerald-700">{profile?.primary_skill?.skill_name || 'HVAC Master'}</div>
              </div>

              <div className="rounded-lg border border-slate-200 bg-slate-50/70 p-4 space-y-1">
                <div className="flex items-center gap-2 text-slate-500 mb-1">
                  <Award className="h-4 w-4 text-emerald-600" />
                  <span className="font-semibold uppercase tracking-wider text-[10px]">Field Experience</span>
                </div>
                <div className="font-bold text-slate-900">{profile?.years_experience || 5} Years</div>
              </div>

              <div className="rounded-lg border border-slate-200 bg-slate-50/70 p-4 space-y-1">
                <div className="flex items-center gap-2 text-slate-500 mb-1">
                  <CheckCircle2 className="h-4 w-4 text-emerald-600" />
                  <span className="font-semibold uppercase tracking-wider text-[10px]">Account Status</span>
                </div>
                <div className="font-bold text-emerald-700">{profile?.user?.status || 'ACTIVE'}</div>
              </div>

              <div className="rounded-lg border border-slate-200 bg-slate-50/70 p-4 space-y-1">
                <div className="flex items-center gap-2 text-slate-500 mb-1">
                  <Calendar className="h-4 w-4 text-emerald-600" />
                  <span className="font-semibold uppercase tracking-wider text-[10px]">Member Since</span>
                </div>
                <div className="font-mono text-slate-600">{formatDate(profile?.created_at || new Date().toISOString())}</div>
              </div>
            </div>

            {/* Certified Skills Taxonomy List */}
            <div className="border-t border-slate-200 pt-5">
              <div className="flex items-center gap-2 mb-3">
                <Sparkles className="h-4 w-4 text-purple-600" />
                <h3 className="text-sm font-bold text-slate-900 uppercase tracking-wider text-[11px]">
                  My Certified Skill Qualifications
                </h3>
              </div>

              <div className="flex flex-wrap gap-2">
                {mySkills.length > 0 ? (
                  mySkills.map((s) => (
                    <div
                      key={s.id}
                      className="flex items-center gap-2 rounded-xl border border-purple-200 bg-purple-50 px-3 py-1.5 text-xs font-semibold text-purple-700"
                    >
                      <Wrench className="h-3.5 w-3.5 text-purple-600" />
                      <span>{s.skill_name}</span>
                      <span className="text-[10px] text-slate-500 bg-white px-1.5 py-0.2 rounded border border-slate-200">
                        {s.category}
                      </span>
                    </div>
                  ))
                ) : profile?.primary_skill ? (
                  <div className="flex items-center gap-2 rounded-xl border border-purple-200 bg-purple-50 px-3 py-1.5 text-xs font-semibold text-purple-700">
                    <Wrench className="h-3.5 w-3.5 text-purple-600" />
                    <span>{profile.primary_skill.skill_name}</span>
                    <span className="text-[10px] text-slate-500 bg-white px-1.5 py-0.2 rounded border border-slate-200">
                      {profile.primary_skill.category}
                    </span>
                  </div>
                ) : (
                  <div className="text-xs text-slate-500 italic">No skill certifications assigned yet.</div>
                )}
              </div>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
