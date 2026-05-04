import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";
import { useLanguage } from "@/i18n/LanguageContext";
import type { EmailAnalysis } from "@/types";

type MailIntent = NonNullable<EmailAnalysis["mail_intent"]>;

const INTENT_STYLES: Record<MailIntent, string> = {
  quote_request:
    "bg-success/15 text-success border-success/30",
  quote_response:
    "bg-muted text-muted-foreground border-border",
  information_request:
    "bg-primary/10 text-primary border-primary/30",
  follow_up:
    "bg-warning/15 text-warning border-warning/30",
  confirmation:
    "bg-muted text-muted-foreground border-border",
  fyi: "bg-muted text-muted-foreground border-border",
};

interface IntentBadgeProps {
  intent: MailIntent | undefined | null;
  className?: string;
}

export function IntentBadge({ intent, className }: IntentBadgeProps) {
  const { t } = useLanguage();

  if (!intent) return null;

  const style = INTENT_STYLES[intent] ?? INTENT_STYLES.fyi;
  // Access mailIntents via type assertion since it's a new block
  const label =
    (t as unknown as { mailIntents: Record<string, string> }).mailIntents?.[intent] ?? intent;

  return (
    <Badge
      variant="outline"
      className={cn(
        "text-[10px] font-medium whitespace-nowrap px-1.5 py-0",
        style,
        className
      )}
    >
      {label}
    </Badge>
  );
}
