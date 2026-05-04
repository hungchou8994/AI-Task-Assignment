import { useState } from "react";
import { 
  Plus, 
  Trash2, 
  ExternalLink, 
  History, 
  Play, 
  CheckCircle2, 
  Webhook as WebhookIcon,
  Loader2,
  AlertCircle,
  MoreVertical,
  Pencil
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Switch } from "@/components/ui/switch";
import { Badge } from "@/components/ui/badge";
import { GlassCard } from "@/components/ui/glass-card";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { useLanguage } from "@/i18n/LanguageContext";
import { useWorkspaceContext } from "@/context/WorkspaceContext";
import { useWebhooks } from "@/hooks/useWebhooks";
import { WebhookFormModal } from "@/components/WebhookFormModal";
import { WebhookLogsModal } from "@/components/WebhookLogsModal";
import { useToast } from "@/components/ui/use-toast";
import { format, isValid } from "date-fns";
import type { WebhookSubscription } from "@/api/webhooks";

export default function WebhooksSettings() {
  const { t } = useLanguage();
  const { toast } = useToast();
  const { currentWorkspaceId } = useWorkspaceContext();
  const { 
    webhooks, 
    isLoading, 
    isError, 
    createWebhook, 
    updateWebhook, 
    deleteWebhook, 
    testWebhook,
    isCreating,
    isUpdating,
    isDeleting,
    isTesting
  } = useWebhooks(currentWorkspaceId || undefined);

  const [formOpen, setFormOpen] = useState(false);
  const [logsOpen, setLogsOpen] = useState(false);
  const [selectedWebhook, setSelectedWebhook] = useState<WebhookSubscription | null>(null);
  const [deleteConfirmId, setDeleteConfirmId] = useState<string | null>(null);
  const [testingId, setTestingId] = useState<string | null>(null);

  const handleCreate = () => {
    setSelectedWebhook(null);
    setFormOpen(true);
  };

  const handleEdit = (webhook: WebhookSubscription) => {
    setSelectedWebhook(webhook);
    setFormOpen(true);
  };

  const handleShowLogs = (webhook: WebhookSubscription) => {
    setSelectedWebhook(webhook);
    setLogsOpen(true);
  };

  const handleSave = async (data: { target_url: string; event_type: string; secret: string }) => {
    try {
      if (selectedWebhook) {
        await updateWebhook({ id: selectedWebhook.id, data });
      } else {
        await createWebhook(data);
      }
      toast({
        title: t.webhooks.saveSuccess,
      });
    } catch (err) {
      toast({
        title: t.webhooks.saveError,
        variant: "destructive",
      });
    }
  };

  const handleToggleActive = async (webhook: WebhookSubscription) => {
    try {
      await updateWebhook({ id: webhook.id, data: { is_active: !webhook.is_active } });
    } catch (err) {
      toast({
        title: t.common.error,
        description: "Failed to update webhook status",
        variant: "destructive",
      });
    }
  };

  const handleDelete = async () => {
    if (deleteConfirmId) {
      try {
        await deleteWebhook(deleteConfirmId);
        toast({
          title: "Webhook deleted",
        });
      } catch (err) {
        toast({
          title: "Delete failed",
          variant: "destructive",
        });
      } finally {
        setDeleteConfirmId(null);
      }
    }
  };

  const handleTest = async (id: string) => {
    setTestingId(id);
    try {
      await testWebhook(id);
      toast({
        title: t.webhooks.testSuccess,
      });
    } catch (err) {
      toast({
        title: t.webhooks.testError,
        variant: "destructive",
      });
    } finally {
      setTestingId(null);
    }
  };

  const formatDateSafely = (dateStr: string) => {
    const date = new Date(dateStr);
    return isValid(date) ? format(date, "MMM d, HH:mm") : "---";
  };

  if (isError) {
    return (
      <div className="flex flex-col items-center justify-center py-16 text-muted-foreground">
        <AlertCircle className="h-12 w-12 mb-4 text-destructive" />
        <p className="text-lg font-medium">{t.common.error}</p>
        <p className="text-sm">Failed to load webhooks. Please try again.</p>
      </div>
    );
  }

  return (
    <div className="space-y-4 md:space-y-6 animate-in fade-in slide-in-from-bottom-2 duration-300">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 sm:gap-4">
        <div>
          <h1 className="text-xl md:text-2xl font-bold text-foreground flex items-center gap-2">
            <WebhookIcon className="h-5 w-5 md:h-6 md:w-6 text-primary" />
            {t.webhooks.title}
          </h1>
          <p className="text-sm text-muted-foreground mt-1">
            {t.webhooks.subtitle}
          </p>
        </div>
        <Button onClick={handleCreate} size="sm" className="gap-2 w-full sm:w-auto">
          <Plus className="h-4 w-4" />
          {t.webhooks.addWebhook}
        </Button>
      </div>

      {isLoading ? (
        <div className="flex flex-col items-center justify-center py-12">
          <Loader2 className="h-8 w-8 animate-spin text-primary mb-4" />
          <p className="text-sm text-muted-foreground">{t.common.loading}</p>
        </div>
      ) : webhooks.length === 0 ? (
        <GlassCard className="text-center py-12">
          <div className="flex flex-col items-center text-muted-foreground">
            <WebhookIcon className="h-12 w-12 mb-4 opacity-30" />
            <p className="text-lg font-medium">{t.webhooks.noWebhooks}</p>
            <p className="text-sm mt-1">{t.webhooks.createFirst}</p>
            <Button onClick={handleCreate} variant="outline" className="mt-6 gap-2">
              <Plus className="h-4 w-4" />
              {t.webhooks.addWebhook}
            </Button>
          </div>
        </GlassCard>
      ) : (
        <GlassCard className="p-0 overflow-hidden">
          <div className="overflow-x-auto">
            <Table>
              <TableHeader>
                <TableRow className="border-border/50 hover:bg-transparent">
                  <TableHead className="w-24 whitespace-nowrap">{t.webhooks.status}</TableHead>
                  <TableHead className="text-muted-foreground whitespace-nowrap">{t.webhooks.url}</TableHead>
                  <TableHead className="text-muted-foreground whitespace-nowrap">{t.webhooks.events}</TableHead>
                  <TableHead className="text-muted-foreground whitespace-nowrap">{t.webhooks.lastTriggered}</TableHead>
                  <TableHead className="w-24 text-right text-muted-foreground whitespace-nowrap">{t.webhooks.actions}</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {webhooks.map((webhook) => (
                  <TableRow 
                    key={webhook.id} 
                    className={`border-border/30 transition-colors hover:bg-primary/5 ${!webhook.is_active ? "opacity-60" : ""}`}
                  >
                    <TableCell>
                      <div className="flex items-center gap-2">
                        <Switch
                          checked={webhook.is_active}
                          onCheckedChange={() => handleToggleActive(webhook)}
                          disabled={isUpdating}
                        />
                        <span className="text-xs font-medium sr-only md:not-sr-only whitespace-nowrap">
                          {webhook.is_active ? t.webhooks.active : t.webhooks.inactive}
                        </span>
                      </div>
                    </TableCell>
                    <TableCell>
                      <div className="flex items-center gap-2 min-w-[200px]">
                        <span className="text-sm font-medium truncate max-w-[300px]" title={webhook.target_url}>
                          {webhook.target_url}
                        </span>
                        <a href={webhook.target_url} target="_blank" rel="noopener noreferrer" className="text-muted-foreground hover:text-primary transition-colors">
                          <ExternalLink className="h-3 w-3" />
                        </a>
                      </div>
                    </TableCell>
                    <TableCell>
                      <Badge variant="secondary" className="text-[10px] py-0 px-1.5 font-mono">
                        {webhook.event_type}
                      </Badge>
                    </TableCell>
                    <TableCell>
                      <div className="flex flex-col text-xs text-muted-foreground whitespace-nowrap">
                        <span className="flex items-center gap-1 text-foreground font-medium">
                          <CheckCircle2 className="h-3 w-3 text-green-500 opacity-50" />
                          {formatDateSafely(webhook.created_at)}
                        </span>
                      </div>
                    </TableCell>
                    <TableCell className="text-right">
                      <div className="flex items-center justify-end gap-1">
                        <Button
                          variant="ghost"
                          size="icon"
                          onClick={() => handleTest(webhook.id)}
                          className="h-8 w-8"
                          title={t.webhooks.test}
                          disabled={isTesting}
                        >
                          {isTesting && testingId === webhook.id ? <Loader2 className="h-4 w-4 animate-spin" /> : <Play className="h-4 w-4" />}
                        </Button>
                        <DropdownMenu>
                          <DropdownMenuTrigger asChild>
                            <Button variant="ghost" size="icon" className="h-8 w-8">
                              <MoreVertical className="h-4 w-4" />
                            </Button>
                          </DropdownMenuTrigger>
                          <DropdownMenuContent align="end">
                            <DropdownMenuItem onClick={() => handleEdit(webhook)} className="gap-2">
                              <Pencil className="h-4 w-4" />
                              {t.webhooks.edit}
                            </DropdownMenuItem>
                            <DropdownMenuItem onClick={() => handleShowLogs(webhook)} className="gap-2">
                              <History className="h-4 w-4" />
                              {t.webhooks.logs}
                            </DropdownMenuItem>
                            <DropdownMenuItem 
                              onClick={() => setDeleteConfirmId(webhook.id)} 
                              className="gap-2 text-destructive focus:text-destructive"
                            >
                              <Trash2 className="h-4 w-4" />
                              {t.webhooks.delete}
                            </DropdownMenuItem>
                          </DropdownMenuContent>
                        </DropdownMenu>
                      </div>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        </GlassCard>
      )}

      {/* Form Modal */}
      <WebhookFormModal
        open={formOpen}
        onOpenChange={setFormOpen}
        webhook={selectedWebhook}
        onSave={handleSave}
        isSaving={isCreating || isUpdating}
      />

      {/* Logs Modal */}
      <WebhookLogsModal
        open={logsOpen}
        onOpenChange={setLogsOpen}
        webhookId={selectedWebhook?.id || null}
      />

      {/* Delete Confirmation Dialog */}
      <AlertDialog open={!!deleteConfirmId} onOpenChange={() => setDeleteConfirmId(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>{t.webhooks.deleteConfirm}</AlertDialogTitle>
            <AlertDialogDescription>
              {t.webhooks.deleteConfirmMsg}
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>{t.common.cancel}</AlertDialogCancel>
            <AlertDialogAction
              onClick={handleDelete}
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
              disabled={isDeleting}
            >
              {isDeleting && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              {t.common.delete}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}
