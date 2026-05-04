import { useState, useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Clock,
  FileText,
  Terminal as TerminalIcon,
} from 'lucide-react';
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Cell,
} from 'recharts';
import { cn } from '@/lib/utils';
import { useTasks } from '@/hooks/useTasks';
import { usePeople } from '@/hooks/usePeople';
import { useFeedbackAnalytics } from '@/hooks/useFeedbackAnalytics';
import { useProjectContext } from '@/context/ProjectContext';
import { useLanguage } from '@/i18n/LanguageContext';
import { StatCard } from '@/components/stats/StatCard';
import { TaskModal } from '@/components/tasks/TaskModal';
import { CreateTaskModal } from '@/components/tasks/CreateTaskModal';
import { formatDate, isOverdue, formatPercent, fieldLabel } from '@/lib/taskFormatters';
import type { FeedbackPeriod, Task } from '@/types';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';

export function TaskDashboard() {
  const { t, language } = useLanguage();
  const navigate = useNavigate();
  const { currentProjectId } = useProjectContext();
  const { data: tasks = [] } = useTasks(currentProjectId);
  const { data: people = [] } = usePeople();
  const [showCreate, setShowCreate] = useState(false);
  const [selectedTask, setSelectedTask] = useState<Task | null>(null);
  const [feedbackPeriod, setFeedbackPeriod] = useState<FeedbackPeriod>('week');
  const { data: feedbackAnalytics, isLoading: isFeedbackLoading } = useFeedbackAnalytics(
    currentProjectId,
    feedbackPeriod,
  );

  const stats = useMemo(() => {
    const now = new Date();
    const weekAgo = new Date(now);
    weekAgo.setDate(weekAgo.getDate() - 7);
    return {
      total: tasks.length,
      needsReview: tasks.filter((t) => t.needs_review).length,
      available: people.filter(
        (p) => p.availability === 'available' || p.availability === null,
      ).length,
      completedWeek: tasks.filter(
        (t) => t.status === 'done' && new Date(t.updated_at) >= weekAgo,
      ).length,
    };
  }, [tasks, people]);

  const highPriorityTasks = useMemo(
    () => tasks.filter((t) => t.priority === 'high' && t.status !== 'done').slice(0, 5),
    [tasks],
  );

  const needsReviewTasks = useMemo(
    () => tasks.filter((t) => t.needs_review).slice(0, 4),
    [tasks],
  );

  const chartData = useMemo(() => {
    const weekStart = (date: Date) => {
      const d = new Date(date);
      const day = d.getDay();
      const diff = (day === 0 ? -6 : 1) - day;
      d.setDate(d.getDate() + diff);
      d.setHours(0, 0, 0, 0);
      return d;
    };

    const now = new Date();
    const thisWeek = weekStart(now);
    return Array.from({ length: 8 }, (_, i) => {
      const start = new Date(thisWeek);
      start.setDate(start.getDate() - (7 * (7 - i)));
      const end = new Date(start);
      end.setDate(end.getDate() + 7);

      const count = tasks.filter((t) => {
        if (t.status !== 'done') return false;
        const doneAt = new Date(t.updated_at);
        return doneAt >= start && doneAt < end;
      }).length;

      const label = start.toLocaleDateString(language === 'ja' ? 'ja-JP' : 'en-US', {
        month: 'short',
        day: 'numeric',
      });

      return { name: label, value: count };
    });
  }, [tasks]);

  const todayIdx = 7;

  const peopleMap = useMemo(() => {
    const m: Record<string, string> = {};
    people.forEach((p) => (m[p.id] = p.name));
    return m;
  }, [people]);

  const iconForIdx = [Clock, FileText, TerminalIcon, FileText, Clock];

  const latestFeedbackRates = useMemo(() => {
    const latest = feedbackAnalytics?.rate_series.at(-1);
    if (!latest) return { accept_rate: 0, reject_rate: 0, edit_rate: 0 };
    return latest;
  }, [feedbackAnalytics]);

  const feedbackTrendData = useMemo(
    () =>
      (feedbackAnalytics?.rate_series ?? []).map((point) => ({
        name: new Date(point.bucket_start).toLocaleDateString(
          language === 'ja' ? 'ja-JP' : 'en-US',
          { month: 'short', day: 'numeric' },
        ),
        accept_rate: Math.round(point.accept_rate * 100),
        reject_rate: Math.round(point.reject_rate * 100),
        edit_rate: Math.round(point.edit_rate * 100),
        total_actions: point.total_actions,
      })),
    [feedbackAnalytics, language],
  );

  const hasFeedbackData =
    (feedbackAnalytics?.rate_series?.reduce((sum, point) => sum + point.total_actions, 0) ??
      0) > 0;

  const performanceKpis = useMemo(() => {
    const now = new Date();
    const fourteenDaysAgo = new Date(now);
    fourteenDaysAgo.setDate(fourteenDaysAgo.getDate() - 14);

    const recentCompleted = tasks.filter(
      (t) => t.status === 'done' && new Date(t.updated_at) >= fourteenDaysAgo,
    );
    const recentCreated = tasks.filter((t) => new Date(t.created_at) >= fourteenDaysAgo);

    const completionRate =
      recentCreated.length > 0 ? recentCompleted.length / recentCreated.length : null;

    const cycleMinutes = recentCompleted
      .map((t) => {
        const created = new Date(t.created_at).getTime();
        const done = new Date(t.updated_at).getTime();
        const delta = done - created;
        return Number.isFinite(delta) && delta >= 0 ? delta / (1000 * 60) : null;
      })
      .filter((v): v is number => v != null);

    const avgCycleMinutes =
      cycleMinutes.length > 0
        ? cycleMinutes.reduce((a, b) => a + b, 0) / cycleMinutes.length
        : null;

    const onTimeCandidates = recentCompleted.filter((t) => !!t.due_date);
    const onTime =
      onTimeCandidates.length > 0
        ? onTimeCandidates.filter((t) => {
            if (!t.due_date) return false;
            const due = new Date(`${t.due_date}T23:59:59.999Z`).getTime();
            const done = new Date(t.updated_at).getTime();
            return done <= due;
          }).length / onTimeCandidates.length
        : null;

    return {
      completionRate,
      avgCycleMinutes,
      onTime,
      recentCompletedCount: recentCompleted.length,
      recentCreatedCount: recentCreated.length,
    };
  }, [tasks]);

  const forecast = useMemo(() => {
    const now = new Date();
    const remaining = tasks.filter((t) => t.status !== 'done').length;
    const fourteenDaysAgo = new Date(now);
    fourteenDaysAgo.setDate(fourteenDaysAgo.getDate() - 14);
    const completed14 = tasks.filter(
      (t) => t.status === 'done' && new Date(t.updated_at) >= fourteenDaysAgo,
    ).length;
    const velocityPerWeek = completed14 / 2;

    if (remaining === 0) {
      return { remaining, velocityPerWeek, projectedDate: now, hasProjection: true };
    }

    if (velocityPerWeek <= 0) {
      return { remaining, velocityPerWeek, projectedDate: null as Date | null, hasProjection: false };
    }

    const weeks = remaining / velocityPerWeek;
    const projected = new Date(now);
    projected.setDate(projected.getDate() + Math.ceil(weeks * 7));
    return { remaining, velocityPerWeek, projectedDate: projected, hasProjection: true };
  }, [tasks]);

  const perPersonPerformance = useMemo(() => {
    const byPerson: Record<
      string,
      {
        personId: string;
        name: string;
        completed: number;
        cycleMinutes: number[];
        onTimeDone: number;
        onTimeTotal: number;
      }
    > = {};

    const nameFor = (id: string | null) =>
      (id && peopleMap[id]) || (id ? id : t.taskModal.unassigned);

    for (const task of tasks) {
      const personId = task.assignee_id ?? 'unassigned';
      if (!byPerson[personId]) {
        byPerson[personId] = {
          personId,
          name: nameFor(task.assignee_id),
          completed: 0,
          cycleMinutes: [],
          onTimeDone: 0,
          onTimeTotal: 0,
        };
      }

      if (task.status === 'done') {
        byPerson[personId].completed += 1;
        const created = new Date(task.created_at).getTime();
        const done = new Date(task.updated_at).getTime();
        const delta = done - created;
        if (Number.isFinite(delta) && delta >= 0) byPerson[personId].cycleMinutes.push(delta / (1000 * 60));

        if (task.due_date) {
          byPerson[personId].onTimeTotal += 1;
          const due = new Date(`${task.due_date}T23:59:59.999Z`).getTime();
          if (done <= due) byPerson[personId].onTimeDone += 1;
        }
      }
    }

    return Object.values(byPerson)
      .map((row) => {
        const avg =
          row.cycleMinutes.length > 0
            ? row.cycleMinutes.reduce((a, b) => a + b, 0) / row.cycleMinutes.length
            : null;
        const onTime = row.onTimeTotal > 0 ? row.onTimeDone / row.onTimeTotal : null;
        return { ...row, avgCycleMinutes: avg, onTime };
      })
      .sort((a, b) => b.completed - a.completed || a.name.localeCompare(b.name));
  }, [peopleMap, t.taskModal.unassigned, tasks]);

  return (
    <div className="p-8">
      {selectedTask && (
        <TaskModal task={selectedTask} people={people} onClose={() => setSelectedTask(null)} />
      )}
      {showCreate && (
        <CreateTaskModal people={people} onClose={() => setShowCreate(false)} />
      )}

      <header className="mb-8 flex justify-between items-end">
        <div>
          <h2 className="text-2xl font-bold text-foreground tracking-tight">
            {t.overview.title}
          </h2>
          <p className="text-muted-foreground text-sm mt-0.5">
            {new Date().toLocaleDateString(language === 'ja' ? 'ja-JP' : 'en-US', {
              weekday: 'long',
              month: 'short',
              day: 'numeric',
              year: 'numeric',
            })}
          </p>
        </div>
        <button
          onClick={() => setShowCreate(true)}
          className="px-4 py-2 bg-primary text-primary-foreground text-sm font-bold hover:bg-primary/90 transition-colors"
        >
          {t.tasks.newTask}
        </button>
      </header>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
        <StatCard title={t.overview.totalTasks} value={stats.total} />
        <StatCard
          title={t.overview.tasksPendingReview}
          value={stats.needsReview}
          alert={stats.needsReview > 0}
        />
        <StatCard title={t.overview.availablePeople} value={stats.available} />
        <StatCard title={t.overview.completedThisWeek} value={stats.completedWeek} />
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-8">
        <StatCard
          title={t.performance.completionRate}
          value={
            performanceKpis.completionRate == null
              ? '—'
              : `${Math.round(performanceKpis.completionRate * 100)}%`
          }
        />
        <StatCard
          title={t.performance.avgCycleTime}
          value={
            performanceKpis.avgCycleMinutes == null
              ? '—'
              : performanceKpis.avgCycleMinutes >= 60 * 24
                ? `${Math.round(performanceKpis.avgCycleMinutes / (60 * 24))}${t.performance.days}`
                : `${Math.round(performanceKpis.avgCycleMinutes / 60)}${t.performance.hours}`
          }
        />
        <StatCard
          title={t.performance.onTimeDelivery}
          value={performanceKpis.onTime == null ? '—' : `${Math.round(performanceKpis.onTime * 100)}%`}
        />
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-3 gap-8">
        <div className="xl:col-span-2 space-y-8">
          {/* High Priority Tasks */}
          <section>
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-[10px] font-bold uppercase tracking-widest text-muted-foreground font-mono">
                {t.overview.highPriorityTasks}
              </h3>
              <button
                onClick={() => navigate('/tasks')}
                className="text-primary text-xs font-bold hover:underline underline-offset-4"
              >
                {t.overview.viewAll}
              </button>
            </div>
            <div className="bg-card border border-border overflow-hidden">
              {highPriorityTasks.length === 0 ? (
                <p className="px-6 py-5 text-sm text-muted-foreground">
                  {t.overview.noHighPriorityTasks}
                </p>
              ) : (
                <div className="divide-y divide-border">
                  {highPriorityTasks.map((task, idx) => {
                    const Icon = iconForIdx[idx % iconForIdx.length];
                    const overdue = isOverdue(task.due_date);
                    return (
                      <div
                        key={task.id}
                        onClick={() => setSelectedTask(task)}
                        className="flex items-center gap-4 px-5 py-3.5 hover:bg-muted/40 transition-colors cursor-pointer group"
                      >
                        <div className="flex-shrink-0 w-8 h-8 flex items-center justify-center bg-destructive/10 text-destructive">
                          <Icon className="w-4 h-4" />
                        </div>
                        <div className="flex-1 min-w-0">
                          <p className="text-sm font-semibold text-foreground truncate">
                            {task.title}
                          </p>
                          <p className="text-xs text-muted-foreground">
                            {task.due_date ? (
                              <>
                                {t.overview.due} {formatDate(task.due_date)} •{' '}
                                <span
                                  className={cn(
                                    'font-medium',
                                    overdue ? 'text-destructive' : 'text-warning',
                                  )}
                                >
                                  {overdue ? t.taskModal.overdue : t.overview.highPriority}
                                </span>
                              </>
                            ) : (
                              <span className="text-destructive font-medium">
                                {t.overview.highPriority}
                              </span>
                            )}
                          </p>
                        </div>
                        <div
                          className={cn(
                            'w-2 h-2 flex-shrink-0',
                            task.status === 'in_progress' ? 'bg-warning' : 'bg-muted-foreground/30',
                          )}
                        />
                      </div>
                    );
                  })}
                </div>
              )}
            </div>
          </section>

          {/* Completed Per Week Chart */}
          <section>
            <h3 className="text-[10px] font-bold uppercase tracking-widest text-muted-foreground font-mono mb-4">
              {t.performance.completedPerWeek}
            </h3>
            <div className="bg-card border border-border p-6 h-[260px]">
              <ResponsiveContainer
                width="100%"
                height="100%"
                minWidth={0}
                initialDimension={{ width: 320, height: 260 }}
              >
                <BarChart data={chartData} margin={{ top: 0, right: 0, left: -20, bottom: 0 }}>
                  <CartesianGrid
                    strokeDasharray="3 3"
                    vertical={false}
                    stroke="hsl(var(--border))"
                  />
                  <XAxis
                    dataKey="name"
                    axisLine={false}
                    tickLine={false}
                    tick={{ fill: 'hsl(var(--muted-foreground))', fontSize: 10, fontWeight: 600 }}
                    dy={10}
                  />
                  <YAxis
                    axisLine={false}
                    tickLine={false}
                    tick={{ fill: 'hsl(var(--muted-foreground))', fontSize: 10, fontWeight: 600 }}
                    allowDecimals={false}
                  />
                  <Tooltip
                    cursor={{ fill: 'hsl(var(--muted))' }}
                    contentStyle={{
                      background: 'hsl(var(--popover))',
                      border: '1px solid hsl(var(--border))',
                      borderRadius: 0,
                      boxShadow: 'none',
                    }}
                  />
                  <Bar dataKey="value" radius={[2, 2, 0, 0]} barSize={36}>
                    {chartData.map((_, index) => (
                      <Cell
                        key={`cell-${index}`}
                        fill={index === todayIdx ? 'hsl(var(--primary))' : 'hsl(var(--muted))'}
                      />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>
          </section>

          {/* Per Person Performance */}
          <section>
            <h3 className="text-[10px] font-bold uppercase tracking-widest text-muted-foreground font-mono mb-4">
              {t.performance.perPersonPerformance}
            </h3>
            <div className="bg-card border border-border overflow-x-auto">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>{t.performance.person}</TableHead>
                    <TableHead className="text-right">{t.performance.tasksCompleted}</TableHead>
                    <TableHead className="text-right">{t.performance.avgCycleTime}</TableHead>
                    <TableHead className="text-right">{t.performance.onTimeDelivery}</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {perPersonPerformance.length === 0 ? (
                    <TableRow>
                      <TableCell colSpan={4} className="py-10 text-center text-muted-foreground">
                        {t.common.noData}
                      </TableCell>
                    </TableRow>
                  ) : (
                    perPersonPerformance.map((row) => (
                      <TableRow key={row.personId}>
                        <TableCell className="font-medium">{row.name}</TableCell>
                        <TableCell className="text-right">{row.completed}</TableCell>
                        <TableCell className="text-right">
                          {row.avgCycleMinutes == null
                            ? '—'
                            : row.avgCycleMinutes >= 60 * 24
                              ? `${Math.round(row.avgCycleMinutes / (60 * 24))}${t.performance.days}`
                              : `${Math.round(row.avgCycleMinutes / 60)}${t.performance.hours}`}
                        </TableCell>
                        <TableCell className="text-right">
                          {row.onTime == null ? '—' : `${Math.round(row.onTime * 100)}%`}
                        </TableCell>
                      </TableRow>
                    ))
                  )}
                </TableBody>
              </Table>
            </div>
          </section>

          {/* Feedback Analytics */}
          <section>
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-[10px] font-bold uppercase tracking-widest text-muted-foreground font-mono">
                {t.overview.feedbackAnalytics}
              </h3>
              <select
                value={feedbackPeriod}
                onChange={(e) => setFeedbackPeriod(e.target.value as FeedbackPeriod)}
                className="bg-background border border-border text-xs font-bold px-3 py-1.5 focus:ring-1 focus:ring-primary outline-none text-foreground"
              >
                <option value="day">{t.overview.daily}</option>
                <option value="week">{t.overview.weekly}</option>
                <option value="month">{t.overview.monthly}</option>
              </select>
            </div>

            <div className="bg-card border border-border p-5 space-y-5">
              {isFeedbackLoading ? (
                <p className="text-sm text-muted-foreground">{t.overview.loadingFeedback}</p>
              ) : !hasFeedbackData ? (
                <p className="text-sm text-muted-foreground">{t.overview.noFeedbackYet}</p>
              ) : (
                <>
                  <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                    <div className="border border-border bg-success/10 p-4">
                      <p className="text-[10px] font-bold uppercase tracking-widest font-mono text-success">
                        {t.overview.acceptRate}
                      </p>
                      <p className="mt-1 text-2xl font-bold text-success tabular-nums">
                        {formatPercent(latestFeedbackRates.accept_rate)}
                      </p>
                    </div>
                    <div className="border border-border bg-destructive/10 p-4">
                      <p className="text-[10px] font-bold uppercase tracking-widest font-mono text-destructive">
                        {t.overview.rejectRate}
                      </p>
                      <p className="text-2xl font-bold text-destructive mt-1 tabular-nums">
                        {formatPercent(latestFeedbackRates.reject_rate)}
                      </p>
                    </div>
                    <div className="border border-border bg-warning/10 p-4">
                      <p className="text-[10px] font-bold uppercase tracking-widest font-mono text-warning">
                        {t.overview.editRate}
                      </p>
                      <p className="mt-1 text-2xl font-bold text-warning tabular-nums">
                        {formatPercent(latestFeedbackRates.edit_rate)}
                      </p>
                    </div>
                  </div>

                  <div className="h-[240px]">
                    <ResponsiveContainer
                      width="100%"
                      height="100%"
                      minWidth={0}
                      initialDimension={{ width: 320, height: 240 }}
                    >
                      <BarChart
                        data={feedbackTrendData}
                        margin={{ top: 0, right: 0, left: -20, bottom: 0 }}
                      >
                        <CartesianGrid
                          strokeDasharray="3 3"
                          vertical={false}
                          stroke="hsl(var(--border))"
                        />
                        <XAxis
                          dataKey="name"
                          axisLine={false}
                          tickLine={false}
                          tick={{ fill: 'hsl(var(--muted-foreground))', fontSize: 10, fontWeight: 600 }}
                          dy={10}
                        />
                        <YAxis
                          axisLine={false}
                          tickLine={false}
                          tick={{ fill: 'hsl(var(--muted-foreground))', fontSize: 10, fontWeight: 600 }}
                          domain={[0, 100]}
                        />
                        <Tooltip
                          cursor={{ fill: 'hsl(var(--muted))' }}
                          contentStyle={{
                            background: 'hsl(var(--popover))',
                            border: '1px solid hsl(var(--border))',
                            borderRadius: 0,
                            boxShadow: 'none',
                          }}
                          // eslint-disable-next-line @typescript-eslint/no-explicit-any
                          formatter={(value: any) => [`${value}%`]}
                        />
                        <Bar dataKey="accept_rate" fill="hsl(var(--success))" radius={[2, 2, 0, 0]} />
                        <Bar dataKey="reject_rate" fill="hsl(var(--destructive))" radius={[2, 2, 0, 0]} />
                        <Bar dataKey="edit_rate" fill="hsl(var(--warning))" radius={[2, 2, 0, 0]} />
                      </BarChart>
                    </ResponsiveContainer>
                  </div>

                  <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
                    <div>
                      <h4 className="text-[10px] font-bold uppercase tracking-widest font-mono text-muted-foreground mb-3">
                        {t.overview.perFieldAccuracy}
                      </h4>
                      <div className="space-y-1.5">
                        {(feedbackAnalytics?.field_accuracy ?? []).map((metric) => (
                          <div
                            key={metric.field}
                            className="flex items-center justify-between text-xs border border-border px-3 py-2"
                          >
                            <span className="font-medium text-muted-foreground">
                              {fieldLabel(metric.field)}
                            </span>
                            <span className="font-bold text-foreground tabular-nums">
                              {formatPercent(metric.accuracy_rate)} ({metric.accurate_count}/
                              {metric.total_considered})
                            </span>
                          </div>
                        ))}
                      </div>
                    </div>

                    <div>
                      <h4 className="text-[10px] font-bold uppercase tracking-widest font-mono text-muted-foreground mb-3">
                        {t.overview.assigneeRecommendation}
                      </h4>
                      <div className="space-y-1.5 text-xs">
                        {[
                          [
                            t.overview.top1,
                            feedbackAnalytics?.assignee_accuracy.top_1_rate,
                            feedbackAnalytics?.assignee_accuracy.top_1_count,
                          ],
                          [
                            t.overview.top2,
                            feedbackAnalytics?.assignee_accuracy.top_2_rate,
                            feedbackAnalytics?.assignee_accuracy.top_2_count,
                          ],
                          [
                            t.overview.top3,
                            feedbackAnalytics?.assignee_accuracy.top_3_rate,
                            feedbackAnalytics?.assignee_accuracy.top_3_count,
                          ],
                          [
                            t.overview.notRecommended,
                            feedbackAnalytics?.assignee_accuracy.not_recommended_rate,
                            feedbackAnalytics?.assignee_accuracy.not_recommended_count,
                          ],
                          [
                            t.taskModal.unassigned,
                            feedbackAnalytics?.assignee_accuracy.unassigned_rate,
                            feedbackAnalytics?.assignee_accuracy.unassigned_count,
                          ],
                        ].map(([label, rate, count]) => (
                          <div
                            key={label as string}
                            className="flex items-center justify-between border border-border px-3 py-2"
                          >
                            <span className="font-medium text-muted-foreground">{label as string}</span>
                            <span className="font-bold text-foreground tabular-nums">
                              {formatPercent((rate as number) ?? 0)} ({(count as number) ?? 0})
                            </span>
                          </div>
                        ))}
                      </div>
                    </div>
                  </div>
                </>
              )}
            </div>
          </section>
        </div>

        {/* Right Column */}
        <div className="xl:col-span-1">
          {/* Forecast */}
          <section className="mb-8">
            <h3 className="text-[10px] font-bold uppercase tracking-widest text-muted-foreground font-mono mb-4">
              {t.forecast.title}
            </h3>
            <div className="bg-card border border-border p-5 space-y-3">
              <div className="flex items-center justify-between">
                <span className="text-[10px] font-bold uppercase tracking-widest font-mono text-muted-foreground">
                  {t.forecast.remaining}
                </span>
                <span className="text-2xl font-bold text-foreground tabular-nums">{forecast.remaining}</span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-[10px] font-bold uppercase tracking-widest font-mono text-muted-foreground">
                  {t.forecast.velocity}
                </span>
                <span className="text-sm font-bold text-foreground">
                  {forecast.velocityPerWeek > 0
                    ? `${forecast.velocityPerWeek.toFixed(1)}${t.forecast.perWeek}`
                    : t.forecast.notEnoughData}
                </span>
              </div>
              <div className="pt-3 border-t border-border flex items-center justify-between">
                <span className="text-[10px] font-bold uppercase tracking-widest font-mono text-muted-foreground">
                  {t.forecast.projected}
                </span>
                <span className="text-sm font-bold text-foreground">
                  {forecast.projectedDate
                    ? forecast.projectedDate.toLocaleDateString(
                        language === 'ja' ? 'ja-JP' : 'en-US',
                        { year: 'numeric', month: 'short', day: 'numeric' },
                      )
                    : '—'}
                </span>
              </div>
              <div className="text-xs text-muted-foreground">
                {t.forecast.hint}
              </div>
            </div>
          </section>

          {/* Needs Review */}
          <section>
            <h3 className="text-[10px] font-bold uppercase tracking-widest text-muted-foreground font-mono mb-4">
              {t.overview.needsReviewSection}
            </h3>
            {needsReviewTasks.length === 0 ? (
              <div className="bg-card border border-border p-5 text-center">
                <p className="text-muted-foreground text-sm">{t.overview.allTasksReviewed}</p>
              </div>
            ) : (
              <div className="flex xl:flex-col gap-4 overflow-x-auto xl:overflow-x-visible custom-scrollbar pb-4 xl:pb-0">
                {needsReviewTasks.map((task) => (
                  <div
                    key={task.id}
                    onClick={() => setSelectedTask(task)}
                    className="min-w-[260px] xl:min-w-0 bg-card border border-border p-4 hover:bg-muted/30 transition-colors cursor-pointer"
                  >
                    <div className="flex justify-between items-start mb-3">
                      <span className="bg-primary text-primary-foreground text-[10px] font-bold px-2 py-0.5 uppercase tracking-wide">
                        {t.overview.reviewNow}
                      </span>
                      <span
                        className={cn(
                          'text-[10px] font-bold uppercase px-2 py-0.5',
                          task.priority === 'high'
                            ? 'bg-destructive/10 text-destructive'
                            : 'bg-muted text-muted-foreground',
                        )}
                      >
                        {t.priority[task.priority]}
                      </span>
                    </div>
                    <h4 className="font-bold text-sm mb-1 text-foreground line-clamp-2">
                      {task.title}
                    </h4>
                    {task.description && (
                      <p className="text-xs text-muted-foreground line-clamp-2 mb-3 leading-relaxed">
                        {task.description}
                      </p>
                    )}
                    {task.assignee_id && (
                      <p className="text-xs text-muted-foreground">
                        {t.overview.assignedTo}{' '}
                        <span className="font-bold text-foreground">
                          {peopleMap[task.assignee_id] ?? '—'}
                        </span>
                      </p>
                    )}
                  </div>
                ))}
              </div>
            )}
          </section>
        </div>
      </div>
    </div>
  );
}
