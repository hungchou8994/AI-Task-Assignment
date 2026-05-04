import { api } from './client';
import type { Workspace, WorkspaceCreate, Project, ProjectCreate } from '../types';

export async function fetchWorkspaces(): Promise<Workspace[]> {
  return api.get<Workspace[]>('/api/workspaces');
}

export async function createWorkspace(data: WorkspaceCreate): Promise<Workspace> {
  return api.post<Workspace>('/api/workspaces', data);
}

export async function fetchProjects(workspaceId: string): Promise<Project[]> {
  return api.get<Project[]>(`/api/workspaces/${workspaceId}/projects`);
}

export async function createProject(
  workspaceId: string,
  data: ProjectCreate
): Promise<Project> {
  return api.post<Project>(`/api/workspaces/${workspaceId}/projects`, data);
}
