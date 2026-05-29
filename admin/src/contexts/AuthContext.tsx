import React, { createContext, useContext, useState, useEffect, useCallback, useRef } from 'react';

interface User {
  id: string;
  email: string;
  name: string | null;
  role: string;
  status: string;
  created_at: string;
  totp_enabled?: boolean;
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
  const initRef = useRef(false);

  const fetchMe = useCallback(async (t: string) => {
    try {
      const res = await fetch(`${API_BASE}/auth/me`, {
        headers: { Authorization: `Bearer ${t}` },
      });
      if (res.ok) {
        const u = await res.json();
        setUser(u);
        localStorage.setItem('user_cache', JSON.stringify(u));
        return;
      }
    } catch (e) {
      console.error('fetchMe error:', e);
    }
    localStorage.removeItem('access_token');
    localStorage.removeItem('refresh_token');
    localStorage.removeItem('user_cache');
    setToken(null);
    setUser(null);
  }, []);

  useEffect(() => {
    if (initRef.current) return;
    initRef.current = true;
    const t = localStorage.getItem('access_token');
    if (!t) { setLoading(false); return; }
    setToken(t);
    const cached = localStorage.getItem('user_cache');
    if (cached) { try { setUser(JSON.parse(cached)); } catch {} }
    fetchMe(t).finally(() => setLoading(false));
  }, []);

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
    if (data.requires_2fa) {
      throw new Error(data.message || '2FA required');
    }
    localStorage.setItem('access_token', data.access_token);
    localStorage.setItem('refresh_token', data.refresh_token);
    if (data.user) {
      setUser(data.user);
      localStorage.setItem('user_cache', JSON.stringify(data.user));
    }
    setToken(data.access_token);
  };

  const logout = () => {
    localStorage.removeItem('access_token');
    localStorage.removeItem('refresh_token');
    localStorage.removeItem('user_cache');
    setToken(null);
    setUser(null);
  };

  const apiFetch = useCallback(async (path: string, opts: RequestInit = {}) => {
    const currentToken = localStorage.getItem('access_token');
    const headers: Record<string, string> = {
      ...(opts.headers as Record<string, string> || {}),
    };
    if (currentToken) headers['Authorization'] = `Bearer ${currentToken}`;
    if (!(opts.body instanceof FormData)) headers['Content-Type'] = 'application/json';

    // Normalize legacy /v1/* paths to /api/v1/* so backend matches
    const normalizedPath = path.startsWith('/v1/') ? `/api${path}` : path;

    const res = await fetch(`${API_BASE}${normalizedPath}`, { ...opts, headers });
    if (res.status === 401) {
      logout();
      throw new Error('Session expired');
    }
    if (!res.ok) {
      const e = await res.json().catch(() => ({ detail: 'Request failed' }));
      throw new Error(e.detail || 'Request failed');
    }
    return res.json();
  }, []);

  return (
    <AuthContext.Provider value={{ user, token, login, logout, loading, apiFetch }}>
      {children}
    </AuthContext.Provider>
  );
};
