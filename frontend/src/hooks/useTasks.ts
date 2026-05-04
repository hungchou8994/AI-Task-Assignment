import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { fetchTasks, createTask, updateTask, assignTask, deleteTask, bulkDeleteTasks, fetchTaskActivity, fetchTaskSources, fetchTaskAssigneeRecommendations } from '../api/tasks';
import type { TaskCreate, TaskUpdate } from '../types';

export const TASKS_KEY = ['tasks'] as const;
export const TASK_ACTIVITY_KEY = ['task-activity'] as const;
export const TASK_SOURCES_KEY = ['task-sources'] as const;

export function useTasks(projectId: string | null) {
  return useQuery({
    queryKey: [...TASKS_KEY, projectId],
    queryFn: () => fetchTasks(projectId || undefined),
    enabled: !!projectId,
    staleTime: 30_000,
  });
}

export function useCreateTask() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: TaskCreate) => createTask(data),
    onSuccess: () => qc.invalidateQueries({ queryKey: TASKS_KEY }),
  });
}

export function useUpdateTask() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: TaskUpdate }) => updateTask(id, data),
    onSuccess: (_, variables) => {
      qc.invalidateQueries({ queryKey: TASKS_KEY });
      qc.invalidateQueries({ queryKey: [...TASK_ACTIVITY_KEY, variables.id] });
    },
  });
}

export function useAssignTask() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, assignee_id }: { id: string; assignee_id: string | null }) =>
      assignTask(id, assignee_id),
    onSuccess: (_, variables) => {
      qc.invalidateQueries({ queryKey: TASKS_KEY });
      qc.invalidateQueries({ queryKey: [...TASK_ACTIVITY_KEY, variables.id] });
    },
  });
}

export function useDeleteTask() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => deleteTask(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: TASKS_KEY }),
  });
}

export function useBulkDeleteTasks() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (ids: string[]) => bulkDeleteTasks(ids),
    onSuccess: () => qc.invalidateQueries({ queryKey: TASKS_KEY }),
  });
}

export function useTaskActivity(taskId: string | null) {
  return useQuery({
    queryKey: [...TASK_ACTIVITY_KEY, taskId],
    queryFn: () => fetchTaskActivity(taskId as string),
    enabled: !!taskId,
    staleTime: 30_000,
  });
}

export function useTaskSources(taskId: string | null) {
  return useQuery({
    queryKey: [...TASK_SOURCES_KEY, taskId],
    queryFn: () => fetchTaskSources(taskId as string),
    enabled: !!taskId,
    staleTime: 60_000,
  });
}

export function useTaskAssigneeRecommendations(taskId: string | null) {
  return useQuery({
    queryKey: ['task-assignee-recommendations', taskId],
    queryFn: () => fetchTaskAssigneeRecommendations(taskId as string),
    enabled: !!taskId,
    staleTime: 60_000,
  });
}
