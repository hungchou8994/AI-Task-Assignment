import { api } from './client';

export interface WebhookSubscription {
  id: string;
  workspace_id: string;
  event_type: string;
  target_url: string;
  is_active: boolean;
  created_at: string;
  secret?: string;
}

export interface WebhookDeliveryLog {
  id: string;
  subscription_id: string;
  event_id: string;
  status: string;
  response_code: number | null;
  attempted_at: string;
}

export async function getWebhooks(workspaceId: string): Promise<WebhookSubscription[]> {
  return api.get(`/api/webhooks?workspace_id=${workspaceId}`);
}

export async function createWebhook(workspaceId: string, data: { target_url: string; event_type: string; secret: string }): Promise<WebhookSubscription> {
  return api.post(`/api/webhooks?workspace_id=${workspaceId}`, data);
}

export async function updateWebhook(id: string, data: Partial<WebhookSubscription>): Promise<WebhookSubscription> {
  return api.patch(`/api/webhooks/${id}`, data);
}

export async function deleteWebhook(id: string): Promise<void> {
  return api.delete(`/api/webhooks/${id}`);
}

export async function testWebhook(id: string): Promise<{ message: string }> {
  return api.post(`/api/webhooks/${id}/test`, {});
}

export async function getWebhookLogs(id: string): Promise<WebhookDeliveryLog[]> {
  return api.get(`/api/webhooks/${id}/deliveries`);
}
