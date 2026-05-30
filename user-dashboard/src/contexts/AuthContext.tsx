import React, { createContext, useContext, useState, useEffect, useCallback, useRef } from 'react';

interface User {
  id: string;
  email: string;
  name: string | null;
  role: string;
  status: string;
  totp_enabled?: boolean;
  created_at?: string;
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
  setUser: (u: User) => void;
}

const AuthContext = createContext<AuthCtx>(null!);
export const useAuth = () => useContext(AuthContext);

const API_BASE = '';  // Same domain — use relative paths

// ─── Token helpers ────────────────────────────────────────────────

function parseJwtPayload(token: string): Record<string, any> | null {
  try {
    const base64 = token.split('.')[1];
    const json = atob(base64.replace(/-/g, '+').replace(/_/g, '/'));
    return JSON.parse(json);
  } catch {
    return null;
  }
}

/** Returns true if the JWT expires within `bufferMs` of now. */
function isTokenExpiringSoon(token: string, bufferMs = 60_000): boolean {
  const payload = parseJwtPayload(token);
  if (!payload?.exp) return false; // no exp claim → assume valid
  const expiresAt = payload.exp * 1000; // exp is in seconds
  return Date.now() >= expiresAt - bufferMs;
}

// ─── Provider ─────────────────────────────────────────────────────

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [user, setUser] = useState<User | null>(() => {
    try {
      const raw = localStorage.getItem('user_cache');
      return raw ? JSON.parse(raw) : null;
    } catch { return null; }
  });
  const [token, setToken] = useState<string | null>(localStorage.getItem('access_token'));
  const [loading, setLoading] = useState(true);
  const [toasts, setToasts] = useState<Toast[]>([]);
  const toastIdRef = useRef(0);

  // Ref to always have the latest token inside async closures
  const tokenRef = useRef<string | null>(token);
  useEffect(() => { tokenRef.current = token; }, [token]);

  const showError = useCallback((msg: string) => {
    const id = ++toastIdRef.current;
    setToasts(prev => [...prev, { id, type: 'error', message: msg }]);
    setTimeout(() => setToasts(prev => prev.filter(t => t.id !== id)), 4000);
  }, []);

  const showSuccess = useCallback((msg: string) => {
    const id = ++toastIdRef.current;
    setToasts(prev => [...prev, { id, type: 'success', message: msg }]);
    setTimeout(() => setToasts(prev => prev.filter(t => t.id !== id)), 4000);
  }, []);

  // ─── Token refresh ────────────────────────────────────────────

  const performRefresh = useCallback(async (): Promise<boolean> => {
    const refreshToken = localStorage.getItem('refresh_token');
    if (!refreshToken) return false;

    try {
      const res = await fetch(`${API_BASE}/auth/refresh`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ refresh_token: refreshToken }),
      });

      if (!res.ok) return false;

      const data = await res.json();
      // Store new token pair (rotation)
      localStorage.setItem('access_token', data.access_token);
      localStorage.setItem('refresh_token', data.refresh_token);
      setToken(data.access_token);
      tokenRef.current = data.access_token;

      // Update user if returned
      if (data.user) {
        setUser(data.user);
        localStorage.setItem('user_cache', JSON.stringify(data.user));
      }

      return true;
    } catch {
      return false;
    }
  }, []);

  /** Ensure we have a valid token. Refresh if expiring soon. Returns current token or null. */
  const ensureValidToken = useCallback(async (): Promise<string | null> => {
    const currentToken = tokenRef.current;
    if (!currentToken) return null;

    // If token is expiring within 60s, refresh proactively
    if (isTokenExpiringSoon(currentToken, 60_000)) {
      const refreshed = await performRefresh();
      if (refreshed) return tokenRef.current;
      // If refresh failed but token isn't expired yet, still use it
      if (!isTokenExpiringSoon(currentToken, 0)) return currentToken;
      return null;
    }

    return currentToken;
  }, [performRefresh]);

  // ─── Fetch /auth/me ─────────────────────────────────────────

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
      // If 401, try refresh
      if (res.status === 401) {
        const refreshed = await performRefresh();
        if (refreshed && tokenRef.current) {
          const retry = await fetch(`${API_BASE}/auth/me`, {
            headers: { Authorization: `Bearer ${tokenRef.current}` },
          });
          if (retry.ok) {
            const u = await retry.json();
            setUser(u);
            localStorage.setItem('user_cache', JSON.stringify(u));
            return;
          }
        }
      }
    } catch {}
    // Only clear if refresh also failed
    localStorage.removeItem('access_token');
    localStorage.removeItem('refresh_token');
    localStorage.removeItem('user_cache');
    setToken(null);
    setUser(null);
  }, [performRefresh]);

  useEffect(() => {
    if (token) {
      const cached = localStorage.getItem('user_cache');
      if (!cached) {
        fetchMe(token).finally(() => setLoading(false));
      } else {
        setLoading(false);
      }
    } else {
      setLoading(false);
    }
  }, [token, fetchMe]);

  // ─── Login ──────────────────────────────────────────────────

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
    tokenRef.current = data.access_token;

    if (data.user) {
      setUser(data.user);
      localStorage.setItem('user_cache', JSON.stringify(data.user));
    } else {
      await fetchMe(data.access_token);
    }
  };

  // ─── Init session (OAuth / 2FA) ─────────────────────────────

  const initSession = async (accessToken: string) => {
    localStorage.setItem('access_token', accessToken);
    setToken(accessToken);
    tokenRef.current = accessToken;
    await fetchMe(accessToken);
  };

  // ─── Logout ─────────────────────────────────────────────────

  const logout = () => {
    localStorage.removeItem('access_token');
    localStorage.removeItem('refresh_token');
    localStorage.removeItem('user_cache');
    setToken(null);
    tokenRef.current = null;
    setUser(null);
  };

  // ─── API fetch with auto-refresh ────────────────────────────

  const apiFetch = async (path: string, opts: RequestInit = {}) => {
    // Ensure we have a valid token before the request
    const validToken = await ensureValidToken();

    const headers: Record<string, string> = {
      ...(opts.headers as Record<string, string> || {}),
    };
    if (validToken) headers['Authorization'] = `Bearer ${validToken}`;
    if (!(opts.body instanceof FormData)) headers['Content-Type'] = 'application/json';

    const res = await fetch(`${API_BASE}${path}`, { ...opts, headers });

    // If 401, try one refresh attempt before giving up
    if (res.status === 401) {
      const refreshed = await performRefresh();
      if (refreshed && tokenRef.current) {
        // Retry with new token
        headers['Authorization'] = `Bearer ${tokenRef.current}`;
        const retry = await fetch(`${API_BASE}${path}`, { ...opts, headers });
        if (retry.ok) return retry.json();
        if (retry.status === 401) {
          // Refresh worked but endpoint still rejects — user-level issue
          const e = await retry.json().catch(() => ({ detail: 'Authentication failed' }));
          throw new Error(e.detail);
        }
        // Other errors on retry
        const e = await retry.json().catch(() => ({ detail: 'Request failed' }));
        throw new Error(e.detail);
      }
      // Refresh failed — hard logout
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
    <AuthContext.Provider value={{ user, token, login, logout, loading, apiFetch, showError, showSuccess, initSession, setUser }}>
      {children}
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
