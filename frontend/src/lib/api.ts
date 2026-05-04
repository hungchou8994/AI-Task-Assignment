import { api } from '@/api/client';
import type {
  AssignmentWithDetails,
  RawDashboardSummary,
  DashboardAnalytics,
  Employee,
  Email,
  EmailDetailData,
  PaginatedAssignments,
  NLRule,
  CreateNLRulePayload,
  UpdateNLRulePayload,
} from '@/types';

export type DashboardPeriod = 'day' | 'week' | 'month';

export const fetchDashboardSummary = (): Promise<RawDashboardSummary> =>
  api.get('/api/assignments/dashboard/summary');

export const fetchDashboardAnalytics = (period: DashboardPeriod): Promise<DashboardAnalytics> =>
  api.get(`/api/assignments/dashboard/analytics?period=${period}`);

export async function fetchAssignments(
  assignmentStatuses: string[] = [],
  emailStatuses: string[] = [],
  page = 1,
  limit = 10,
  employeeIds: string[] = [],
  emailTypes: string[] = [],
  needsReview = false,
): Promise<PaginatedAssignments> {
  const params = new URLSearchParams({ page: String(page), limit: String(limit) });
  assignmentStatuses.forEach((s) => params.append('assignment_status', s));
  emailStatuses.forEach((s) => params.append('email_status', s));
  employeeIds.forEach((id) => params.append('employee_id', id));
  emailTypes.forEach((t) => params.append('email_type', t));
  if (needsReview) params.append('needs_review', 'true');
  return api.get(`/api/assignments?${params}`);
}

export const fetchEmployees = (): Promise<Employee[]> => api.get('/api/employees');

export const processBatch = (): Promise<{
  status?: string;
  processed?: number;
  assigned_count?: number;
  ingested_count?: number;
  analyzed_count?: number;
  message?: string;
}> => api.post('/api/assignments/process-batch', {});

export const fetchRules = (includeInactive = true): Promise<NLRule[]> =>
  api.get(`/api/rules?include_inactive=${includeInactive}`);

export const createRule = (rule: CreateNLRulePayload): Promise<NLRule> =>
  api.post('/api/rules', rule);

export const updateRule = (id: string, rule: UpdateNLRulePayload): Promise<NLRule> =>
  api.patch(`/api/rules/${id}`, rule);

export const deleteRule = (id: string): Promise<void> => api.delete(`/api/rules/${id}`);

export const fetchEmailDetail = (id: string): Promise<EmailDetailData> =>
  api.get(`/api/emails/${id}`);

export const fetchEmailThread = (emailId: string): Promise<EmailDetailData[]> =>
  api.get(`/api/emails/${emailId}/thread`);

export const ingestEmails = (): Promise<{ ingested: number; message: string }> =>
  api.post('/api/emails/ingest', {});

export const submitManualEmail = (formData: FormData): Promise<Email> =>
  api.postForm('/api/emails/manual', formData);

export const markAssignmentAsCompleted = (
  id: string,
): Promise<{ status: string; message: string }> =>
  api.patch(`/api/assignments/${id}/complete`, {});

export interface BulkCompleteResponse {
  completed_count: number;
  skipped_count: number;
  skipped_ids: string[];
}

export const bulkCompleteAssignments = (ids: string[]): Promise<BulkCompleteResponse> =>
  api.post('/api/assignments/bulk-complete', { assignment_ids: ids });

export const reassignAssignment = (
  assignmentId: string,
  employeeId: string,
  reason: string,
  force = false,
): Promise<{ status: string; message: string; new_assignment_id: string }> =>
  api.post(`/api/assignments/${assignmentId}/reassign`, { employee_id: employeeId, reason, force });

export const processEmail = (
  assignmentId: string,
): Promise<{
  status: string;
  message: string;
  old_assignment_id: string | null;
  new_assignment_id: string | null;
  email_id: string;
  reason?: string;
}> => api.post(`/api/assignments/${assignmentId}/process`, {});

export interface Alert {
  type: string;
  count: number;
  message: string;
  severity: 'info' | 'warning' | 'error';
}

export interface AlertStatus {
  has_alerts: boolean;
  alert_count: number;
  alerts: Alert[];
}

export const fetchAlertStatus = (): Promise<AlertStatus> => api.get('/api/alerts/status');

export interface SystemConfig {
  imap_username: string;
}

export const fetchSystemConfig = (): Promise<SystemConfig> => api.get('/api/system/config');

export interface AvailabilityToggleRequest {
  is_available: boolean;
  reason?: string;
}

export interface AvailabilityToggleResponse {
  employee_id: string;
  date: string;
  is_available: boolean;
  reason?: string;
  message: string;
}

export const toggleEmployeeAvailability = (
  employeeId: string,
  request: AvailabilityToggleRequest,
): Promise<AvailabilityToggleResponse> =>
  api.post(`/api/employees/${employeeId}/availability`, request);
