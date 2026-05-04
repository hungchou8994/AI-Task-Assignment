export type TaskStatus = 'todo' | 'in_progress' | 'done';
export type TaskPriority = 'low' | 'medium' | 'high';
export type AvailabilityStatus = 'available' | 'busy' | 'on_leave';
export type TaskActivityAction = 'task_created' | 'status_changed' | 'assignment_changed' | 'field_changed';

export interface User {
  id: string;
  email: string;
  created_at: string;
}

export interface UserAuthPayload {
  email: string;
  password: string;
}

export interface Workspace {
  id: string;
  name: string;
  description: string | null;
  created_at: string;
  updated_at: string;
}

export interface Project {
  id: string;
  name: string;
  description: string | null;
  workspace_id: string;
  created_at: string;
  updated_at: string;
}

export interface WorkspaceCreate {
  name: string;
  description?: string | null;
}

export interface ProjectCreate {
  name: string;
  description?: string | null;
}

export interface Source {
  id: string;
  workspace_id: string;
  project_id: string | null;
  source_type: 'text' | 'url' | 'email';
  title: string | null;
  uri: string | null;
  content_hash: string | null;
  summary: string | null;
  excerpt: string | null;
  payload: Record<string, any> | null;
  created_by_user_id: string | null;
  created_at: string;
}

export interface TaskSourceLink {
  task_id: string;
  source_id: string;
  link_type: string;
  confidence_score: number | null;
  created_at: string;
  source?: Source;
}

export interface Task {
  id: string;
  title: string;
  description: string | null;
  status: TaskStatus;
  priority: TaskPriority;
  due_date: string | null; // "YYYY-MM-DD"
  assignee_id: string | null;
  project_id: string;
  needs_review: boolean;
  created_at: string;
  updated_at: string;
  sources?: Source[];
}

export interface TaskActivityEvent {
  id: string;
  task_id: string;
  project_id: string;
  action_type: TaskActivityAction;
  field_name: string | null;
  before_value: unknown;
  after_value: unknown;
  event_metadata: Record<string, unknown>;
  actor_type: string;
  actor_label: string | null;
  actor_id: string | null;
  occurred_at: string;
  created_at: string;
}

export interface Person {
  id: string;
  name: string;
  email: string | null;
  role: string | null;
  skills: string[] | null;
  bio: string | null;
  availability: AvailabilityStatus | null;
  created_at: string;
}

export interface TaskCreate {
  title: string;
  project_id: string;
  description?: string | null;
  status?: TaskStatus;
  priority?: TaskPriority;
  due_date?: string | null;
  assignee_id?: string | null;
  needs_review?: boolean;
}

export interface TaskAssigneeRecommendationsResponse {
  recommendations: AssigneeRecommendation[];
}

export interface TaskUpdate {
  title?: string;
  description?: string | null;
  status?: TaskStatus;
  priority?: TaskPriority;
  due_date?: string | null;
  assignee_id?: string | null;
}

export interface PersonCreate {
  name: string;
  email?: string | null;
  role?: string | null;
  skills?: string[] | null;
  bio?: string | null;
  availability?: AvailabilityStatus | null;
}

export interface PersonUpdate {
  name?: string;
  email?: string | null;
  role?: string | null;
  skills?: string[] | null;
  bio?: string | null;
  availability?: AvailabilityStatus | null;
}

export type TaskCandidateStatus = 'pending' | 'approved' | 'rejected';

export interface ScoreBreakdown {
  final_score: number;
  skill_match: number;
  domain_familiarity: number;
  project_familiarity: number;
  similar_task_success: number;
  workload_score: number;
  urgency_alignment: number;
  explicit_mention: number;
  historical_acceptance_prior: number;
  override_risk: number;
  historical_ownership: number;
  completion_quality: number;
  reassignment_risk: number;
  collaboration_affinity: number;
  team_preference_prior: number;
}

export interface AssigneeRecommendation {
  rank: 1 | 2 | 3;
  person_id: string | null;
  name: string;
  confidence_score: number;
  reasoning: string;

  score_breakdown?: ScoreBreakdown;
  policy_flags?: string[];
}

export interface ExtractTasksRequest {
  source_type: 'text' | 'url' | 'email';
  content: string;
  project_id: string;
}

export interface TaskCandidate {
  id: string;
  project_id: string;
  title: string;
  description: string | null;
  priority: TaskPriority;
  due_date: string | null;
  selected_assignee_id: string | null;
  confidence_score: number;
  source_type: string;
  source_excerpt: string | null;
  source_summary: string;
  sources?: Source[];
  assignee_recommendations: AssigneeRecommendation[];
  status: TaskCandidateStatus;
  approved_task_id: string | null;
  approved_at: string | null;
  rejected_at: string | null;
  undo_expires_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface ExtractedTask {
  title: string;
  description: string | null;
  priority: TaskPriority;
  due_date: string | null;
  confidence_score: number;
}

export interface ExtractTasksResult {
  source_summary: string;
  tasks: ExtractedTask[];
  created_task_ids: string[];
}

export interface ExtractJobQueued { job_id: string; status: 'queued'; }

export interface ExtractJobStatus {
  job_id: string;
  status: 'queued' | 'running' | 'done' | 'failed';
  attempts?: number;
  result?: ExtractTasksResult;
  error?: string;
}

export interface AgentEvent {
  id?: string;
  iteration?: number;
  event_type?: string;
  type?: string;
  display_message?: string;
  tool_name?: string;
  message?: string;
  output?: string;
  timestamp?: string;
  created_at?: string;
  metadata?: Record<string, unknown>;
}

export interface AgentEventsResponse {
  events: AgentEvent[];
}

export interface JobEntry {
  jobId: string;
  status: 'queued' | 'running' | 'done' | 'failed';
  attempts?: number;
  result?: ExtractTasksResult;
  error?: string;
}

export interface TaskCandidatePatch {
  title?: string;
  description?: string | null;
  priority?: TaskPriority;
  due_date?: string | null;
  selected_assignee_id?: string | null;
}

export interface ApproveCandidateResponse {
  candidate: TaskCandidate;
  task_id: string;
}

export interface RejectCandidateResponse {
  candidate: TaskCandidate;
  undo_expires_at: string;
}

export interface UndoRejectResponse {
  candidate: TaskCandidate;
}

export interface RerunCandidateResponse {
  candidate: TaskCandidate;
  message?: string;
}

export interface BatchCandidateActionRequest {
  candidate_ids: string[];
}

export interface BatchCandidateItemResult {
  candidate_id: string;
  status: 'approved' | 'rejected' | 'conflict';
  task_id?: string;
  message?: string;
}

export interface BatchCandidateActionResponse {
  results: BatchCandidateItemResult[];
}

export interface AssigneeSuggestion {
  person_id: string | null;
  name: string | null;
  reasoning: string;
}

export type FeedbackPeriod = 'day' | 'week' | 'month';

export interface FeedbackRatePoint {
  bucket_start: string;
  total_actions: number;
  accept_rate: number;
  reject_rate: number;
  edit_rate: number;
}

export interface FieldAccuracyMetric {
  field: 'title' | 'description' | 'priority' | 'due_date' | 'selected_assignee_id';
  total_considered: number;
  accurate_count: number;
  accuracy_rate: number;
}

export interface AssigneeAccuracyMetric {
  total_accepts: number;
  top_1_count: number;
  top_1_rate: number;
  top_2_count: number;
  top_2_rate: number;
  top_3_count: number;
  top_3_rate: number;
  not_recommended_count: number;
  not_recommended_rate: number;
  unassigned_count: number;
  unassigned_rate: number;
}

export interface FeedbackAnalyticsResponse {
  project_id: string;
  period: FeedbackPeriod;
  rate_series: FeedbackRatePoint[];
  field_accuracy: FieldAccuracyMetric[];
  assignee_accuracy: AssigneeAccuracyMetric;
}

// ─── Email Assignment Domain ──────────────────────────────────────────────────

export interface Employee {
  id: string;
  name: string;
  level: 'veteran' | 'general' | 'newcomer';
  base_capacity: number;
  current_load?: number;
  is_active?: boolean;
  is_available_today?: boolean;
  unavailable_reason?: string;
}

export interface Attachment {
  id: string;
  filename: string;
  file_type: string;
  mime_type?: string;
  file_size?: number;
  extraction_status: string;
  has_extracted_text: boolean;
}

export interface Email {
  id: string;
  subject: string;
  sender: string;
  received_at: string;
  status:
    | 'pending'
    | 'processing'
    | 'analyzed'
    | 'assigned'
    | 'ignored'
    | 'error'
    | 'manual_review'
    | 'hold'
    | 'no_action';
  body_preview?: string;
  attachments?: Attachment[];
  thread_id?: string | null;
  in_reply_to?: string | null;
}

export interface EmailDetailData {
  id: string;
  subject?: string;
  normalized_subject?: string | null;
  sender: string;
  sender_name?: string;
  received_at: string;
  status: string;
  message_id: string;
  thread_id?: string | null;
  in_reply_to?: string | null;
  body_text?: string | null;
  body_html?: string | null;
  latest_message_text?: string | null;
  quoted_history_text?: string | null;
  recipients?: string[] | null;
  attachments: Attachment[];
}

export type EmailThread = EmailDetailData[];

export interface EmailAnalysis {
  email_type: 'site_quote' | 'single_quote' | 'catalog_request' | 'sample_request' | 'other';
  mail_intent?:
    | 'quote_request'
    | 'quote_response'
    | 'information_request'
    | 'follow_up'
    | 'confirmation'
    | 'fyi';
  workflow_action?: 'assign' | 'hold' | 'no_action' | 'merge_into_existing_case';
  workflow_reason?: string;
  workflow_confidence?: number;
  confidence_score: number;
  makers: string[];
  complexity_points: number;
  classification_reason?: string;
  violation_reason?: string;
}

export interface Assignment {
  kind: 'assignment';
  id: string;
  email_id: string;
  employee_id: string;
  status: 'pending' | 'accepted' | 'in_progress' | 'completed' | 'reassigned' | 'cancelled';
  stage_matched: 'priority_rule' | 'history' | 'load_balance';
  match_reason: string;
  points?: number;
  needs_review?: boolean;
  completed_at?: string | null;
  human_explanation?: string | null;
}

export interface AssignmentWithDetails extends Assignment {
  email: Email;
  analysis?: EmailAnalysis;
  employee?: Employee | null;
}

export interface UnassignedEmail {
  kind: 'unassigned';
  id: string;
  email_id: string;
  employee_id: null;
  status: 'pending' | 'processing' | 'analyzed' | 'assigned' | 'ignored' | 'error' | 'manual_review' | 'hold' | 'no_action' | 'completed' | 'in_progress' | 'reassigned' | 'cancelled' | 'accepted';
  stage_matched: string;
  match_reason: string;
  needs_review?: boolean;
  completed_at?: null;
  human_explanation?: null;
  assigned_at: string;
  email?: Email;
  analysis?: EmailAnalysis;
  employee?: null;
}

export type AssignmentOrUnassigned = AssignmentWithDetails | (UnassignedEmail & { email: Email });

export interface RawDashboardSummary {
  total_emails: number;
  pending_assignments: number;
  emails_by_status: Record<string, number>;
  emails_by_type: Record<string, number>;
  top_assignees: Array<{
    name: string;
    count: number;
    completed: number;
    pending: number;
  }>;
}

export interface DashboardSummary {
  todays_emails: number;
  pending_count: number;
  completed_today: number;
  email_types: EmailTypeDistribution[];
  top_assignees: TopAssignee[];
}

export interface EmailTypeDistribution {
  type: EmailAnalysis['email_type'];
  count: number;
  percentage: number;
}

export interface TopAssignee {
  employee_id: string;
  employee_name: string;
  assignment_count: number;
  completed?: number;
  pending?: number;
  level: Employee['level'];
}

export interface PaginatedAssignments {
  items: AssignmentOrUnassigned[];
  total: number;
  page: number;
  size: number;
}

export type RuleType = 'filter' | 'assignment' | 'flag';

export interface NLRule {
  id: string;
  content: string;
  rule_type: RuleType;
  priority: number;
  is_active: boolean;
}

export interface CreateNLRulePayload {
  content: string;
  rule_type: RuleType;
  priority?: number;
  is_active?: boolean;
}

export interface UpdateNLRulePayload {
  content?: string;
  rule_type?: RuleType;
  priority?: number;
  is_active?: boolean;
}

export interface ChartDataPoint {
  label: string;
  received: number;
  processed: number;
  pending: number;
}

export interface EmployeePerformance {
  employee_id: string;
  name: string;
  task_count: number;
  avg_handling_minutes: number | null;
}

export interface AnalyticsSummary {
  total_received: number;
  received_change: number | null;
  total_processed: number;
  processed_change: number | null;
  total_pending: number;
  pending_change: number | null;
  avg_handling_minutes: number | null;
  handling_time_change: number | null;
}

export interface DashboardAnalytics {
  chart_data: ChartDataPoint[];
  summary: AnalyticsSummary;
  employee_table: EmployeePerformance[];
}
