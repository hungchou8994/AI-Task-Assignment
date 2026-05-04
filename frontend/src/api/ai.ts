import type { AgentEvent, AgentEventsResponse, ExtractJobQueued, ExtractJobStatus, ExtractTasksRequest } from '../types';
import { api } from './client';

export const startExtraction = (data: ExtractTasksRequest) =>
  api.post<ExtractJobQueued>('/api/ai/extract-tasks', data);

export const getExtractionJob = (jobId: string) =>
  api.get<ExtractJobStatus>(`/api/ai/jobs/${jobId}`);

export const getAgentEvents = async (jobId: string): Promise<AgentEventsResponse> => {
  const response = await api.get<AgentEventsResponse | unknown[]>(`/api/ai/jobs/${jobId}/events`);
  if (Array.isArray(response)) {
    return { events: response as AgentEvent[] };
  }
  if (response && typeof response === 'object' && 'events' in response) {
    const events = (response as AgentEventsResponse).events;
    return { events: Array.isArray(events) ? events : [] };
  }
  return { events: [] };
};
