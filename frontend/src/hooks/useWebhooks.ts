import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { 
  getWebhooks, 
  createWebhook, 
  updateWebhook, 
  deleteWebhook, 
  testWebhook,
  getWebhookLogs
} from '../api/webhooks';

export function useWebhooks(workspaceId?: string) {
  const queryClient = useQueryClient();

  const webhooksQuery = useQuery({
    queryKey: ['webhooks', workspaceId],
    queryFn: () => workspaceId ? getWebhooks(workspaceId) : Promise.resolve([]),
    enabled: !!workspaceId,
  });

  const createMutation = useMutation({
    mutationFn: (data: { target_url: string; event_type: string; secret: string }) => 
      workspaceId ? createWebhook(workspaceId, data) : Promise.reject(new Error('No workspaceId')),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['webhooks', workspaceId] });
    },
  });

  const updateMutation = useMutation({
    mutationFn: ({ id, data }: { id: string; data: any }) => updateWebhook(id, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['webhooks', workspaceId] });
    },
  });

  const deleteMutation = useMutation({
    mutationFn: deleteWebhook,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['webhooks', workspaceId] });
    },
  });

  const testMutation = useMutation({
    mutationFn: testWebhook,
  });

  return {
    webhooks: webhooksQuery.data ?? [],
    isLoading: webhooksQuery.isLoading,
    isError: webhooksQuery.isError,
    error: webhooksQuery.error,
    createWebhook: createMutation.mutateAsync,
    updateWebhook: updateMutation.mutateAsync,
    deleteWebhook: deleteMutation.mutateAsync,
    testWebhook: testMutation.mutateAsync,
    isCreating: createMutation.isPending,
    isUpdating: updateMutation.isPending,
    isDeleting: deleteMutation.isPending,
    isTesting: testMutation.isPending,
  };
}

export function useWebhookLogs(id: string | null) {
  return useQuery({
    queryKey: ['webhook-logs', id],
    queryFn: () => id ? getWebhookLogs(id) : Promise.resolve([]),
    enabled: !!id,
  });
}
