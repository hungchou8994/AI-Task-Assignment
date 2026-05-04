import React, { useEffect, useMemo, useState } from 'react';
import {
  AlertTriangle,
  CheckCircle2,
  Edit3,
  RefreshCw,
  RotateCcw,
  Sparkles,
  Wand2,
  XCircle,
} from 'lucide-react';
import { useProjectContext } from '../context/ProjectContext';
import { usePeople } from '../hooks/usePeople';
import {
  useApproveCandidate,
  useBatchApproveCandidates,
  useBatchRejectCandidates,
  usePatchTaskCandidate,
  useRejectCandidate,
  useRerunCandidate,
  useTaskCandidates,
  useUndoReject,
} from '../hooks/useTaskCandidates';
import { cn } from '@/lib/utils';
import type { TaskCandidate, TaskCandidatePatch } from '../types';
import { useLanguage } from '../i18n/LanguageContext';

type UndoState = {
  candidateId: string;
  expiresAt: string;
} | null;

type ActionErrorState = {
  message: string;
  retry: () => void;
} | null;

type LocalAuditEvent = {
  id: string;
  candidateId: string;
  action: 'approved' | 'edited' | 'rejected' | 'rerun' | 'batch-approved' | 'batch-rejected' | 'undo-reject';
  detail?: string;
  at: string;
};

function confidenceBadgeClass(score: number) {
  if (score >= 0.8) return 'bg-success/10 text-success border-success/30';
  if (score >= 0.5) return 'bg-warning/10 text-warning border-warning/30';
  return 'bg-destructive/10 text-destructive border-destructive/30';
}

function typingTarget(target: EventTarget | null) {
  if (!(target instanceof HTMLElement)) return false;
  const tag = target.tagName.toLowerCase();
  return tag === 'input' || tag === 'textarea' || tag === 'select' || target.isContentEditable;
}

function formatDate(dateLike: string | null) {
  if (!dateLike) return '—';
  const date = new Date(dateLike);
  if (Number.isNaN(date.getTime())) return '—';
  return `${date.toLocaleDateString()} ${date.toLocaleTimeString()}`;
}

function normalizeText(input: string | null | undefined) {
  return (input ?? '').trim();
}

function FieldDiffRow({
  label,
  original,
  edited,
}: {
  label: string;
  original: string;
  edited: string;
}) {
  const changed = normalizeText(original) !== normalizeText(edited);
  return (
    <div className={cn('grid gap-2 rounded-md border p-2 md:grid-cols-2', changed ? 'border-primary/40 bg-primary/5' : 'border-border')}>
      <p className="md:col-span-2 text-[10px] font-bold uppercase tracking-widest text-muted-foreground">{label}</p>
      <div>
        <p className="text-[10px] font-bold uppercase tracking-wide text-muted-foreground">AI Candidate</p>
        <p className="mt-1 text-sm text-foreground whitespace-pre-wrap break-words">{original || '—'}</p>
      </div>
      <div>
        <p className="text-[10px] font-bold uppercase tracking-wide text-muted-foreground">Final Task</p>
        <p className="mt-1 text-sm text-foreground whitespace-pre-wrap break-words">{edited || '—'}</p>
      </div>
    </div>
  );
}

export const ReviewQueuePage = () => {
  const { t } = useLanguage();
  const { currentProjectId } = useProjectContext();
  const {
    data: candidates = [],
    isLoading,
    isError,
    error,
    refetch,
  } = useTaskCandidates(currentProjectId, 'pending');
  const { data: people = [] } = usePeople();

  const patchCandidate = usePatchTaskCandidate(currentProjectId);
  const approveCandidate = useApproveCandidate(currentProjectId);
  const rejectCandidate = useRejectCandidate(currentProjectId);
  const rerunCandidate = useRerunCandidate(currentProjectId);
  const undoReject = useUndoReject(currentProjectId);
  const batchApprove = useBatchApproveCandidates(currentProjectId);
  const batchReject = useBatchRejectCandidates(currentProjectId);

  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [focusedId, setFocusedId] = useState<string | null>(null);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [draft, setDraft] = useState<TaskCandidatePatch>({});
  const [undoState, setUndoState] = useState<UndoState>(null);
  const [remainingSeconds, setRemainingSeconds] = useState(0);
  const [actionError, setActionError] = useState<ActionErrorState>(null);
  const [auditEvents, setAuditEvents] = useState<LocalAuditEvent[]>([]);

  const peopleMap = useMemo(() => {
    const map: Record<string, string> = {};
    people.forEach((person) => {
      map[person.id] = person.name;
    });
    return map;
  }, [people]);

  const focusedCandidate = useMemo(
    () => candidates.find((candidate) => candidate.id === focusedId) ?? null,
    [candidates, focusedId],
  );

  useEffect(() => {
    if (focusedId && candidates.some((candidate) => candidate.id === focusedId)) return;
    setFocusedId(candidates[0]?.id ?? null);
  }, [candidates, focusedId]);

  useEffect(() => {
    setSelectedIds((previous) => {
      const next = new Set<string>();
      previous.forEach((id) => {
        if (candidates.some((candidate) => candidate.id === id)) next.add(id);
      });
      return next;
    });
  }, [candidates]);

  useEffect(() => {
    if (!undoState) {
      setRemainingSeconds(0);
      return;
    }

    const interval = window.setInterval(() => {
      const delta = Math.max(0, Math.ceil((new Date(undoState.expiresAt).getTime() - Date.now()) / 1000));
      setRemainingSeconds(delta);
      if (delta === 0) setUndoState(null);
    }, 250);

    return () => window.clearInterval(interval);
  }, [undoState]);

  function pushAudit(event: Omit<LocalAuditEvent, 'id' | 'at'>) {
    setAuditEvents((prev) => [
      {
        id: `${Date.now()}-${Math.random().toString(36).slice(2)}`,
        at: new Date().toISOString(),
        ...event,
      },
      ...prev,
    ]);
  }

  function openActionError(message: string, retry: () => void) {
    setActionError({ message, retry });
  }

  const allSelected = candidates.length > 0 && selectedIds.size === candidates.length;

  const isMutating =
    patchCandidate.isPending ||
    approveCandidate.isPending ||
    rejectCandidate.isPending ||
    undoReject.isPending ||
    batchApprove.isPending ||
    batchReject.isPending ||
    rerunCandidate.isPending;

  function toggleSelected(candidateId: string) {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (next.has(candidateId)) next.delete(candidateId);
      else next.add(candidateId);
      return next;
    });
  }

  function startEdit(candidate: TaskCandidate) {
    setEditingId(candidate.id);
    setDraft({
      title: candidate.title,
      description: candidate.description,
      priority: candidate.priority,
      due_date: candidate.due_date,
      selected_assignee_id: candidate.selected_assignee_id,
    });
  }

  function saveEdit(candidate: TaskCandidate) {
    const beforeTitle = candidate.title;
    const beforeDescription = candidate.description ?? '';
    const afterTitle = draft.title ?? candidate.title;
    const afterDescription = draft.description ?? candidate.description ?? '';

    patchCandidate.mutate(
      { id: candidate.id, data: draft },
      {
        onSuccess: () => {
          pushAudit({
            candidateId: candidate.id,
            action: 'edited',
            detail:
              normalizeText(beforeTitle) !== normalizeText(afterTitle)
                ? `Title updated from "${beforeTitle}" to "${afterTitle}"`
                : normalizeText(beforeDescription) !== normalizeText(afterDescription)
                ? 'Description updated'
                : 'Candidate fields updated',
          });
          setEditingId(null);
          setDraft({});
          setActionError(null);
        },
        onError: (err) => {
          openActionError((err as Error).message, () => saveEdit(candidate));
        },
      },
    );
  }

  function approveOne(candidateId: string) {
    approveCandidate.mutate(candidateId, {
      onSuccess: () => {
        pushAudit({ candidateId, action: 'approved', detail: 'Candidate approved and task created' });
        setSelectedIds((prev) => {
          const next = new Set(prev);
          next.delete(candidateId);
          return next;
        });
        setActionError(null);
      },
      onError: (err) => openActionError((err as Error).message, () => approveOne(candidateId)),
    });
  }

  function rejectOne(candidateId: string) {
    rejectCandidate.mutate(candidateId, {
      onSuccess: (response) => {
        pushAudit({ candidateId, action: 'rejected', detail: 'Candidate rejected' });
        setUndoState({ candidateId, expiresAt: response.undo_expires_at });
        setSelectedIds((prev) => {
          const next = new Set(prev);
          next.delete(candidateId);
          return next;
        });
        setActionError(null);
      },
      onError: (err) => openActionError((err as Error).message, () => rejectOne(candidateId)),
    });
  }

  function requestRerun(candidateId: string) {
    rerunCandidate.mutate(candidateId, {
      onSuccess: () => {
        pushAudit({ candidateId, action: 'rerun', detail: 'Re-run requested for candidate extraction' });
        setActionError(null);
      },
      onError: (err) => openActionError((err as Error).message, () => requestRerun(candidateId)),
    });
  }

  function runBatchApprove() {
    const ids = Array.from(selectedIds);
    if (ids.length === 0) return;
    batchApprove.mutate(
      { candidate_ids: ids },
      {
        onSuccess: () => {
          ids.forEach((candidateId) => pushAudit({ candidateId, action: 'batch-approved' }));
          setSelectedIds(new Set());
          setActionError(null);
        },
        onError: (err) => openActionError((err as Error).message, runBatchApprove),
      },
    );
  }

  function runBatchReject() {
    const ids = Array.from(selectedIds);
    if (ids.length === 0) return;
    batchReject.mutate(
      { candidate_ids: ids },
      {
        onSuccess: () => {
          ids.forEach((candidateId) => pushAudit({ candidateId, action: 'batch-rejected' }));
          setSelectedIds(new Set());
          setActionError(null);
        },
        onError: (err) => openActionError((err as Error).message, runBatchReject),
      },
    );
  }

  useEffect(() => {
    const handler = (event: KeyboardEvent) => {
      if (typingTarget(event.target) || !focusedCandidate || isMutating) return;

      if (event.key === 'a') {
        event.preventDefault();
        approveOne(focusedCandidate.id);
      }

      if (event.key === 'r') {
        event.preventDefault();
        rejectOne(focusedCandidate.id);
      }

      if (event.key === 'e') {
        event.preventDefault();
        setEditingId((current) => (current === focusedCandidate.id ? null : focusedCandidate.id));
        setDraft({
          title: focusedCandidate.title,
          description: focusedCandidate.description,
          priority: focusedCandidate.priority,
          due_date: focusedCandidate.due_date,
          selected_assignee_id: focusedCandidate.selected_assignee_id,
        });
      }
    };

    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [focusedCandidate, isMutating]);

  const effectiveCandidate = focusedCandidate
    ? editingId === focusedCandidate.id
      ? { ...focusedCandidate, ...draft }
      : focusedCandidate
    : null;

  const focusedAudit = focusedCandidate
    ? auditEvents.filter((event) => event.candidateId === focusedCandidate.id)
    : [];

  function auditActionLabel(action: LocalAuditEvent['action']) {
    switch (action) {
      case 'approved':
        return t.reviewQueue.approved;
      case 'edited':
        return t.reviewQueue.edited;
      case 'rejected':
        return t.reviewQueue.rejected;
      case 'rerun':
        return t.reviewQueue.rerun;
      case 'batch-approved':
        return t.reviewQueue.batchApproved;
      case 'batch-rejected':
        return t.reviewQueue.batchRejected;
      case 'undo-reject':
        return t.reviewQueue.undoReject;
      default:
        return action;
    }
  }

  return (
    <div className="space-y-4">
      <header className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h2 className="text-2xl font-bold tracking-tight text-foreground">{t.reviewQueue.title}</h2>
          <p className="mt-0.5 text-sm text-muted-foreground">{t.reviewQueue.subtitle}</p>
        </div>
        <div className="text-xs font-bold text-muted-foreground">{t.reviewQueue.shortcuts}</div>
      </header>

      {actionError && (
        <div className="flex flex-wrap items-center justify-between gap-3 rounded-md border border-destructive/40 bg-destructive/5 p-3">
          <p className="flex items-center gap-2 text-sm text-destructive">
            <AlertTriangle className="h-4 w-4" />
            {t.reviewQueue.actionFailed}: {actionError.message}
          </p>
          <div className="flex items-center gap-2">
            <button
              onClick={actionError.retry}
              className="inline-flex items-center gap-1 rounded-md bg-destructive px-3 py-1.5 text-xs font-bold text-white hover:bg-destructive/90"
            >
              <RefreshCw className="h-3.5 w-3.5" /> {t.reviewQueue.retryAction}
            </button>
            <button
              onClick={() => setActionError(null)}
              className="rounded-md border border-border px-3 py-1.5 text-xs font-bold text-foreground hover:bg-muted"
            >
              {t.reviewQueue.dismiss}
            </button>
          </div>
        </div>
      )}

      {selectedIds.size > 0 && (
        <div className="flex flex-wrap items-center justify-between gap-3 rounded-md border border-border bg-card p-3">
          <span className="text-sm font-bold text-foreground">
            {selectedIds.size} {t.reviewQueue.selected}
          </span>
          <div className="flex items-center gap-2">
            <button
              onClick={runBatchApprove}
              disabled={isMutating}
              className="rounded-md bg-success px-3 py-1.5 text-xs font-bold text-success-foreground transition-colors hover:bg-success/90 disabled:opacity-50"
            >
              {t.reviewQueue.approveSelected}
            </button>
            <button
              onClick={runBatchReject}
              disabled={isMutating}
              className="rounded-md bg-destructive px-3 py-1.5 text-xs font-bold text-white transition-colors hover:bg-destructive/90 disabled:opacity-50"
            >
              {t.reviewQueue.rejectSelected}
            </button>
          </div>
        </div>
      )}

      {isLoading ? (
        <div className="rounded-md border border-border bg-card px-8 py-16 text-center text-sm text-muted-foreground">
          {t.reviewQueue.loadingCandidates}
        </div>
      ) : isError ? (
        <div className="space-y-3 rounded-md border border-destructive/40 bg-destructive/5 px-8 py-10 text-center">
          <p className="text-sm font-medium text-destructive">{t.reviewQueue.loadFailed}</p>
          <p className="text-xs text-muted-foreground">{(error as Error)?.message}</p>
          <div>
            <button
              onClick={() => {
                void refetch();
              }}
              className="inline-flex items-center gap-1 rounded-md border border-border bg-card px-3 py-1.5 text-xs font-bold text-foreground hover:bg-muted"
            >
              <RefreshCw className="h-3.5 w-3.5" /> {t.reviewQueue.retryLoad}
            </button>
          </div>
        </div>
      ) : candidates.length === 0 ? (
        <div className="rounded-md border border-border bg-card px-8 py-16 text-center text-sm text-muted-foreground">
          {t.reviewQueue.noPendingCandidates}
        </div>
      ) : (
        <div className="grid gap-4 xl:grid-cols-[280px_minmax(0,1fr)_minmax(0,1fr)]">
          <section className="rounded-md border border-border bg-card">
            <div className="flex items-center gap-2 border-b border-border px-3 py-2 text-[11px] font-bold uppercase tracking-widest text-muted-foreground">
              <input
                type="checkbox"
                checked={allSelected}
                onChange={() => {
                  if (allSelected) setSelectedIds(new Set());
                  else setSelectedIds(new Set(candidates.map((candidate) => candidate.id)));
                }}
              />
              {t.reviewQueue.selectAll}
            </div>

            <div className="max-h-[72vh] overflow-auto p-2">
              {candidates.map((candidate) => {
                const isFocused = focusedId === candidate.id;
                return (
                  <button
                    key={candidate.id}
                    onClick={() => setFocusedId(candidate.id)}
                    className={cn(
                      'mb-2 w-full rounded-md border p-3 text-left transition-colors',
                      isFocused ? 'border-primary bg-primary/5' : 'border-border hover:border-border/80 hover:bg-muted/20',
                    )}
                  >
                    <div className="mb-2 flex items-start justify-between gap-2">
                      <div className="flex items-start gap-2">
                        <input
                          type="checkbox"
                          checked={selectedIds.has(candidate.id)}
                          onChange={(event) => {
                            event.stopPropagation();
                            toggleSelected(candidate.id);
                          }}
                          onClick={(event) => event.stopPropagation()}
                        />
                        <h3 className="line-clamp-2 text-sm font-bold text-foreground">{candidate.title}</h3>
                      </div>
                      <span className={cn('rounded-full border px-2 py-0.5 text-[10px] font-bold', confidenceBadgeClass(candidate.confidence_score))}>
                        {Math.round(candidate.confidence_score * 100)}%
                      </span>
                    </div>
                    <p className="line-clamp-2 text-xs text-muted-foreground">{candidate.description ?? candidate.source_summary}</p>
                  </button>
                );
              })}
            </div>
          </section>

          <section className="rounded-md border border-border bg-card p-4">
            {!focusedCandidate ? (
              <p className="text-sm text-muted-foreground">{t.reviewQueue.selectCandidateHint}</p>
            ) : (
              <div className="space-y-4">
                <div className="flex items-center justify-between gap-3">
                  <div>
                    <h3 className="text-sm font-bold uppercase tracking-widest text-muted-foreground">{t.reviewQueue.sourceText}</h3>
                    <p className="text-xs text-muted-foreground">{formatDate(focusedCandidate.created_at)}</p>
                  </div>
                  <span className={cn('rounded-full border px-2.5 py-1 text-xs font-bold', confidenceBadgeClass(focusedCandidate.confidence_score))}>
                    {t.reviewQueue.confidence} {Math.round(focusedCandidate.confidence_score * 100)}%
                  </span>
                </div>

                <div className="rounded-md border border-border bg-muted/20 p-3">
                  <p className="text-[11px] font-bold uppercase tracking-widest text-muted-foreground">{t.reviewQueue.source}</p>
                  <p className="mt-1 text-sm text-foreground whitespace-pre-wrap break-words">
                    {focusedCandidate.source_excerpt ?? focusedCandidate.source_summary}
                  </p>
                </div>

                <div className="space-y-2">
                  <p className="text-[11px] font-bold uppercase tracking-widest text-muted-foreground">{t.reviewQueue.explanationChips}</p>
                  <div className="flex flex-wrap gap-1.5">
                    <span className="rounded-full border border-border bg-background px-2 py-0.5 text-[11px] text-foreground">
                      <Sparkles className="mr-1 inline h-3 w-3" /> {focusedCandidate.source_type}
                    </span>
                    {focusedCandidate.assignee_recommendations[0]?.policy_flags?.slice(0, 4).map((flag) => (
                      <span
                        key={flag}
                        className={cn(
                          'rounded-full px-2 py-0.5 text-[11px]',
                          flag.includes('risk')
                            ? 'bg-warning/10 text-warning'
                            : flag.includes('expert') || flag.includes('strong')
                            ? 'bg-success/10 text-success'
                            : 'bg-muted text-muted-foreground',
                        )}
                      >
                        {flag.replace(/_/g, ' ')}
                      </span>
                    ))}
                  </div>
                </div>

                <div className="rounded-md border border-border p-3">
                  <p className="text-[11px] font-bold uppercase tracking-widest text-muted-foreground">{t.reviewQueue.aiCandidate}</p>
                  <p className="mt-1 text-base font-bold text-foreground">{focusedCandidate.title}</p>
                  <p className="mt-1 text-sm text-muted-foreground whitespace-pre-wrap break-words">{focusedCandidate.description ?? '—'}</p>
                </div>
              </div>
            )}
          </section>

          <section className="rounded-md border border-border bg-card p-4">
            {!focusedCandidate || !effectiveCandidate ? (
              <p className="text-sm text-muted-foreground">{t.reviewQueue.selectCandidateHint}</p>
            ) : (
              <div className="space-y-4">
                <div>
                  <h3 className="text-sm font-bold uppercase tracking-widest text-muted-foreground">{t.reviewQueue.finalApprovedTask}</h3>
                  <p className="text-xs text-muted-foreground">{t.reviewQueue.inlineDiffHint}</p>
                </div>

                <FieldDiffRow label={t.reviewQueue.titleField} original={focusedCandidate.title} edited={effectiveCandidate.title} />
                <FieldDiffRow
                  label={t.reviewQueue.description}
                  original={focusedCandidate.description ?? ''}
                  edited={effectiveCandidate.description ?? ''}
                />

                <div className="grid grid-cols-1 gap-3 md:grid-cols-3">
                  <div>
                    <p className="mb-1 text-[10px] font-bold uppercase tracking-widest text-muted-foreground">{t.reviewQueue.priority}</p>
                    {editingId === focusedCandidate.id ? (
                      <select
                        value={effectiveCandidate.priority}
                        onChange={(event) => setDraft((prev) => ({ ...prev, priority: event.target.value as TaskCandidate['priority'] }))}
                        className="w-full rounded-md border border-border bg-background px-2 py-1 text-sm text-foreground outline-none focus:ring-1 focus:ring-primary"
                      >
                        <option value="low">{t.reviewQueue.low}</option>
                        <option value="medium">{t.reviewQueue.medium}</option>
                        <option value="high">{t.reviewQueue.high}</option>
                      </select>
                    ) : (
                      <p className="text-sm capitalize text-foreground">{effectiveCandidate.priority}</p>
                    )}
                  </div>
                  <div>
                    <p className="mb-1 text-[10px] font-bold uppercase tracking-widest text-muted-foreground">{t.reviewQueue.dueDate}</p>
                    {editingId === focusedCandidate.id ? (
                      <input
                        type="date"
                        value={effectiveCandidate.due_date ?? ''}
                        onChange={(event) => setDraft((prev) => ({ ...prev, due_date: event.target.value || null }))}
                        className="w-full rounded-md border border-border bg-background px-2 py-1 text-sm text-foreground outline-none focus:ring-1 focus:ring-primary"
                      />
                    ) : (
                      <p className="text-sm text-foreground">{effectiveCandidate.due_date ?? '—'}</p>
                    )}
                  </div>
                  <div>
                    <p className="mb-1 text-[10px] font-bold uppercase tracking-widest text-muted-foreground">{t.reviewQueue.assignee}</p>
                    {editingId === focusedCandidate.id ? (
                      <select
                        value={effectiveCandidate.selected_assignee_id ?? ''}
                        onChange={(event) => setDraft((prev) => ({ ...prev, selected_assignee_id: event.target.value || null }))}
                        className="w-full rounded-md border border-border bg-background px-2 py-1 text-sm text-foreground outline-none focus:ring-1 focus:ring-primary"
                      >
                        <option value="">{t.reviewQueue.unassigned}</option>
                        {people.map((person) => (
                          <option key={person.id} value={person.id}>
                            {person.name}
                          </option>
                        ))}
                      </select>
                    ) : (
                      <p className="text-sm text-foreground">
                        {effectiveCandidate.selected_assignee_id
                          ? peopleMap[effectiveCandidate.selected_assignee_id] ?? effectiveCandidate.selected_assignee_id
                          : t.reviewQueue.unassigned}
                      </p>
                    )}
                  </div>
                </div>

                {editingId === focusedCandidate.id && (
                  <textarea
                    rows={4}
                    value={effectiveCandidate.description ?? ''}
                    onChange={(event) => setDraft((prev) => ({ ...prev, description: event.target.value || null }))}
                    className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm text-foreground outline-none focus:ring-1 focus:ring-primary"
                  />
                )}

                <div className="flex flex-wrap items-center gap-2 border-t border-border pt-3">
                  {editingId === focusedCandidate.id ? (
                    <>
                      <button
                        onClick={() => {
                          setEditingId(null);
                          setDraft({});
                        }}
                        className="rounded-md border border-border px-3 py-1.5 text-xs font-bold text-foreground hover:bg-muted"
                      >
                        {t.reviewQueue.cancel}
                      </button>
                      <button
                        onClick={() => saveEdit(focusedCandidate)}
                        disabled={isMutating}
                        className="rounded-md bg-primary px-3 py-1.5 text-xs font-bold text-primary-foreground hover:bg-primary/90 disabled:opacity-50"
                      >
                        {t.reviewQueue.save}
                      </button>
                    </>
                  ) : (
                    <button
                      onClick={() => startEdit(focusedCandidate)}
                      className="inline-flex items-center gap-1 rounded-md border border-border px-3 py-1.5 text-xs font-bold text-foreground hover:bg-muted"
                    >
                      <Edit3 className="h-3.5 w-3.5" /> {t.reviewQueue.edit}
                    </button>
                  )}

                  <button
                    onClick={() => requestRerun(focusedCandidate.id)}
                    disabled={isMutating}
                    className="inline-flex items-center gap-1 rounded-md border border-border px-3 py-1.5 text-xs font-bold text-foreground hover:bg-muted disabled:opacity-50"
                  >
                    <Wand2 className="h-3.5 w-3.5" /> {t.reviewQueue.requestRerun}
                  </button>

                  <button
                    onClick={() => approveOne(focusedCandidate.id)}
                    disabled={isMutating}
                    className="inline-flex items-center gap-1 rounded-md bg-success px-3 py-1.5 text-xs font-bold text-success-foreground hover:bg-success/90 disabled:opacity-50"
                  >
                    <CheckCircle2 className="h-3.5 w-3.5" /> {t.reviewQueue.approve}
                  </button>

                  <button
                    onClick={() => rejectOne(focusedCandidate.id)}
                    disabled={isMutating}
                    className="inline-flex items-center gap-1 rounded-md bg-destructive px-3 py-1.5 text-xs font-bold text-white hover:bg-destructive/90 disabled:opacity-50"
                  >
                    <XCircle className="h-3.5 w-3.5" /> {t.reviewQueue.reject}
                  </button>
                </div>

                <div className="rounded-md border border-border bg-muted/20 p-3">
                  <p className="mb-2 text-[11px] font-bold uppercase tracking-widest text-muted-foreground">{t.reviewQueue.auditTimeline}</p>
                  <ul className="space-y-2">
                    <li className="flex items-start justify-between gap-3 rounded-md border border-border bg-background px-2.5 py-2">
                      <span className="text-xs text-foreground">{t.reviewQueue.extractedEvent}</span>
                      <span className="text-[11px] text-muted-foreground">{formatDate(focusedCandidate.created_at)}</span>
                    </li>
                    {focusedAudit.length === 0 ? (
                      <li className="text-xs text-muted-foreground">{t.reviewQueue.noAuditEvents}</li>
                    ) : (
                      focusedAudit.map((event) => (
                        <li key={event.id} className="rounded-md border border-border bg-background px-2.5 py-2">
                          <div className="flex items-start justify-between gap-3">
                            <span className="text-xs font-medium text-foreground">{auditActionLabel(event.action)}</span>
                            <span className="text-[11px] text-muted-foreground">{formatDate(event.at)}</span>
                          </div>
                          {event.detail ? <p className="mt-1 text-xs text-muted-foreground">{event.detail}</p> : null}
                        </li>
                      ))
                    )}
                  </ul>
                </div>
              </div>
            )}
          </section>
        </div>
      )}

      {undoState && (
        <div className="fixed bottom-6 right-6 rounded-md border border-border bg-card px-4 py-3 shadow-sm">
          <div className="flex items-center gap-3">
            <p className="text-sm font-medium text-foreground">{t.reviewQueue.candidateRejected}</p>
            <button
              onClick={() => {
                undoReject.mutate(undoState.candidateId, {
                  onSuccess: () => {
                    pushAudit({ candidateId: undoState.candidateId, action: 'undo-reject' });
                    setUndoState(null);
                    setActionError(null);
                  },
                  onError: (err) => openActionError((err as Error).message, () => {
                    if (!undoState) return;
                    undoReject.mutate(undoState.candidateId);
                  }),
                });
              }}
              className="inline-flex items-center gap-1 rounded-md bg-foreground px-3 py-1.5 text-xs font-bold text-background hover:bg-foreground/80"
            >
              <RotateCcw className="h-3.5 w-3.5" /> {t.reviewQueue.undo} ({remainingSeconds}s)
            </button>
          </div>
        </div>
      )}
    </div>
  );
};
