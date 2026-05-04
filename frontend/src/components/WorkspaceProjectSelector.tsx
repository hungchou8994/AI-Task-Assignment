import { useState } from 'react';
import { ChevronDown, Building2, FolderKanban, Check } from 'lucide-react';
import { useWorkspaceContext } from '../context/WorkspaceContext';
import { useWorkspaces } from '../hooks/useWorkspaces';
import { useProjects } from '../hooks/useProjects';
import { Popover, PopoverContent, PopoverTrigger } from './ui/popover';
import { cn } from '@/lib/utils';

interface WorkspaceProjectSelectorProps {
  /** When true, renders a compact single-line version suitable for a sidebar header */
  compact?: boolean;
}

export function WorkspaceProjectSelector({ compact = false }: WorkspaceProjectSelectorProps) {
  const { currentWorkspaceId, currentProjectId, selectWorkspace, selectProject } =
    useWorkspaceContext();
  const { data: workspaces, isLoading: workspacesLoading } = useWorkspaces();
  const { data: projects, isLoading: projectsLoading } = useProjects(currentWorkspaceId);
  const [open, setOpen] = useState(false);

  if (workspacesLoading) {
    return <div className="h-6 w-full bg-muted animate-pulse rounded" />;
  }

  const currentWorkspace = workspaces?.find((w) => w.id === currentWorkspaceId);
  const currentProject = projects?.find((p) => p.id === currentProjectId);

  const workspaceName = currentWorkspace?.name ?? 'Select workspace';
  const projectName = currentProject?.name;

  if (compact) {
    return (
      <Popover open={open} onOpenChange={setOpen}>
        <PopoverTrigger asChild>
          <button
            className={cn(
              'w-full flex items-center gap-2 px-1 py-1 text-left transition-colors',
              'hover:bg-accent/50 focus:outline-none',
            )}
          >
            <div className="flex-1 min-w-0">
              <p className="text-sm font-semibold text-foreground truncate leading-tight">
                {projectName ? (
                  <>
                    <span className="text-muted-foreground font-medium">{workspaceName}</span>
                    <span className="text-muted-foreground/40 mx-1">/</span>
                    <span>{projectName}</span>
                  </>
                ) : (
                  workspaceName
                )}
              </p>
            </div>
            <ChevronDown className="h-3.5 w-3.5 text-muted-foreground shrink-0" />
          </button>
        </PopoverTrigger>

        <PopoverContent
          align="start"
          side="bottom"
          sideOffset={6}
          className="w-[220px] p-0 overflow-hidden z-50"
        >
          {_dropdownContent(workspaces, projects, currentWorkspaceId, currentProjectId, workspacesLoading, projectsLoading, selectWorkspace, selectProject, setOpen)}
        </PopoverContent>
      </Popover>
    );
  }

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <button
          className={cn(
            'w-full flex items-center gap-2.5 px-3 py-2.5 text-left transition-all',
            'border border-border hover:border-ring/50 hover:bg-accent/30',
            'focus:outline-none focus:ring-2 focus:ring-ring/20',
            'group',
          )}
        >
          <div className="flex-1 min-w-0">
            <p className="text-[10px] font-bold uppercase tracking-[0.15em] text-muted-foreground leading-none mb-1">
              Workspace
            </p>
            <p className="text-sm font-semibold text-foreground truncate leading-tight">
              {projectName ? (
                <>
                  <span className="text-muted-foreground font-medium">{workspaceName}</span>
                  <span className="text-muted-foreground/40 mx-1">/</span>
                  <span>{projectName}</span>
                </>
              ) : (
                workspaceName
              )}
            </p>
          </div>
          <ChevronDown className="h-4 w-4 text-muted-foreground group-hover:text-foreground transition-colors shrink-0" />
        </button>
      </PopoverTrigger>

      <PopoverContent
        align="start"
        side="bottom"
        sideOffset={6}
        className="w-[220px] p-0 overflow-hidden z-50"
      >
        {_dropdownContent(workspaces, projects, currentWorkspaceId, currentProjectId, workspacesLoading, projectsLoading, selectWorkspace, selectProject, setOpen)}
      </PopoverContent>
    </Popover>
  );
}

function _dropdownContent(
  workspaces: import('../types').Workspace[] | undefined,
  projects: import('../types').Project[] | undefined,
  currentWorkspaceId: string | null,
  currentProjectId: string | null,
  _workspacesLoading: boolean,
  projectsLoading: boolean,
  selectWorkspace: (id: string) => void,
  selectProject: (id: string) => void,
  setOpen: (open: boolean) => void,
) {
  return (
    <>
      {/* Workspaces */}
      <div className="p-2 border-b border-border">
        <p className="px-2 py-1.5 text-[10px] font-bold uppercase tracking-[0.15em] text-muted-foreground flex items-center gap-1.5">
          <Building2 className="h-3 w-3" />
          Workspaces
        </p>
        {workspaces?.map((workspace) => (
          <button
            key={workspace.id}
            onClick={() => selectWorkspace(workspace.id)}
            className={cn(
              'w-full flex items-center gap-2 px-2 py-2 text-left text-sm transition-colors',
              workspace.id === currentWorkspaceId
                ? 'bg-accent text-foreground font-semibold'
                : 'text-foreground/80 hover:bg-accent/50',
            )}
          >
            <span className="truncate flex-1">{workspace.name}</span>
            {workspace.id === currentWorkspaceId && <Check className="h-3.5 w-3.5 shrink-0" />}
          </button>
        ))}
      </div>

      {/* Projects */}
      <div className="p-2">
        <p className="px-2 py-1.5 text-[10px] font-bold uppercase tracking-[0.15em] text-muted-foreground flex items-center gap-1.5">
          <FolderKanban className="h-3 w-3" />
          Projects
        </p>
        {projectsLoading ? (
          <div className="px-2 py-3">
            <div className="h-4 w-3/4 bg-muted animate-pulse rounded" />
          </div>
        ) : projects && projects.length > 0 ? (
          projects.map((project) => (
            <button
              key={project.id}
              onClick={() => { selectProject(project.id); setOpen(false); }}
              className={cn(
                'w-full flex items-center gap-2 px-2 py-2 text-left text-sm transition-colors',
                project.id === currentProjectId
                  ? 'bg-accent text-foreground font-semibold'
                  : 'text-foreground/80 hover:bg-accent/50',
              )}
            >
              <span className="truncate flex-1">{project.name}</span>
              {project.id === currentProjectId && <Check className="h-3.5 w-3.5 shrink-0" />}
            </button>
          ))
        ) : (
          <p className="px-2 py-2.5 text-xs text-muted-foreground">No projects yet</p>
        )}
      </div>
    </>
  );
}
