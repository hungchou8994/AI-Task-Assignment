/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

import { 
  BookOpen, 
  HelpCircle, 
  Sparkles, 
  Zap, 
  ShieldCheck, 
  AlertCircle,
  Info,
  CheckCircle2,
  Users,
  Database,
  LayoutDashboard,
  CheckSquare
} from 'lucide-react';
import { useLanguage } from '../i18n/LanguageContext';

export const DocumentationPage = () => {
  const { t } = useLanguage();

  const sections = [
    {
      id: 'introduction',
      title: 'Introduction',
      icon: <Info className="w-5 h-5" />,
      content: (
        <div className="space-y-6">
          <div className="space-y-4">
            <h3 className="text-lg font-semibold">Mission</h3>
            <p>
              The AI Task Management Platform bridges unstructured communication and structured project execution. It runs asynchronous extraction jobs over text, URLs, and emails, persists candidate and task artifacts, and gives teams a review workflow to validate decisions and improve quality over time.
            </p>
          </div>
          
          <div className="space-y-4">
            <h3 className="text-lg font-semibold">Architectural Principles</h3>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div className="p-4 border border-border bg-card/50 rounded-lg">
                <h4 className="font-bold flex items-center gap-2 mb-2 text-primary">
                  <ShieldCheck className="w-4 h-4" />
                  Human-in-the-Loop
                </h4>
                <p className="text-sm text-muted-foreground">
                  AI extraction can persist linked tasks and candidates automatically, while reviewers still decide candidate outcomes (approve, edit, reject) and shape the learning signal.
                </p>
              </div>
              <div className="p-4 border border-border bg-card/50 rounded-lg">
                <h4 className="font-bold flex items-center gap-2 mb-2 text-blue-500">
                  <Database className="w-4 h-4" />
                  Two-Layer Separation
                </h4>
                <p className="text-sm text-muted-foreground">
                  The core task platform remains the source of truth, while the AI layer supports intake, triage, and enrichment.
                </p>
              </div>
              <div className="p-4 border border-border bg-card/50 rounded-lg">
                <h4 className="font-bold flex items-center gap-2 mb-2 text-green-500">
                  <CheckCircle2 className="w-4 h-4" />
                  Fail-Safe Behavior
                </h4>
                <p className="text-sm text-muted-foreground">
                  AI failures, latency, or vendor issues never break core CRUD task operations. The system remains reliable.
                </p>
              </div>
              <div className="p-4 border border-border bg-card/50 rounded-lg">
                <h4 className="font-bold flex items-center gap-2 mb-2 text-purple-500">
                  <Sparkles className="w-4 h-4" />
                  Traceability
                </h4>
                <p className="text-sm text-muted-foreground">
                  Every approved task is traceable from original source input to AI candidate output to final human-approved task.
                </p>
              </div>
            </div>
          </div>
        </div>
      )
    },
    {
      id: 'getting-started',
      title: 'Getting Started',
      icon: <Zap className="w-5 h-5" />,
      content: (
        <div className="space-y-8">
          <div className="relative pl-10">
            <div className="absolute left-0 top-0 w-8 h-8 rounded-full bg-primary/10 text-primary flex items-center justify-center font-bold">1</div>
            <h4 className="font-bold mb-1">Select a Project</h4>
            <p className="text-sm text-muted-foreground">Use the workspace/project selector in the sidebar to set your current context. All tasks and candidates are scoped to the selected project.</p>
          </div>
          <div className="relative pl-10">
            <div className="absolute left-0 top-0 w-8 h-8 rounded-full bg-primary/10 text-primary flex items-center justify-center font-bold">2</div>
            <h4 className="font-bold mb-1">Ingest Content</h4>
            <p className="text-sm text-muted-foreground">Navigate to the <strong>AI Analysis</strong> page. Paste a URL, email thread, or raw text. The AI pipeline will process the input asynchronously.</p>
          </div>
          <div className="relative pl-10">
            <div className="absolute left-0 top-0 w-8 h-8 rounded-full bg-primary/10 text-primary flex items-center justify-center font-bold">3</div>
            <h4 className="font-bold mb-1">Review Candidates</h4>
            <p className="text-sm text-muted-foreground">Open the <strong>Review Queue</strong> to inspect pending candidates. Edit fields, adjust selected assignee, approve/reject, undo recent rejects, or run batch actions.</p>
          </div>
          <div className="relative pl-10">
            <div className="absolute left-0 top-0 w-8 h-8 rounded-full bg-primary/10 text-primary flex items-center justify-center font-bold">4</div>
            <h4 className="font-bold mb-1">Manage Tasks</h4>
            <p className="text-sm text-muted-foreground">Use the <strong>Tasks</strong> page to update status, assignees, estimates, dependencies, labels, archives, and activity history while provenance stays available for traceability.</p>
          </div>
        </div>
      )
    },
    {
      id: 'feature-guides',
      title: 'Feature Guides',
      icon: <LayoutDashboard className="w-5 h-5" />,
      content: (
        <div className="space-y-10">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
            <div className="space-y-3">
              <h4 className="font-bold flex items-center gap-2 text-blue-500">
                <CheckSquare className="w-5 h-5" />
                Core Task Platform
              </h4>
              <ul className="text-sm text-muted-foreground space-y-2 list-disc pl-5">
                <li><strong>Task CRUD:</strong> Full lifecycle management from creation to completion.</li>
                <li><strong>Dependencies:</strong> Link tasks within a workspace to visualize blockers.</li>
                <li><strong>Fields:</strong> Comprehensive support for title, description, priority, and due dates.</li>
                <li><strong>Effort Tracking:</strong> Track estimated vs. actual hours with snapshots.</li>
              </ul>
            </div>
            <div className="space-y-3">
              <h4 className="font-bold flex items-center gap-2 text-amber-500">
                <Sparkles className="w-5 h-5" />
                AI Intake Pipeline
              </h4>
              <ul className="text-sm text-muted-foreground space-y-2 list-disc pl-5">
                <li><strong>Multi-Source:</strong> Process text, URLs, and email threads seamlessly.</li>
                <li><strong>Async Processing:</strong> Background jobs ensure the UI remains responsive.</li>
                <li><strong>Monitoring:</strong> Real-time status updates and event streams for every job.</li>
                <li><strong>Resilience:</strong> Dead-letter handling with explicit retry mechanisms.</li>
              </ul>
            </div>
            <div className="space-y-3">
              <h4 className="font-bold flex items-center gap-2 text-purple-500">
                <Users className="w-5 h-5" />
                Intelligence & Analytics
              </h4>
              <ul className="text-sm text-muted-foreground space-y-2 list-disc pl-5">
                <li><strong>Recommendations:</strong> AI-driven assignee suggestions with rationale.</li>
                <li><strong>Feedback Analytics:</strong> Monitor extraction accuracy and human override rates.</li>
                <li><strong>Dashboards:</strong> Visual throughput, completion trends, and cycle time metrics.</li>
                <li><strong>Forecasts:</strong> Velocity-based completion date predictions for projects.</li>
              </ul>
            </div>
            <div className="space-y-3">
              <h4 className="font-bold flex items-center gap-2 text-green-500">
                <Zap className="w-5 h-5" />
                Integrations
              </h4>
              <ul className="text-sm text-muted-foreground space-y-2 list-disc pl-5">
                <li><strong>Webhooks:</strong> Workspace-scoped subscriptions for task and candidate events.</li>
                <li><strong>Source Explorer:</strong> Detailed view of ingested content and its provenance.</li>
                <li><strong>Audit Trail:</strong> Full history of status changes, assignments, and edits.</li>
                <li><strong>Manual Tests:</strong> Trigger test webhook deliveries to verify integrations.</li>
              </ul>
            </div>
          </div>
        </div>
      )
    },
    {
      id: 'ai-workflow',
      title: 'AI Workflow',
      icon: <Sparkles className="w-5 h-5" />,
      content: (
        <div className="space-y-6">
          <p className="text-sm">
            The extraction pipeline runs as an asynchronous job and exposes progress/events so users can monitor the full lifecycle.
          </p>
          <div className="flex flex-col gap-4">
            <div className="p-4 bg-muted/30 border rounded-lg">
              <h5 className="font-bold text-sm mb-2">1. Ingestion & Normalization</h5>
              <p className="text-xs text-muted-foreground">Raw text, URL content, or parsed email payload is normalized and preprocessed before model reasoning.</p>
            </div>
            <div className="p-4 bg-muted/30 border rounded-lg">
              <h5 className="font-bold text-sm mb-2">2. Candidate & Task Persistence</h5>
              <p className="text-xs text-muted-foreground">Agent tools persist source records, task candidates, linked tasks, and provenance-ready metadata in one extraction run.</p>
            </div>
            <div className="p-4 bg-muted/30 border rounded-lg">
              <h5 className="font-bold text-sm mb-2">3. Assignee Recommendation</h5>
              <p className="text-xs text-muted-foreground">Recommendations are ranked per candidate and can auto-apply top assignees when confidence and policy thresholds are satisfied.</p>
            </div>
            <div className="p-4 bg-muted/30 border rounded-lg">
              <h5 className="font-bold text-sm mb-2">4. Human Review & Feedback</h5>
              <p className="text-xs text-muted-foreground">Review actions (edit, approve, reject, undo reject, batch operations) update candidate state and feed analytics/audit signals.</p>
            </div>
          </div>
        </div>
      )
    },
    {
      id: 'deployment',
      title: 'Deployment',
      icon: <Database className="w-5 h-5" />,
      content: (
        <div className="space-y-6">
          <div className="space-y-2">
            <h4 className="font-bold text-sm">System Requirements</h4>
            <ul className="text-xs text-muted-foreground space-y-1 list-disc pl-5">
              <li><strong>Node.js:</strong> v18+ (Frontend & PM2)</li>
              <li><strong>Python:</strong> v3.10+ (Backend)</li>
              <li><strong>PostgreSQL:</strong> v16+</li>
              <li><strong>PM2:</strong> Global installation for process management</li>
            </ul>
          </div>
          <div className="space-y-2">
            <h4 className="font-bold text-sm">Quick Setup</h4>
            <div className="bg-muted p-4 rounded-md font-mono text-[10px] space-y-2 overflow-x-auto">
              <p># 1. Backend</p>
              <p>cd backend && python3 -m venv venv && source venv/bin/activate && pip install -r requirements.txt</p>
              <p>cp .env.example .env && alembic upgrade head</p>
              <p># 2. Database Migration</p>
              <p># already covered above</p>
              <p># 3. Frontend</p>
              <p>cd ../frontend && npm ci && npm run build</p>
              <p># 4. Start with PM2</p>
              <p>pm2 start ecosystem.config.cjs</p>
              <p># API: :8003, Frontend: :3003 (default config)</p>
            </div>
          </div>
        </div>
      )
    },
    {
      id: 'api-overview',
      title: 'API Overview',
      icon: <BookOpen className="w-5 h-5" />,
      content: (
        <div className="space-y-4">
          <p className="text-sm">
            The platform provides a REST API. Interactive docs are available at <code>/docs</code> on the backend host.
          </p>
          <div className="space-y-3">
            <div className="flex items-center justify-between p-2 border-b text-xs">
              <code className="text-primary font-bold">POST /api/ai/extract-tasks</code>
              <span className="text-muted-foreground">Queue async extraction job</span>
            </div>
            <div className="flex items-center justify-between p-2 border-b text-xs">
              <code className="text-primary font-bold">GET /api/ai/jobs/{'{job_id}'}</code>
              <span className="text-muted-foreground">Fetch job status and result</span>
            </div>
            <div className="flex items-center justify-between p-2 border-b text-xs">
              <code className="text-primary font-bold">GET /api/task-candidates?project_id=...&status=pending</code>
              <span className="text-muted-foreground">Access the review queue</span>
            </div>
            <div className="flex items-center justify-between p-2 border-b text-xs">
              <code className="text-primary font-bold">POST /api/task-candidates/{'{id}'}/approve</code>
              <span className="text-muted-foreground">Approve candidate decision</span>
            </div>
            <div className="flex items-center justify-between p-2 border-b text-xs">
              <code className="text-primary font-bold">POST /api/webhooks?workspace_id=...</code>
              <span className="text-muted-foreground">Manage webhook subscriptions</span>
            </div>
          </div>
        </div>
      )
    },
    {
      id: 'troubleshooting',
      title: 'FAQ',
      icon: <HelpCircle className="w-5 h-5" />,
      content: (
        <div className="space-y-6">
          <div className="space-y-2">
            <h4 className="font-bold text-sm flex items-center gap-2">
              <AlertCircle className="w-4 h-4 text-orange-500" />
              What if the AI fails to extract anything?
            </h4>
            <p className="text-sm text-muted-foreground">
              Check the job card and event timeline first. If a job moves to failed/dead-letter, retry with clearer input or use the dead-letter retry endpoint for the same project.
            </p>
          </div>
          <div className="space-y-2">
            <h4 className="font-bold text-sm flex items-center gap-2">
              <CheckCircle2 className="w-4 h-4 text-green-500" />
              Can I use the platform without AI?
            </h4>
            <p className="text-sm text-muted-foreground">
              Yes. Manual task creation and core APIs remain independently usable. AI features are designed to augment existing workflows.
            </p>
          </div>
        </div>
      )
    }
  ];

  return (
    <div className="flex flex-col h-full bg-background">
      {/* Header */}
      <div className="px-8 py-10 border-b border-border bg-card/50">
        <div className="max-w-5xl mx-auto">
          <div className="flex items-center gap-4 mb-3">
            <div className="p-3 bg-primary/10 text-primary rounded-xl">
              <BookOpen className="w-6 h-6" />
            </div>
            <div>
              <h1 className="text-3xl font-extrabold text-foreground tracking-tight">
                {t.documentation.title}
              </h1>
              <p className="text-muted-foreground">
                {t.documentation.subtitle}
              </p>
            </div>
          </div>
        </div>
      </div>

      <div className="flex-1 flex overflow-hidden">
        {/* Sidebar Nav */}
        <div className="hidden lg:block w-64 border-r border-border bg-muted/20 overflow-y-auto p-6">
          <h4 className="text-[10px] font-bold uppercase tracking-widest text-muted-foreground mb-6">
            {t.documentation.contents}
          </h4>
          <nav className="flex flex-col gap-1">
            {sections.map((section) => (
              <a 
                key={section.id}
                href={`#${section.id}`}
                className="text-sm py-2 px-3 rounded-md text-muted-foreground hover:text-primary hover:bg-primary/5 transition-all flex items-center gap-3 group"
              >
                <span className="opacity-50 group-hover:opacity-100">{section.icon}</span>
                {section.title}
              </a>
            ))}
          </nav>
        </div>

        {/* Main Content Area */}
        <div className="flex-1 overflow-auto">
          <div className="max-w-4xl mx-auto px-8 py-12 space-y-20 pb-32">
            {sections.map((section) => (
              <section key={section.id} id={section.id} className="scroll-mt-24">
                <div className="flex items-center gap-3 mb-8">
                  <h2 className="text-2xl font-bold text-foreground">
                    {section.title}
                  </h2>
                </div>
                <div className="bg-card border border-border rounded-2xl p-8 shadow-sm">
                  {section.content}
                </div>
              </section>
            ))}
            
            {/* Footer Info */}
            <div className="pt-12 border-t border-border flex flex-col items-center text-center">
              <div className="p-4 bg-muted rounded-full mb-4">
                <HelpCircle className="w-8 h-8 text-muted-foreground/50" />
              </div>
              <h3 className="font-bold mb-2">{t.documentation.stillNeedHelp}</h3>
              <p className="text-sm text-muted-foreground max-w-md">
                {t.documentation.contactAdmin}
              </p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
