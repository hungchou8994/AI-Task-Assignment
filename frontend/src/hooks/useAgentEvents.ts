import { useEffect, useMemo, useRef, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { getAgentEvents } from '../api/ai';

export function useAgentEvents(jobId: string | null, enabled: boolean) {
  const [shouldPoll, setShouldPoll] = useState(true);
  const prevJobId = useRef(jobId);

  // Reset the error gate when the job changes
  useEffect(() => {
    if (prevJobId.current !== jobId) {
      prevJobId.current = jobId;
      setShouldPoll(true);
    }
  }, [jobId]);

  const query = useQuery({
    queryKey: ['agent-events', jobId],
    queryFn: () => getAgentEvents(jobId as string),
    enabled: enabled && !!jobId && shouldPoll,
    refetchInterval: enabled ? 1500 : false,
    staleTime: 1000,
    retry: (failureCount, err) => {
      // 404 means the job is gone — never retry
      if (err && typeof err === 'object' && 'message' in err && String((err as { message: string }).message).startsWith('404')) {
        return false;
      }
      return failureCount < 2;
    },
  });

  // If the query errored (any error), stop polling permanently
  useEffect(() => {
    if (query.error) {
      setShouldPoll(false);
    }
  }, [query.error]);

  const events = useMemo(() => {
    const value = query.data?.events;
    return Array.isArray(value) ? value : [];
  }, [query.data]);

  return {
    events,
    isLoading: query.isLoading,
    isError: query.isError,
    error: query.error,
  };
}
