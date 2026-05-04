import React, { useState, useRef, useEffect } from 'react';
import { X, Sparkles } from 'lucide-react';
import { Link } from 'react-router-dom';
import { useCreateTask } from '@/hooks/useTasks';
import { useProjectContext } from '@/context/ProjectContext';
import { useLanguage } from '@/i18n/LanguageContext';
import type { TaskStatus, TaskPriority, TaskCreate } from '@/types';
import { AssigneePicker } from './AssigneePicker';
import { Alert, AlertDescription } from '@/components/ui/alert';

interface CreateTaskModalProps {
  people: { id: string; name: string }[];
  onClose: () => void;
}

export function CreateTaskModal({ people, onClose }: CreateTaskModalProps) {
  const { t } = useLanguage();
  const { currentProjectId } = useProjectContext();
  const createTask = useCreateTask();
  const [title, setTitle] = useState('');
  const [description, setDescription] = useState('');
  const [status, setStatus] = useState<TaskStatus>('todo');
  const [priority, setPriority] = useState<TaskPriority>('medium');
  const [dueDate, setDueDate] = useState('');
  const [assigneeId, setAssigneeId] = useState('');
  const titleRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    titleRef.current?.focus();
    const handler = (e: KeyboardEvent) => e.key === 'Escape' && onClose();
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [onClose]);

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!title.trim() || !currentProjectId) return;
    const data: TaskCreate = {
      title: title.trim(),
      project_id: currentProjectId,
      description: description || null,
      status,
      priority,
      due_date: dueDate || null,
      assignee_id: assigneeId || null,
    };
    createTask.mutate(data, { onSuccess: onClose });
  }

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60"
      onClick={(e) => e.target === e.currentTarget && onClose()}
    >
      <div className="bg-background border border-border w-full max-w-lg overflow-hidden">
        <div className="flex items-center justify-between px-6 py-4 border-b border-border">
          <h3 className="text-sm font-bold text-foreground">{t.tasks.newTask}</h3>
          <button
            onClick={onClose}
            className="p-1.5 text-muted-foreground hover:text-foreground hover:bg-muted transition-colors"
          >
            <X className="w-4 h-4" />
          </button>
        </div>
        <form onSubmit={handleSubmit}>
          <div className="px-6 py-5 space-y-4">
            <Alert className="bg-primary/5 border-primary/20">
              <div className="flex items-center gap-2">
                <Sparkles className="h-4 w-4 text-primary" />
                <AlertDescription className="text-sm text-primary">
                  {t.taskModal.tryAiAlertPrefix}
                  <Link to="/ai" className="underline font-medium hover:text-primary/80" onClick={onClose}>
                    {t.taskModal.tryAiAlertLink}
                  </Link>
                  {t.taskModal.tryAiAlertSuffix}
                </AlertDescription>
              </div>
            </Alert>

            <div>
              <label className="text-[10px] font-bold uppercase tracking-widest text-muted-foreground font-mono block mb-1">
                {t.taskModal.titleRequired}
              </label>
              <input
                ref={titleRef}
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                required
                placeholder={t.taskModal.taskTitlePlaceholder}
                className="w-full border border-border bg-background text-foreground px-3 py-2 text-sm focus:ring-1 focus:ring-primary outline-none"
              />
            </div>

            <div>
              <label className="text-[10px] font-bold uppercase tracking-widest text-muted-foreground font-mono block mb-1">
                {t.taskModal.description}
              </label>
              <textarea
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                rows={2}
                className="w-full border border-border bg-background text-foreground px-3 py-2 text-sm focus:ring-1 focus:ring-primary outline-none resize-none"
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
                  className="w-full border border-border bg-background text-foreground px-3 py-2 text-sm focus:ring-1 focus:ring-primary outline-none"
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
                  className="w-full border border-border bg-background text-foreground px-3 py-2 text-sm focus:ring-1 focus:ring-primary outline-none"
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
                  className="w-full border border-border bg-background text-foreground px-3 py-2 text-sm focus:ring-1 focus:ring-primary outline-none"
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
                />
              </div>
            </div>
          </div>

          <div className="flex justify-end gap-3 px-6 py-4 border-t border-border">
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2 text-sm font-bold text-muted-foreground hover:text-foreground transition-colors"
            >
              {t.taskModal.cancel}
            </button>
            <button
              type="submit"
              disabled={createTask.isPending}
              className="px-4 py-2 bg-primary text-primary-foreground text-sm font-bold hover:bg-primary/90 transition-colors disabled:opacity-60"
            >
              {createTask.isPending ? t.taskModal.creating : t.tasks.createTask}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
