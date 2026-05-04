import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { fetchRules, createRule, updateRule, deleteRule } from '@/lib/api';
import { useToast } from '@/hooks/useToast';
import type { NLRule, CreateNLRulePayload, UpdateNLRulePayload } from "@/types";

// Natural Language Rules Hooks
export function useRules(includeInactive: boolean = true) {
  return useQuery({
    queryKey: ["rules", includeInactive],
    queryFn: () => fetchRules(includeInactive),
    refetchInterval: 30000,
  });
}

export function useCreateRule() {
  const queryClient = useQueryClient();
  const { toast } = useToast();

  return useMutation({
    mutationFn: (rule: CreateNLRulePayload) => createRule(rule),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["rules"] });
      toast({
        title: "Rule Created",
        description: "The rule has been created successfully",
      });
    },
    onError: (error: Error) => {
      toast({
        title: "Failed to Create Rule",
        description: error.message || "Could not create the rule",
        variant: "destructive",
      });
    },
  });
}

export function useUpdateRule() {
  const queryClient = useQueryClient();
  const { toast } = useToast();

  return useMutation({
    mutationFn: ({ id, ...rule }: { id: string } & UpdateNLRulePayload) => updateRule(id, rule),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["rules"] });
      toast({
        title: "Rule Updated",
        description: "The rule has been updated successfully",
      });
    },
    onError: (error: Error) => {
      toast({
        title: "Failed to Update Rule",
        description: error.message || "Could not update the rule",
        variant: "destructive",
      });
    },
  });
}

export function useDeleteRule() {
  const queryClient = useQueryClient();
  const { toast } = useToast();

  return useMutation({
    mutationFn: deleteRule,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["rules"] });
      toast({
        title: "Rule Deleted",
        description: "The rule has been removed",
      });
    },
    onError: (error: Error) => {
      toast({
        title: "Failed to Delete Rule",
        description: error.message || "Could not delete the rule",
        variant: "destructive",
      });
    },
  });
}

export function useToggleRuleActive() {
  const queryClient = useQueryClient();
  const { toast } = useToast();

  return useMutation({
    mutationFn: ({ id, is_active }: { id: string; is_active: boolean }) => 
      updateRule(id, { is_active }),
    onSuccess: (data: NLRule) => {
      queryClient.invalidateQueries({ queryKey: ["rules"] });
      toast({
        title: data.is_active ? "Rule Enabled" : "Rule Disabled",
        description: `Rule is now ${data.is_active ? "enabled" : "disabled"}`,
      });
    },
    onError: (error: Error) => {
      toast({
        title: "Failed to Update Rule",
        description: error.message || "Could not toggle rule status",
        variant: "destructive",
      });
    },
  });
}
