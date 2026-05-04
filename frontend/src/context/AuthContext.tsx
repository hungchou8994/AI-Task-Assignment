import React, { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react';
import { login, logout, me, register } from '../api/auth';
import type { User } from '../types';

type AuthActionPayload = { email: string; password: string };

type AuthContextValue = {
  user: User | null;
  loading: boolean;
  loginUser: (payload: AuthActionPayload) => Promise<void>;
  registerUser: (payload: AuthActionPayload) => Promise<void>;
  logoutUser: () => Promise<void>;
};

const AuthContext = createContext<AuthContextValue | undefined>(undefined);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let mounted = true;

    me()
      .then((currentUser) => {
        if (mounted) setUser(currentUser);
      })
      .catch(() => {
        if (mounted) setUser(null);
      })
      .finally(() => {
        if (mounted) setLoading(false);
      });

    return () => {
      mounted = false;
    };
  }, []);

  useEffect(() => {
    const handleUnauthorized = () => setUser(null);
    window.addEventListener('auth:unauthorized', handleUnauthorized);
    return () => window.removeEventListener('auth:unauthorized', handleUnauthorized);
  }, []);

  const loginUser = useCallback(async (payload: AuthActionPayload) => {
    const currentUser = await login(payload);
    setUser(currentUser);
  }, []);

  const registerUser = useCallback(async (payload: AuthActionPayload) => {
    const currentUser = await register(payload);
    setUser(currentUser);
  }, []);

  const logoutUser = useCallback(async () => {
    await logout();
    setUser(null);
  }, []);

  const value = useMemo(
    () => ({ user, loading, loginUser, registerUser, logoutUser }),
    [user, loading, loginUser, registerUser, logoutUser],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within AuthProvider');
  }
  return context;
}
