import { useEffect, useMemo, useRef, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { getAgentEvents } from '../api/ai';
import type { AgentEvent } from '../types';
import { useAgentEvents } from './useAgentEvents';

type StreamTransport = 'idle' | 'sse' | 'polling';
type StreamConnectionState = 'idle' | 'connecting' | 'live' | 'fallback';

interface UseJobEventStreamResult {
  events: AgentEvent[];
  isLoading: boolean;
  isError: boolean;
  transport: StreamTransport;
  connectionState: StreamConnectionState;
}

function isAgentEvent(value: unknown): value is AgentEvent {
  return typeof value === 'object' && value !== null;
}

function parseSsePayload(raw: string): AgentEvent[] {
  if (!raw) return [];

  try {
    const payload = JSON.parse(raw) as unknown;
    if (Array.isArray(payload)) return payload.filter(isAgentEvent);
    if (payload && typeof payload === 'object') {
      if ('events' in payload) {
        const events = (payload as { events?: unknown }).events;
        return Array.isArray(events) ? events.filter(isAgentEvent) : [];
      }
      return [payload as AgentEvent];
    }
  } catch {
    return [{ message: raw, event_type: 'message' }];
  }

  return [];
}

function mergeEvents(base: AgentEvent[], incoming: AgentEvent[]): AgentEvent[] {
  if (incoming.length === 0) return base;

  const merged = [...base];
  const seen = new Set(
    base.map((event, index) => event.id || `${event.timestamp || event.created_at || 'unknown'}:${event.event_type || event.type || 'event'}:${index}`)
  );

  incoming.forEach((event, index) => {
    const key = event.id || `${event.timestamp || event.created_at || 'unknown'}:${event.event_type || event.type || 'event'}:${event.message || event.output || index}`;
    if (!seen.has(key)) {
      seen.add(key);
      merged.push(event);
    }
  });

  return merged;
}

export function useJobEventStream(jobId: string | null, enabled: boolean): UseJobEventStreamResult {
  const [streamEvents, setStreamEvents] = useState<AgentEvent[]>([]);
  const [transport, setTransport] = useState<StreamTransport>('idle');
  const [connectionState, setConnectionState] = useState<StreamConnectionState>('idle');
  const [sseFailed, setSseFailed] = useState(false);
  const sourceRef = useRef<EventSource | null>(null);

  const snapshotQuery = useQuery({
    queryKey: ['agent-events', jobId, 'snapshot'],
    queryFn: () => getAgentEvents(jobId as string),
    enabled: enabled && !!jobId,
    staleTime: 1000,
    retry: false,
  });

  const polling = useAgentEvents(jobId, enabled && !!jobId && sseFailed);

  // Seed streamEvents from the snapshot when it first arrives.
  // Use a ref to track whether the snapshot has already been seeded
  // so this only fires once per jobId, not on every re-render.
  const snapshotSeededRef = useRef(false);

  useEffect(() => {
    // Reset the seeded flag whenever the job changes or stream is disabled
    snapshotSeededRef.current = false;
  }, [enabled, jobId]);

  useEffect(() => {
    if (snapshotSeededRef.current) return;
    const seedEvents = snapshotQuery.data?.events;
    if (Array.isArray(seedEvents) && seedEvents.length > 0) {
      snapshotSeededRef.current = true;
      setStreamEvents((prev) => mergeEvents(prev, seedEvents));
    }
  }, [snapshotQuery.data]);

  // Reset all state when disabled or jobId changes
  useEffect(() => {
    if (!enabled || !jobId) {
      sourceRef.current?.close();
      sourceRef.current = null;
      setStreamEvents([]);
      setTransport('idle');
      setConnectionState('idle');
      setSseFailed(false);
    }
  }, [enabled, jobId]);

  useEffect(() => {
    if (!enabled || !jobId || sseFailed) return;

    setTransport('sse');
    setConnectionState('connecting');

    let hasOpened = false;
    const source = new EventSource(`/api/ai/jobs/${jobId}/events/stream`, { withCredentials: true });
    sourceRef.current = source;

    const promoteToFallback = () => {
      if (sourceRef.current !== source) return;
      source.close();
      sourceRef.current = null;
      setSseFailed(true);
      setTransport('polling');
      setConnectionState('fallback');
    };

    const connectionGuard = window.setTimeout(() => {
      if (!hasOpened) {
        promoteToFallback();
      }
    }, 3000);

    const handleMessage = (event: MessageEvent<string>) => {
      const parsed = parseSsePayload(event.data);
      if (parsed.length === 0) return;

      // Filter out internal control events before storing
      const displayEvents = parsed.filter(
        (e) => e.event_type !== 'heartbeat' && e.event_type !== 'job_terminal'
      );
      if (displayEvents.length > 0) {
        setStreamEvents((prev) => mergeEvents(prev, displayEvents));
      }

      // Close the connection cleanly when the job reaches a terminal state
      const isTerminal = parsed.some((e) => e.event_type === 'job_terminal');
      if (isTerminal) {
        window.clearTimeout(connectionGuard);
        source.close();
        sourceRef.current = null;
        setTransport('idle');
        setConnectionState('idle');
      }
    };

    let errorCount = 0;

    source.onopen = () => {
      hasOpened = true;
      errorCount = 0;
      setConnectionState('live');
      window.clearTimeout(connectionGuard);
    };

    source.onmessage = handleMessage;
    source.onerror = () => {
      errorCount += 1;
      if (!hasOpened) {
        // Never connected — fall back immediately
        promoteToFallback();
      } else if (source.readyState === EventSource.CLOSED) {
        // Connection was closed after being live — fall back
        promoteToFallback();
      } else if (errorCount >= 3) {
        // Repeated reconnect attempts after a successful open — fall back
        promoteToFallback();
      }
    };

    return () => {
      window.clearTimeout(connectionGuard);
      source.close();
      if (sourceRef.current === source) {
        sourceRef.current = null;
      }
    };
  }, [enabled, jobId, sseFailed]);

  const events = useMemo(() => {
    if (sseFailed) {
      return mergeEvents(streamEvents, polling.events);
    }
    return streamEvents;
  }, [sseFailed, streamEvents, polling.events]);

  const isLoading = (snapshotQuery.isLoading && events.length === 0) || (sseFailed && polling.isLoading && events.length === 0);
  const isError = sseFailed && polling.isError && events.length === 0;

  return {
    events,
    isLoading,
    isError,
    transport,
    connectionState,
  };
}
