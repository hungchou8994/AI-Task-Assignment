import { useState, useEffect } from "react";
import { Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { useLanguage } from "@/i18n/LanguageContext";
import type { WebhookSubscription } from "@/api/webhooks";

interface WebhookFormModalProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  webhook: WebhookSubscription | null;
  onSave: (data: { target_url: string; event_type: string; secret: string }) => Promise<void>;
  isSaving: boolean;
}

const AVAILABLE_EVENTS = [
  "task.created",
  "task.updated",
  "task.completed",
  "candidate.approved",
  "candidate.rejected",
];

export function WebhookFormModal({
  open,
  onOpenChange,
  webhook,
  onSave,
  isSaving,
}: WebhookFormModalProps) {
  const { t } = useLanguage();
  const [url, setUrl] = useState("");
  const [eventType, setEventType] = useState("");
  const [secret, setSecret] = useState("");

  useEffect(() => {
    if (webhook) {
      setUrl(webhook.target_url);
      setEventType(webhook.event_type);
      setSecret(""); // In edit mode, we leave it empty unless rotating
    } else {
      setUrl("");
      setEventType("task.created");
      setSecret("");
    }
  }, [webhook, open]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!url || !eventType || (!webhook && !secret)) return;
    
    // For update, only send secret if it was provided
    const saveSecret = webhook && !secret ? undefined : secret;
    
    await onSave({ 
      target_url: url, 
      event_type: eventType, 
      secret: saveSecret as string 
    });
    onOpenChange(false);
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[425px]">
        <form onSubmit={handleSubmit}>
          <DialogHeader>
            <DialogTitle>
              {webhook ? t.webhooks.edit : t.webhooks.addWebhook}
            </DialogTitle>
            <DialogDescription>
              {t.webhooks.subtitle}
            </DialogDescription>
          </DialogHeader>

          <div className="grid gap-4 py-4">
            <div className="grid gap-2">
              <Label htmlFor="url">{t.webhooks.url}</Label>
              <Input
                id="url"
                value={url}
                onChange={(e) => setUrl(e.target.value)}
                placeholder="https://api.example.com/webhook"
                required
                type="url"
              />
            </div>

            <div className="grid gap-2">
              <Label htmlFor="event_type">{t.webhooks.events}</Label>
              <Select value={eventType} onValueChange={setEventType}>
                <SelectTrigger id="event_type">
                  <SelectValue placeholder="Select an event" />
                </SelectTrigger>
                <SelectContent>
                  {AVAILABLE_EVENTS.map((event) => (
                    <SelectItem key={event} value={event}>
                      {event}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            <div className="grid gap-2">
              <Label htmlFor="secret">
                {webhook ? "New Secret (optional)" : "Secret"}
              </Label>
              <Input
                id="secret"
                value={secret}
                onChange={(e) => setSecret(e.target.value)}
                placeholder={webhook ? "Leave blank to keep current" : "Webhook signing secret"}
                required={!webhook}
                type="password"
              />
              <p className="text-[10px] text-muted-foreground">
                {webhook 
                  ? "Only fill this if you want to rotate the signing secret." 
                  : "Used to sign the payload via HMAC-SHA256"}
              </p>
            </div>
          </div>

          <DialogFooter>
            <Button
              type="button"
              variant="outline"
              onClick={() => onOpenChange(false)}
              disabled={isSaving}
            >
              {t.common.cancel}
            </Button>
            <Button type="submit" disabled={isSaving || !url || !eventType || (!webhook && !secret)}>
              {isSaving && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              {t.common.save}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
