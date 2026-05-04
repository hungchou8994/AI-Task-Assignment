import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";
import { useLanguage } from "@/i18n/LanguageContext";
import type { EmailAnalysis } from "@/types";

type EmailType = EmailAnalysis["email_type"] | "unclassified";

const EMAIL_TYPE_STYLES: Record<EmailType, string> = {
  site_quote: "bg-warning text-warning-foreground border-transparent hover:bg-warning/90",
  single_quote: "bg-success text-success-foreground border-transparent hover:bg-success/90",
  catalog_request: "bg-primary text-primary-foreground border-transparent hover:bg-primary/90",
  sample_request: "bg-secondary text-secondary-foreground border-transparent hover:bg-secondary/90",
  other: "bg-muted text-muted-foreground border-transparent hover:bg-muted/80",
  unclassified: "bg-muted text-muted-foreground border-transparent hover:bg-muted/80",
};

interface EmailTypeBadgeProps {
  type: EmailType | undefined;
  className?: string;
}

export function EmailTypeBadge({ type, className }: EmailTypeBadgeProps) {
  const { t } = useLanguage();

  if (!type) {
    type = "unclassified";
  }

  const style = EMAIL_TYPE_STYLES[type] || EMAIL_TYPE_STYLES.other;
  const label = t.taskTypes[type as keyof typeof t.taskTypes] || t.taskTypes.other;

  return (
    <Badge 
      variant="outline" 
      className={cn("text-xs font-medium whitespace-nowrap", style, className)}
    >
      {label}
    </Badge>
  );
}
