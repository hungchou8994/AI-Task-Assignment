import { useEffect, useRef, useState } from 'react';
import { CheckCircle2, ChevronDown, ChevronRight, Loader2, X, XCircle } from 'lucide-react';
import type { AgentEvent, ExtractedTask, JobEntry } from '../types';
import { fetchTask } from '../api/tasks';
import { useJobEventStream } from '../hooks/useJobEventStream';
import { usePeople } from '../hooks/usePeople';
import { useLanguage } from '../i18n/LanguageContext';
import { TaskModal } from './tasks/TaskModal';
import { AgentLoopTimeline } from './AgentLoopTimeline';

interface JobCardProps {
  job: JobEntry;
  projectId: string | null;
  onRemove: (jobId: string) => void;
  onTerminal?: () => void;
}

function normalizeEventType(event: AgentEvent) {
  return (event.event_type || event.type || 'event').toLowerCase();
}

function parseEventTimestamp(event: AgentEvent) {
  const value = event.created_at || event.timestamp;
  if (!value) return null;
  const timestamp = Date.parse(value);
  return Number.isNaN(timestamp) ? null : timestamp;
}

export function JobCard({ job, projectId, onRemove, onTerminal }: JobCardProps) {
  const { t } = useLanguage();
  const { status, result, error, attempts } = job;
  const extractedTaskCount = Math.max(
    result?.tasks.length ?? 0,
    result?.created_task_ids?.length ?? 0,
  );
  const [showAgentDetails, setShowAgentDetails] = useState(false);
  const [showTasks, setShowTasks] = useState(true);
  const [showProgress, setShowProgress] = useState(true);
  const isTerminal = status === 'done' || status === 'failed';
  const shouldLoadAgentEvents = status === 'queued' || status === 'running' || status === 'done';
  const isProcessing = status === 'queued' || status === 'running';
  const {
    events,
    isLoading: isEventsLoading,
    isError: isEventsError,
    connectionState,
  } = useJobEventStream(
    job.jobId,
    shouldLoadAgentEvents
  );

  // When SSE signals terminal (idle after being live/fallback), fetch the final job status once
  const wasLiveRef = useRef(false);
  const terminalFetchedRef = useRef(false);
  useEffect(() => {
    if (connectionState === 'live' || connectionState === 'fallback') {
      wasLiveRef.current = true;
    }
  }, [connectionState]);

  useEffect(() => {
    if (terminalFetchedRef.current) return;
    // SSE signaled terminal (idle after being live/fallback)
    if (connectionState === 'idle' && wasLiveRef.current) {
      terminalFetchedRef.current = true;
      onTerminal?.();
      return;
    }
    // Both SSE and polling failed (e.g., job evicted on backend restart) —
    // fetch status once to confirm and evict from localStorage
    if (isEventsError) {
      terminalFetchedRef.current = true;
      onTerminal?.();
    }
  }, [connectionState, isEventsError, onTerminal]);

  const connectionBadge =
    connectionState === 'live'
      ? {
          label: t.jobCard.connectionLive,
          className: 'text-muted-foreground',
          dotClassName: 'bg-success',
        }
      : connectionState === 'fallback'
        ? {
            label: t.jobCard.connectionPolling,
            className: 'text-muted-foreground',
            dotClassName: 'bg-warning',
          }
        : {
            label: t.jobCard.connectionConnecting,
            className: 'text-muted-foreground',
            dotClassName: 'bg-muted-foreground/70',
          };

  const rounds = new Set(
    events
      .map((event) => event.iteration ?? (event.metadata?.iteration as number | undefined))
      .filter((value): value is number => typeof value === 'number')
  ).size;
  const steps = events.filter((event) => normalizeEventType(event) === 'tool_call').length;
  const timestamps = events
    .map((event) => parseEventTimestamp(event))
    .filter((value): value is number => value !== null)
    .sort((a, b) => a - b);
  const durationMs = timestamps.length > 1 ? timestamps[timestamps.length - 1] - timestamps[0] : null;

  const durationLabel = (() => {
    if (durationMs === null) return t.jobCard.durationUnknown;
    const totalSeconds = Math.max(1, Math.round(durationMs / 1000));
    if (totalSeconds < 60) {
      return t.jobCard.durationSeconds.replace('{count}', String(totalSeconds));
    }
    const minutes = Math.floor(totalSeconds / 60);
    const seconds = totalSeconds % 60;
    return t.jobCard.durationMinutes
      .replace('{minutes}', String(minutes))
      .replace('{seconds}', String(seconds));
  })();
  const executionSummary = t.jobCard.executionSummary
    .replace('{rounds}', String(rounds))
    .replace('{steps}', String(steps))
    .replace('{duration}', durationLabel);

  return (
    <div className={`rounded-lg border bg-card p-4 transition-colors hover:bg-muted/15 ${
      status === 'done'
        ? 'border-success/30 border-l-[3px] border-l-success'
        : status === 'failed'
          ? 'border-destructive/30 border-l-[3px] border-l-destructive'
          : 'border-primary/30 border-l-[3px] border-l-primary'
    }`}>
      {/* ── Header ── */}
      <div className="flex items-start justify-between gap-2">
        <div className="flex items-center gap-2">
          {status === 'queued' || status === 'running' ? (
            <>
              <Loader2 className="h-4 w-4 animate-spin text-primary" />
              <span className="text-sm font-semibold text-foreground">{t.jobCard.analyzing}</span>
            </>
          ) : status === 'done' ? (
            <>
              <CheckCircle2 className="h-4 w-4 text-success" />
              <span className="text-sm font-semibold text-foreground">
                {t.jobCard.tasksExtracted.replace('{count}', String(extractedTaskCount))}
              </span>
            </>
          ) : (
            <>
              <XCircle className="h-4 w-4 text-destructive" />
              <span className="text-sm font-semibold text-destructive">{t.jobCard.extractionFailed}</span>
            </>
          )}
          {attempts && attempts > 1 && (
            <span className="text-[11px] text-muted-foreground">
              {t.jobCard.attempt.replace('{count}', String(attempts))}
            </span>
          )}
        </div>
        {isTerminal && (
          <button
            onClick={() => onRemove(job.jobId)}
            className="rounded p-1 text-muted-foreground transition-all hover:bg-accent hover:text-foreground"
            aria-label="Remove job"
          >
            <X className="h-3.5 w-3.5" />
          </button>
        )}
      </div>

      {/* ── Source summary ── */}
      {status === 'done' && result?.source_summary && (
        <div className="mt-3">
          <p className="text-[11px] font-bold tracking-wide text-muted-foreground">
            Source Summary
          </p>
          <p className="mt-0.5 text-xs text-muted-foreground">{result.source_summary}</p>
        </div>
      )}

      {/* ── Execution row – click to toggle agent details ── */}
      {(isProcessing || (events.length > 0 && status === 'done')) && (
        <div className="mt-3">
          <button
            type="button"
            onClick={() => status === 'done'
              ? setShowAgentDetails((v) => !v)
              : setShowProgress((v) => !v)
            }
            className="group flex w-full items-center gap-1.5 rounded py-0.5 text-xs text-muted-foreground transition-colors hover:bg-muted/40 hover:text-foreground"
          >
            {(status === 'done' ? showAgentDetails : showProgress)
              ? <ChevronDown className="h-3 w-3 shrink-0" />
              : <ChevronRight className="h-3 w-3 shrink-0" />
            }
            <span>
              {events.length > 0 ? executionSummary : t.jobCard.agentRunning}
            </span>
          </button>

          {/* Agent timeline (done) */}
          {status === 'done' && showAgentDetails && (
            <div className="mt-2">
              <AgentLoopTimeline
                events={events}
                isLoading={isEventsLoading}
                isError={isEventsError}
                connectionState={connectionState}
              />
            </div>
          )}
          {/* Agent timeline (running/queued) – auto-open */}
          {isProcessing && showProgress && (
            <div className="mt-2">
              <AgentLoopTimeline
                events={events}
                isLoading={isEventsLoading}
                isError={isEventsError}
                connectionState={connectionState}
              />
            </div>
          )}
        </div>
      )}

      {status === 'failed' && error && (
        <p className="mt-2 text-xs text-destructive">{error}</p>
      )}

      {/* ── Extracted tasks ── */}
      {status === 'done' && result && result.tasks.length > 0 && (
        <div className="pt-3">
          <button
            type="button"
            onClick={() => setShowTasks((v) => !v)}
            className="group flex w-full items-center gap-1.5 rounded py-0.5 text-xs text-muted-foreground transition-colors hover:bg-muted/40 hover:text-foreground"
          >
            {(showTasks)
              ? <ChevronDown className="h-3 w-3 shrink-0" />
              : <ChevronRight className="h-3 w-3 shrink-0" />
            }
            <span>Tasks</span>
          </button>
          {showTasks && result.tasks.map((task, idx) => {
            const taskId = result.created_task_ids?.[idx];
            return (
              <TaskRow key={idx} task={task} taskId={taskId} />
            );
          })}
        </div>
      )}
    </div>
  );
}

interface TaskRowProps {
  task: ExtractedTask;
  taskId: string | undefined;
}

function TaskRow({ task, taskId }: TaskRowProps) {
  const { t } = useLanguage();
  const { data: people = [] } = usePeople();
  const [selectedTask, setSelectedTask] = useState<import('../types').Task | null>(null);
  const [loading, setLoading] = useState(false);

  async function handleView() {
    if (!taskId) return;
    setLoading(true);
    try {
      const fetched = await fetchTask(taskId);
      setSelectedTask(fetched);
    } catch {
      // ignore — button stays clickable
    } finally {
      setLoading(false);
    }
  }

  return (
    <>
      <button 
        className="w-full p-2 flex items-center justify-between gap-2 border-b border-border/40 py-2 transition-colors hover:bg-muted/80"
        onClick={handleView}
        disabled={loading}
      >
        <div className="flex items-center gap-2">
          <span className="text-xs text-foreground">{task.title}</span>
        </div>
        <div className="flex items-center gap-2">
          <span
            className={`rounded-full px-2 py-0.5 text-[8px] font-medium uppercase ${
              task.priority === 'high'
                ? 'bg-destructive/10 text-destructive'
                : task.priority === 'medium'
                  ? 'bg-muted text-foreground/70'
                  : 'bg-muted/60 text-muted-foreground'
            }`}
          >
            {t.priority[task.priority]}
          </span>
          <div
            className="text-[10px] font-medium text-primary hover:underline underline-offset-4 transition-all disabled:opacity-50"
          >
            {loading ? t.jobCard.loading : t.jobCard.view}
          </div>
        </div>
      </button>
      {selectedTask && (
        <TaskModal task={selectedTask} people={people} onClose={() => setSelectedTask(null)} />
      )}
    </>
  );
}
