import { useQuery } from '@tanstack/react-query';
import { fetchSystemConfig } from '@/lib/api';

// System Config Query
export function useSystemConfig() {
  return useQuery({
    queryKey: ['system-config'],
    queryFn: fetchSystemConfig,
    staleTime: Infinity, // config rarely changes — only reload on page refresh
  });
}
