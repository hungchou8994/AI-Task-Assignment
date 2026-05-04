import { useEffect } from 'react';
import { Routes, Route, Navigate, useParams } from 'react-router-dom';
import { Layout } from './components/Layout';
import { AuthPage } from './pages/AuthPage';
import { TaskDashboard } from './pages/TaskDashboard';
import { TasksPage } from './pages/Tasks';
import { TeamMembersPage } from './pages/TeamMembers';
import { ReviewQueuePage } from './pages/ReviewQueue';
import { AIAnalysisPage } from './pages/AIAnalysis';
import { SourcesPage } from './pages/Sources';
import { DocumentationPage } from './pages/Documentation';
import WebhooksSettingsPage from './pages/WebhooksSettings';
import NotFound from './pages/NotFound';
import { useAuth } from './context/AuthContext';
import { useWorkspaceContext } from './context/WorkspaceContext';

/**
 * Root redirect: sends the user to /:workspaceId/dashboard (or /auth if not logged in).
 * Waits for the workspace context to resolve.
 */
function WorkspaceRootRedirect() {
  const { user, loading: authLoading } = useAuth();
  const { currentWorkspaceId, workspacesLoading, workspacesError } = useWorkspaceContext();

  if (authLoading) {
    return <div className="flex items-center justify-center min-h-screen text-sm text-muted-foreground">Loading...</div>;
  }

  if (!user) {
    return <Navigate to="/auth" replace />;
  }

  if (!currentWorkspaceId && workspacesLoading) {
    return <div className="flex items-center justify-center min-h-screen text-sm text-muted-foreground">Loading workspace...</div>;
  }

  if (!currentWorkspaceId || workspacesError) {
    return <div className="flex items-center justify-center min-h-screen text-sm text-destructive">Unable to load workspace.</div>;
  }

  return <Navigate to={`/${currentWorkspaceId}/dashboard`} replace />;
}

/**
 * The Layout wrapper that also guards auth and syncs /:workspaceId from URL.
 */
function ProtectedLayout() {
  const { user, loading } = useAuth();
  const { workspaceId } = useParams<{ workspaceId: string }>();
  const { currentWorkspaceId, selectWorkspace } = useWorkspaceContext();
  const isDemoRoute = workspaceId === 'demo';

  // When the URL workspaceId changes (e.g. user navigates via bookmark), sync context.
  useEffect(() => {
    if (isDemoRoute) {
      return;
    }

    if (workspaceId && workspaceId !== currentWorkspaceId) {
      selectWorkspace(workspaceId);
    }
  }, [workspaceId, currentWorkspaceId, selectWorkspace, isDemoRoute]);

  if (!isDemoRoute && loading) {
    return <div className="flex items-center justify-center min-h-screen text-sm text-muted-foreground">Loading...</div>;
  }

  if (!isDemoRoute && !user) {
    return <Navigate to="/auth" replace />;
  }

  return <Layout />;
}

export function AppRoutes() {
  return (
    <Routes>
      {/* Public auth route */}
      <Route path="/auth" element={<AuthPage />} />

      {/* Root redirect */}
      <Route index element={<WorkspaceRootRedirect />} />

      {/* Workspace-scoped task management routes */}
      <Route path="/:workspaceId" element={<ProtectedLayout />}>
        <Route index element={<Navigate to="dashboard" replace />} />
        <Route path="dashboard" element={<TaskDashboard />} />
        <Route path="tasks" element={<TasksPage />} />
        <Route path="team" element={<TeamMembersPage />} />
        <Route path="review" element={<ReviewQueuePage />} />
        <Route path="ai" element={<AIAnalysisPage />} />
        <Route path="sources" element={<SourcesPage />} />
        <Route path="settings/webhooks" element={<WebhooksSettingsPage />} />
        <Route path="documentation" element={<DocumentationPage />} />
      </Route>

      {/* Catch-all */}
      <Route path="*" element={<NotFound />} />
    </Routes>
  );
}
