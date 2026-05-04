import type {
  Task,
  TaskActivityEvent,
  TaskCreate,
  TaskUpdate,
  TaskAssigneeRecommendationsResponse,
  TaskSourceLink,
} from '../types';
import { api } from './client';

export const fetchTasks = (projectId?: string) => {
  const url = projectId ? `/api/tasks?project_id=${projectId}` : '/api/tasks';
  return api.get<Task[]>(url);
};
export const fetchTask = (id: string) => api.get<Task>(`/api/tasks/${id}`);
export const createTask = (data: TaskCreate) => api.post<Task>('/api/tasks', data);
export const updateTask = (id: string, data: TaskUpdate) => api.put<Task>(`/api/tasks/${id}`, data);
export const assignTask = (id: string, assignee_id: string | null) =>
  api.patch<Task>(`/api/tasks/${id}`, { assignee_id });
export const deleteTask = (id: string) => api.delete(`/api/tasks/${id}`);
export const bulkDeleteTasks = (taskIds: string[]) =>
  api.post<{ deleted_count: number }>('/api/tasks/bulk-delete', { task_ids: taskIds });
export const fetchTaskActivity = (taskId: string) =>
  api.get<TaskActivityEvent[]>(`/api/tasks/${taskId}/activity`);
export const fetchTaskSources = (taskId: string) =>
  api.get<TaskSourceLink[]>(`/api/tasks/${taskId}/sources`);
export const fetchTaskAssigneeRecommendations = (taskId: string) =>
  api.get<TaskAssigneeRecommendationsResponse>(`/api/tasks/${taskId}/assignee-recommendations`);
