import { useQuery } from '@tanstack/react-query';
import { fetchDashboardSummary, fetchDashboardAnalytics, type DashboardPeriod } from '@/lib/api';
import type { DashboardSummary, RawDashboardSummary } from '@/types';

// Reshape raw backend summary response into the DashboardSummary shape used by components.
function transformDashboardSummary(data: RawDashboardSummary): DashboardSummary {
  const email_types = Object.entries(data.emails_by_type || {}).map(([type, count]) => ({
    type: type as DashboardSummary['email_types'][number]['type'],
    count: Number(count),
    percentage: 0, // TODO: backend does not provide percentage; compute or remove this field
  }));

  const top_assignees = (data.top_assignees || []).map((a) => ({
    employee_id: 'unknown', // TODO: backend /dashboard/summary does not return employee_id yet
    employee_name: a.name,
    assignment_count: a.count,
    completed: a.completed,
    pending: a.pending,
    level: 'general' as const, // TODO: backend /dashboard/summary does not return level yet
  }));

  return {
    todays_emails: data.total_emails || 0,
    pending_count: data.pending_assignments || 0,
    // NOTE: "assigned" email status is used as a proxy for "completed today" — this is a known
    // approximation; no dedicated "completed" email status exists on the backend.
    completed_today: data.emails_by_status?.assigned ?? 0,
    email_types,
    top_assignees,
  };
}

// Dashboard Summary
export function useDashboardSummary() {
  return useQuery({
    queryKey: ['dashboard-summary'],
    queryFn: fetchDashboardSummary,
    select: transformDashboardSummary,
    refetchInterval: 30000, // Real-time: refresh every 30s
  });
}

// Dashboard Analytics (Phase 4)
export function useDashboardAnalytics(period: DashboardPeriod) {
  return useQuery({
    queryKey: ['dashboard-analytics', period],
    queryFn: () => fetchDashboardAnalytics(period),
    staleTime: 60_000,  // analytics data doesn't need sub-minute freshness
  });
}
