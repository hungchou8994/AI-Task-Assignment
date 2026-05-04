import { useState, useEffect } from 'react';
import { X, Pencil, Trash2, Link2, ExternalLink, FileText } from 'lucide-react';
import { cn } from '@/lib/utils';
import { useUpdateTask, useDeleteTask, useTaskActivity, useTaskSources } from '@/hooks/useTasks';
import { useLanguage } from '@/i18n/LanguageContext';
import {
  TASK_ACTIVITY_ACTION_LABELS,
  TASK_ACTIVITY_ACTION_STYLES,
} from '@/constants/taskLabels';
import {
  formatDate,
  isOverdue,
  formatActivityTimestamp,
  activityFieldLabel,
  activityValueSummary,
} from '@/lib/taskFormatters';
import type { Task, TaskStatus, TaskPriority, TaskUpdate } from '@/types';
import { AssigneePicker } from './AssigneePicker';

interface TaskModalProps {
  task: Task;
  people: { id: string; name: string }[];
  onClose: () => void;
}

export function TaskModal({ task, people, onClose }: TaskModalProps) {
  const { t } = useLanguage();
  const updateTask = useUpdateTask();
  const deleteTask = useDeleteTask();
  const [editing, setEditing] = useState(false);
  const [confirmDelete, setConfirmDelete] = useState(false);
  const { data: activity = [], isLoading: isActivityLoading } = useTaskActivity(task.id);
  const { data: sources = [], isLoading: isSourcesLoading } = useTaskSources(task.id);

  const [title, setTitle] = useState(task.title);
  const [description, setDescription] = useState(task.description ?? '');
  const [status, setStatus] = useState<TaskStatus>(task.status);
  const [priority, setPriority] = useState<TaskPriority>(task.priority);
  const [dueDate, setDueDate] = useState(task.due_date ?? '');
  const [assigneeId, setAssigneeId] = useState(task.assignee_id ?? '');

  const assigneeName = people.find((p) => p.id === task.assignee_id)?.name;

  useEffect(() => {
    const handler = (e: KeyboardEvent) => e.key === 'Escape' && onClose();
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [onClose]);

  function handleSave() {
    const data: TaskUpdate = {
      title: title.trim() || task.title,
      description: description || null,
      status,
      priority,
      due_date: dueDate || null,
      assignee_id: assigneeId || null,
    };
    updateTask.mutate({ id: task.id, data }, { onSuccess: onClose });
  }

  function handleDelete() {
    deleteTask.mutate(task.id, { onSuccess: onClose });
  }

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60"
      onClick={(e) => e.target === e.currentTarget && onClose()}
    >
      <div className="bg-background border border-border w-full max-w-lg overflow-hidden flex flex-col max-h-[90vh]">
        {/* Header */}
        <div className="flex items-start justify-between px-6 py-4 border-b border-border shrink-0">
          <div className="flex-1 pr-4">
            {editing ? (
              <input
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                className="text-base font-bold text-foreground w-full border border-border px-3 py-1.5 focus:ring-2 focus:ring-ring outline-none bg-background"
              />
            ) : (
              <h3 className="text-base font-bold text-foreground">{task.title}</h3>
            )}
            <div className="flex gap-2 mt-1.5 flex-wrap">
              {task.needs_review && (
                <span className="px-2 py-0.5 text-[10px] font-bold uppercase tracking-wider bg-warning/10 text-warning">
                  {t.tasks.needsReview}
                </span>
              )}
              {isOverdue(task.due_date) && task.status !== 'done' && (
                <span className="text-[10px] bg-destructive/10 text-destructive px-2 py-0.5 font-bold uppercase tracking-wider">
                  {t.taskModal.overdue}
                </span>
              )}
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-1.5 text-muted-foreground hover:bg-accent hover:text-foreground transition-colors"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Body */}
        <div className="p-6 space-y-4 overflow-y-auto flex-1">
          {editing ? (
            <>
              <div>
                <label className="text-[10px] font-bold uppercase tracking-widest text-muted-foreground font-mono block mb-1">
                  {t.taskModal.description}
                </label>
                <textarea
                  value={description}
                  onChange={(e) => setDescription(e.target.value)}
                  rows={3}
                  className="w-full border border-border bg-background px-3 py-2 text-sm text-foreground focus:ring-2 focus:ring-ring outline-none resize-none"
                />
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="text-[10px] font-bold uppercase tracking-widest text-muted-foreground font-mono block mb-1">
                    {t.taskModal.status}
                  </label>
                  <select
                    value={status}
                    onChange={(e) => setStatus(e.target.value as TaskStatus)}
                    className="w-full border border-border bg-background px-3 py-2 text-sm text-foreground focus:ring-2 focus:ring-ring outline-none"
                  >
                    <option value="todo">{t.statuses.pending}</option>
                    <option value="in_progress">{t.statuses.in_progress}</option>
                    <option value="done">{t.statuses.completed}</option>
                  </select>
                </div>
                <div>
                  <label className="text-[10px] font-bold uppercase tracking-widest text-muted-foreground font-mono block mb-1">
                    {t.taskModal.priority}
                  </label>
                  <select
                    value={priority}
                    onChange={(e) => setPriority(e.target.value as TaskPriority)}
                    className="w-full border border-border bg-background px-3 py-2 text-sm text-foreground focus:ring-2 focus:ring-ring outline-none"
                  >
                    <option value="low">{t.priority.low}</option>
                    <option value="medium">{t.priority.medium}</option>
                    <option value="high">{t.priority.high}</option>
                  </select>
                </div>
                <div>
                  <label className="text-[10px] font-bold uppercase tracking-widest text-muted-foreground font-mono block mb-1">
                    {t.taskModal.dueDate}
                  </label>
                  <input
                    type="date"
                    value={dueDate}
                    onChange={(e) => setDueDate(e.target.value)}
                    className="w-full border border-border bg-background px-3 py-2 text-sm text-foreground focus:ring-2 focus:ring-ring outline-none"
                  />
                </div>
                <div>
                  <label className="text-[10px] font-bold uppercase tracking-widest text-muted-foreground font-mono block mb-1">
                    {t.taskModal.assignee}
                  </label>
                  <AssigneePicker
                    value={assigneeId}
                    onChange={setAssigneeId}
                    people={people}
                    taskId={task.id}
                  />
                </div>
              </div>
            </>
          ) : (
            <>
              {task.description && (
                <p className="text-sm text-muted-foreground leading-relaxed">{task.description}</p>
              )}
              <div className="grid grid-cols-2 gap-4 text-sm">
                <div>
                  <p className="text-[10px] font-bold uppercase tracking-widest text-muted-foreground font-mono mb-1">
                    {t.taskModal.status}
                  </p>
                  <span
                    className={cn(
                      'inline-flex px-2 py-0.5 text-[10px] font-bold uppercase tracking-wider',
                      task.status === 'in_progress' && 'bg-primary/10 text-primary',
                      task.status === 'todo' && 'bg-muted text-muted-foreground',
                      task.status === 'done' && 'bg-success/10 text-success',
                    )}
                  >
                    {task.status === 'todo'
                      ? t.statuses.pending
                      : task.status === 'in_progress'
                      ? t.statuses.in_progress
                      : t.statuses.completed}
                  </span>
                </div>
                <div>
                  <p className="text-[10px] font-bold uppercase tracking-widest text-muted-foreground font-mono mb-1">
                    {t.taskModal.priority}
                  </p>
                  <span
                    className={cn(
                      'inline-flex px-2 py-0.5 text-[10px] font-bold uppercase tracking-wider',
                      task.priority === 'high' && 'bg-destructive/10 text-destructive',
                      task.priority === 'medium' && 'bg-warning/10 text-warning',
                      task.priority === 'low' && 'bg-success/10 text-success',
                    )}
                  >
                    {t.priority[task.priority]}
                  </span>
                </div>
                <div>
                  <p className="text-[10px] font-bold uppercase tracking-widest text-muted-foreground font-mono mb-1">
                    {t.taskModal.dueDate}
                  </p>
                  <p
                    className={cn(
                      'font-medium text-foreground',
                      isOverdue(task.due_date) && task.status !== 'done' && 'text-destructive',
                    )}
                  >
                    {formatDate(task.due_date)}
                  </p>
                </div>
                <div>
                  <p className="text-[10px] font-bold uppercase tracking-widest text-muted-foreground font-mono mb-1">
                    {t.taskModal.assignee}
                  </p>
                  <p className="font-medium text-foreground">
                    {assigneeName ?? t.taskModal.unassigned}
                  </p>
                </div>
              </div>
            </>
          )}

          <section className="pt-3 border-t border-border">
            <h4 className="text-[10px] font-bold uppercase tracking-widest text-muted-foreground font-mono mb-3 flex items-center gap-1.5">
              <Link2 className="w-3 h-3" />
              {t.taskModal.sources}
            </h4>
            <div className="space-y-2.5">
              {isSourcesLoading ? (
                <p className="text-xs text-muted-foreground">{t.taskModal.loadingSources}</p>
              ) : sources && sources.length > 0 ? (
                sources.map((link) => {
                  const source = link.source;
                  if (!source) return null;
                  const confidencePercent =
                    typeof link.confidence_score === 'number'
                      ? Math.round(link.confidence_score * 100)
                      : null;
                  return (
                    <div
                      key={source.id}
                      className="p-3 bg-muted/50 border border-border/60 hover:border-border transition-colors"
                    >
                      <div className="flex items-start gap-3 min-w-0">
                        <div className="p-1.5 bg-background border border-border shrink-0 mt-0.5">
                          {source.source_type === 'url' ? (
                            <ExternalLink className="w-3.5 h-3.5 text-blue-500" />
                          ) : source.source_type === 'email' ? (
                            <FileText className="w-3.5 h-3.5 text-green-500" />
                          ) : (
                            <FileText className="w-3.5 h-3.5 text-muted-foreground" />
                          )}
                        </div>
                        <div className="min-w-0 flex-1 space-y-1.5">
                          <div className="flex flex-wrap items-center gap-2">
                            <p className="text-xs font-semibold text-foreground truncate">
                              {source.title || (source.source_type === 'url' ? source.uri : source.source_type)}
                            </p>
                            <span className="inline-flex px-1.5 py-0.5 text-[10px] uppercase tracking-wide bg-background border border-border text-muted-foreground">
                              {source.source_type}
                            </span>
                            {confidencePercent !== null && (
                              <span className="inline-flex px-1.5 py-0.5 text-[10px] uppercase tracking-wide bg-primary/10 text-primary">
                                {t.taskModal.confidence}: {confidencePercent}%
                              </span>
                            )}
                          </div>
                          {source.uri && source.source_type === 'url' && (
                            <a
                              href={source.uri}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="text-[10px] text-muted-foreground hover:text-primary transition-colors truncate block"
                            >
                              {source.uri}
                            </a>
                          )}
                          {source.summary && (
                            <p className="text-[11px] text-muted-foreground line-clamp-2">
                              {source.summary}
                            </p>
                          )}
                          {!source.summary && source.excerpt && (
                            <p className="text-[11px] text-muted-foreground line-clamp-2">
                              {source.excerpt}
                            </p>
                          )}
                          {confidencePercent !== null && (
                            <div className="h-1.5 w-full bg-background border border-border overflow-hidden">
                              <div
                                className="h-full bg-primary transition-all"
                                style={{ width: `${confidencePercent}%` }}
                                aria-label={`${t.taskModal.confidence}: ${confidencePercent}%`}
                              />
                            </div>
                          )}
                        </div>
                        <p className="text-[10px] text-muted-foreground shrink-0 mt-0.5">
                          {new Date(link.created_at).toLocaleDateString()}
                        </p>
                      </div>
                    </div>
                  );
                })
              ) : (
                <p className="text-xs text-muted-foreground italic">
                  {t.taskModal.noSources}
                </p>
              )}
            </div>
          </section>

          <section className="pt-3 border-t border-border">
            <h4 className="text-[10px] font-bold uppercase tracking-widest text-muted-foreground font-mono mb-3">
              {t.taskModal.activityTimeline}
            </h4>
                {isActivityLoading ? (
                  <p className="text-xs text-muted-foreground">{t.taskModal.loadingActivity}</p>
                ) : activity.length === 0 ? (
                  <p className="text-xs text-muted-foreground">{t.taskModal.noActivity}</p>
                ) : (
                  <div className="space-y-2 max-h-52 overflow-auto pr-1">
                    {activity.map((event) => (
                      <div
                        key={event.id}
                        className="border border-border bg-muted/30 px-3 py-2"
                      >
                        <div className="flex flex-wrap items-center gap-2 text-[11px]">
                          <span
                            className={cn(
                              'inline-flex px-2 py-0.5 font-bold uppercase tracking-wider',
                              TASK_ACTIVITY_ACTION_STYLES[event.action_type],
                            )}
                          >
                            {TASK_ACTIVITY_ACTION_LABELS[event.action_type]}
                          </span>
                          <span className="text-muted-foreground">
                            {event.actor_label ?? event.actor_type}
                          </span>
                          <span className="text-muted-foreground/50">•</span>
                          <span className="text-muted-foreground">
                            {formatActivityTimestamp(event.occurred_at)}
                          </span>
                        </div>
                        <p className="text-xs text-muted-foreground mt-1">
                          <span className="font-semibold text-foreground">
                            {activityFieldLabel(event.field_name)}:
                          </span>{' '}
                          {activityValueSummary(event, people)}
                        </p>
                      </div>
                    ))}
                  </div>
                )}
              </section>
        </div>

        {/* Footer */}
        <div className="flex items-center justify-between px-6 py-4 border-t border-border shrink-0">
          {confirmDelete ? (
            <div className="flex items-center gap-3">
              <span className="text-sm text-destructive font-medium">{t.taskModal.deleteTask}</span>
              <button
                onClick={handleDelete}
                disabled={deleteTask.isPending}
                className="text-xs font-bold text-white bg-destructive hover:bg-destructive/90 px-3 py-1.5 transition-colors"
              >
                {deleteTask.isPending ? t.taskModal.deleting : t.taskModal.yesDelete}
              </button>
              <button
                onClick={() => setConfirmDelete(false)}
                className="text-xs font-bold text-muted-foreground hover:text-foreground px-3 py-1.5"
              >
                {t.taskModal.cancel}
              </button>
            </div>
          ) : (
            <button
              onClick={() => setConfirmDelete(true)}
              className="flex items-center gap-2 text-sm font-bold text-destructive hover:text-destructive/80 transition-colors"
            >
              <Trash2 className="w-4 h-4" />
              {t.taskModal.delete}
            </button>
          )}
          <div className="flex gap-3">
            {editing ? (
              <>
                <button
                  onClick={() => setEditing(false)}
                  className="px-4 py-2 text-sm font-bold text-muted-foreground hover:text-foreground transition-colors"
                >
                  {t.taskModal.cancel}
                </button>
                <button
                  onClick={handleSave}
                  disabled={updateTask.isPending}
                  className="px-4 py-2 bg-primary text-primary-foreground text-sm font-bold hover:bg-primary/90 transition-all disabled:opacity-60"
                >
                  {updateTask.isPending ? t.taskModal.saving : t.taskModal.saveChanges}
                </button>
              </>
            ) : (
              <button
                onClick={() => setEditing(true)}
                className="flex items-center gap-2 px-4 py-2 border border-border text-sm font-bold text-foreground hover:bg-accent transition-all"
              >
                <Pencil className="w-3.5 h-3.5" />
                {t.taskModal.edit}
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
