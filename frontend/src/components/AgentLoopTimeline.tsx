import { useEffect, useMemo, useRef, useState } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import {
  AlertTriangle,
  Bot,
  Brain,
  ChevronDown,
  ChevronRight,
  Lightbulb,
  Loader2,
  Sparkles,
  Wrench,
  Zap,
} from 'lucide-react';
import type { AgentEvent } from '../types';

interface AgentLoopTimelineProps {
  events: AgentEvent[];
  isLoading?: boolean;
  isError?: boolean;
  connectionState?: 'idle' | 'connecting' | 'live' | 'fallback';
}

/* ---------- helpers ---------- */

function normalizeType(event: AgentEvent) {
  return (event.event_type || event.type || 'event').toLowerCase();
}

interface IterationGroup {
  iteration: number;
  events: Array<{ event: AgentEvent; type: string }>;
}

interface MergedToolStep {
  key: string;
  toolName?: string;
  callEvent?: AgentEvent;
  resultEvent?: AgentEvent;
  errorEvent?: AgentEvent;
}

type IterationRenderItem =
  | { kind: 'event'; event: AgentEvent; type: string; key: string }
  | { kind: 'tool_step'; step: MergedToolStep };

/**
 * Collapse streaming delta events into their _start event.
 *
 * The backend emits:  thinking_start → N × thinking_delta → thinking_end
 *                     text_start     → N × text_delta     → text_end
 *
 * We accumulate all delta messages into the _start event's `message` field
 * and mark it as streaming (isStreaming flag in metadata) until _end arrives.
 * Individual _delta and _end events are filtered out of the final list.
 */
function collapseStreamDeltas(events: AgentEvent[]): AgentEvent[] {
  const streamAccum: Map<string, { startEvent: AgentEvent; text: string; finished: boolean }> = new Map();
  const result: AgentEvent[] = [];

  for (const event of events) {
    const type = normalizeType(event);
    const streamId = event.metadata?.stream_id as string | undefined;

    if (type === 'thinking_start' || type === 'text_start') {
      const syntheticType = type === 'thinking_start' ? 'thinking' : 'reasoning';
      const collapsed: AgentEvent = {
        ...event,
        event_type: syntheticType,
        type: syntheticType,
        message: '',
        metadata: { ...event.metadata, isStreaming: true },
      };
      if (streamId) {
        streamAccum.set(streamId, { startEvent: collapsed, text: '', finished: false });
      }
      result.push(collapsed);
    } else if ((type === 'thinking_delta' || type === 'text_delta') && streamId) {
      const accum = streamAccum.get(streamId);
      if (accum) {
        accum.text += event.message ?? '';
        accum.startEvent.message = accum.text;
      }
      // Skip — don't add delta events to result
    } else if ((type === 'thinking_end' || type === 'text_end') && streamId) {
      const accum = streamAccum.get(streamId);
      if (accum) {
        accum.finished = true;
        accum.startEvent.metadata = { ...accum.startEvent.metadata, isStreaming: false };
      }
      // Skip — don't add end events to result
    } else {
      result.push(event);
    }
  }

  return result;
}

function groupByIteration(events: AgentEvent[]): { groups: IterationGroup[]; ungrouped: Array<{ event: AgentEvent; type: string }> } {
  // First collapse streaming deltas
  const collapsed = collapseStreamDeltas(events);

  const groups: Map<number, IterationGroup> = new Map();
  const ungrouped: Array<{ event: AgentEvent; type: string }> = [];

  for (const event of collapsed) {
    const type = normalizeType(event);
    const iter = event.iteration ?? (event.metadata?.iteration as number | undefined);

    if (typeof iter === 'number') {
      let group = groups.get(iter);
      if (!group) {
        group = { iteration: iter, events: [] };
        groups.set(iter, group);
      }
      group.events.push({ event, type });
    } else {
      ungrouped.push({ event, type });
    }
  }

  return { groups: Array.from(groups.values()), ungrouped };
}

function getCallId(event: AgentEvent): string | undefined {
  const value = event.metadata?.call_id;
  return typeof value === 'string' && value ? value : undefined;
}

function mergeToolEvents(entries: Array<{ event: AgentEvent; type: string }>): IterationRenderItem[] {
  const merged: IterationRenderItem[] = [];
  const byCallId = new Map<string, MergedToolStep>();

  const findFallbackStep = (toolName: string | undefined) => {
    if (!toolName) return undefined;
    for (let i = merged.length - 1; i >= 0; i -= 1) {
      const item = merged[i];
      if (item.kind !== 'tool_step') continue;
      if (item.step.toolName !== toolName) continue;
      if (!item.step.resultEvent && !item.step.errorEvent) return item.step;
    }
    return undefined;
  };

  entries.forEach(({ event, type }, index) => {
    if (type === 'tool_call') {
      const callId = getCallId(event);
      const step: MergedToolStep = {
        key: event.id || callId || `tool-call-${event.tool_name || 'unknown'}-${index}`,
        toolName: event.tool_name,
        callEvent: event,
      };
      merged.push({ kind: 'tool_step', step });
      if (callId) byCallId.set(callId, step);
      return;
    }

    if (type === 'tool_result' || type === 'tool_error') {
      const callId = getCallId(event);
      const byId = callId ? byCallId.get(callId) : undefined;
      const byName = findFallbackStep(event.tool_name);
      const step = byId || byName;

      if (step) {
        if (type === 'tool_result') step.resultEvent = event;
        if (type === 'tool_error') step.errorEvent = event;
        return;
      }

      const syntheticStep: MergedToolStep = {
        key: event.id || callId || `tool-${type}-${event.tool_name || 'unknown'}-${index}`,
        toolName: event.tool_name,
        resultEvent: type === 'tool_result' ? event : undefined,
        errorEvent: type === 'tool_error' ? event : undefined,
      };
      merged.push({ kind: 'tool_step', step: syntheticStep });
      return;
    }

    merged.push({
      kind: 'event',
      event,
      type,
      key: event.id || `${type}-${event.created_at || index}`,
    });
  });

  return merged;
}

function getToolIcon(toolName: string | undefined) {
  const iconMap: Record<string, typeof Wrench> = {
    analyze_content: Zap,
    extract_entities: Lightbulb,
    validate_task: Sparkles,
    get_assignee_skills: Bot,
    finalize_extraction: Sparkles,
  };
  return toolName ? iconMap[toolName] ?? Wrench : Wrench;
}

function truncate(text: string, maxLen: number) {
  if (text.length <= maxLen) return text;
  return text.slice(0, maxLen) + '...';
}

function tryFormatJson(raw: string | undefined): string | null {
  if (!raw) return null;
  try {
    const obj = JSON.parse(raw);
    return JSON.stringify(obj, null, 2);
  } catch {
    return null;
  }
}

function toDomId(value: string): string {
  return value.replace(/[^a-zA-Z0-9_-]/g, '-');
}

function useSmoothStreamingText(text: string, isStreaming: boolean) {
  const [displayed, setDisplayed] = useState(text);

  useEffect(() => {
    // Keep resets/smaller updates immediate.
    setDisplayed((prev) => {
      if (!text.startsWith(prev)) return text;
      return prev;
    });

    // Animate forward growth even if the backend delivered a burst so
    // the UI still feels token-streamed.
    if (displayed.length >= text.length) {
      return;
    }

    const frameMs = isStreaming ? 16 : 12;
    const timer = window.setInterval(() => {
      setDisplayed((prev) => {
        if (prev.length >= text.length) return prev;
        const remaining = text.length - prev.length;
        const step = Math.max(1, Math.min(20, Math.ceil(remaining / 10)));
        return text.slice(0, prev.length + step);
      });
    }, frameMs);

    return () => window.clearInterval(timer);
  }, [text, isStreaming, displayed.length]);

  return displayed;
}

/* ---------- markdown & json renderers ---------- */

function MarkdownContent({ text, className = '' }: { text: string; className?: string }) {
  return (
    <div className={`prose prose-xs dark:prose-invert max-w-none text-xs leading-relaxed
      prose-p:my-0.5 prose-p:leading-relaxed
      prose-headings:font-semibold prose-headings:my-1
      prose-h1:text-sm prose-h2:text-xs prose-h3:text-xs
      prose-ul:my-0.5 prose-ul:pl-4 prose-ol:my-0.5 prose-ol:pl-4
      prose-li:my-0 prose-li:leading-relaxed
      prose-code:text-[11px] prose-code:bg-muted/60 prose-code:px-1 prose-code:py-0.5 prose-code:rounded prose-code:font-mono
      prose-pre:my-1 prose-pre:bg-muted/60 prose-pre:text-[11px]
      prose-strong:font-semibold
      prose-blockquote:border-l-2 prose-blockquote:border-primary/30 prose-blockquote:pl-2 prose-blockquote:italic prose-blockquote:text-foreground/70
      prose-hr:my-1 prose-hr:border-border
      prose-a:text-primary prose-a:underline
      ${className}`}
    >
      <ReactMarkdown remarkPlugins={[remarkGfm]}>{text}</ReactMarkdown>
    </div>
  );
}

type JsonValue = string | number | boolean | null | JsonValue[] | { [key: string]: JsonValue };

function JsonNode({ value, depth = 0 }: { value: JsonValue; depth?: number }) {
  const [collapsed, setCollapsed] = useState(depth > 1);

  if (value === null) return <span className="text-muted-foreground italic">null</span>;
  if (typeof value === 'boolean') return <span className="text-warning font-mono">{value.toString()}</span>;
  if (typeof value === 'number') return <span className="text-blue-500 dark:text-blue-400 font-mono">{value}</span>;
  if (typeof value === 'string') {
    // Truncate very long strings
    const MAX = 200;
    const display = value.length > MAX ? value.slice(0, MAX) + '…' : value;
    return <span className="text-success dark:text-green-400 font-mono break-all">"{display}"</span>;
  }

  if (Array.isArray(value)) {
    if (value.length === 0) return <span className="text-muted-foreground font-mono">[]</span>;
    return (
      <span>
        <button
          type="button"
          onClick={() => setCollapsed(v => !v)}
          className="font-mono text-muted-foreground hover:text-foreground"
        >
          {collapsed ? `[…${value.length}]` : '['}
        </button>
        {!collapsed && (
          <>
            <div className="ml-3 border-l border-border/50 pl-2">
              {value.map((item, i) => (
                <div key={i} className="flex gap-1">
                  <span className="shrink-0 text-muted-foreground/50 font-mono text-[10px] select-none w-4 text-right">{i}</span>
                  <span className="text-muted-foreground font-mono">:</span>
                  <JsonNode value={item as JsonValue} depth={depth + 1} />
                  {i < value.length - 1 && <span className="text-muted-foreground font-mono">,</span>}
                </div>
              ))}
            </div>
            <span className="font-mono text-muted-foreground">]</span>
          </>
        )}
      </span>
    );
  }

  // Object
  const entries = Object.entries(value as Record<string, JsonValue>);
  if (entries.length === 0) return <span className="text-muted-foreground font-mono">{'{}'}</span>;

  return (
    <span>
      <button
        type="button"
        onClick={() => setCollapsed(v => !v)}
        className="font-mono text-muted-foreground hover:text-foreground"
      >
        {collapsed ? `{…${entries.length}}` : '{'}
      </button>
      {!collapsed && (
        <>
          <div className="ml-3 border-l border-border/50 pl-2">
            {entries.map(([k, v], i) => (
              <div key={k} className="flex gap-1 flex-wrap">
                <span className="text-primary/80 font-mono shrink-0">"{k}"</span>
                <span className="text-muted-foreground font-mono">:</span>
                <JsonNode value={v as JsonValue} depth={depth + 1} />
                {i < entries.length - 1 && <span className="text-muted-foreground font-mono">,</span>}
              </div>
            ))}
          </div>
          <span className="font-mono text-muted-foreground">{'}'}</span>
        </>
      )}
    </span>
  );
}

function JsonViewer({ raw }: { raw: string }) {
  const [parseError, setParseError] = useState(false);
  const [parsed, setParsed] = useState<JsonValue | null>(null);

  useEffect(() => {
    try {
      setParsed(JSON.parse(raw));
      setParseError(false);
    } catch {
      setParseError(true);
    }
  }, [raw]);

  if (parseError || parsed === null) {
    return (
      <pre className="max-h-40 overflow-auto rounded bg-muted/50 px-2 py-1 text-[11px] text-foreground/80 whitespace-pre-wrap break-all">
        {raw}
      </pre>
    );
  }

  return (
    <div className="max-h-40 overflow-auto rounded bg-muted/50 px-2 py-1.5 text-[11px] font-mono leading-relaxed">
      <JsonNode value={parsed} depth={0} />
    </div>
  );
}

/* ---------- sub-components ---------- */

function ThinkingBubble({ text, isStreaming = false }: { text: string; isStreaming?: boolean }) {
  const [expanded, setExpanded] = useState(true);
  const smoothText = useSmoothStreamingText(text, isStreaming);
  const preview = truncate(smoothText, 180);
  const needsExpand = !isStreaming && text.length > 180;

  return (
    <div className="flex gap-2 border-l-2 border-primary/30 px-2.5 py-1">
      <Brain className="mt-0.5 h-3.5 w-3.5 shrink-0 text-primary/60" />
      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-1.5">
          <p className="text-[11px] font-medium text-muted-foreground">Thinking</p>
          {isStreaming && <Loader2 className="h-2.5 w-2.5 animate-spin text-primary/40" />}
        </div>
        <div className="mt-0.5 text-foreground/70">
          <MarkdownContent text={expanded || isStreaming ? smoothText : preview} />
          {isStreaming && <span className="inline-block w-1.5 h-3 ml-0.5 bg-primary/40 animate-pulse rounded-sm" />}
        </div>
        {needsExpand && (
          <button
            type="button"
            onClick={() => setExpanded((v) => !v)}
            className="mt-1 text-[10px] font-medium text-primary/70 hover:text-primary"
          >
            {expanded ? 'Show less' : 'Show more'}
          </button>
        )}
      </div>
    </div>
  );
}

function ReasoningBubble({ text, isStreaming = false }: { text: string; isStreaming?: boolean }) {
  const [expanded, setExpanded] = useState(true);
  const smoothText = useSmoothStreamingText(text, isStreaming);
  const preview = truncate(smoothText, 200);
  const needsExpand = !isStreaming && text.length > 200;

  return (
    <div className="flex gap-2 border-l-2 border-border/60 px-2.5 py-1">
      <Lightbulb className="mt-0.5 h-3.5 w-3.5 shrink-0 text-warning" />
      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-1.5">
          <p className="text-[11px] font-medium text-muted-foreground">Planning</p>
          {isStreaming && <Loader2 className="h-2.5 w-2.5 animate-spin text-muted-foreground/50" />}
        </div>
        <div className="mt-0.5 text-foreground/80">
          <MarkdownContent text={expanded || isStreaming ? smoothText : preview} />
          {isStreaming && <span className="inline-block w-1.5 h-3 ml-0.5 bg-foreground/30 animate-pulse rounded-sm" />}
        </div>
        {needsExpand && (
          <button
            type="button"
            onClick={() => setExpanded((v) => !v)}
            className="mt-1 text-[10px] font-medium text-muted-foreground hover:text-foreground"
          >
            {expanded ? 'Show less' : 'Show more'}
          </button>
        )}
      </div>
    </div>
  );
}

function ToolCallCard({ step }: { step: MergedToolStep }) {
  const [expanded, setExpanded] = useState(false);
  const Icon = getToolIcon(step.toolName);
  const detailsId = `tool-step-${toDomId(step.key)}-details`;
  const args = step.callEvent?.metadata?.arguments as Record<string, unknown> | undefined;
  const output = step.errorEvent?.output || step.resultEvent?.output;
  const formattedOutput = tryFormatJson(output);
  const errorMessage = step.errorEvent?.message;
  const hasDetails = args || formattedOutput || output || errorMessage;
  const isError = !!step.errorEvent;
  const isDone = !!step.resultEvent || !!step.errorEvent;

  const displayMsg = step.callEvent?.display_message
    || step.callEvent?.message
    || step.resultEvent?.display_message
    || step.resultEvent?.message
    || step.errorEvent?.display_message
    || step.errorEvent?.message
    || (step.toolName ? `Using ${step.toolName}` : 'Tool event');

  return (
    <div
      className={`rounded-md border px-2.5 py-1.5 ${
        isError
          ? 'border-destructive/30 bg-destructive/5'
          : 'border-border/50 bg-background/50'
      }`}
    >
      <div className="flex items-center gap-2">
        <Icon className={`h-3.5 w-3.5 shrink-0 ${isError ? 'text-destructive' : 'text-muted-foreground'}`} />
        <span className="flex-1 text-xs leading-relaxed text-foreground">{displayMsg}</span>
        <span
          className={`inline-flex items-center rounded-full px-1.5 py-0.5 text-[9px] font-medium ${
            isError
              ? 'bg-destructive/10 text-destructive'
              : isDone
                ? 'bg-success/10 text-success'
                : 'bg-muted text-muted-foreground'
          }`}
        >
          {isError ? 'Failed' : isDone ? 'Done' : 'Running'}
        </span>
        {hasDetails && (
          <button
            type="button"
            onClick={() => setExpanded((v) => !v)}
            aria-label={expanded ? 'Collapse step details' : 'Expand step details'}
            aria-expanded={expanded}
            aria-controls={detailsId}
            className="shrink-0 rounded p-0.5 text-muted-foreground hover:bg-accent hover:text-foreground"
          >
            {expanded ? <ChevronDown className="h-3 w-3" /> : <ChevronRight className="h-3 w-3" />}
          </button>
        )}
      </div>
      {expanded && hasDetails && (
        <div id={detailsId} className="mt-2 space-y-1.5 border-t border-border/50 pt-2">
          {args && Object.keys(args).length > 0 && (
            <div>
              <p className="text-[10px] font-medium text-muted-foreground">Arguments</p>
              <div className="mt-0.5">
                <JsonViewer raw={JSON.stringify(args)} />
              </div>
            </div>
          )}
          {formattedOutput && (
            <div>
              <p className="text-[10px] font-medium text-muted-foreground">Output</p>
              <div className="mt-0.5">
                <JsonViewer raw={formattedOutput} />
              </div>
            </div>
          )}
          {!formattedOutput && output && (
            <div>
              <p className="text-[10px] font-medium text-muted-foreground">Output</p>
              <pre className="max-h-40 overflow-auto rounded bg-muted/50 px-2 py-1 text-[11px] text-foreground/80 whitespace-pre-wrap break-all">
                {output}
              </pre>
            </div>
          )}
          {errorMessage && (
            <div>
              <p className="text-[10px] font-medium text-muted-foreground">Error</p>
              <p className="mt-0.5 text-[11px] text-destructive">{errorMessage}</p>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function GenericEvent({ event, type }: { event: AgentEvent; type: string }) {
  const isError = type.includes('error') || type.includes('fail');
  const isFinalized = type.includes('finalized') || type.includes('done') || type.includes('complete');
  const Icon = isFinalized ? Sparkles : isError ? AlertTriangle : Bot;

  const displayMsg = event.display_message || event.message || type.replaceAll('_', ' ');

  return (
    <div
      className={`flex items-center gap-2 px-2.5 py-1.5 ${
        isFinalized
          ? 'border-l-2 border-success/40 bg-success/5'
          : isError
            ? 'border-l-2 border-destructive/40 bg-destructive/5'
            : 'border-l-2 border-border/60 bg-background/40'
      }`}
    >
      <Icon
        className={`h-3.5 w-3.5 shrink-0 ${
          isFinalized ? 'text-success' : isError ? 'text-destructive' : 'text-muted-foreground'
        }`}
      />
      <span className="text-xs leading-relaxed text-foreground">{displayMsg}</span>
    </div>
  );
}

function IterationSection({ group, isLatest }: { group: IterationGroup; isLatest: boolean }) {
  const [collapsed, setCollapsed] = useState(false);
  const hasFinalized = group.events.some((e) => e.type === 'finalized');
  const contentId = `iteration-${group.iteration}-content`;
  const renderItems = useMemo(() => mergeToolEvents(group.events), [group.events]);

  return (
    <div className={`${isLatest ? 'animate-in fade-in-0 duration-300' : ''}`}>
      <div id={contentId} className="space-y-1.5">
        {renderItems.map((item, idx) => {
          if (item.kind === 'tool_step') {
            return <ToolCallCard key={item.step.key || idx} step={item.step} />;
          }

          const { event, type, key } = item;
          if (type === 'iteration_started') return null;
          if (type === 'thinking') {
            const streaming = !!(event.metadata?.isStreaming);
            return <ThinkingBubble key={key} text={event.message ?? ''} isStreaming={streaming} />;
          }
          if (type === 'reasoning') {
            const streaming = !!(event.metadata?.isStreaming);
            return <ReasoningBubble key={key} text={event.message ?? ''} isStreaming={streaming} />;
          }
          return <GenericEvent key={key} event={event} type={type} />;
        })}
      </div>
    </div>
  );
}

/* ---------- main component ---------- */

export function AgentLoopTimeline({
  events,
  isLoading = false,
  isError = false,
  connectionState = 'idle',
}: AgentLoopTimelineProps) {
  const scrollRef = useRef<HTMLDivElement>(null);
  const prevLenRef = useRef(0);

  // Auto-scroll on new events (length change covers both new events and delta accumulation
  // since the parent re-renders on each SSE message)
  useEffect(() => {
    if (events.length > prevLenRef.current && scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
    prevLenRef.current = events.length;
  }, [events.length]);

  // Also auto-scroll during streaming (events array identity changes on each delta)
  useEffect(() => {
    if (scrollRef.current) {
      const el = scrollRef.current;
      const isNearBottom = el.scrollHeight - el.scrollTop - el.clientHeight < 60;
      if (isNearBottom) {
        el.scrollTop = el.scrollHeight;
      }
    }
  }, [events]);

  const { groups, ungrouped } = useMemo(() => groupByIteration(events), [events]);

  if (isError) {
    return (
      <div className="rounded-lg border border-warning/30 bg-warning/10 px-3 py-2 text-xs text-warning">
        Agent event stream unavailable right now.
      </div>
    );
  }

  if (isLoading && events.length === 0) {
    return (
      <div className="flex items-center gap-2 rounded-lg border border-border bg-muted/30 px-3 py-2 text-xs text-muted-foreground">
        <Loader2 className="h-3.5 w-3.5 animate-spin" />
        Loading agent events...
      </div>
    );
  }

  if (events.length === 0) {
    return (
      <div className="flex items-center gap-2 rounded-lg border border-border bg-muted/30 px-3 py-2 text-xs text-muted-foreground">
        <Bot className="h-3.5 w-3.5" />
        Waiting for agent to start...
      </div>
    );
  }

  const isActive = connectionState === 'live' || connectionState === 'connecting';

  return (
    <div
      ref={scrollRef}
      className="max-h-72 space-y-2.5 overflow-y-auto rounded-lg"
    >
      {connectionState === 'fallback' && (
        <div className="rounded-md border border-warning/20 bg-warning/5 px-2.5 py-1.5 text-[11px] text-warning">
          Live stream unavailable, using polling.
        </div>
      )}

      {/* Iteration groups */}
      {groups.map((group, idx) => (
        <IterationSection
          key={group.iteration}
          group={group}
          isLatest={idx === groups.length - 1}
        />
      ))}

      {/* Loop ended */}
      {ungrouped
        .filter(({ type }) => type === 'loop_ended')
        .map(({ event, type }, idx) => (
          <GenericEvent key={event.id ?? `end-${idx}`} event={event} type={type} />
        ))}
    </div>
  );
}
