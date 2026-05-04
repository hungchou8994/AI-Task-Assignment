import { useQuery } from '@tanstack/react-query';
import { fetchFeedbackAnalytics } from '../api/feedbackAnalytics';
import type { FeedbackPeriod } from '../types';

export function useFeedbackAnalytics(projectId: string | null, period: FeedbackPeriod) {
  return useQuery({
    queryKey: ['feedback-analytics', projectId, period],
    queryFn: () => fetchFeedbackAnalytics(projectId!, period),
    enabled: !!projectId,
    staleTime: 30_000,
  });
}
