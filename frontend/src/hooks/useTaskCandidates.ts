import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import type { BatchCandidateActionRequest, TaskCandidatePatch, TaskCandidateStatus } from '../types';
import {
  approveTaskCandidate,
  batchApproveTaskCandidates,
  batchRejectTaskCandidates,
  fetchTaskCandidates,
  patchTaskCandidate,
  rejectTaskCandidate,
  rerunTaskCandidate,
  undoRejectTaskCandidate,
} from '../api/taskCandidates';

export const TASK_CANDIDATES_KEY = ['task-candidates'] as const;

function candidateQueryKey(projectId: string | null, status: TaskCandidateStatus) {
  return [...TASK_CANDIDATES_KEY, projectId, status] as const;
}

export function useTaskCandidates(projectId: string | null, status: TaskCandidateStatus = 'pending') {
  return useQuery({
    queryKey: candidateQueryKey(projectId, status),
    queryFn: () => fetchTaskCandidates(projectId!, status),
    enabled: !!projectId,
    staleTime: 15_000,
  });
}

export function usePatchTaskCandidate(projectId: string | null) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: TaskCandidatePatch }) =>
      patchTaskCandidate(id, data),
    onSuccess: () => qc.invalidateQueries({ queryKey: [...TASK_CANDIDATES_KEY, projectId] }),
  });
}

export function useApproveCandidate(projectId: string | null) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (candidateId: string) => approveTaskCandidate(candidateId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: [...TASK_CANDIDATES_KEY, projectId] });
      qc.invalidateQueries({ queryKey: ['tasks'] });
    },
  });
}

export function useRejectCandidate(projectId: string | null) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (candidateId: string) => rejectTaskCandidate(candidateId),
    onSuccess: () => qc.invalidateQueries({ queryKey: [...TASK_CANDIDATES_KEY, projectId] }),
  });
}

export function useUndoReject(projectId: string | null) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (candidateId: string) => undoRejectTaskCandidate(candidateId),
    onSuccess: () => qc.invalidateQueries({ queryKey: [...TASK_CANDIDATES_KEY, projectId] }),
  });
}

export function useRerunCandidate(projectId: string | null) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (candidateId: string) => rerunTaskCandidate(candidateId),
    onSuccess: () => qc.invalidateQueries({ queryKey: [...TASK_CANDIDATES_KEY, projectId] }),
  });
}

export function useBatchApproveCandidates(projectId: string | null) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: BatchCandidateActionRequest) => batchApproveTaskCandidates(data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: [...TASK_CANDIDATES_KEY, projectId] });
      qc.invalidateQueries({ queryKey: ['tasks'] });
    },
  });
}

export function useBatchRejectCandidates(projectId: string | null) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: BatchCandidateActionRequest) => batchRejectTaskCandidates(data),
    onSuccess: () => qc.invalidateQueries({ queryKey: [...TASK_CANDIDATES_KEY, projectId] }),
  });
}
