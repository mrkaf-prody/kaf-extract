import React, { useEffect, useState, useMemo } from 'react';
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

const STAT_CARDS: StatCard[] = [
  { label: 'Total Users', value: '12,847', change: '+12%', trend: 'up', icon: Users },
  { label: 'Active Subscriptions', value: '3,421', change: '+8%', trend: 'up', icon: CreditCard },
  { label: 'API Calls Today', value: '284.6K', change: '+23%', trend: 'up', icon: Activity },
  { label: 'Error Rate', value: '0.42%', change: '-0.15%', trend: 'down', icon: AlertTriangle },
];

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

const RECENT_ACTIVITY: ActivityItem[] = [
  { event: 'User registered', user: 'alice@example.com', time: '2 min ago' },
  { event: 'Subscription upgraded', user: 'bob@acme.com', time: '5 min ago' },
  { event: 'Voucher redeemed', user: 'carol@demo.io', time: '12 min ago' },
  { event: 'API key revoked', user: 'admin@kaf.io', time: '28 min ago' },
  { event: 'Feature flag toggled', user: 'admin@kaf.io', time: '45 min ago' },
  { event: 'User suspended', user: 'dave@test.com', time: '1 hour ago' },
  { event: 'Voucher batch generated', user: 'admin@kaf.io', time: '2 hours ago' },
  { event: 'Subscription cancelled', user: 'eve@corp.net', time: '3 hours ago' },
];

// ─── Page ───

export const OverviewPage: React.FC = () => {
  const { apiFetch } = useAuth();
  const [metrics, setMetrics] = useState<Record<string, any> | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [chartData] = useState(() => generateChartData());

  useEffect(() => {
    // TODO: Replace with real API call when /metrics endpoint is ready
    // apiFetch('/v1/admin/metrics').then(setMetrics).catch(setError).finally(() => setLoading(false));
    const timer = setTimeout(() => {
      setMetrics({
        requests_total: 284621,
        cache_hits: 189234,
        cache_misses: 95387,
        avg_duration_ms: 42.3,
        queue_depth: 3,
        error_count: 1195,
        uptime_seconds: 86400,
        db_status: 'ok',
        redis_status: 'ok',
      });
      setLoading(false);
    }, 800);
    return () => clearTimeout(timer);
  }, []);

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
          onClick={() => { setLoading(true); setTimeout(() => setLoading(false), 600); }}
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
