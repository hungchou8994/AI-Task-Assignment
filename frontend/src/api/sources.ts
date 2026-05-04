import { Source } from '../types';
import { api } from './client';

export const fetchProjectSources = (projectId: string) =>
  api.get<Source[]>(`/api/projects/${projectId}/sources`);

export const fetchSource = (id: string) => api.get<Source>(`/api/sources/${id}`);
