import type { TaskStatus, TaskPriority, TaskActivityEvent } from '@/types';
import { STATUS_LABELS, PRIORITY_LABELS } from '@/constants/taskLabels';

export function formatDate(d: string | null): string {
  if (!d) return '—';
  const date = new Date(d + 'T00:00:00');
  return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
}

export function isOverdue(due: string | null): boolean {
  if (!due) return false;
  return new Date(due + 'T00:00:00') < new Date(new Date().toDateString());
}

export function formatPercent(value: number): string {
  return `${Math.round(value * 100)}%`;
}

export function fieldLabel(field: string): string {
  const labels: Record<string, string> = {
    title: 'Title',
    description: 'Description',
    priority: 'Priority',
    due_date: 'Due Date',
    selected_assignee_id: 'Assignee',
  };
  return labels[field] ?? field;
}

export function formatActivityTimestamp(timestamp: string): string {
  return new Date(timestamp).toLocaleString('en-US', {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
    hour: 'numeric',
    minute: '2-digit',
  });
}

export function activityFieldLabel(fieldName: string | null): string {
  if (!fieldName) return 'Task';
  const labels: Record<string, string> = {
    title: 'Title',
    description: 'Description',
    priority: 'Priority',
    due_date: 'Due Date',
    status: 'Status',
    assignee_id: 'Assignee',
  };
  return labels[fieldName] ?? fieldName;
}

export function formatActivityValue(
  value: unknown,
  fieldName: string | null,
  people: { id: string; name: string }[],
): string {
  if (value === null || value === undefined || value === '') return '—';

  if (fieldName === 'status' && typeof value === 'string') {
    return STATUS_LABELS[value as TaskStatus] ?? value;
  }
  if (fieldName === 'priority' && typeof value === 'string') {
    return PRIORITY_LABELS[value as TaskPriority] ?? value;
  }
  if (fieldName === 'due_date' && typeof value === 'string') {
    return formatDate(value);
  }
  if (fieldName === 'assignee_id' && typeof value === 'string') {
    return people.find((p) => p.id === value)?.name ?? value;
  }
  if (typeof value === 'string') return value;
  return JSON.stringify(value);
}

export function activityValueSummary(
  event: TaskActivityEvent,
  people: { id: string; name: string }[],
): string {
  if (event.action_type === 'task_created') return 'Task record created';
  return `${formatActivityValue(event.before_value, event.field_name, people)} → ${formatActivityValue(event.after_value, event.field_name, people)}`;
}
