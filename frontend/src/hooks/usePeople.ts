import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { fetchPeople, createPerson, updatePerson, deletePerson } from '../api/people';
import type { PersonCreate, PersonUpdate } from '../types';

export const PEOPLE_KEY = ['people'] as const;

export function usePeople() {
  return useQuery({ queryKey: PEOPLE_KEY, queryFn: fetchPeople, staleTime: 30_000 });
}

export function useCreatePerson() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: PersonCreate) => createPerson(data),
    onSuccess: () => qc.invalidateQueries({ queryKey: PEOPLE_KEY }),
  });
}

export function useUpdatePerson() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: PersonUpdate }) => updatePerson(id, data),
    onSuccess: () => qc.invalidateQueries({ queryKey: PEOPLE_KEY }),
  });
}

export function useDeletePerson() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => deletePerson(id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: PEOPLE_KEY });
      qc.invalidateQueries({ queryKey: ['tasks'] });
    },
  });
}
