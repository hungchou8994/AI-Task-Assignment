import { useState } from "react";
import { useDashboardAnalytics } from "@/hooks/use-api";
import type { DashboardPeriod } from "@/lib/api";
import type { EmployeePerformance } from "@/types";
import { GlassCard } from "@/components/ui/glass-card";
import { SkeletonCard, SkeletonChart } from "@/components/ui/skeleton-card";
import { cn } from "@/lib/utils";
import { useLanguage } from "@/i18n/LanguageContext";
import { Mail, CheckCircle2, Clock, Timer, ArrowUpDown } from "lucide-react";
import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from "recharts";
import { format, parseISO } from "date-fns";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

function ChangeBadge({ change }: { change: number | null }) {
  if (change === null) return null;
  const isPositive = change > 0;
  const isZero = change === 0;
  return (
    <span
      className={cn(
        "text-xs font-medium inline-flex items-center gap-0.5 mt-1",
        isPositive
          ? "text-success"
          : isZero
          ? "text-muted-foreground"
          : "text-destructive"
      )}
    >
      {isPositive ? "↑" : isZero ? "→" : "↓"}
      {Math.abs(change).toFixed(1)}%
    </span>
  );
}

function PeriodToggle({
  value,
  onChange,
  labels,
}: {
  value: DashboardPeriod;
  onChange: (p: DashboardPeriod) => void;
  labels: Record<DashboardPeriod, string>;
}) {
  return (
    <div className="flex rounded-lg border border-border overflow-hidden w-fit">
      {(["day", "week", "month"] as DashboardPeriod[]).map((p) => (
        <button
          key={p}
          onClick={() => onChange(p)}
          className={cn(
            "px-4 py-2 text-sm font-medium transition-colors",
            value === p
              ? "bg-primary text-primary-foreground"
              : "bg-background text-muted-foreground hover:bg-muted"
          )}
        >
          {labels[p]}
        </button>
      ))}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function formatXLabel(label: string, period: DashboardPeriod): string {
  try {
    if (period === "month") {
      return format(parseISO(label + "-01"), "yyyy/M");
    }
    return format(parseISO(label), "M/d");
  } catch {
    return label;
  }
}

// ---------------------------------------------------------------------------
// Main component
// ---------------------------------------------------------------------------

type SortColumn = "name" | "task_count" | "avg_handling_minutes";

export default function Dashboard() {
  const [period, setPeriod] = useState<DashboardPeriod>("week");
  const { data: analytics, isLoading } = useDashboardAnalytics(period);
  const { t } = useLanguage();

  const [sortCol, setSortCol] = useState<SortColumn>("task_count");
  const [sortDir, setSortDir] = useState<"asc" | "desc">("desc");

  function handleColumnSort(col: SortColumn) {
    if (sortCol !== col) {
      setSortCol(col);
      setSortDir("asc");
    } else if (sortDir === "asc") {
      setSortDir("desc");
    } else {
      setSortCol("task_count");
      setSortDir("desc");
    }
  }

  const sortedEmployees: EmployeePerformance[] = [
    ...(analytics?.employee_table ?? []),
  ].sort((a, b) => {
    if (sortCol === "task_count") {
      return sortDir === "asc"
        ? a.task_count - b.task_count
        : b.task_count - a.task_count;
    }
    if (sortCol === "avg_handling_minutes") {
      const aVal = a.avg_handling_minutes ?? Infinity;
      const bVal = b.avg_handling_minutes ?? Infinity;
      return sortDir === "asc" ? aVal - bVal : bVal - aVal;
    }
    // name
    return sortDir === "asc"
      ? a.name.localeCompare(b.name)
      : b.name.localeCompare(a.name);
  });

  // Loading skeleton on first load (no cached data yet)
  if (isLoading && !analytics) {
    return (
      <div className="space-y-6">
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 md:gap-4">
          {[...Array(4)].map((_, i) => (
            <SkeletonCard key={i} lines={1} />
          ))}
        </div>
        <SkeletonCard className="h-10 w-48" lines={0} hasIcon={false} />
        <SkeletonChart />
        <SkeletonChart />
      </div>
    );
  }

  const summaryCards = [
    {
      title: t.dashboard.totalReceived,
      value: analytics?.summary.total_received ?? 0,
      change: analytics?.summary.received_change ?? null,
      icon: Mail,
      color: "text-primary",
      bgColor: "bg-primary/10",
    },
    {
      title: t.dashboard.totalProcessed,
      value: analytics?.summary.total_processed ?? 0,
      change: analytics?.summary.processed_change ?? null,
      icon: CheckCircle2,
      color: "text-success",
      bgColor: "bg-success/10",
    },
    {
      title: t.dashboard.totalPending,
      value: analytics?.summary.total_pending ?? 0,
      change: analytics?.summary.pending_change ?? null,
      icon: Clock,
      color: "text-warning",
      bgColor: "bg-warning/10",
    },
    {
      title: t.dashboard.avgHandlingTime,
      value:
        analytics?.summary.avg_handling_minutes != null
          ? `${Math.round(analytics.summary.avg_handling_minutes)}${t.dashboard.minutes}`
          : "—",
      change: analytics?.summary.handling_time_change ?? null,
      icon: Timer,
      color: "text-secondary-foreground",
      bgColor: "bg-secondary",
    },
  ];

  return (
    <div className="space-y-4 md:space-y-6">
      {/* Page header */}
      <div>
        <h1 className="text-2xl md:text-3xl font-bold text-foreground">
          {t.dashboard.title}
        </h1>
        <p className="text-sm md:text-base text-muted-foreground">
          {t.dashboard.subtitle}
        </p>
      </div>

      {/* 1. Summary Cards */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 md:gap-4">
        {summaryCards.map((card) => (
          <GlassCard key={card.title} className="flex flex-col p-3 sm:p-6">
            <div className="flex items-center gap-2 sm:gap-4">
              <div
                className={cn(
                  "p-2 sm:p-3 rounded-lg sm:rounded-xl shrink-0",
                  card.bgColor
                )}
              >
                <card.icon className={cn("h-4 w-4 sm:h-6 sm:w-6", card.color)} />
              </div>
              <div className="min-w-0">
                <p className="text-xs sm:text-sm text-muted-foreground truncate">
                  {card.title}
                </p>
                <p className="text-lg sm:text-2xl font-bold text-foreground">
                  {card.value}
                </p>
              </div>
            </div>
            <ChangeBadge change={card.change} />
          </GlassCard>
        ))}
      </div>

      {/* 2. Period Toggle */}
      <div className="flex items-center gap-3">
        <PeriodToggle
          value={period}
          onChange={setPeriod}
          labels={{
            day: t.dashboard.day,
            week: t.dashboard.week,
            month: t.dashboard.month,
          }}
        />
      </div>

      {/* 3. Stacked Area Chart */}
      <GlassCard>
        <h3 className="text-lg font-semibold mb-4 text-foreground">
          {t.dashboard.emailVolumeOverTime}
        </h3>
        <div className="h-72">
          {(analytics?.chart_data?.length ?? 0) > 0 ? (
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart
                data={analytics!.chart_data}
                margin={{ top: 5, right: 10, left: 0, bottom: 5 }}
              >
                <CartesianGrid
                  strokeDasharray="3 3"
                  stroke="hsl(var(--border))"
                />
                <XAxis
                  dataKey="label"
                  stroke="hsl(var(--muted-foreground))"
                  tick={{ fill: "hsl(var(--muted-foreground))", fontSize: 12 }}
                  tickFormatter={(label) => formatXLabel(label, period)}
                />
                <YAxis
                  stroke="hsl(var(--muted-foreground))"
                  tick={{ fill: "hsl(var(--muted-foreground))", fontSize: 12 }}
                  allowDecimals={false}
                />
                <Tooltip
                  contentStyle={{
                    backgroundColor: "hsl(var(--card))",
                    border: "1px solid hsl(var(--border))",
                    borderRadius: "0.75rem",
                  }}
                  labelFormatter={(label) => formatXLabel(String(label), period)}
                />
                <Legend />
                <Area
                  type="monotone"
                  dataKey="received"
                  stackId="1"
                  stroke="hsl(245, 75%, 60%)"
                  fill="hsl(245, 75%, 60%)"
                  fillOpacity={0.3}
                  name={t.dashboard.received}
                />
                <Area
                  type="monotone"
                  dataKey="processed"
                  stackId="1"
                  stroke="hsl(145, 70%, 42%)"
                  fill="hsl(145, 70%, 42%)"
                  fillOpacity={0.3}
                  name={t.dashboard.processed}
                />
                <Area
                  type="monotone"
                  dataKey="pending"
                  stackId="1"
                  stroke="hsl(38, 92%, 55%)"
                  fill="hsl(38, 92%, 55%)"
                  fillOpacity={0.3}
                  name={t.dashboard.pending}
                />
              </AreaChart>
            </ResponsiveContainer>
          ) : (
            <div className="h-full flex items-center justify-center text-muted-foreground">
              {t.dashboard.noData}
            </div>
          )}
        </div>
      </GlassCard>

      {/* 4. Employee Performance Table */}
      <GlassCard>
        <h3 className="text-lg font-semibold mb-4 text-foreground">
          {t.dashboard.employeePerformance}
        </h3>
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead
                className="cursor-pointer hover:text-foreground select-none"
                onClick={() => handleColumnSort("name")}
              >
                <span className="flex items-center gap-1">
                  {t.dashboard.employee}
                  {sortCol === "name" && (
                    <ArrowUpDown className="h-3 w-3 opacity-60" />
                  )}
                </span>
              </TableHead>
              <TableHead
                className="cursor-pointer hover:text-foreground select-none text-right"
                onClick={() => handleColumnSort("task_count")}
              >
                <span className="flex items-center justify-end gap-1">
                  {t.dashboard.tasks}
                  {sortCol === "task_count" && (
                    <ArrowUpDown className="h-3 w-3 opacity-60" />
                  )}
                </span>
              </TableHead>
              <TableHead
                className="cursor-pointer hover:text-foreground select-none text-right"
                onClick={() => handleColumnSort("avg_handling_minutes")}
              >
                <span className="flex items-center justify-end gap-1">
                  {t.dashboard.avgTime}
                  {sortCol === "avg_handling_minutes" && (
                    <ArrowUpDown className="h-3 w-3 opacity-60" />
                  )}
                </span>
              </TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {sortedEmployees.length > 0 ? (
              sortedEmployees.map((emp) => (
                <TableRow key={emp.employee_id}>
                  <TableCell className="font-medium">{emp.name}</TableCell>
                  <TableCell className="text-right">{emp.task_count}</TableCell>
                  <TableCell className="text-right">
                    {emp.avg_handling_minutes != null
                      ? `${Math.round(emp.avg_handling_minutes)}${t.dashboard.minutes}`
                      : "—"}
                  </TableCell>
                </TableRow>
              ))
            ) : (
              <TableRow>
                <TableCell
                  colSpan={3}
                  className="text-center text-muted-foreground py-8"
                >
                  {t.dashboard.noData}
                </TableCell>
              </TableRow>
            )}
          </TableBody>
        </Table>
      </GlassCard>
    </div>
  );
}
