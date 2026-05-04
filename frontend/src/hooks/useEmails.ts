import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { submitManualEmail, fetchEmailDetail, fetchEmailThread, processEmail } from '@/lib/api';
import { useToast } from '@/hooks/useToast';

function extractErrorMessage(error: unknown, fallback: string): string {
  if (error instanceof Error) return error.message || fallback;
  return fallback;
}

// Submit Manual Email Mutation
export function useSubmitManualEmail() {
  const queryClient = useQueryClient();
  const { toast } = useToast();

  return useMutation({
    mutationFn: submitManualEmail,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['assignments'] });
      queryClient.invalidateQueries({ queryKey: ['dashboard-summary'] });
      toast({
        title: 'Email Submitted',
        description: 'Your email has been added to the queue',
      });
    },
    onError: (error: Error) => {
      toast({
        title: 'Submission Failed',
        description: error.message || 'Failed to submit email',
        variant: 'destructive',
      });
    },
  });
}

// Email Detail Query
export function useEmailDetail(emailId: string | null | undefined) {
  return useQuery({
    queryKey: ['email-detail', emailId],
    queryFn: () => fetchEmailDetail(emailId!),
    enabled: !!emailId,
    staleTime: 60_000, // Cache for 1 minute — email bodies don't change
  });
}

export function useEmailThread(emailId: string | null, enabled: boolean = false) {
  return useQuery({
    queryKey: ['email-thread', emailId],
    queryFn: () => fetchEmailThread(emailId!),
    enabled: !!emailId && enabled,
    staleTime: 60_000,
  });
}

// Process Email Mutation
export function useProcessEmail() {
  const queryClient = useQueryClient();
  const { toast } = useToast();

  return useMutation({
    mutationFn: processEmail,
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ["assignments"] });
      queryClient.invalidateQueries({ queryKey: ["dashboard-summary"] });
      queryClient.invalidateQueries({ queryKey: ["employees"] });

      if (data.status === "ignored") {
        toast({
          title: "Email Ignored",
          description: data.reason || "Email was marked as ignored during processing",
          variant: "default",
        });
      } else {
        toast({
          title: "Email Processed",
          description: data.message,
          variant: "default",
        });
      }
    },
    onError: (error: unknown) => {
      toast({
        title: "Processing Failed",
        description: extractErrorMessage(error, 'Failed to process email'),
        variant: "destructive",
      });
    },
  });
}
