import { api } from './client';
import type {
  ApproveCandidateResponse,
  BatchCandidateActionResponse,
  BatchCandidateActionRequest,
  RejectCandidateResponse,
  RerunCandidateResponse,
  TaskCandidate,
  TaskCandidatePatch,
  TaskCandidateStatus,
  UndoRejectResponse,
} from '../types';

export const fetchTaskCandidates = (projectId: string, status: TaskCandidateStatus = 'pending') =>
  api.get<TaskCandidate[]>(`/api/task-candidates?project_id=${projectId}&status=${status}`);

export const patchTaskCandidate = (candidateId: string, data: TaskCandidatePatch) =>
  api.patch<TaskCandidate>(`/api/task-candidates/${candidateId}`, data);

export const approveTaskCandidate = (candidateId: string) =>
  api.post<ApproveCandidateResponse>(`/api/task-candidates/${candidateId}/approve`, {});

export const rejectTaskCandidate = (candidateId: string) =>
  api.post<RejectCandidateResponse>(`/api/task-candidates/${candidateId}/reject`, {});

export const undoRejectTaskCandidate = (candidateId: string) =>
  api.post<UndoRejectResponse>(`/api/task-candidates/${candidateId}/undo-reject`, {});

export const rerunTaskCandidate = (candidateId: string) =>
  api.post<RerunCandidateResponse>(`/api/task-candidates/${candidateId}/rerun`, {});

export const batchApproveTaskCandidates = (data: BatchCandidateActionRequest) =>
  api.post<BatchCandidateActionResponse>('/api/task-candidates/batch-approve', data);

export const batchRejectTaskCandidates = (data: BatchCandidateActionRequest) =>
  api.post<BatchCandidateActionResponse>('/api/task-candidates/batch-reject', data);
