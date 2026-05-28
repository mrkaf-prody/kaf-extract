import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import {
  Key, BarChart3, Zap, ArrowUpRight, Clock,
  Copy, Check, RefreshCw, LogOut, Activity,
} from 'lucide-react';
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, BarChart, Bar,
} from 'recharts';

// ─── Types ────────────────────────────────────────────────────────────────

interface ApiKey {
  id: string;
  label: string;
  key_prefix: string;
  created_at: string;
  last_used_at: string | null;
  status: 'active' | 'revoked';
}

interface UsagePoint {
  date: string;
  calls: number;
}

interface PlanInfo {
  name: string;
  daily_limit: number;
  rate_limit: number;
  features: string[];
}

// ─── Mock data ────────────────────────────────────────────────────────────
// TODO: Replace with real API calls when backend endpoints are available

const MOCK_API_KEYS: ApiKey[] = [
  {
    id: '1',
    label: 'Production',
    key_prefix: 'kaf_live_',
    created_at: '2025-03-15T10:30:00Z',
    last_used_at: '2026-05-28T14:22:00Z',
    status: 'active',
  },
  {
    id: '2',
    label: 'Development',
    key_prefix: 'kaf_test_',
    created_at: '2025-06-01T08:00:00Z',
    last_used_at: '2026-05-27T22:10:00Z',
    status: 'active',
  },
  {
    id: '3',
    label: 'Old Key',
    key_prefix: 'kaf_live_',
    created_at: '2024-11-01T12:00:00Z',
    last_used_at: null,
    status: 'revoked',
  },
];

const MOCK_PLAN: PlanInfo = {
  name: 'Hobby',
  daily_limit: 1000,
  rate_limit: 100,
  features: [
    'Up to 1,000 requests/day',
    'CSS selector extraction',
    'AI extraction (kimi-k2.6)',
    'Screenshot capture',
    'Markdown export',
    'CSV export',
    'Batch extraction (up to 10 URLs)',
  ],
};

function generateUsageData(): UsagePoint[] {
  const data: UsagePoint[] = [];
  const now = new Date();
  for (let i = 29; i >= 0; i--) {
    const d = new Date(now);
    d.setDate(d.getDate() - i);
    data.push({
      date: d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' }),
      calls: Math.floor(Math.random() * 800) + 50,
    });
  }
  return data;
}

// ─── Dashboard Page ───────────────────────────────────────────────────────

export const DashboardPage: React.FC = () => {
  const { user, logout } = useAuth();
  const navigate = useNavigate();

  // TODO: Replace mock data with real API calls
  // const { apiFetch } = useAuth();
  // apiFetch('/v1/me/keys').then(setKeys);
  // apiFetch('/v1/me/usage').then(setUsage);
  // apiFetch('/v1/me/plan').then(setPlan);

  const [apiKeys] = useState<ApiKey[]>(MOCK_API_KEYS);
  const [plan] = useState<PlanInfo>(MOCK_PLAN);
  const [usageData] = useState<UsagePoint[]>(() => generateUsageData());
  const [copiedId, setCopiedId] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  // Simulate loading
  useEffect(() => {
    setLoading(true);
    const t = setTimeout(() => setLoading(false), 600);
    return () => clearTimeout(t);
  }, []);

  const totalCalls = usageData.reduce((s, p) => s + p.calls, 0);
  const avgDaily = Math.round(totalCalls / usageData.length);
  const percentUsed = Math.round((avgDaily / plan.daily_limit) * 100);

  const handleCopy = (label: string) => {
    setCopiedId(label);
    // TODO: Real key retrieval via API
    navigator.clipboard.writeText('kaf_live_xxxxxxxxxxxxx');
    setTimeout(() => setCopiedId(null), 2000);
  };

  const handleRefresh = () => {
    setLoading(true);
    // TODO: Re-fetch data from API
    setTimeout(() => setLoading(false), 600);
  };

  if (!user) {
    return (
      <div className="flex items-center justify-center h-screen text-slate-400 bg-slate-950">
        Please sign in to view your dashboard.
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-slate-950">
      {/* ─── Navbar ─── */}
      <nav className="sticky top-0 z-10 bg-slate-900/95 backdrop-blur border-b border-slate-800">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex items-center justify-between h-16">
            <div className="flex items-center gap-3">
              <h1 className="text-lg font-bold text-white">Kaf Extract</h1>
              <span className="text-xs text-slate-500 bg-slate-800 px-2 py-0.5 rounded">
                Dashboard
              </span>
            </div>
            <div className="flex items-center gap-4">
              <span className="text-sm text-slate-400 hidden sm:block">
                {user.email}
              </span>
              <button
                onClick={() => navigate('/admin')}
                className="text-xs text-slate-400 hover:text-blue-400 transition-colors"
              >
                Admin
              </button>
              <button
                onClick={logout}
                className="flex items-center gap-1 text-xs text-slate-500 hover:text-red-400 transition-colors"
              >
                <LogOut size={14} />
                Sign out
              </button>
            </div>
          </div>
        </div>
      </nav>

      {/* ─── Content ─── */}
      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-8">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-2xl font-bold text-white">
              Welcome, {user.name || user.email}
            </h2>
            <p className="text-sm text-slate-400 mt-1">
              Manage your API keys and monitor usage
            </p>
          </div>
          <button
            onClick={handleRefresh}
            className="flex items-center gap-2 px-3 py-1.5 text-sm text-slate-400 bg-slate-900 border border-slate-800 rounded-lg hover:bg-slate-800 transition-colors"
          >
            <RefreshCw size={14} className={loading ? 'animate-spin' : ''} />
            Refresh
          </button>
        </div>

        {/* ─── Plan Card ─── */}
        <div className="bg-slate-900 border border-slate-800 rounded-xl p-6">
          <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
            <div className="flex items-start gap-4">
              <div className="p-2.5 bg-blue-600/20 rounded-lg">
                <Zap size={24} className="text-blue-400" />
              </div>
              <div>
                <h3 className="text-lg font-semibold text-white">
                  {plan.name} Plan
                </h3>
                <p className="text-sm text-slate-400 mt-1">
                  {plan.daily_limit.toLocaleString()} requests/day ·{' '}
                  {plan.rate_limit} req/min rate limit
                </p>
                <div className="flex flex-wrap gap-2 mt-3">
                  {plan.features.slice(0, 4).map((f) => (
                    <span
                      key={f}
                      className="text-xs text-slate-300 bg-slate-800 px-2 py-0.5 rounded-full"
                    >
                      {f}
                    </span>
                  ))}
                  {plan.features.length > 4 && (
                    <span className="text-xs text-slate-500 bg-slate-800 px-2 py-0.5 rounded-full">
                      +{plan.features.length - 4} more
                    </span>
                  )}
                </div>
              </div>
            </div>
            <button
              onClick={() => {
                // TODO: Navigate to upgrade/pricing page or open Stripe checkout
                alert('Upgrade flow coming soon!');
              }}
              className="flex items-center gap-2 px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white text-sm font-medium rounded-lg transition-colors shrink-0"
            >
              Upgrade Plan
              <ArrowUpRight size={14} />
            </button>
          </div>

          {/* Usage bar */}
          <div className="mt-5">
            <div className="flex items-center justify-between text-sm mb-2">
              <span className="text-slate-400">
                Avg daily usage: <span className="text-white font-medium">{avgDaily.toLocaleString()}</span> / {plan.daily_limit.toLocaleString()}
              </span>
              <span className={`font-medium ${percentUsed > 80 ? 'text-amber-400' : 'text-emerald-400'}`}>
                {percentUsed}%
              </span>
            </div>
            <div className="w-full bg-slate-800 rounded-full h-2.5">
              <div
                className={`h-2.5 rounded-full transition-all ${
                  percentUsed > 80 ? 'bg-amber-500' : 'bg-blue-500'
                }`}
                style={{ width: `${Math.min(percentUsed, 100)}%` }}
              />
            </div>
          </div>
        </div>

        {/* ─── Usage Chart ─── */}
        <div className="bg-slate-900 border border-slate-800 rounded-xl p-6">
          <h3 className="text-sm font-semibold text-white mb-4 flex items-center gap-2">
            <Activity size={16} className="text-blue-400" />
            API Usage (Last 30 Days)
          </h3>
          {loading ? (
            <div className="flex items-center justify-center h-64 text-slate-500">
              <RefreshCw size={24} className="animate-spin mr-2" />
              Loading usage data...
            </div>
          ) : (
            <ResponsiveContainer width="100%" height={280}>
              <BarChart data={usageData}>
                <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
                <XAxis
                  dataKey="date"
                  stroke="#64748b"
                  fontSize={11}
                  tickLine={false}
                  interval="preserveStartEnd"
                />
                <YAxis stroke="#64748b" fontSize={11} tickLine={false} />
                <Tooltip
                  contentStyle={{
                    background: '#0f172a',
                    border: '1px solid #334155',
                    borderRadius: '8px',
                    color: '#e2e8f0',
                  }}
                />
                <Bar dataKey="calls" fill="#3b82f6" radius={[4, 4, 0, 0]} name="API Calls" />
              </BarChart>
            </ResponsiveContainer>
          )}
          <div className="flex gap-6 mt-4 text-sm">
            <div>
              <span className="text-slate-500">Total (30d): </span>
              <span className="text-white font-medium">{totalCalls.toLocaleString()}</span>
            </div>
            <div>
              <span className="text-slate-500">Avg/day: </span>
              <span className="text-white font-medium">{avgDaily.toLocaleString()}</span>
            </div>
            <div>
              <span className="text-slate-500">Peak: </span>
              <span className="text-white font-medium">
                {Math.max(...usageData.map((d) => d.calls)).toLocaleString()}
              </span>
            </div>
          </div>
        </div>

        {/* ─── API Keys Table ─── */}
        <div className="bg-slate-900 border border-slate-800 rounded-xl overflow-hidden">
          <div className="px-6 py-4 border-b border-slate-800 flex items-center justify-between">
            <h3 className="text-sm font-semibold text-white flex items-center gap-2">
              <Key size={16} className="text-blue-400" />
              API Keys
            </h3>
            <button
              onClick={() => {
                // TODO: POST /api/v1/keys to create a new key
                alert('Create key flow coming soon!');
              }}
              className="text-xs px-3 py-1.5 bg-blue-600 hover:bg-blue-700 text-white rounded-lg transition-colors"
            >
              + Create Key
            </button>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full text-left">
              <thead>
                <tr className="border-b border-slate-800 text-xs text-slate-500 uppercase">
                  <th className="px-6 py-3 font-medium">Label</th>
                  <th className="px-6 py-3 font-medium">Prefix</th>
                  <th className="px-6 py-3 font-medium hidden sm:table-cell">
                    Created
                  </th>
                  <th className="px-6 py-3 font-medium hidden md:table-cell">
                    Last Used
                  </th>
                  <th className="px-6 py-3 font-medium">Status</th>
                  <th className="px-6 py-3 font-medium">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800">
                {apiKeys.map((key) => (
                  <tr
                    key={key.id}
                    className="hover:bg-slate-800/50 transition-colors"
                  >
                    <td className="px-6 py-3 text-sm text-white font-medium">
                      {key.label}
                    </td>
                    <td className="px-6 py-3 text-sm text-slate-400 font-mono">
                      {key.key_prefix}••••
                    </td>
                    <td className="px-6 py-3 text-sm text-slate-400 hidden sm:table-cell">
                      {new Date(key.created_at).toLocaleDateString()}
                    </td>
                    <td className="px-6 py-3 text-sm text-slate-400 hidden md:table-cell">
                      {key.last_used_at ? (
                        <span className="flex items-center gap-1">
                          <Clock size={12} />
                          {new Date(key.last_used_at).toLocaleDateString()}
                        </span>
                      ) : (
                        <span className="text-slate-600">Never</span>
                      )}
                    </td>
                    <td className="px-6 py-3 text-sm">
                      <span
                        className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium ${
                          key.status === 'active'
                            ? 'bg-emerald-900/30 text-emerald-400'
                            : 'bg-red-900/30 text-red-400'
                        }`}
                      >
                        {key.status}
                      </span>
                    </td>
                    <td className="px-6 py-3">
                      <button
                        onClick={() => handleCopy(key.label)}
                        className="flex items-center gap-1 text-xs text-slate-400 hover:text-blue-400 transition-colors"
                      >
                        {copiedId === key.label ? (
                          <>
                            <Check size={12} className="text-emerald-400" />
                            <span className="text-emerald-400">Copied!</span>
                          </>
                        ) : (
                          <>
                            <Copy size={12} />
                            Copy
                          </>
                        )}
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {apiKeys.length === 0 && (
            <div className="px-6 py-12 text-center text-slate-500">
              <Key size={32} className="mx-auto mb-3 opacity-50" />
              <p>No API keys yet. Create one to start using the API.</p>
            </div>
          )}
        </div>
      </main>
    </div>
  );
};
