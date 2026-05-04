import type { TaskStatus, TaskPriority, TaskActivityAction } from '@/types';

export const STATUS_LABELS: Record<TaskStatus, string> = {
  todo: 'Todo',
  in_progress: 'In Progress',
  done: 'Done',
};

export const PRIORITY_LABELS: Record<TaskPriority, string> = {
  low: 'Low',
  medium: 'Medium',
  high: 'High',
};

export const TASK_ACTIVITY_ACTION_LABELS: Record<TaskActivityAction, string> = {
  task_created: 'Task Created',
  status_changed: 'Status Changed',
  assignment_changed: 'Assignment Changed',
  field_changed: 'Field Changed',
};

export const TASK_ACTIVITY_ACTION_STYLES: Record<TaskActivityAction, string> = {
  task_created: 'bg-success/10 text-success',
  status_changed: 'bg-primary/10 text-primary',
  assignment_changed: 'bg-secondary text-secondary-foreground',
  field_changed: 'bg-muted text-muted-foreground',
};
