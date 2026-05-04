import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { fetchWorkspaces, createWorkspace } from '../api/workspaces';
import type { WorkspaceCreate } from '../types';

export const WORKSPACES_KEY = ['workspaces'] as const;

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
