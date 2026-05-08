/**
 * WorkspaceContext wraps ProjectContext to also provide the current workspace
 * object (name, id) needed for routing and display in the Layout.
 *
 * We re-export everything from ProjectContext and add `currentWorkspace` and
 * `currentProject` as convenience objects.
 */
import React, { createContext, useContext, useState, useEffect, useCallback } from 'react';
import { useAuth } from './AuthContext';
import { useWorkspaces } from '../hooks/useWorkspaces';
import { useProjects } from '../hooks/useProjects';
import type { Workspace, Project } from '../types';

const STORAGE_KEY = 'lastProjectId';

interface WorkspaceContextType {
  currentWorkspaceId: string | null;
  currentProjectId: string | null;
  currentWorkspace: Workspace | null;
  currentProject: Project | null;
  workspacesLoading: boolean;
  workspacesError: boolean;
  selectWorkspace: (id: string) => void;
  selectProject: (id: string) => void;
}

const WorkspaceContext = createContext<WorkspaceContextType | undefined>(undefined);

export function WorkspaceProvider({ children }: { children: React.ReactNode }) {
  const [currentWorkspaceId, setCurrentWorkspaceId] = useState<string | null>(null);
  const [currentProjectId, setCurrentProjectId] = useState<string | null>(null);
  const { user, loading: authLoading } = useAuth();

  const {
    data: workspaces,
    isLoading: workspacesLoading,
    isError: workspacesError,
  } = useWorkspaces(!!user && !authLoading);
  const { data: projects, isLoading: projectsLoading } = useProjects(currentWorkspaceId);

  useEffect(() => {
    if (!authLoading && !user) {
      setCurrentWorkspaceId(null);
      setCurrentProjectId(null);
    }
  }, [user, authLoading]);

  // Initialize from localStorage and validate on mount.
  // Also handles stale workspace/project UUIDs (e.g. after a DB reseed).
  useEffect(() => {
    if (!user) return;
    if (workspacesLoading) return;
    if (!workspaces || workspaces.length === 0) return;

    const storedProjectId = localStorage.getItem(STORAGE_KEY);

    // If the current workspace ID is stale (not in the workspaces list),
    // reset it so the auto-select below can pick a valid workspace.
    if (currentWorkspaceId && !workspaces.some((w) => w.id === currentWorkspaceId)) {
      setCurrentWorkspaceId(null);
      setCurrentProjectId(null);
      localStorage.removeItem(STORAGE_KEY);
      return;
    }

    if (!currentWorkspaceId) {
      setCurrentWorkspaceId(workspaces[0].id);
      return;
    }

    if (projectsLoading) return;

    if (projects && projects.length > 0) {
      if (storedProjectId && projects.some((p) => p.id === storedProjectId)) {
        setCurrentProjectId(storedProjectId);
      } else if (!currentProjectId) {
        setCurrentProjectId(projects[0].id);
        localStorage.setItem(STORAGE_KEY, projects[0].id);
      }
    }
  }, [user, workspaces, projects, currentWorkspaceId, currentProjectId, workspacesLoading, projectsLoading]);

  const selectWorkspace = useCallback((id: string) => {
    setCurrentWorkspaceId(id);
    setCurrentProjectId(null);
  }, []);

  const selectProject = useCallback((id: string) => {
    setCurrentProjectId(id);
    localStorage.setItem(STORAGE_KEY, id);
  }, []);

  const currentWorkspace = workspaces?.find((w) => w.id === currentWorkspaceId) ?? null;
  const currentProject = projects?.find((p) => p.id === currentProjectId) ?? null;

  return (
    <WorkspaceContext.Provider
      value={{
        currentWorkspaceId,
        currentProjectId,
        currentWorkspace,
        currentProject,
        workspacesLoading,
        workspacesError,
        selectWorkspace,
        selectProject,
      }}
    >
      {children}
    </WorkspaceContext.Provider>
  );
}

export function useWorkspaceContext() {
  const context = useContext(WorkspaceContext);
  if (context === undefined) {
    throw new Error('useWorkspaceContext must be used within a WorkspaceProvider');
  }
  return context;
}

// Backward-compat alias for code that still uses useProjectContext
export { useWorkspaceContext as useProjectContext };
