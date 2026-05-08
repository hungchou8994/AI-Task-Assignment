import { api } from './client';
import type {
  Workspace,
  WorkspaceCreate,
  WorkspaceMember,
  WorkspaceMemberCreate,
  Project,
  ProjectCreate,
} from '../types';

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

export const fetchMyWorkspaceRole = (workspaceId: string) =>
  api.get<{ role: string }>(`/api/workspaces/${workspaceId}/my-role`);

export const fetchWorkspaceMembers = (workspaceId: string) =>
  api.get<WorkspaceMember[]>(`/api/workspaces/${workspaceId}/members`);

export const addWorkspaceMember = (workspaceId: string, data: WorkspaceMemberCreate) =>
  api.post<WorkspaceMember>(`/api/workspaces/${workspaceId}/members`, data);
