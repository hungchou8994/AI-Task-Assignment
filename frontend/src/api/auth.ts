import { api } from './client';
import type { User, UserAuthPayload } from '../types';

export const register = (payload: UserAuthPayload) =>
  api.post<User>('/api/auth/register', payload);

export const login = (payload: UserAuthPayload) => api.post<User>('/api/auth/login', payload);

export const logout = () => api.post<void>('/api/auth/logout', {});

export const me = () => api.get<User>('/api/auth/me');
