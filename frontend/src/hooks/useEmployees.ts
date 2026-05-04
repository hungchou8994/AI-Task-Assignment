import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { fetchEmployees, toggleEmployeeAvailability } from '@/lib/api';
import { useToast } from '@/hooks/useToast';

function extractErrorMessage(error: unknown, fallback: string): string {
  if (error instanceof Error) return error.message || fallback;
  return fallback;
}

// Employees List
export function useEmployees() {
  return useQuery({
    queryKey: ['employees'],
    queryFn: fetchEmployees,
    refetchInterval: 120000,
  });
}

// Toggle Employee Availability Mutation
export function useToggleAvailability() {
  const queryClient = useQueryClient();
  const { toast } = useToast();

  return useMutation({
    mutationFn: ({
      employeeId,
      request,
    }: {
      employeeId: string;
      request: { is_available: boolean; reason?: string };
    }) => toggleEmployeeAvailability(employeeId, request),
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ["employees"] });
      queryClient.invalidateQueries({ queryKey: ["dashboard-summary"] });
      toast({
        title: "勤務状態を更新しました",
        description: data.message,
      });
    },
    onError: (error: unknown) => {
      toast({
        title: "更新に失敗しました",
        description: extractErrorMessage(error, 'Failed to toggle availability'),
        variant: "destructive",
      });
    },
  });
}
