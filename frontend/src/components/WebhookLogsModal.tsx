import { Loader2, AlertCircle, Clock, CheckCircle2, XCircle } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import { useLanguage } from "@/i18n/LanguageContext";
import { useWebhookLogs } from "@/hooks/useWebhooks";
import { format } from "date-fns";

interface WebhookLogsModalProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  webhookId: string | null;
}

export function WebhookLogsModal({
  open,
  onOpenChange,
  webhookId,
}: WebhookLogsModalProps) {
  const { t } = useLanguage();
  const { data: logs = [], isLoading, isError } = useWebhookLogs(webhookId);

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-4xl max-h-[80vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>{t.webhooks.deliveryLogs}</DialogTitle>
          <DialogDescription>
            {t.webhooks.subtitle}
          </DialogDescription>
        </DialogHeader>

        <div className="py-4">
          {isLoading ? (
            <div className="flex flex-col items-center justify-center py-12">
              <Loader2 className="h-8 w-8 animate-spin text-primary mb-4" />
              <p className="text-sm text-muted-foreground">{t.common.loading}</p>
            </div>
          ) : isError ? (
            <div className="flex flex-col items-center justify-center py-12 text-muted-foreground text-center">
              <AlertCircle className="h-10 w-10 mb-4 text-destructive" />
              <p className="text-lg font-medium">{t.common.error}</p>
              <p className="text-sm">Failed to load logs</p>
            </div>
          ) : logs.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-12 text-muted-foreground text-center">
              <Clock className="h-10 w-10 mb-4 opacity-50" />
              <p className="font-medium">{t.webhooks.noLogs}</p>
            </div>
          ) : (
            <div className="border rounded-lg overflow-hidden">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Event ID</TableHead>
                    <TableHead>{t.webhooks.status}</TableHead>
                    <TableHead>{t.webhooks.response}</TableHead>
                    <TableHead>{t.webhooks.time}</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {logs.map((log) => (
                    <TableRow key={log.id}>
                      <TableCell>
                        <span className="text-xs font-mono text-muted-foreground">
                          {log.event_id.substring(0, 8)}...
                        </span>
                      </TableCell>
                      <TableCell>
                        <div className="flex items-center gap-2">
                          {log.status === "success" ? (
                            <CheckCircle2 className="h-4 w-4 text-green-500" />
                          ) : (
                            <XCircle className="h-4 w-4 text-destructive" />
                          )}
                          <span className={log.status !== "success" ? "text-destructive font-medium capitalize" : "capitalize"}>
                            {log.status}
                          </span>
                        </div>
                      </TableCell>
                      <TableCell>
                        <Badge variant={log.response_code && log.response_code < 400 ? "outline" : "destructive"} className="font-mono">
                          {log.response_code || "ERR"}
                        </Badge>
                      </TableCell>
                      <TableCell className="text-xs text-muted-foreground whitespace-nowrap">
                        {format(new Date(log.attempted_at), "MMM d, HH:mm:ss")}
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
          )}
        </div>

        <div className="flex justify-end pt-4">
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            {t.common.close}
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}
