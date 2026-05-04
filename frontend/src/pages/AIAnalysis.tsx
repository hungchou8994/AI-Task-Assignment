/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

import { useState } from 'react';
import { AlertTriangle, ClipboardList, Loader2 } from 'lucide-react';
import { cn } from '../lib/utils';
import { useProjectContext } from '../context/ProjectContext';
import { useLanguage } from '../i18n/LanguageContext';
import { useExtractionJobs } from '../hooks/useExtractionJobs';
import { JobCard } from '../components/JobCard';
import { useQuery } from '@tanstack/react-query';
import { fetchProjectSources } from '../api/sources';
import { useTaskCandidates } from '../hooks/useTaskCandidates';
import { useWorkspaceContext } from '../context/WorkspaceContext';
import type { TaskCandidate } from '../types';


type SourceType = 'text' | 'url' | 'email';

type IntakeRiskFlag = {
  id: string;
  label: string;
  severity: 'low' | 'medium' | 'high';
};

function normalizeContent(input: string) {
  return input.trim().replace(/\s+/g, ' ').toLowerCase();
}

function wordCount(input: string) {
  return input.trim().split(/\s+/).filter(Boolean).length;
}

function buildEmailContent(subject: string, sender: string, body: string) {
  const safeSubject = subject.trim() || '(no subject)';
  const safeSender = sender.trim() || '(unknown sender)';
  return `Subject: ${safeSubject}\nFrom: ${safeSender}\n\n${body.trim()}`;
}

export const AIAnalysisPage = () => {
  const { t } = useLanguage();
  const { currentProjectId } = useProjectContext();
  const { currentWorkspaceId } = useWorkspaceContext();
  const [sourceType, setSourceType] = useState<SourceType>('text');
  const [textContent, setTextContent] = useState('');
  const [urlContent, setUrlContent] = useState('');
  const [emailSubject, setEmailSubject] = useState('');
  const [emailSender, setEmailSender] = useState('');
  const [emailBody, setEmailBody] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const { jobs, submitJob, removeJob, fetchJobStatus } = useExtractionJobs(currentProjectId);

  const { data: projectSources = [] } = useQuery({
    queryKey: ['sources', currentProjectId],
    queryFn: () => fetchProjectSources(currentProjectId as string),
    enabled: !!currentProjectId,
    staleTime: 10_000,
  });

  const pendingCandidatesQuery = useTaskCandidates(currentProjectId, 'pending');
  const approvedCandidatesQuery = useTaskCandidates(currentProjectId, 'approved');
  const rejectedCandidatesQuery = useTaskCandidates(currentProjectId, 'rejected');

  const allCandidates = [
    ...(pendingCandidatesQuery.data ?? []),
    ...(approvedCandidatesQuery.data ?? []),
    ...(rejectedCandidatesQuery.data ?? []),
  ];

  const activeContent =
    sourceType === 'text'
      ? textContent
      : sourceType === 'url'
      ? urlContent
      : buildEmailContent(emailSubject, emailSender, emailBody);

  const normalizedActiveContent = normalizeContent(activeContent);

  const dedupeHint =
    sourceType === 'url'
      ? projectSources.find((source) => source.source_type === 'url' && normalizeContent(source.uri ?? '') === normalizeContent(urlContent))
      : projectSources.find((source) => {
          const sourceText = normalizeContent(`${source.title ?? ''} ${source.summary ?? ''} ${source.excerpt ?? ''}`);
          if (!sourceText || !normalizedActiveContent) return false;
          return sourceText.includes(normalizedActiveContent.slice(0, Math.min(80, normalizedActiveContent.length)));
        });

  const intakeFlags: IntakeRiskFlag[] = [];
  if (sourceType === 'text' && wordCount(textContent) < 12 && textContent.trim().length > 0) {
    intakeFlags.push({ id: 'thin-text', label: 'Input may be too short for reliable extraction', severity: 'medium' });
  }
  if (sourceType === 'url' && urlContent.trim()) {
    try {
      const parsed = new URL(urlContent.trim());
      if (parsed.protocol !== 'http:' && parsed.protocol !== 'https:') {
        intakeFlags.push({ id: 'protocol-risk', label: 'Only http/https URLs are supported', severity: 'high' });
      }
    } catch {
      intakeFlags.push({ id: 'invalid-url', label: 'URL format looks invalid', severity: 'high' });
    }
  }
  if (sourceType === 'email') {
    if (emailBody.trim() && wordCount(emailBody) < 10) {
      intakeFlags.push({ id: 'thin-email', label: 'Email body has limited context', severity: 'medium' });
    }
    if (emailSender.trim() && !/^\S+@\S+\.\S+$/.test(emailSender.trim())) {
      intakeFlags.push({ id: 'sender-format', label: 'Sender address format looks invalid', severity: 'high' });
    }
  }
  if (dedupeHint) {
    intakeFlags.push({ id: 'dedupe', label: `Possible duplicate of existing source ${dedupeHint.id.slice(0, 8)}`, severity: 'low' });
  }

  const validationError =
    sourceType === 'text'
      ? !textContent.trim()
        ? 'Paste source text before extracting.'
        : null
      : sourceType === 'url'
      ? !urlContent.trim()
        ? 'Provide a URL before extracting.'
        : intakeFlags.some((flag) => flag.severity === 'high')
        ? 'Fix URL validation issues before extracting.'
        : null
      : !emailBody.trim()
      ? 'Provide email body text before extracting.'
      : intakeFlags.some((flag) => flag.id === 'sender-format')
      ? 'Fix the sender email format before extracting.'
      : null;


  async function handleAnalyze() {
    if (!activeContent.trim() || !currentProjectId || validationError) return;

    setSubmitting(true);
    setSubmitError(null);

    try {
      await submitJob({ source_type: sourceType, content: activeContent, project_id: currentProjectId });

      if (sourceType === 'text') setTextContent('');
      if (sourceType === 'url') setUrlContent('');
      if (sourceType === 'email') {
        setEmailSubject('');
        setEmailSender('');
        setEmailBody('');
      }
    } catch (error) {
      setSubmitError(error instanceof Error ? error.message : t.aiAnalysis.analysisFailed);
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="flex min-h-full flex-col bg-background p-4">
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-12">
        <section className="lg:col-span-7 border border-border bg-card p-6">
          <div className="mb-4 flex gap-0.5 bg-muted p-0.5">
            {(['text', 'url', 'email'] as SourceType[]).map((value) => {
              return (
                <button
                  key={value}
                  onClick={() => setSourceType(value)}
                  className={cn(
                    'px-4 py-1.5 text-xs font-bold capitalize transition-all',
                    sourceType === value ? 'bg-background text-foreground' : 'text-muted-foreground',
                  )}
                  aria-pressed={sourceType === value}
                >
                  {t.aiAnalysis[value]}
                </button>
              );
            })}
          </div>

          {sourceType === 'text' && (
            <textarea
              value={textContent}
              onChange={(event) => setTextContent(event.target.value)}
              className="min-h-[280px] w-full resize-none border border-border bg-background p-4 text-sm leading-relaxed text-foreground outline-none focus:ring-1 focus:ring-primary"
              placeholder={t.aiAnalysis.textPlaceholder}
            />
          )}

          {sourceType === 'url' && (
            <div className="space-y-3">
              <label className="block text-xs font-semibold uppercase tracking-wide text-muted-foreground" htmlFor="intake-url-input">
                Source URL
              </label>
              <input
                id="intake-url-input"
                value={urlContent}
                onChange={(event) => setUrlContent(event.target.value)}
                className="w-full border border-border bg-background px-3 py-2 text-sm text-foreground outline-none focus:ring-1 focus:ring-primary"
                placeholder={t.aiAnalysis.urlPlaceholder}
              />
              <p className="text-xs text-muted-foreground">We ingest the URL and extract candidate tasks from the fetched content.</p>
            </div>
          )}

          {sourceType === 'email' && (
            <div className="space-y-3">
              <div>
                <label className="block text-xs font-semibold uppercase tracking-wide text-muted-foreground" htmlFor="intake-email-subject">
                  Email subject
                </label>
                <input
                  id="intake-email-subject"
                  value={emailSubject}
                  onChange={(event) => setEmailSubject(event.target.value)}
                  className="mt-1 w-full border border-border bg-background px-3 py-2 text-sm text-foreground outline-none focus:ring-1 focus:ring-primary"
                  placeholder="Subject: Supplier onboarding timeline"
                />
              </div>
              <div>
                <label className="block text-xs font-semibold uppercase tracking-wide text-muted-foreground" htmlFor="intake-email-sender">
                  Sender
                </label>
                <input
                  id="intake-email-sender"
                  value={emailSender}
                  onChange={(event) => setEmailSender(event.target.value)}
                  className="mt-1 w-full border border-border bg-background px-3 py-2 text-sm text-foreground outline-none focus:ring-1 focus:ring-primary"
                  placeholder="owner@example.com"
                />
              </div>
              <div>
                <label className="block text-xs font-semibold uppercase tracking-wide text-muted-foreground" htmlFor="intake-email-body">
                  Email body
                </label>
                <textarea
                  id="intake-email-body"
                  value={emailBody}
                  onChange={(event) => setEmailBody(event.target.value)}
                  className="mt-1 min-h-[200px] w-full resize-none border border-border bg-background p-4 text-sm leading-relaxed text-foreground outline-none focus:ring-1 focus:ring-primary"
                  placeholder={t.aiAnalysis.emailPlaceholder}
                />
              </div>
            </div>
          )}

          <button
            onClick={handleAnalyze}
            disabled={!activeContent.trim() || submitting || !currentProjectId}
            className="mt-4 inline-flex w-full items-center justify-center gap-2 bg-primary hover:bg-primary/90 text-primary-foreground px-6 py-2.5 text-sm font-bold transition-colors disabled:cursor-not-allowed disabled:opacity-60"
          >
            {submitting ? (
              <>
                <Loader2 className="h-4 w-4 animate-spin" /> {t.aiAnalysis.analyzing}
              </>
            ) : (
              <>
                <ClipboardList className="h-4 w-4" /> {t.aiAnalysis.extractButton}
              </>
            )}
          </button>

          {!currentProjectId && (
            <p className="mt-3 text-xs font-medium text-warning">
              {t.aiAnalysis.selectProjectWarning}
            </p>
          )}

          {submitError && (
            <div className="mt-4 flex items-start gap-3 border border-destructive/30 bg-destructive/5 p-3">
              <AlertTriangle className="mt-0.5 h-4 w-4 text-destructive" />
              <p className="text-xs text-destructive">{submitError}</p>
            </div>
          )}

          {currentWorkspaceId && (
            <div className="mt-4">
              <a
                href={`/${currentWorkspaceId}/review`}
                className="text-xs font-semibold text-primary hover:underline"
              >
                Open full review queue
              </a>
            </div>
          )}
        </section>

        <section className="lg:col-span-5 border border-border bg-card p-6">
          <h3 className="text-[10px] font-bold uppercase tracking-widest font-mono text-muted-foreground mb-1">
            {t.aiAnalysis.ingestionResult}
          </h3>
          <p className="text-sm text-muted-foreground mb-4">{t.aiAnalysis.candidatesSavedTo}</p>

          {jobs.length > 0 ? (
            <div className="space-y-3">
              {jobs.map((job) => (
                <JobCard
                  key={job.jobId}
                  job={job}
                  projectId={currentProjectId}
                  onRemove={removeJob}
                  onTerminal={() => fetchJobStatus(job.jobId)}
                />
              ))}
            </div>
          ) : (
            <div className="border border-border bg-muted/30 p-5 text-center text-sm text-muted-foreground">
              {t.aiAnalysis.runAnalysisPrompt}
            </div>
          )}
        </section>
      </div>

      {/* <section className="mt-6 border border-border bg-card p-6">
        <div className="mb-4 flex flex-wrap items-end justify-between gap-3">
          <div>
            <h3 className="text-sm font-bold uppercase tracking-widest text-foreground">Candidate triage queue</h3>
            <p className="text-xs text-muted-foreground">Filter by source, confidence, assignee suggestion, and status.</p>
          </div>
          <p className="text-xs text-muted-foreground">
            {filteredCandidates.length} candidate{filteredCandidates.length === 1 ? '' : 's'}
          </p>
        </div>

        <div className="grid gap-3 md:grid-cols-5">
          <div>
            <label htmlFor="queue-status" className="text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">
              Status
            </label>
            <select
              id="queue-status"
              value={queueStatus}
              onChange={(event) => setQueueStatus(event.target.value as typeof queueStatus)}
              className="mt-1 w-full border border-border bg-background px-2 py-1.5 text-sm text-foreground"
            >
              <option value="all">All</option>
              <option value="pending">Pending</option>
              <option value="approved">Approved</option>
              <option value="rejected">Rejected</option>
            </select>
          </div>

          <div>
            <label htmlFor="queue-source" className="text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">
              Source
            </label>
            <select
              id="queue-source"
              value={queueSource}
              onChange={(event) => setQueueSource(event.target.value as typeof queueSource)}
              className="mt-1 w-full border border-border bg-background px-2 py-1.5 text-sm text-foreground"
            >
              <option value="all">All</option>
              <option value="text">Text</option>
              <option value="url">URL</option>
              <option value="email">Email</option>
            </select>
          </div>

          <div>
            <label htmlFor="queue-assignee" className="text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">
              Suggested assignee
            </label>
            <select
              id="queue-assignee"
              value={assigneeFilter}
              onChange={(event) => setAssigneeFilter(event.target.value)}
              className="mt-1 w-full border border-border bg-background px-2 py-1.5 text-sm text-foreground"
            >
              <option value="all">All</option>
              {assigneeOptions.map((name) => (
                <option key={name} value={name}>
                  {name}
                </option>
              ))}
            </select>
          </div>

          <div>
            <label htmlFor="queue-confidence" className="text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">
              Minimum confidence ({minimumConfidence}%)
            </label>
            <input
              id="queue-confidence"
              type="range"
              min={0}
              max={100}
              step={5}
              value={minimumConfidence}
              onChange={(event) => setMinimumConfidence(Number(event.target.value))}
              className="mt-2 w-full"
            />
          </div>

          <div>
            <label htmlFor="queue-search" className="text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">
              Search
            </label>
            <input
              id="queue-search"
              value={queueQuery}
              onChange={(event) => setQueueQuery(event.target.value)}
              placeholder="Title, description, assignee..."
              className="mt-1 w-full border border-border bg-background px-2 py-1.5 text-sm text-foreground"
            />
          </div>
        </div>

        <div className="mt-4 overflow-x-auto">
          <table className="w-full min-w-[780px] border-collapse text-sm">
            <thead>
              <tr className="border-b border-border text-left text-[11px] uppercase tracking-widest text-muted-foreground">
                <th className="px-2 py-2">Candidate</th>
                <th className="px-2 py-2">Source</th>
                <th className="px-2 py-2">Status</th>
                <th className="px-2 py-2">Confidence</th>
                <th className="px-2 py-2">Assignee Suggestion</th>
                <th className="px-2 py-2">Risk Flags</th>
              </tr>
            </thead>
            <tbody>
              {pendingCandidatesQuery.isLoading || approvedCandidatesQuery.isLoading || rejectedCandidatesQuery.isLoading ? (
                <tr>
                  <td colSpan={6} className="px-2 py-5 text-center text-xs text-muted-foreground">
                    Loading candidates...
                  </td>
                </tr>
              ) : filteredCandidates.length === 0 ? (
                <tr>
                  <td colSpan={6} className="px-2 py-5 text-center text-xs text-muted-foreground">
                    No candidates match the current filters.
                  </td>
                </tr>
              ) : (
                filteredCandidates.map((candidate) => {
                  const topAssignee = candidate.assignee_recommendations[0]?.name ?? 'Unassigned';
                  const riskFlags = getCandidateRiskFlags(candidate);

                  return (
                    <tr key={candidate.id} className="border-b border-border/70 align-top hover:bg-muted/20">
                      <td className="px-2 py-2">
                        <p className="font-semibold text-foreground">{candidate.title}</p>
                        <p className="line-clamp-2 text-xs text-muted-foreground">{candidate.description ?? candidate.source_summary}</p>
                      </td>
                      <td className="px-2 py-2 capitalize text-foreground">{candidate.source_type}</td>
                      <td className="px-2 py-2">
                        <span
                          className={cn(
                            'rounded-full border px-2 py-0.5 text-[10px] font-bold uppercase',
                            candidate.status === 'pending'
                              ? 'border-warning/40 bg-warning/10 text-warning'
                              : candidate.status === 'approved'
                              ? 'border-success/40 bg-success/10 text-success'
                              : 'border-border bg-muted text-muted-foreground',
                          )}
                        >
                          {candidate.status}
                        </span>
                      </td>
                      <td className="px-2 py-2 text-foreground">{Math.round(candidate.confidence_score * 100)}%</td>
                      <td className="px-2 py-2 text-foreground">{topAssignee}</td>
                      <td className="px-2 py-2">
                        {riskFlags.length === 0 ? (
                          <span className="text-xs text-success">None</span>
                        ) : (
                          <ul className="space-y-1 text-xs">
                            {riskFlags.slice(0, 2).map((flag) => (
                              <li
                                key={flag.id}
                                className={cn(
                                  flag.severity === 'high'
                                    ? 'text-destructive'
                                    : flag.severity === 'medium'
                                    ? 'text-warning'
                                    : 'text-muted-foreground',
                                )}
                              >
                                {flag.label}
                              </li>
                            ))}
                          </ul>
                        )}
                      </td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>
      </section> */}
    </div>
  );
};
