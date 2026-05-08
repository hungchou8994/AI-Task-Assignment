import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { fetchTasks, createTask, updateTask, assignTask, deleteTask, bulkDeleteTasks, fetchTaskActivity, fetchTaskSources, fetchTaskAssigneeRecommendations, fetchTaskComments, createTaskComment, updateTaskComment, deleteTaskComment } from '../api/tasks';
import { fetchMyWorkspaceRole } from '../api/workspaces';
import type { TaskCreate, TaskUpdate, TaskComment } from '../types';

export const TASKS_KEY = ['tasks'] as const;
export const TASK_ACTIVITY_KEY = ['task-activity'] as const;
export const TASK_SOURCES_KEY = ['task-sources'] as const;
export const TASK_COMMENTS_KEY = ['task-comments'] as const;

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

export function useTaskComments(taskId: string | null) {
  return useQuery({
    queryKey: [...TASK_COMMENTS_KEY, taskId],
    queryFn: () => fetchTaskComments(taskId as string),
    enabled: !!taskId,
    staleTime: 30_000,
  });
}

export function useCreateComment(taskId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: string) => createTaskComment(taskId, body),
    onSuccess: () => qc.invalidateQueries({ queryKey: [...TASK_COMMENTS_KEY, taskId] }),
  });
}

export function useUpdateComment(taskId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ commentId, body }: { commentId: string; body: string }) =>
      updateTaskComment(taskId, commentId, body),
    onSuccess: () => qc.invalidateQueries({ queryKey: [...TASK_COMMENTS_KEY, taskId] }),
  });
}

export function useDeleteComment(taskId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (commentId: string) => deleteTaskComment(taskId, commentId),
    onSuccess: () => qc.invalidateQueries({ queryKey: [...TASK_COMMENTS_KEY, taskId] }),
  });
}

export function useWorkspaceRole(workspaceId: string | null) {
  return useQuery({
    queryKey: ['workspace-role', workspaceId],
    queryFn: () => fetchMyWorkspaceRole(workspaceId as string),
    enabled: !!workspaceId,
    staleTime: 60_000,
  });
}

