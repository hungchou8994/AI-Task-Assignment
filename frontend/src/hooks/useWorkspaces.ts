import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  fetchWorkspaces,
  createWorkspace,
  fetchWorkspaceMembers,
  addWorkspaceMember,
} from '../api/workspaces';
import type { WorkspaceCreate, WorkspaceMemberCreate } from '../types';

export const WORKSPACES_KEY = ['workspaces'] as const;
export const WORKSPACE_MEMBERS_KEY = ['workspace-members'] as const;

export function useWorkspaces(enabled = true) {
  return useQuery({
    queryKey: WORKSPACES_KEY,
    queryFn: fetchWorkspaces,
    enabled,
    staleTime: 30_000,
  });
}

export function useCreateWorkspace() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data: WorkspaceCreate) => createWorkspace(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: WORKSPACES_KEY });
    },
  });
}

export function useWorkspaceMembers(workspaceId: string | null) {
  return useQuery({
    queryKey: [...WORKSPACE_MEMBERS_KEY, workspaceId],
    queryFn: () => fetchWorkspaceMembers(workspaceId as string),
    enabled: !!workspaceId,
    staleTime: 30_000,
  });
}

export function useAddWorkspaceMember(workspaceId: string | null) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data: WorkspaceMemberCreate) => addWorkspaceMember(workspaceId as string, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: [...WORKSPACE_MEMBERS_KEY, workspaceId] });
    },
  });
}
