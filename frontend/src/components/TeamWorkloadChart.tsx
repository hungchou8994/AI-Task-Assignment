import { ResponsiveContainer, BarChart, Bar, XAxis, YAxis, Tooltip } from "recharts";
import { GlassCard } from "@/components/ui/glass-card";
import { LevelBadge } from "@/components/ui/status-badge";
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible";
import { Button } from "@/components/ui/button";
import { ChevronDown, Users } from "lucide-react";
import { useState } from "react";
import { useLanguage } from "@/i18n/LanguageContext";

interface AssigneeData {
  name: string;
  assignments: number;
  level: "veteran" | "general" | "newcomer";
}

interface TeamWorkloadChartProps {
  data: AssigneeData[];
  title?: string;
  collapsible?: boolean;
  defaultOpen?: boolean;
}

export function TeamWorkloadChart({
  data,
  title = "Team Workload",
  collapsible = true,
  defaultOpen = false
}: TeamWorkloadChartProps) {
  const { t } = useLanguage();
  const [isOpen, setIsOpen] = useState(defaultOpen);

  const chartContent = (
    <div className="h-48">
      {data.length > 0 ? (
        <ResponsiveContainer width="100%" height="100%">
          <BarChart 
            data={data} 
            layout="vertical"
            margin={{ top: 5, right: 30, left: 80, bottom: 5 }}
          >
            <XAxis type="number" stroke="hsl(var(--muted-foreground))" />
            <YAxis 
              type="category" 
              dataKey="name" 
              stroke="hsl(var(--muted-foreground))"
              tick={{ fill: 'hsl(var(--foreground))', fontSize: 12 }}
            />
            <Tooltip
              contentStyle={{
                backgroundColor: 'hsl(var(--card))',
                border: '1px solid hsl(var(--border))',
                borderRadius: '0.75rem',
              }}
              // eslint-disable-next-line @typescript-eslint/no-explicit-any
              formatter={(value: any) => [`${value} ${t.employees.tasks}`, t.assignments.assignee]}
            />
            <Bar 
              dataKey="assignments" 
              fill="hsl(var(--primary))" 
              radius={[0, 8, 8, 0]}
            />
          </BarChart>
        </ResponsiveContainer>
      ) : (
        <div className="h-full flex items-center justify-center text-muted-foreground">
          {t.common.noData}
        </div>
      )}
    </div>
  );

  if (!collapsible) {
    return (
      <GlassCard>
        <h3 className="text-lg font-semibold mb-4 text-foreground flex items-center gap-2">
          <Users className="h-5 w-5 text-primary" />
          {title}
        </h3>
        {chartContent}
      </GlassCard>
    );
  }

  return (
    <Collapsible open={isOpen} onOpenChange={setIsOpen}>
      <GlassCard className="p-0 overflow-hidden">
        <CollapsibleTrigger asChild>
          <Button 
            variant="ghost" 
            className="w-full flex items-center justify-between p-4 hover:bg-primary/5 rounded-none"
          >
            <span className="text-lg font-semibold text-foreground flex items-center gap-2">
              <Users className="h-5 w-5 text-primary" />
              {title}
            </span>
            <ChevronDown 
              className={`h-5 w-5 text-muted-foreground transition-transform duration-200 ${
                isOpen ? "rotate-180" : ""
              }`} 
            />
          </Button>
        </CollapsibleTrigger>
        <CollapsibleContent>
          <div className="px-4 pb-4">
            {chartContent}
          </div>
        </CollapsibleContent>
      </GlassCard>
    </Collapsible>
  );
}