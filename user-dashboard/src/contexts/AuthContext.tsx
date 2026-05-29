import React, { createContext, useContext, useState, useEffect, useCallback, useRef } from 'react';

interface User {
  id: string;
  email: string;
  name: string | null;
  role: string;
  status: string;
  created_at: string;
}

interface Toast {
  id: number;
  type: 'error' | 'success';
  message: string;
}

interface AuthCtx {
  user: User | null;
  token: string | null;
  login: (email: string, password: string) => Promise<void>;
  logout: () => void;
  loading: boolean;
  apiFetch: (path: string, opts?: RequestInit) => Promise<any>;
  showError: (msg: string) => void;
  showSuccess: (msg: string) => void;
  initSession: (accessToken: string) => Promise<void>;
}

const AuthContext = createContext<AuthCtx>(null!);
export const useAuth = () => useContext(AuthContext);

const API_BASE = 'https://extract.kafcenter.com';

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [user, setUser] = useState<User | null>(null);
  const [token, setToken] = useState<string | null>(localStorage.getItem('access_token'));
  const [loading, setLoading] = useState(true);
  const [toasts, setToasts] = useState<Toast[]>([]);
  const toastIdRef = useRef(0);

  const showError = useCallback((msg: string) => {
    const id = ++toastIdRef.current;
    setToasts(prev => [...prev, { id, type: 'error', message: msg }]);
    setTimeout(() => {
      setToasts(prev => prev.filter(t => t.id !== id));
    }, 4000);
  }, []);

  const showSuccess = useCallback((msg: string) => {
    const id = ++toastIdRef.current;
    setToasts(prev => [...prev, { id, type: 'success', message: msg }]);
    setTimeout(() => {
      setToasts(prev => prev.filter(t => t.id !== id));
    }, 4000);
  }, []);

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

  const initSession = async (accessToken: string) => {
    localStorage.setItem('access_token', accessToken);
    setToken(accessToken);
    await fetchMe(accessToken);
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
    <AuthContext.Provider value={{ user, token, login, logout, loading, apiFetch, showError, showSuccess, initSession }}>
      {children}
      {/* Toast container */}
      <div className="fixed bottom-4 right-4 z-[9999] flex flex-col gap-2 pointer-events-none">
        {toasts.map(t => (
          <div
            key={t.id}
            className={`pointer-events-auto max-w-sm rounded-lg px-4 py-3 shadow-lg text-sm font-medium transition-all
              ${t.type === 'error'
                ? 'bg-red-900/90 border border-red-700 text-red-100'
                : 'bg-emerald-900/90 border border-emerald-700 text-emerald-100'
              }`}
          >
            {t.message}
          </div>
        ))}
      </div>
    </AuthContext.Provider>
  );
};
