import { useCallback, useEffect, useRef, useState } from 'react';
import type { ExtractJobStatus, ExtractTasksRequest, JobEntry } from '../types';
import { getExtractionJob, startExtraction } from '../api/ai';

const STORAGE_KEY = 'ai_extraction_jobs';

function loadJobIds(projectId: string): string[] {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return [];
    const parsed: Record<string, string[]> = JSON.parse(raw);
    return parsed[projectId] ?? [];
  } catch {
    return [];
  }
}

function saveJobIds(projectId: string, ids: string[]) {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    const parsed: Record<string, string[]> = raw ? JSON.parse(raw) : {};
    parsed[projectId] = ids;
    localStorage.setItem(STORAGE_KEY, JSON.stringify(parsed));
  } catch {
    // storage full or unavailable — degrade gracefully
  }
}

function removeJobId(projectId: string, jobId: string) {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return;
    const parsed: Record<string, string[]> = JSON.parse(raw);
    parsed[projectId] = (parsed[projectId] ?? []).filter((id) => id !== jobId);
    if (parsed[projectId].length === 0) delete parsed[projectId];
    localStorage.setItem(STORAGE_KEY, JSON.stringify(parsed));
  } catch {
    // degrade gracefully
  }
}

export function useExtractionJobs(projectId: string | null) {
  const [jobs, setJobs] = useState<JobEntry[]>([]);
  const fetchedRef = useRef<Set<string>>(new Set());

  // Load job IDs from localStorage on mount / projectId change
  useEffect(() => {
    if (!projectId) {
      setJobs([]);
      return;
    }

    const ids = loadJobIds(projectId);
    if (ids.length === 0) {
      setJobs([]);
      return;
    }

    // Verify all jobs exist on the backend immediately.
    // This evicts stale IDs (e.g., from a backend restart) before any
    // SSE/polling machinery starts, preventing infinite 404 storms.
    let cancelled = false;

    void Promise.all(
      ids.map(async (jobId) => {
        try {
          const response: ExtractJobStatus = await getExtractionJob(jobId);
          return { jobId, entry: response };
        } catch {
          // 404 or network error — job is gone
          return { jobId, entry: null };
        }
      }),
    ).then((results) => {
      if (cancelled) return;

      const valid: JobEntry[] = [];
      const stale: string[] = [];

      for (const { jobId, entry } of results) {
        if (entry) {
          valid.push({
            jobId,
            status: entry.status as JobEntry['status'],
            result: entry.result,
            error: entry.error,
            attempts: entry.attempts,
          });
        } else {
          stale.push(jobId);
        }
      }

      // Evict stale jobs from localStorage
      stale.forEach((id) => removeJobId(projectId, id));

      setJobs(valid);
      fetchedRef.current.clear();
    });

    return () => {
      cancelled = true;
    };
  }, [projectId]);

  const fetchJobStatus = useCallback(async (jobId: string) => {
    if (fetchedRef.current.has(jobId)) return;
    fetchedRef.current.add(jobId);

    try {
      const response: ExtractJobStatus = await getExtractionJob(jobId);
      const { status, result, error, attempts } = response;

      setJobs((prev) =>
        prev.map((job) =>
          job.jobId === jobId
            ? { jobId, status, result, error, attempts }
            : job
        )
      );
    } catch (err) {
      if (err instanceof Error && err.message.startsWith('404:')) {
        // Job evicted from backend — remove from view and storage
        setJobs((prev) => prev.filter((job) => job.jobId !== jobId));
        if (projectId) removeJobId(projectId, jobId);
      }
      // other errors — leave the job as-is
    }
  }, [projectId]);

  const submitJob = useCallback(
    async (request: ExtractTasksRequest) => {
      if (!projectId) return;

      const response = await startExtraction(request);
      const jobId = response.job_id;

      // Persist to localStorage
      const ids = loadJobIds(projectId);
      saveJobIds(projectId, [...ids, jobId]);

      // Add to state
      setJobs((prev) => [{ jobId, status: 'queued' as const }, ...prev]);
      fetchedRef.current.delete(jobId);
    },
    [projectId]
  );

  const removeJob = useCallback(
    (jobId: string) => {
      if (!projectId) return;
      fetchedRef.current.delete(jobId);
      setJobs((prev) => prev.filter((job) => job.jobId !== jobId));
      if (projectId) removeJobId(projectId, jobId);
    },
    [projectId]
  );

  // Return newest-first
  const sortedJobs = [...jobs].sort((a, b) => {
    const aIdx = jobs.indexOf(a);
    const bIdx = jobs.indexOf(b);
    return bIdx - aIdx;
  });

  return { jobs: sortedJobs, submitJob, removeJob, fetchJobStatus };
}
