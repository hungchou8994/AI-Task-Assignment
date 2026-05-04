import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { fetchProjects, createProject } from '../api/workspaces';
import type { ProjectCreate } from '../types';

export const PROJECTS_KEY = ['projects'] as const;

export function useProjects(workspaceId: string | null) {
  return useQuery({
    queryKey: [...PROJECTS_KEY, workspaceId],
    queryFn: () => fetchProjects(workspaceId!),
    enabled: !!workspaceId,
    staleTime: 30_000,
  });
}

export function useCreateProject() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({
      workspaceId,
      data,
    }: {
      workspaceId: string;
      data: ProjectCreate;
    }) => createProject(workspaceId, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: PROJECTS_KEY });
    },
  });
}
