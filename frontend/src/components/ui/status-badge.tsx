import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";
import { Loader2 } from "lucide-react";
import type { Email, Assignment } from "@/types";
import { useLanguage } from "@/i18n/LanguageContext";

type EmailStatus = Email['status'];
type AssignmentStatus = Assignment['status'];
type Status = EmailStatus | AssignmentStatus;

interface StatusBadgeProps {
  status: Status;
  className?: string;
}

const statusStyles: Record<string, string> = {
  // Common statuses
  pending: "bg-muted text-muted-foreground border-transparent",
  processing: "bg-warning text-warning-foreground border-transparent",
  analyzed: "bg-warning text-warning-foreground border-transparent",
  assigned: "bg-primary text-primary-foreground border-transparent",
  completed: "bg-success text-success-foreground border-transparent",
  error: "bg-destructive text-destructive-foreground border-transparent",
  // Less common
  in_progress: "bg-warning text-warning-foreground border-transparent",
  reassigned: "bg-secondary text-secondary-foreground border-transparent",
  cancelled: "bg-muted text-muted-foreground border-transparent",
  accepted: "bg-success text-success-foreground border-transparent",
  ignored: "bg-destructive text-destructive-foreground border-transparent",
  hold: "bg-secondary text-secondary-foreground border-transparent",
  no_action: "bg-muted text-muted-foreground border-transparent",
};

export function StatusBadge({ status, className }: StatusBadgeProps) {
  const { t } = useLanguage();
  const isProcessing = status === "processing";

  return (
    <Badge
      variant="outline"
      className={cn(
        "font-medium capitalize border whitespace-nowrap",
        statusStyles[status] || statusStyles.pending,
        className
      )}
    >
      {isProcessing && <Loader2 className="h-3 w-3 mr-1 animate-spin" />}
      {t.statuses[status as keyof typeof t.statuses] || status}
    </Badge>
  );
}

// Level badge for employees
type Level = 'veteran' | 'general' | 'newcomer';

interface LevelBadgeProps {
  level: Level;
  className?: string;
}

const levelStyles: Record<Level, string> = {
  veteran: "bg-primary text-primary-foreground border-transparent",
  general: "bg-secondary text-secondary-foreground border-transparent",
  newcomer: "bg-accent text-accent-foreground border-transparent",
};

export function LevelBadge({ level, className }: LevelBadgeProps) {
  const { t } = useLanguage();

  return (
    <Badge
      variant="outline"
      className={cn(
        "font-medium border",
        levelStyles[level],
        className
      )}
    >
      {t.levels[level]}
    </Badge>
  );
}
