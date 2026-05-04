import { useState, useMemo, useEffect } from 'react';
import { Search, Plus, Filter, ChevronLeft, ChevronRight, Trash2 } from 'lucide-react';
import { useSearchParams } from 'react-router-dom';
import { cn } from '@/lib/utils';
import { useBulkDeleteTasks, useTasks } from '@/hooks/useTasks';
import { usePeople } from '@/hooks/usePeople';
import { useProjectContext } from '@/context/ProjectContext';
import { useLanguage } from '@/i18n/LanguageContext';
import { TaskModal } from '@/components/tasks/TaskModal';
import { CreateTaskModal } from '@/components/tasks/CreateTaskModal';
import { formatDate, isOverdue } from '@/lib/taskFormatters';
import type { Task, TaskStatus, TaskPriority } from '@/types';

const ITEMS_PER_PAGE = 10;

export function TasksPage() {
  const { t } = useLanguage();
  const { currentProjectId } = useProjectContext();
  const [searchParams, setSearchParams] = useSearchParams();
  const { data: tasks = [], isLoading } = useTasks(currentProjectId);
  const bulkDeleteTasks = useBulkDeleteTasks();
  const { data: people = [] } = usePeople();

  const [search, setSearch] = useState('');
  const [statusFilter, setStatusFilter] = useState<TaskStatus | 'all'>('all');
  const [priorityFilter, setPriorityFilter] = useState<TaskPriority | 'all'>('all');
  const [assigneeFilter, setAssigneeFilter] = useState('');
  const [reviewFilter, setReviewFilter] = useState(false);
  const [page, setPage] = useState(1);
  const [selectedTask, setSelectedTask] = useState<Task | null>(null);
  const [selectedTaskIds, setSelectedTaskIds] = useState<Set<string>>(new Set());
  const [showCreate, setShowCreate] = useState(false);
  const highlightedTaskId = searchParams.get('task');

  const createdFilterIds = useMemo(() => {
    const raw = searchParams.get('created');
    if (!raw) return new Set<string>();
    return new Set(
      raw
        .split(',')
        .map((item) => item.trim())
        .filter((item) => item.length > 0),
    );
  }, [searchParams]);

  const hasCreatedFilter = createdFilterIds.size > 0;

  const peopleMap = useMemo(() => {
    const m: Record<string, string> = {};
    people.forEach((p) => (m[p.id] = p.name));
    return m;
  }, [people]);

  const filtered = useMemo(() => {
    return tasks.filter((t) => {
      if (hasCreatedFilter && !createdFilterIds.has(t.id)) return false;
      if (search && !t.title.toLowerCase().includes(search.toLowerCase())) return false;
      if (statusFilter !== 'all' && t.status !== statusFilter) return false;
      if (priorityFilter !== 'all' && t.priority !== priorityFilter) return false;
      if (assigneeFilter && t.assignee_id !== assigneeFilter) return false;
      if (reviewFilter && !t.needs_review) return false;
      return true;
    });
  }, [tasks, hasCreatedFilter, createdFilterIds, search, statusFilter, priorityFilter, assigneeFilter, reviewFilter]);

  const totalPages = Math.max(1, Math.ceil(filtered.length / ITEMS_PER_PAGE));
  const paginated = filtered.slice((page - 1) * ITEMS_PER_PAGE, page * ITEMS_PER_PAGE);
  const paginatedIds = useMemo(() => paginated.map((task) => task.id), [paginated]);
  const filteredIds = useMemo(() => filtered.map((task) => task.id), [filtered]);
  const selectedCount = selectedTaskIds.size;
  const allPageSelected = paginatedIds.length > 0 && paginatedIds.every((id) => selectedTaskIds.has(id));

  // Reset to page 1 when filters change
  useEffect(() => setPage(1), [hasCreatedFilter, search, statusFilter, priorityFilter, assigneeFilter, reviewFilter]);

  useEffect(() => {
    setPage((currentPage) => Math.min(currentPage, totalPages));
  }, [totalPages]);

  useEffect(() => {
    const existingIds = new Set(tasks.map((task) => task.id));
    setSelectedTaskIds((previous) => {
      const next = new Set([...previous].filter((id) => existingIds.has(id)));
      return next.size === previous.size ? previous : next;
    });
  }, [tasks]);

  useEffect(() => {
    if (!highlightedTaskId) return;
    const match = tasks.find((task) => task.id === highlightedTaskId);
    if (!match) return;
    setSelectedTask(match);
  }, [highlightedTaskId, tasks]);

  const hasFilters =
    hasCreatedFilter ||
    statusFilter !== 'all' ||
    priorityFilter !== 'all' ||
    assigneeFilter !== '' ||
    reviewFilter ||
    search !== '';

  const toggleTaskSelection = (taskId: string) => {
    setSelectedTaskIds((previous) => {
      const next = new Set(previous);
      if (next.has(taskId)) next.delete(taskId);
      else next.add(taskId);
      return next;
    });
  };

  const toggleCurrentPageSelection = () => {
    setSelectedTaskIds((previous) => {
      const next = new Set(previous);
      if (allPageSelected) paginatedIds.forEach((id) => next.delete(id));
      else paginatedIds.forEach((id) => next.add(id));
      return next;
    });
  };

  const selectAllFiltered = () => {
    setSelectedTaskIds((previous) => new Set([...previous, ...filteredIds]));
  };

  const deleteTaskIds = (ids: string[], confirmation: string) => {
    if (ids.length === 0 || !window.confirm(confirmation)) return;
    bulkDeleteTasks.mutate(ids, {
      onSuccess: () => {
        setSelectedTaskIds((previous) => {
          const next = new Set(previous);
          ids.forEach((id) => next.delete(id));
          return next;
        });
        if (selectedTask && ids.includes(selectedTask.id)) setSelectedTask(null);
      },
    });
  };

  const deleteSelectedTasks = () => {
    const ids = [...selectedTaskIds];
    deleteTaskIds(ids, t.tasks.confirmDeleteSelected.replace('{count}', String(ids.length)));
  };

  const deleteAllFilteredTasks = () => {
    deleteTaskIds(
      filteredIds,
      t.tasks.confirmDeleteAll.replace('{count}', String(filteredIds.length)),
    );
  };

  return (
    <div className="flex flex-col h-screen overflow-hidden">
      {selectedTask && (
        <TaskModal task={selectedTask} people={people} onClose={() => setSelectedTask(null)} />
      )}
      {showCreate && <CreateTaskModal people={people} onClose={() => setShowCreate(false)} />}

      {/* Header */}
      <header className="h-[56px] border-b border-border bg-background flex items-center justify-between px-6 shrink-0">
        <div className="flex items-center gap-3">
          <h2 className="text-sm font-bold text-foreground">{t.tasks.title}</h2>
          <span className="px-2 py-0.5 bg-muted text-muted-foreground text-xs font-bold">
            {filtered.length}{' '}
            {filtered.length === tasks.length
              ? t.tasks.total
              : `${t.tasks.of} ${tasks.length}`}
          </span>
        </div>
        <div className="flex items-center gap-3">
          <div className="relative">
            <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 text-muted-foreground w-3.5 h-3.5" />
            <input
              type="text"
              placeholder={t.tasks.searchPlaceholder}
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="pl-8 pr-3 py-1.5 bg-muted border-none text-sm w-60 focus:ring-1 focus:ring-primary transition-all outline-none text-foreground"
            />
          </div>
          <button
            onClick={() => setShowCreate(true)}
            className="bg-primary hover:bg-primary/90 text-primary-foreground px-3 py-1.5 text-xs font-bold flex items-center gap-1.5 transition-colors"
          >
            <Plus className="w-3.5 h-3.5" />
            {t.tasks.createTask}
          </button>
        </div>
      </header>

      {/* Created filter banner */}
      {hasCreatedFilter && (
        <section className="flex items-center justify-between border-b border-success/20 bg-success/5 px-6 py-2 shrink-0">
          <p className="text-xs font-bold text-success">
            {t.tasks.createdFocus.replace('{count}', String(createdFilterIds.size))}
          </p>
          <button
            onClick={() => {
              const next = new URLSearchParams(searchParams);
              next.delete('created');
              setSearchParams(next);
            }}
            className="text-xs font-bold text-success hover:underline underline-offset-4"
          >
            {t.tasks.clearCreatedFocus}
          </button>
        </section>
      )}

      {/* Filter bar */}
      <section className="px-6 py-3 bg-background border-b border-border flex flex-wrap items-center gap-3 shrink-0">
        <div className="flex bg-muted p-0.5">
          {(['all', 'todo', 'in_progress', 'done'] as const).map((s) => (
            <button
              key={s}
              onClick={() => setStatusFilter(s)}
              className={cn(
                'px-3 py-1 text-xs font-bold transition-all capitalize',
                statusFilter === s
                  ? 'bg-background text-foreground'
                  : 'text-muted-foreground hover:text-foreground',
              )}
            >
              {s === 'all'
                ? t.assignments.allStatuses
                : s === 'in_progress'
                ? t.statuses.in_progress
                : s === 'todo'
                ? t.statuses.pending
                : t.statuses.completed}
            </button>
          ))}
        </div>

        <div className="h-4 w-px bg-border" />

        <select
          value={priorityFilter}
          onChange={(e) => setPriorityFilter(e.target.value as TaskPriority | 'all')}
          className="bg-background border border-border text-xs font-bold px-3 py-1.5 focus:ring-1 focus:ring-primary outline-none cursor-pointer text-foreground"
        >
          <option value="all">{t.tasks.priorityAll}</option>
          <option value="high">{t.priority.high}</option>
          <option value="medium">{t.priority.medium}</option>
          <option value="low">{t.priority.low}</option>
        </select>

        <select
          value={assigneeFilter}
          onChange={(e) => setAssigneeFilter(e.target.value)}
          className="bg-background border border-border text-xs font-bold px-3 py-1.5 focus:ring-1 focus:ring-primary outline-none cursor-pointer text-foreground"
        >
          <option value="">{t.tasks.assigneeAll}</option>
          {people.map((p) => (
            <option key={p.id} value={p.id}>
              {p.name}
            </option>
          ))}
        </select>

        <label className="flex items-center gap-2 cursor-pointer group">
          <div className="relative inline-flex items-center">
            <input
              type="checkbox"
              className="sr-only peer"
              checked={reviewFilter}
              onChange={(e) => setReviewFilter(e.target.checked)}
            />
            <div className="w-8 h-4 bg-muted peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-border after:border after:h-3 after:w-3 after:transition-all peer-checked:bg-primary" />
          </div>
          <span className="text-xs font-bold text-muted-foreground group-hover:text-foreground transition-colors">
            {t.tasks.needsReview}
          </span>
        </label>

        {hasFilters && (
          <button
            onClick={() => {
              const next = new URLSearchParams(searchParams);
              next.delete('created');
              setSearchParams(next);
              setSearch('');
              setStatusFilter('all');
              setPriorityFilter('all');
              setAssigneeFilter('');
              setReviewFilter(false);
            }}
            className="ml-auto text-muted-foreground hover:text-primary flex items-center gap-1.5 text-xs font-bold transition-colors"
          >
            <Filter className="w-3.5 h-3.5" />
            {t.tasks.clearAll}
          </button>
        )}
      </section>

      {!isLoading && filtered.length > 0 && (
        <section className="px-6 py-2.5 bg-background border-b border-border flex flex-wrap items-center gap-2 shrink-0">
          <label className="flex items-center gap-2 text-xs font-bold text-muted-foreground cursor-pointer">
            <input
              type="checkbox"
              checked={allPageSelected}
              onChange={toggleCurrentPageSelection}
              className="h-4 w-4 accent-primary"
            />
            {t.tasks.selectAllPage}
          </label>
          <button
            onClick={selectAllFiltered}
            disabled={filteredIds.every((id) => selectedTaskIds.has(id))}
            className="px-2.5 py-1.5 text-xs font-bold border border-border bg-card hover:bg-muted disabled:opacity-40 disabled:hover:bg-card transition-colors"
          >
            {t.tasks.selectAllFiltered}
          </button>
          <span className="text-xs font-bold text-muted-foreground tabular-nums px-1">
            {t.tasks.selectedCount.replace('{count}', String(selectedCount))}
          </span>
          <div className="ml-auto flex items-center gap-2">
            <button
              onClick={deleteSelectedTasks}
              disabled={selectedCount === 0 || bulkDeleteTasks.isPending}
              className="px-2.5 py-1.5 text-xs font-bold border border-border text-muted-foreground hover:text-destructive hover:border-destructive/30 hover:bg-destructive/5 disabled:opacity-40 disabled:hover:text-muted-foreground disabled:hover:border-border disabled:hover:bg-transparent transition-colors flex items-center gap-1.5"
            >
              <Trash2 className="h-3.5 w-3.5" />
              {t.tasks.deleteSelected}
            </button>
            <button
              onClick={deleteAllFilteredTasks}
              disabled={filteredIds.length === 0 || bulkDeleteTasks.isPending}
              className="px-2.5 py-1.5 text-xs font-bold border border-destructive/20 bg-destructive/8 text-destructive hover:bg-destructive/12 disabled:opacity-40 transition-colors flex items-center gap-1.5"
            >
              <Trash2 className="h-3.5 w-3.5" />
              {hasFilters ? t.tasks.deleteAllFiltered : t.tasks.deleteAllTasks}
            </button>
          </div>
        </section>
      )}

      {/* Table */}
      <section className="flex-1 overflow-auto bg-background">
        <div className="bg-card border-b border-border">
          {isLoading ? (
            <div className="px-6 py-16 text-center text-muted-foreground text-sm">
              {t.tasks.loadingTasks}
            </div>
          ) : paginated.length === 0 ? (
            <div className="px-6 py-16 text-center text-muted-foreground text-sm">
              {t.tasks.noTasksMatch}
            </div>
          ) : (
            <table className="w-full text-left border-collapse">
              <thead>
                <tr className="border-b border-border">
                  <th className="px-6 py-3 w-10">
                    <input
                      type="checkbox"
                      checked={allPageSelected}
                      onChange={toggleCurrentPageSelection}
                      className="h-4 w-4 accent-primary"
                      aria-label={t.tasks.selectAllPage}
                    />
                  </th>
                  <th className="px-6 py-3 text-[10px] font-bold text-muted-foreground uppercase tracking-widest font-mono w-[40%]">
                    {t.tasks.taskTitle}
                  </th>
                  <th className="px-6 py-3 text-[10px] font-bold text-muted-foreground uppercase tracking-widest font-mono">
                    {t.taskModal.assignee}
                  </th>
                  <th className="px-6 py-3 text-[10px] font-bold text-muted-foreground uppercase tracking-widest font-mono text-center">
                    {t.taskModal.status}
                  </th>
                  <th className="px-6 py-3 text-[10px] font-bold text-muted-foreground uppercase tracking-widest font-mono text-center">
                    {t.taskModal.priority}
                  </th>
                  <th className="px-6 py-3 text-[10px] font-bold text-muted-foreground uppercase tracking-widest font-mono">
                    {t.taskModal.dueDate}
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {paginated.map((task) => {
                  const overdue = isOverdue(task.due_date) && task.status !== 'done';
                  return (
                    <tr
                      key={task.id}
                      onClick={() => setSelectedTask(task)}
                      className={cn(
                        'hover:bg-muted/40 transition-colors group border-l-2 cursor-pointer',
                        task.needs_review ? 'border-l-warning' : 'border-l-transparent',
                      )}
                    >
                      <td className="px-6 py-3">
                        <input
                          type="checkbox"
                          checked={selectedTaskIds.has(task.id)}
                          onClick={(event) => event.stopPropagation()}
                          onChange={() => toggleTaskSelection(task.id)}
                          className="h-4 w-4 accent-primary"
                          aria-label={`Select ${task.title}`}
                        />
                      </td>
                      <td className="px-6 py-3">
                        <div className="flex flex-col">
                          <span className="text-sm font-semibold text-foreground group-hover:text-primary transition-colors">
                            {task.title}
                          </span>
                          {task.needs_review && (
                            <span className="mt-1 w-fit bg-warning/10 px-1.5 py-0.5 text-[9px] font-bold uppercase tracking-wider text-warning">
                              {t.tasks.needsReview}
                            </span>
                          )}
                        </div>
                      </td>
                      <td className="px-6 py-3">
                        <span className="text-xs font-bold text-muted-foreground">
                          {task.assignee_id ? (peopleMap[task.assignee_id] ?? '—') : '—'}
                        </span>
                      </td>
                      <td className="px-6 py-3 text-center">
                        <span
                          className={cn(
                            'inline-flex items-center px-2 py-0.5 text-[10px] font-bold uppercase tracking-wider',
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
                      </td>
                      <td className="px-6 py-3 text-center">
                        <span
                          className={cn(
                            'inline-flex items-center px-2 py-0.5 text-[10px] font-bold uppercase tracking-wider',
                            task.priority === 'high' && 'bg-destructive/10 text-destructive',
                            task.priority === 'medium' && 'bg-warning/10 text-warning',
                            task.priority === 'low' && 'bg-success/10 text-success',
                          )}
                        >
                          {t.priority[task.priority]}
                        </span>
                      </td>
                      <td className="px-6 py-3">
                        <span
                          className={cn(
                            'text-xs font-bold',
                            overdue ? 'text-destructive italic' : 'text-muted-foreground',
                          )}
                        >
                          {task.due_date ? formatDate(task.due_date) : '—'}
                        </span>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          )}
        </div>

        {!isLoading && filtered.length > 0 && (
          <div className="px-6 py-3 border-b border-border flex items-center justify-between bg-background">
            <p className="text-xs font-bold text-muted-foreground tabular-nums">
              {t.tasks.showing} {Math.min((page - 1) * ITEMS_PER_PAGE + 1, filtered.length)}–
              {Math.min(page * ITEMS_PER_PAGE, filtered.length)} {t.tasks.of} {filtered.length}
            </p>
            <div className="flex items-center gap-1">
              <button
                onClick={() => setPage((p) => Math.max(1, p - 1))}
                disabled={page === 1}
                className="p-1.5 border border-border hover:bg-muted text-muted-foreground hover:text-foreground transition-all disabled:opacity-40"
              >
                <ChevronLeft className="w-3.5 h-3.5" />
              </button>
              {Array.from({ length: Math.min(totalPages, 5) }, (_, i) => {
                const p = i + 1;
                return (
                  <button
                    key={p}
                    onClick={() => setPage(p)}
                    className={cn(
                      'px-3 py-1.5 text-xs font-bold transition-all',
                      p === page
                        ? 'bg-primary text-primary-foreground'
                        : 'text-muted-foreground hover:bg-muted hover:text-foreground',
                    )}
                  >
                    {p}
                  </button>
                );
              })}
              <button
                onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                disabled={page === totalPages}
                className="p-1.5 border border-border hover:bg-muted text-muted-foreground hover:text-foreground transition-all disabled:opacity-40"
              >
                <ChevronRight className="w-3.5 h-3.5" />
              </button>
            </div>
          </div>
        )}
      </section>
    </div>
  );
}
