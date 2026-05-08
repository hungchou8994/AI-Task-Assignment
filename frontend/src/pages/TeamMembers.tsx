/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

import React, { useState, useMemo } from 'react';
import {
  Search,
  Plus,
  Mail,
  X,
  Pencil,
  Trash2,
  Loader2,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import { usePeople, useCreatePerson, useUpdatePerson, useDeletePerson } from '../hooks/usePeople';
import { useTasks } from '../hooks/useTasks';
import { useAddWorkspaceMember, useWorkspaceMembers } from '../hooks/useWorkspaces';
import { useProjectContext } from '../context/ProjectContext';
import type { Person, AvailabilityStatus, PersonUpdate, WorkspacePermissionRole } from '../types';
import { useLanguage } from '../i18n/LanguageContext';

type AssignableWorkspaceRole = Extract<WorkspacePermissionRole, 'admin' | 'member'>;

// ─── Add Person Modal ─────────────────────────────────────────────────────────

function AddPersonModal({
  currentWorkspaceId,
  onClose,
  t,
}: {
  currentWorkspaceId: string | null;
  onClose: () => void;
  t: ReturnType<typeof useLanguage>['t'];
}) {
  const createPerson = useCreatePerson();
  const addWorkspaceMember = useAddWorkspaceMember(currentWorkspaceId);
  const [name, setName] = useState('');
  const [email, setEmail] = useState('');
  const [role, setRole] = useState('');
  const [workspaceRole, setWorkspaceRole] = useState<AssignableWorkspaceRole>('member');
  const [bio, setBio] = useState('');
  const [skills, setSkills] = useState('');
  const [availability, setAvailability] = useState<AvailabilityStatus | ''>('');
  const [maxCapacity, setMaxCapacity] = useState(8);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!name.trim()) return;
    setError(null);
    const normalizedEmail = email.trim().toLowerCase();

    try {
      if (currentWorkspaceId && normalizedEmail) {
        try {
          await addWorkspaceMember.mutateAsync({ email: normalizedEmail, role: workspaceRole });
        } catch (err) {
          if (!(err instanceof Error) || !err.message.startsWith('409:')) {
            throw err;
          }
        }
      }

      await createPerson.mutateAsync({
        name: name.trim(),
        email: normalizedEmail || null,
        role: role.trim() || null,
        bio: bio.trim() || null,
        skills: skills
          .split(',')
          .map((s) => s.trim())
          .filter(Boolean),
        availability: (availability as AvailabilityStatus) || null,
        max_capacity: maxCapacity,
      });

      onClose();
    } catch (err) {
      setError(err instanceof Error ? err.message : t.teamMembers.addMemberFailed);
    }
  }

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60"
      onClick={(e) => e.target === e.currentTarget && onClose()}
    >
      <div className="bg-background border border-border w-full max-w-lg overflow-hidden">
        <div className="flex items-center justify-between px-6 py-4 border-b border-border">
          <h3 className="text-sm font-bold text-foreground">{t.teamMembers.addTeamMember}</h3>
          <button onClick={onClose} className="p-1.5 text-muted-foreground hover:text-foreground hover:bg-muted transition-colors">
            <X className="w-4 h-4" />
          </button>
        </div>
        <form onSubmit={handleSubmit}>
          <div className="px-6 py-5 space-y-4 max-h-[60vh] overflow-y-auto">
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="text-[10px] font-bold uppercase tracking-widest text-muted-foreground font-mono block mb-1">
                  {t.teamMembers.name} *
                </label>
                <input
                  autoFocus
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  required
                  className="w-full border border-border bg-background text-foreground px-3 py-2 text-sm focus:ring-1 focus:ring-primary outline-none"
                />
              </div>
              <div>
                <label className="text-[10px] font-bold uppercase tracking-widest text-muted-foreground font-mono block mb-1">
                  {t.teamMembers.email}
                </label>
                <input
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  className="w-full border border-border bg-background text-foreground px-3 py-2 text-sm focus:ring-1 focus:ring-primary outline-none"
                />
              </div>
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="text-[10px] font-bold uppercase tracking-widest text-muted-foreground font-mono block mb-1">
                  {t.teamMembers.role}
                </label>
                <input
                  value={role}
                  onChange={(e) => setRole(e.target.value)}
                  placeholder="e.g. Frontend Engineer"
                  className="w-full border border-border bg-background text-foreground px-3 py-2 text-sm focus:ring-1 focus:ring-primary outline-none"
                />
              </div>
              <div>
                <label className="text-[10px] font-bold uppercase tracking-widest text-muted-foreground font-mono block mb-1">
                  {t.teamMembers.workspaceRole}
                </label>
                <select
                  value={workspaceRole}
                  onChange={(e) => setWorkspaceRole(e.target.value as AssignableWorkspaceRole)}
                  className="w-full border border-border bg-background text-foreground px-3 py-2 text-sm focus:ring-1 focus:ring-primary outline-none"
                >
                  <option value="member">{t.teamMembers.workspaceRoleMember}</option>
                  <option value="admin">{t.teamMembers.workspaceRoleAdmin}</option>
                </select>
                <p className="mt-1 text-[10px] text-muted-foreground">
                  {t.teamMembers.workspaceRoleHelp}
                </p>
              </div>
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="text-[10px] font-bold uppercase tracking-widest text-muted-foreground font-mono block mb-1">
                  {t.teamMembers.availability}
                </label>
                <select
                  value={availability}
                  onChange={(e) => setAvailability(e.target.value as AvailabilityStatus | '')}
                  className="w-full border border-border bg-background text-foreground px-3 py-2 text-sm focus:ring-1 focus:ring-primary outline-none"
                >
                  <option value="">{t.teamMembers.availabilityUnknown}</option>
                  <option value="available">{t.teamMembers.availabilityAvailable}</option>
                  <option value="busy">{t.teamMembers.availabilityBusy}</option>
                  <option value="on_leave">{t.teamMembers.availabilityOnLeave}</option>
                  </select>
                </div>
              <div>
                <label className="text-[10px] font-bold uppercase tracking-widest text-muted-foreground font-mono block mb-1">
                  {t.teamMembers.maxCapacity}
                </label>
                <input
                  type="number"
                  min={1}
                  max={100}
                  value={maxCapacity}
                  onChange={(e) => setMaxCapacity(Math.max(1, Math.min(100, Number(e.target.value))))}
                  className="w-full border border-border bg-background text-foreground px-3 py-2 text-sm focus:ring-1 focus:ring-primary outline-none"
                />
              </div>
            </div>
            <div>
              <label className="text-[10px] font-bold uppercase tracking-widest text-muted-foreground font-mono block mb-1">
                {t.teamMembers.skills} (comma-separated)
              </label>
              <input
                value={skills}
                onChange={(e) => setSkills(e.target.value)}
                placeholder="React, TypeScript, Node.js"
                className="w-full border border-border bg-background text-foreground px-3 py-2 text-sm focus:ring-1 focus:ring-primary outline-none"
              />
            </div>
            <div>
              <label className="text-[10px] font-bold uppercase tracking-widest text-muted-foreground font-mono block mb-1">
                {t.teamMembers.bio}
              </label>
              <textarea
                value={bio}
                onChange={(e) => setBio(e.target.value)}
                rows={3}
                className="w-full border border-border bg-background text-foreground px-3 py-2 text-sm focus:ring-1 focus:ring-primary outline-none resize-none"
              />
            </div>
            {error && <p className="text-xs font-medium text-destructive">{error}</p>}
          </div>
          <div className="flex justify-end gap-3 px-6 py-4 border-t border-border">
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2 text-sm font-bold text-muted-foreground hover:text-foreground transition-colors"
            >
              {t.teamMembers.cancel}
            </button>
            <button
              type="submit"
              disabled={createPerson.isPending || addWorkspaceMember.isPending}
              className="px-4 py-2 bg-primary text-primary-foreground text-sm font-bold hover:bg-primary/90 transition-colors disabled:opacity-60 flex items-center gap-2"
            >
              {(createPerson.isPending || addWorkspaceMember.isPending) && <Loader2 className="w-4 h-4 animate-spin" />}
              {t.teamMembers.addMember}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

// ─── Edit Person Modal ────────────────────────────────────────────────────────

function EditPersonModal({ person, onClose, t }: { person: Person; onClose: () => void; t: ReturnType<typeof useLanguage>['t'] }) {
  const updatePerson = useUpdatePerson();
  const deletePerson = useDeletePerson();
  const [name, setName] = useState(person.name);
  const [email, setEmail] = useState(person.email ?? '');
  const [role, setRole] = useState(person.role ?? '');
  const [bio, setBio] = useState(person.bio ?? '');
  const [skills, setSkills] = useState((person.skills ?? []).join(', '));
  const [availability, setAvailability] = useState<AvailabilityStatus | ''>(
    person.availability ?? '',
  );
  const [maxCapacity, setMaxCapacity] = useState(person.max_capacity ?? 8);
  const [confirmDelete, setConfirmDelete] = useState(false);

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    const data: PersonUpdate = {
      name: name.trim() || person.name,
      email: email.trim() || null,
      role: role.trim() || null,
      bio: bio.trim() || null,
      skills: skills
        .split(',')
        .map((s) => s.trim())
        .filter(Boolean),
      availability: (availability as AvailabilityStatus) || null,
      max_capacity: maxCapacity,
    };
    updatePerson.mutate({ id: person.id, data }, { onSuccess: onClose });
  }

  function handleDelete() {
    deletePerson.mutate(person.id, { onSuccess: onClose });
  }

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60"
      onClick={(e) => e.target === e.currentTarget && onClose()}
    >
      <div className="bg-background border border-border w-full max-w-lg overflow-hidden">
        <div className="flex items-center justify-between px-6 py-4 border-b border-border">
          <h3 className="text-sm font-bold text-foreground">{t.teamMembers.editProfile}</h3>
          <button onClick={onClose} className="p-1.5 text-muted-foreground hover:text-foreground hover:bg-muted transition-colors">
            <X className="w-4 h-4" />
          </button>
        </div>
        <form onSubmit={handleSubmit}>
          <div className="px-6 py-5 space-y-4 max-h-[60vh] overflow-y-auto">
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="text-[10px] font-bold uppercase tracking-widest text-muted-foreground font-mono block mb-1">
                  {t.teamMembers.name} *
                </label>
                <input
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  required
                  className="w-full border border-border bg-background text-foreground px-3 py-2 text-sm focus:ring-1 focus:ring-primary outline-none"
                />
              </div>
              <div>
                <label className="text-[10px] font-bold uppercase tracking-widest text-muted-foreground font-mono block mb-1">
                  {t.teamMembers.email}
                </label>
                <input
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  className="w-full border border-border bg-background text-foreground px-3 py-2 text-sm focus:ring-1 focus:ring-primary outline-none"
                />
              </div>
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="text-[10px] font-bold uppercase tracking-widest text-muted-foreground font-mono block mb-1">
                  {t.teamMembers.role}
                </label>
                <input
                  value={role}
                  onChange={(e) => setRole(e.target.value)}
                  placeholder="e.g. Frontend Engineer"
                  className="w-full border border-border bg-background text-foreground px-3 py-2 text-sm focus:ring-1 focus:ring-primary outline-none"
                />
              </div>
              <div>
                <label className="text-[10px] font-bold uppercase tracking-widest text-muted-foreground font-mono block mb-1">
                  {t.teamMembers.availability}
                </label>
                <select
                  value={availability}
                  onChange={(e) => setAvailability(e.target.value as AvailabilityStatus | '')}
                  className="w-full border border-border bg-background text-foreground px-3 py-2 text-sm focus:ring-1 focus:ring-primary outline-none"
                >
                  <option value="">{t.teamMembers.availabilityUnknown}</option>
                  <option value="available">{t.teamMembers.availabilityAvailable}</option>
                  <option value="busy">{t.teamMembers.availabilityBusy}</option>
                  <option value="on_leave">{t.teamMembers.availabilityOnLeave}</option>
                </select>
              </div>
            </div>
            <div>
              <label className="text-[10px] font-bold uppercase tracking-widest text-muted-foreground font-mono block mb-1">
                {t.teamMembers.maxCapacity}
              </label>
              <input
                type="number"
                min={1}
                max={100}
                value={maxCapacity}
                onChange={(e) => setMaxCapacity(Math.max(1, Math.min(100, Number(e.target.value))))}
                className="w-full border border-border bg-background text-foreground px-3 py-2 text-sm focus:ring-1 focus:ring-primary outline-none"
              />
            </div>
            <div>
              <label className="text-[10px] font-bold uppercase tracking-widest text-muted-foreground font-mono block mb-1">
                {t.teamMembers.skills} (comma-separated)
              </label>
              <input
                value={skills}
                onChange={(e) => setSkills(e.target.value)}
                placeholder="React, TypeScript, Node.js"
                className="w-full border border-border bg-background text-foreground px-3 py-2 text-sm focus:ring-1 focus:ring-primary outline-none"
              />
            </div>
            <div>
              <label className="text-[10px] font-bold uppercase tracking-widest text-muted-foreground font-mono block mb-1">
                {t.teamMembers.bio}
              </label>
              <textarea
                value={bio}
                onChange={(e) => setBio(e.target.value)}
                rows={3}
                className="w-full border border-border bg-background text-foreground px-3 py-2 text-sm focus:ring-1 focus:ring-primary outline-none resize-none"
              />
            </div>
          </div>
          <div className="flex items-center justify-between px-6 py-4 border-t border-border">
            {confirmDelete ? (
              <div className="flex items-center gap-3">
                <span className="text-sm text-destructive font-medium">{t.teamMembers.removeConfirmMessage}</span>
                <button
                  type="button"
                  onClick={handleDelete}
                  disabled={deletePerson.isPending}
                  className="text-xs font-bold text-white bg-destructive hover:bg-destructive/90 px-3 py-1.5"
                >
                  {deletePerson.isPending ? 'Removing…' : t.teamMembers.yesRemove}
                </button>
                <button
                  type="button"
                  onClick={() => setConfirmDelete(false)}
                  className="text-xs font-bold text-muted-foreground hover:text-foreground px-3 py-1.5"
                >
                  {t.teamMembers.cancel}
                </button>
              </div>
            ) : (
              <button
                type="button"
                onClick={() => setConfirmDelete(true)}
                className="flex items-center gap-2 text-sm font-bold text-destructive hover:text-destructive/80"
              >
                <Trash2 className="w-4 h-4" />
                {t.teamMembers.remove}
              </button>
            )}
            <div className="flex gap-3">
              <button
                type="button"
                onClick={onClose}
                className="px-4 py-2 text-sm font-bold text-muted-foreground hover:text-foreground transition-colors"
              >
                {t.teamMembers.cancel}
              </button>
              <button
                type="submit"
                disabled={updatePerson.isPending}
                className="px-4 py-2 bg-primary text-primary-foreground text-sm font-bold hover:bg-primary/90 transition-colors disabled:opacity-60 flex items-center gap-2"
              >
                {updatePerson.isPending && <Loader2 className="w-4 h-4 animate-spin" />}
                {t.teamMembers.saveChanges}
              </button>
            </div>
          </div>
        </form>
      </div>
    </div>
  );
}

// ─── Member Card ──────────────────────────────────────────────────────────────

function getAvailabilityConfig(status: AvailabilityStatus, t: ReturnType<typeof useLanguage>['t']) {
  const configs: Record<AvailabilityStatus, { label: string; dot: string; badge: string }> = {
    available: { label: t.teamMembers.availabilityAvailable, dot: 'bg-success', badge: 'bg-success/10 text-success' },
    busy: { label: t.teamMembers.availabilityBusy, dot: 'bg-warning', badge: 'bg-warning/10 text-warning' },
    on_leave: { label: t.teamMembers.availabilityOnLeave, dot: 'bg-destructive/70', badge: 'bg-destructive/10 text-destructive' },
  };
  return configs[status];
}

function getInitials(name: string) {
  return name
    .split(' ')
    .map((n) => n[0])
    .slice(0, 2)
    .join('')
    .toUpperCase();
}

// Deterministic color from name
const AVATAR_COLORS = [
  'bg-primary/10 text-primary',
  'bg-secondary text-secondary-foreground',
  'bg-success/10 text-success',
  'bg-warning/10 text-warning',
  'bg-destructive/10 text-destructive',
  'bg-muted text-muted-foreground',
];

function avatarColor(name: string) {
  let h = 0;
  for (let i = 0; i < name.length; i++) h = (h * 31 + name.charCodeAt(i)) | 0;
  return AVATAR_COLORS[Math.abs(h) % AVATAR_COLORS.length];
}

type LoadLevel = 'low' | 'medium' | 'high';

function loadLevel(taskCount: number, availability: string | null, maxCapacity: number): LoadLevel {
  if (availability === 'on_leave') return 'low';
  if (taskCount >= maxCapacity * 0.875) return 'high';
  if (taskCount >= maxCapacity * 0.5) return 'medium';
  return 'low';
}

const MemberCard = ({
  person,
  onEdit,
  openTaskCount,
  level,
  workspaceRole,
  t,
}: {
  person: Person;
  onEdit: (p: Person) => void;
  openTaskCount: number;
  level: LoadLevel;
  workspaceRole: WorkspacePermissionRole | null;
  t: ReturnType<typeof useLanguage>['t'];
  key?: React.Key;
}) => {
  const avail = person.availability ? getAvailabilityConfig(person.availability, t) : null;
  const cap = Math.min(100, (openTaskCount / (person.max_capacity || 8)) * 100);

  return (
    <div className="bg-card border border-border p-5 hover:bg-muted/20 transition-colors group">
      <div className="flex items-start justify-between mb-4">
        <div
          className={cn(
            'w-12 h-12 flex items-center justify-center text-base font-bold border border-border',
            avatarColor(person.name),
          )}
        >
          {getInitials(person.name)}
        </div>
        <div className="flex flex-col items-end gap-2">
          <div className="flex items-center gap-2">
            <button
              onClick={() => onEdit(person)}
              className="p-1.5 text-muted-foreground hover:bg-muted hover:text-foreground opacity-0 group-hover:opacity-100 transition-all"
              title={t.teamMembers.editProfile}
            >
              <Pencil className="w-3.5 h-3.5" />
            </button>
            {avail ? (
              <span
                className={cn(
                  'inline-flex items-center gap-1.5 px-2 py-0.5 text-[10px] font-bold uppercase tracking-wider',
                  avail.badge,
                )}
              >
                <span className={cn('w-1.5 h-1.5 rounded-full', avail.dot)} />
                {avail.label}
              </span>
            ) : (
              <span className="inline-flex items-center gap-1.5 px-2 py-0.5 text-[10px] font-bold uppercase tracking-wider bg-muted text-muted-foreground">
                <span className="w-1.5 h-1.5 rounded-full bg-muted-foreground/40" />
                {t.teamMembers.availabilityUnknown}
              </span>
            )}
          </div>
          <div className="text-right">
            <div className="text-[10px] font-bold uppercase tracking-widest font-mono text-muted-foreground">
              {t.workload.openTasks}
            </div>
            <div className="text-xl font-bold text-foreground tabular-nums">{openTaskCount}</div>
          </div>
        </div>
      </div>

      <div>
        <h3 className="text-sm font-bold text-foreground">{person.name}</h3>
        <p className="text-xs font-medium text-muted-foreground">{person.role ?? t.teamMembers.noRoleSet}</p>
        <span className="mt-2 inline-flex px-2 py-0.5 text-[10px] font-bold uppercase tracking-wider bg-primary/10 text-primary border border-primary/10">
          {workspaceRole ? t.teamMembers.workspaceRoleLabels[workspaceRole] : t.teamMembers.noWorkspaceAccess}
        </span>
      </div>

      <div className="mt-4">
        <div className="flex items-center justify-between text-[10px] font-bold uppercase tracking-widest text-muted-foreground mb-1.5">
          <span>{t.workload.capacity}</span>
          <span className={cn(
            "px-1.5 py-0.5 border text-[9px] font-bold",
            level === 'high' ? 'bg-destructive/10 text-destructive border-destructive/20' :
            level === 'medium' ? 'bg-warning/10 text-warning border-warning/20' :
            'bg-success/10 text-success border-success/20'
          )}>
            {level === 'high'
              ? t.workload.loadHigh
              : level === 'medium'
                ? t.workload.loadMedium
                : t.workload.loadLow} LOAD
          </span>
        </div>
        <div className="h-1.5 w-full bg-muted overflow-hidden">
          <div
            className={cn(
              'h-full transition-all',
              level === 'high' ? 'bg-destructive' :
              level === 'medium' ? 'bg-warning' :
              'bg-success',
            )}
            style={{ width: `${cap}%` }}
          />
        </div>
      </div>

      {person.bio && (
        <p className="mt-4 text-xs text-muted-foreground line-clamp-2 leading-relaxed">{person.bio}</p>
      )}

      {person.skills && person.skills.length > 0 && (
        <div className="mt-3 flex flex-wrap gap-1.5">
          {person.skills.map((skill) => (
            <span key={skill} className="px-2 py-0.5 bg-primary/5 text-primary text-[11px] font-bold border border-primary/10">
              {skill}
            </span>
          ))}
        </div>
      )}

      <div className="mt-4 pt-4 border-t border-border">
        {person.email ? (
          <div className="flex items-center gap-2 text-xs text-muted-foreground">
            <Mail className="w-3.5 h-3.5 flex-shrink-0" />
            <span className="truncate">{person.email}</span>
          </div>
        ) : (
          <p className="text-xs text-muted-foreground italic">{t.teamMembers.noEmailSet}</p>
        )}
      </div>
    </div>
  );
};

// ─── Team Members Page ────────────────────────────────────────────────────────

export const TeamMembersPage = () => {
  const { t } = useLanguage();
  const { currentProjectId, currentWorkspaceId } = useProjectContext();
  const { data: people = [], isLoading: peopleLoading } = usePeople();
  const { data: workspaceMembers = [], isLoading: workspaceMembersLoading } = useWorkspaceMembers(currentWorkspaceId);
  const { data: tasks = [], isLoading: tasksLoading } = useTasks(currentProjectId);
  const [search, setSearch] = useState('');
  const [availFilter, setAvailFilter] = useState<AvailabilityStatus | 'all'>('all');
  const [showAdd, setShowAdd] = useState(false);
  const [editPerson, setEditPerson] = useState<Person | null>(null);

  const isLoading = peopleLoading || workspaceMembersLoading || tasksLoading;

  const workspaceMembersByEmail = useMemo(() => {
    const byEmail = new Map<string, WorkspacePermissionRole>();
    for (const member of workspaceMembers) {
      byEmail.set(member.email.toLowerCase(), member.role);
    }
    return byEmail;
  }, [workspaceMembers]);

  const byAssignee = useMemo(() => {
    const counts = new Map<string, number>();
    for (const task of tasks) {
      if (!task.assignee_id) continue;
      if (task.status === 'done') continue;
      counts.set(task.assignee_id, (counts.get(task.assignee_id) ?? 0) + 1);
    }
    return counts;
  }, [tasks]);

  const filtered = useMemo(() => {
    return people.filter((p) => {
      if (
        search &&
        !p.name.toLowerCase().includes(search.toLowerCase()) &&
        !p.role?.toLowerCase().includes(search.toLowerCase()) &&
        !p.skills?.some((s) => s.toLowerCase().includes(search.toLowerCase()))
      )
        return false;
      if (availFilter !== 'all' && p.availability !== availFilter) return false;
      return true;
    });
  }, [people, search, availFilter]);

  return (
    <div className="flex flex-col min-h-screen bg-background">
      {showAdd && <AddPersonModal currentWorkspaceId={currentWorkspaceId} onClose={() => setShowAdd(false)} t={t} />}
      {editPerson && <EditPersonModal person={editPerson} onClose={() => setEditPerson(null)} t={t} />}

      <header className="px-8 py-6 border-b border-border">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div>
            <h2 className="text-2xl font-bold text-foreground tracking-tight">{t.teamMembers.title}</h2>
            <p className="text-muted-foreground text-sm mt-0.5">
              {people.length} {t.teamMembers.membersCount}
            </p>
          </div>
          <button
            onClick={() => setShowAdd(true)}
            className="inline-flex items-center justify-center gap-2 bg-primary hover:bg-primary/90 text-primary-foreground px-4 py-2 text-sm font-bold transition-colors"
          >
            <Plus className="w-4 h-4" />
            {t.teamMembers.addPerson}
          </button>
        </div>

        <div className="mt-5 flex flex-col lg:flex-row gap-3">
          <div className="relative flex-1">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground w-4 h-4" />
            <input
              type="text"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder={t.teamMembers.searchPlaceholder}
              className="w-full pl-9 pr-4 py-2 bg-background border border-border text-foreground focus:ring-1 focus:ring-primary outline-none text-sm transition-all"
            />
          </div>
          <div className="flex gap-3">
            <select
              value={availFilter}
              onChange={(e) => setAvailFilter(e.target.value as AvailabilityStatus | 'all')}
              className="px-4 py-2 bg-background border border-border text-sm font-bold text-foreground hover:bg-muted transition-all outline-none focus:ring-1 focus:ring-primary cursor-pointer"
            >
              <option value="all">{t.teamMembers.availability}: All</option>
              <option value="available">{t.teamMembers.availabilityAvailable}</option>
              <option value="busy">{t.teamMembers.availabilityBusy}</option>
              <option value="on_leave">{t.teamMembers.availabilityOnLeave}</option>
            </select>
          </div>
        </div>
      </header>

      <section className="p-8">
        {isLoading ? (
          <div className="flex justify-center py-20">
            <Loader2 className="w-6 h-6 animate-spin text-primary" />
          </div>
        ) : filtered.length === 0 ? (
          <div className="text-center py-20 text-muted-foreground">
            {people.length === 0 ? (
              <div>
                <p className="text-sm font-bold mb-1">{t.teamMembers.noMembersYet}</p>
                <p className="text-xs">{t.teamMembers.addPerson}</p>
              </div>
            ) : (
              <p className="text-sm">{t.teamMembers.noMembersMatch}</p>
            )}
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
            {filtered.map((person) => {
              const openTaskCount = byAssignee.get(person.id) ?? 0;
              const level = loadLevel(openTaskCount, person.availability, person.max_capacity || 8);
              return (
                <MemberCard 
                  key={person.id} 
                  person={person} 
                  onEdit={setEditPerson} 
                  openTaskCount={openTaskCount}
                  level={level}
                  workspaceRole={person.email ? workspaceMembersByEmail.get(person.email.toLowerCase()) ?? null : null}
                  t={t} 
                />
              );
            })}
          </div>
        )}
      </section>
    </div>
  );
};
