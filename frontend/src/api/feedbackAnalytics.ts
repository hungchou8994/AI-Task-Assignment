import { api } from './client';
import type { FeedbackAnalyticsResponse, FeedbackPeriod } from '../types';

export const fetchFeedbackAnalytics = (projectId: string, period: FeedbackPeriod) =>
  api.get<FeedbackAnalyticsResponse>(
    `/api/feedback-analytics?project_id=${projectId}&period=${period}`,
  );
