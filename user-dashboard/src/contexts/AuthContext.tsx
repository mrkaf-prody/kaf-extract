import React, { createContext, useContext, useState, useEffect, useCallback } from 'react';

interface User {
  id: string;
  email: string;
  name: string | null;
  role: string;
  status: string;
  created_at: string;
}

interface AuthCtx {
  user: User | null;
  token: string | null;
  login: (email: string, password: string) => Promise<void>;
  logout: () => void;
  loading: boolean;
  apiFetch: (path: string, opts?: RequestInit) => Promise<any>;
}

const AuthContext = createContext<AuthCtx>(null!);
export const useAuth = () => useContext(AuthContext);

const API_BASE = 'https://extract.kafcenter.com';

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [user, setUser] = useState<User | null>(null);
  const [token, setToken] = useState<string | null>(localStorage.getItem('access_token'));
  const [loading, setLoading] = useState(true);

  const fetchMe = useCallback(async (t: string) => {
    try {
      const res = await fetch(`${API_BASE}/auth/me`, {
        headers: { Authorization: `Bearer ${t}` },
      });
      if (res.ok) {
        const u = await res.json();
        setUser(u);
        return;
      }
    } catch {}
    localStorage.removeItem('access_token');
    localStorage.removeItem('refresh_token');
    setToken(null);
    setUser(null);
  }, []);

  useEffect(() => {
    if (token) {
      fetchMe(token).finally(() => setLoading(false));
    } else {
      setLoading(false);
    }
  }, [token, fetchMe]);

  const login = async (email: string, password: string) => {
    const res = await fetch(`${API_BASE}/auth/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email, password }),
    });
    if (!res.ok) {
      const e = await res.json();
      throw new Error(e.detail || 'Login failed');
    }
    const data = await res.json();
    localStorage.setItem('access_token', data.access_token);
    localStorage.setItem('refresh_token', data.refresh_token);
    setToken(data.access_token);
    await fetchMe(data.access_token);
  };

  const logout = () => {
    localStorage.removeItem('access_token');
    localStorage.removeItem('refresh_token');
    setToken(null);
    setUser(null);
  };

  const apiFetch = async (path: string, opts: RequestInit = {}) => {
    const headers: Record<string, string> = {
      ...(opts.headers as Record<string, string> || {}),
    };
    if (token) headers['Authorization'] = `Bearer ${token}`;
    if (!(opts.body instanceof FormData)) headers['Content-Type'] = 'application/json';
    const res = await fetch(`${API_BASE}${path}`, { ...opts, headers });
    if (res.status === 401) {
      logout();
      throw new Error('Session expired');
    }
    if (!res.ok) {
      const e = await res.json().catch(() => ({ detail: 'Request failed' }));
      throw new Error(e.detail);
    }
    return res.json();
  };

  return (
    <AuthContext.Provider value={{ user, token, login, logout, loading, apiFetch }}>
      {children}
    </AuthContext.Provider>
  );
};
