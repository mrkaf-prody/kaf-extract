import React, { useEffect, useState, useCallback } from 'react';
import { useAuth } from '../contexts/AuthContext';
import {
  Users, CreditCard, Activity, AlertTriangle,
  TrendingUp, TrendingDown, RefreshCw, Clock,
} from 'lucide-react';
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, Legend,
} from 'recharts';

// ─── Mock data (replace with real API calls when backend is ready) ───

interface StatCard {
  label: string;
  value: string;
  change: string;
  trend: 'up' | 'down';
  icon: React.FC<{ size?: number; className?: string }>;
}

interface ActivityItem {
  event: string;
  user: string;
  time: string;
}

const STAT_CARDS: StatCard[] = [];

function StatCards({ metrics }: { metrics: Record<string, any> | null }) {
  if (!metrics) return null;
  const cards = [
    { label: 'Total Users', value: metrics.total_users?.toLocaleString() || '0', change: '+0%', trend: 'up' as const, icon: Users },
    { label: 'Active Subscriptions', value: metrics.active_subscriptions?.toLocaleString() || '0', change: '+0%', trend: 'up' as const, icon: CreditCard },
    { label: 'API Calls Total', value: metrics.requests_total?.toLocaleString() || '0', change: '+0%', trend: 'up' as const, icon: Activity },
    { label: 'Error Rate', value: `${metrics.error_rate_percent?.toFixed(2) || '0'}%`, change: '-0%', trend: 'down' as const, icon: AlertTriangle },
  ];
  return (
    <>
      {cards.map((card) => (
        <div key={card.label} className="bg-slate-900 border border-slate-800 rounded-xl p-5 hover:border-slate-700 transition-colors">
          <div className="flex items-center justify-between mb-3">
            <card.icon size={20} className="text-blue-400" />
          </div>
          <p className="text-2xl font-bold text-white">{card.value}</p>
          <p className="text-xs text-slate-500 mt-1">{card.label}</p>
        </div>
      ))}
    </>
  );
}

function generateChartData(): { hour: string; calls: number; errors: number }[] {
  const data = [];
  for (let i = 0; i < 24; i++) {
    data.push({
      hour: `${i.toString().padStart(2, '0')}:00`,
      calls: Math.floor(Math.random() * 15000) + 2000,
      errors: Math.floor(Math.random() * 80) + 5,
    });
  }
  return data;
}

const RECENT_ACTIVITY: ActivityItem[] = [];

// ─── Page ───

export const OverviewPage: React.FC = () => {
  const { apiFetch } = useAuth();
  const [metrics, setMetrics] = useState<Record<string, any> | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [chartData, setChartData] = useState(() => generateChartData());

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [stats, systemMetrics] = await Promise.all([
        apiFetch('/api/v1/admin/stats').catch(() => null),
        apiFetch('/metrics').catch(() => null),
      ]);
      setMetrics({
        ...stats,
        ...systemMetrics,
        total_users: stats?.total_users ?? 0,
        active_subscriptions: stats?.active_subscriptions ?? 0,
        requests_total: systemMetrics?.requests_total ?? 0,
        error_count: systemMetrics?.error_count ?? 0,
        db_status: systemMetrics?.db_status ?? 'unknown',
        redis_status: systemMetrics?.redis_status ?? 'unknown',
        avg_duration_ms: systemMetrics?.avg_duration_ms ?? 0,
        queue_depth: systemMetrics?.queue_depth ?? 0,
        uptime_seconds: systemMetrics?.uptime_seconds ?? 0,
        cache_hits: systemMetrics?.cache_hits ?? 0,
        cache_misses: systemMetrics?.cache_misses ?? 0,
      });
    } catch (err: any) {
      setError(err.message || 'Failed to load dashboard');
    } finally {
      setLoading(false);
    }
  }, [apiFetch]);

  useEffect(() => {
    load();
  }, [load]);

  const trendColor = (trend: 'up' | 'down') =>
    trend === 'up' ? 'text-emerald-400' : 'text-red-400';

  const TrendIcon = ({ trend }: { trend: 'up' | 'down' }) =>
    trend === 'up' ? <TrendingUp size={14} /> : <TrendingDown size={14} />;

  if (error) {
    return (
      <div className="flex flex-col items-center justify-center h-64 text-red-400 gap-2">
        <AlertTriangle size={32} />
        <p>Failed to load dashboard: {error}</p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xl font-bold text-white">Overview</h2>
          <p className="text-sm text-slate-400 mt-1">Key metrics and system activity</p>
        </div>
        <button
          onClick={load}
          className="flex items-center gap-2 px-3 py-1.5 text-sm text-slate-400 bg-slate-800 rounded-lg hover:bg-slate-700 transition-colors"
        >
          <RefreshCw size={14} className={loading ? 'animate-spin' : ''} />
          Refresh
        </button>
      </div>

      {/* Stat Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {STAT_CARDS.map((card) => (
          <div
            key={card.label}
            className="bg-slate-900 border border-slate-800 rounded-xl p-5 hover:border-slate-700 transition-colors"
          >
            <div className="flex items-center justify-between mb-3">
              <card.icon size={20} className="text-blue-400" />
              <span className={`flex items-center gap-0.5 text-xs font-medium ${trendColor(card.trend)}`}>
                <TrendIcon trend={card.trend} />
                {card.change}
              </span>
            </div>
            <p className="text-2xl font-bold text-white">{card.value}</p>
            <p className="text-xs text-slate-500 mt-1">{card.label}</p>
          </div>
        ))}
      </div>

      {/* Chart + Activity */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        {/* API Calls Chart */}
        <div className="lg:col-span-2 bg-slate-900 border border-slate-800 rounded-xl p-5">
          <h3 className="text-sm font-semibold text-white mb-4">API Calls (Last 24h)</h3>
          {loading ? (
            <div className="flex items-center justify-center h-64 text-slate-500">
              <RefreshCw size={24} className="animate-spin mr-2" />
              Loading chart data...
            </div>
          ) : (
            <ResponsiveContainer width="100%" height={280}>
              <LineChart data={chartData}>
                <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
                <XAxis dataKey="hour" stroke="#64748b" fontSize={11} tickLine={false} />
                <YAxis stroke="#64748b" fontSize={11} tickLine={false} />
                <Tooltip
                  contentStyle={{
                    background: '#0f172a',
                    border: '1px solid #334155',
                    borderRadius: '8px',
                    color: '#e2e8f0',
                  }}
                />
                <Legend />
                <Line
                  type="monotone"
                  dataKey="calls"
                  stroke="#3b82f6"
                  strokeWidth={2}
                  dot={false}
                  name="API Calls"
                />
                <Line
                  type="monotone"
                  dataKey="errors"
                  stroke="#ef4444"
                  strokeWidth={2}
                  dot={false}
                  name="Errors"
                />
              </LineChart>
            </ResponsiveContainer>
          )}
        </div>

        {/* Recent Activity */}
        <div className="bg-slate-900 border border-slate-800 rounded-xl p-5">
          <h3 className="text-sm font-semibold text-white mb-4">Recent Activity</h3>
          {loading ? (
            <div className="flex items-center justify-center h-64 text-slate-500">
              <RefreshCw size={24} className="animate-spin mr-2" />
              Loading activity...
            </div>
          ) : (
            <div className="space-y-3">
              {RECENT_ACTIVITY.map((item, idx) => (
                <div key={idx} className="flex items-start gap-3 pb-3 border-b border-slate-800 last:border-0 last:pb-0">
                  <Clock size={14} className="text-slate-600 mt-0.5 shrink-0" />
                  <div className="min-w-0">
                    <p className="text-sm text-slate-300 truncate">{item.event}</p>
                    <p className="text-xs text-slate-500">{item.user} · {item.time}</p>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* System Status (from /metrics mock) */}
      {metrics && (
        <div className="bg-slate-900 border border-slate-800 rounded-xl p-5">
          <h3 className="text-sm font-semibold text-white mb-4">System Status</h3>
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 text-sm">
            <div>
              <p className="text-slate-500">DB Status</p>
              <p className={`font-medium ${metrics.db_status === 'ok' ? 'text-emerald-400' : 'text-red-400'}`}>
                {metrics.db_status === 'ok' ? '● Healthy' : '● Down'}
              </p>
            </div>
            <div>
              <p className="text-slate-500">Redis Status</p>
              <p className={`font-medium ${metrics.redis_status === 'ok' ? 'text-emerald-400' : 'text-red-400'}`}>
                {metrics.redis_status === 'ok' ? '● Healthy' : '● Down'}
              </p>
            </div>
            <div>
              <p className="text-slate-500">Avg Response</p>
              <p className="text-white font-medium">{metrics.avg_duration_ms} ms</p>
            </div>
            <div>
              <p className="text-slate-500">Queue Depth</p>
              <p className="text-white font-medium">{metrics.queue_depth}</p>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
