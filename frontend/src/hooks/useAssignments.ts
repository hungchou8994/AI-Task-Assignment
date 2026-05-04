import { useQuery, useMutation, useQueryClient, keepPreviousData } from '@tanstack/react-query';
import {
  fetchAssignments,
  processBatch,
  ingestEmails,
  bulkCompleteAssignments,
  markAssignmentAsCompleted,
  reassignAssignment,
} from '@/lib/api';
import { useToast } from '@/hooks/useToast';

function extractErrorMessage(error: unknown, fallback: string): string {
  if (error instanceof Error) return error.message || fallback;
  return fallback;
}

// Assignments List
export function useAssignments(
  assignmentStatuses: string[] = [],
  emailStatuses: string[] = [],
  page: number = 1,
  limit: number = 10,
  employeeIds: string[] = [],
  emailTypes: string[] = [],
  needsReview: boolean = false,
) {
  return useQuery({
    queryKey: ["assignments", assignmentStatuses, emailStatuses, page, limit, employeeIds, emailTypes, needsReview],
    queryFn: () => fetchAssignments(assignmentStatuses, emailStatuses, page, limit, employeeIds, emailTypes, needsReview),
    placeholderData: keepPreviousData,
    refetchInterval: 10000,
  });
}

// Process Batch Mutation
export function useProcessBatch() {
  const queryClient = useQueryClient();
  const { toast } = useToast();

  return useMutation({
    mutationFn: processBatch,
    onSuccess: (data) => {
      const processedCount =
        typeof data?.processed === "number"
          ? data.processed
          : typeof data?.assigned_count === "number"
          ? data.assigned_count
          : typeof data?.analyzed_count === "number"
          ? data.analyzed_count
          : 0;
      queryClient.invalidateQueries({ queryKey: ['assignments'] });
      queryClient.invalidateQueries({ queryKey: ['dashboard-summary'] });
      toast({
        title: 'Batch Processing Complete',
        description: `Successfully processed ${processedCount} emails`,
      });
    },
    onError: (error: Error) => {
      toast({
        title: 'Processing Failed',
        description: error.message || 'Failed to process batch',
        variant: 'destructive',
      });
    },
  });
}

// Ingest Emails Mutation
export function useIngestEmails() {
  const queryClient = useQueryClient();
  const { toast } = useToast();

  return useMutation({
    mutationFn: ingestEmails,
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ['assignments'] });
      queryClient.invalidateQueries({ queryKey: ['dashboard-summary'] });
      toast({
        title: 'Email Ingestion Complete',
        description: `Successfully ingested ${data.ingested} emails`,
      });
    },
    onError: (error: Error) => {
      toast({
        title: 'Ingestion Failed',
        description: error.message || 'Failed to ingest emails',
        variant: 'destructive',
      });
    },
  });
}

// Mark Assignment as Completed Mutation
export function useMarkAssignmentAsCompleted() {
  const queryClient = useQueryClient();
  const { toast } = useToast();

  return useMutation({
    mutationFn: (id: string) => markAssignmentAsCompleted(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['assignments'] });
      queryClient.invalidateQueries({ queryKey: ['dashboard-summary'] });
      queryClient.invalidateQueries({ queryKey: ['dashboard-analytics'] });
      toast({
        title: 'Assignment Completed',
        description: 'The assignment has been marked as completed successfully',
        variant: 'default',
      });
    },
    onError: (error: Error) => {
      toast({
        title: 'Action Failed',
        description: error.message || 'Failed to mark assignment as completed',
        variant: 'destructive',
      });
    },
  });
}

// Bulk Complete Assignments Mutation
export function useBulkCompleteAssignments() {
  const queryClient = useQueryClient();
  const { toast } = useToast();

  return useMutation({
    mutationFn: (ids: string[]) => bulkCompleteAssignments(ids),
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ['assignments'] });
      queryClient.invalidateQueries({ queryKey: ['dashboard-summary'] });
      queryClient.invalidateQueries({ queryKey: ['dashboard-analytics'] });
      const skipped = data.skipped_count > 0 ? ` (${data.skipped_count} skipped)` : '';
      toast({
        title: 'Tasks Completed',
        description: `${data.completed_count} assignment${data.completed_count !== 1 ? 's' : ''} marked as complete${skipped}`,
        variant: 'default',
      });
    },
    onError: (error: unknown) => {
      toast({
        title: 'Bulk Complete Failed',
        description: extractErrorMessage(error, 'Failed to complete assignments'),
        variant: 'destructive',
      });
    },
  });
}

// Reassign Assignment Mutation
export function useReassignAssignment() {
  const queryClient = useQueryClient();
  const { toast } = useToast();

  return useMutation({
    mutationFn: ({
      assignmentId,
      employeeId,
      reason,
      force = false,
    }: {
      assignmentId: string;
      employeeId: string;
      reason: string;
      force?: boolean;
    }) =>
      reassignAssignment(assignmentId, employeeId, reason, force),
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ["assignments"] });
      queryClient.invalidateQueries({ queryKey: ["dashboard-summary"] });
      queryClient.invalidateQueries({ queryKey: ["employees"] });
      toast({
        title: "Task Reassigned",
        description: data.message,
        variant: "default",
      });
    },
    onError: (error: unknown) => {
      toast({
        title: "Reassignment Failed",
        description: extractErrorMessage(error, 'Failed to reassign assignment'),
        variant: "destructive",
      });
    },
  });
}
