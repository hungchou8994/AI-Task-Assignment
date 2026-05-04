import type { Person, PersonCreate, PersonUpdate } from '../types';
import { api } from './client';

export const fetchPeople = () => api.get<Person[]>('/api/people');
export const createPerson = (data: PersonCreate) => api.post<Person>('/api/people', data);
export const updatePerson = (id: string, data: PersonUpdate) => api.put<Person>(`/api/people/${id}`, data);
export const deletePerson = (id: string) => api.delete(`/api/people/${id}`);
