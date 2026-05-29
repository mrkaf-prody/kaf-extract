import React, { useEffect, useState, useRef, useCallback } from 'react';
import { useAuth } from '../contexts/AuthContext';
import {
  Activity, Server, Database, HardDrive, Clock, AlertTriangle,
  Zap, RefreshCw, Wifi, WifiOff, Radio, Layers, BarChart3,
} from 'lucide-react';

// ─── Types ───

interface SystemMetrics {
  total_requests: number;
  active_jobs: number;
  queue_depth: number;
  cache_hit_rate: number;   // 0–100
  avg_latency_ms: number;
  error_count: number;
  db_status: 'healthy' | 'degraded' | 'down';
  redis_status: 'healthy' | 'degraded' | 'down';
  uptime_seconds: number;
  requests_per_minute: number;
  recent_errors: RecentError[];
}

interface RecentError {
  timestamp: string;
  endpoint: string;
  status_code: number;
  message: string;
}

// ─── Real data from /metrics endpoint ───

// ─── Status indicator helpers ───

const statusColor = (status: 'healthy' | 'degraded' | 'down') => {
  switch (status) {
    case 'healthy': return { dot: 'bg-emerald-400', text: 'text-emerald-400', ring: 'ring-emerald-500/20' };
    case 'degraded': return { dot: 'bg-amber-400', text: 'text-amber-400', ring: 'ring-amber-500/20' };
    case 'down': return { dot: 'bg-red-400', text: 'text-red-400', ring: 'ring-red-500/20' };
  }
};

const statusLabel = (status: 'healthy' | 'degraded' | 'down') => {
  switch (status) {
    case 'healthy': return 'Healthy';
    case 'degraded': return 'Degraded';
    case 'down': return 'Down';
  }
};

const statusCodeColor = (code: number) => {
  if (code >= 500) return 'text-red-400 bg-red-500/10';
  if (code >= 400) return 'text-amber-400 bg-amber-500/10';
  return 'text-slate-400 bg-slate-500/10';
};

function formatUptime(seconds: number): string {
  const d = Math.floor(seconds / 86400);
  const h = Math.floor((seconds % 86400) / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  const parts: string[] = [];
  if (d > 0) parts.push(`${d}d`);
  if (h > 0) parts.push(`${h}h`);
  parts.push(`${m}m`);
  return parts.join(' ');
}

function timeAgo(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime();
  const secs = Math.floor(diff / 1000);
  if (secs < 60) return `${secs}s ago`;
  const mins = Math.floor(secs / 60);
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.floor(mins / 60);
  return `${hrs}h ago`;
}

// ─── Skeleton card ───

const SkeletonCard = () => (
  <div className="bg-slate-900 border border-slate-800 rounded-xl p-5 animate-pulse">
    <div className="flex items-center justify-between mb-3">
      <div className="w-5 h-5 bg-slate-800 rounded" />
      <div className="w-12 h-3 bg-slate-800 rounded" />
    </div>
    <div className="w-20 h-7 bg-slate-800 rounded mb-2" />
    <div className="w-24 h-3 bg-slate-800 rounded" />
  </div>
);

// ─── Page ───

export const MonitorPage: React.FC = () => {
  const { apiFetch } = useAuth();
  const [metrics, setMetrics] = useState<SystemMetrics | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [autoRefresh, setAutoRefresh] = useState(true);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const fetchMetrics = useCallback(async () => {
    try {
      const data = await apiFetch('/metrics');
      setMetrics(data);
      setError(null);
    } catch (err: any) {
      setError(err.message || 'Failed to fetch metrics');
    } finally {
      setLoading(false);
    }
  }, [apiFetch]);

  // Initial load + auto-refresh
  useEffect(() => {
    fetchMetrics();
    if (autoRefresh) {
      intervalRef.current = setInterval(fetchMetrics, 5000);
    }
    return () => {
      if (intervalRef.current) clearInterval(intervalRef.current);
    };
  }, [autoRefresh, fetchMetrics]);

  const toggleRefresh = () => setAutoRefresh((prev) => !prev);

  if (error && !metrics) {
    return (
      <div className="flex flex-col items-center justify-center h-64 text-red-400 gap-2">
        <AlertTriangle size={32} />
        <p>Failed to load monitor data: {error}</p>
        <button
          onClick={fetchMetrics}
          className="mt-2 px-4 py-2 text-sm bg-slate-800 text-slate-300 rounded-lg hover:bg-slate-700 transition-colors"
        >
          Retry
        </button>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xl font-bold text-white">API Monitor</h2>
          <p className="text-sm text-slate-400 mt-1">
            Real-time system metrics and health status
          </p>
        </div>
        <div className="flex items-center gap-3">
          {/* Auto-refresh indicator */}
          <button
            onClick={toggleRefresh}
            className={`flex items-center gap-2 px-3 py-1.5 text-xs rounded-lg border transition-colors ${
              autoRefresh
                ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/30'
                : 'bg-slate-800 text-slate-500 border-slate-700'
            }`}
          >
            {autoRefresh ? <Wifi size={13} /> : <WifiOff size={13} />}
            {autoRefresh ? 'Live (5s)' : 'Paused'}
          </button>

          {/* Manual refresh */}
          <button
            onClick={() => { setLoading(true); fetchMetrics(); }}
            className="flex items-center gap-2 px-3 py-1.5 text-sm text-slate-400 bg-slate-800 rounded-lg hover:bg-slate-700 transition-colors"
          >
            <RefreshCw size={14} className={loading ? 'animate-spin' : ''} />
            Refresh
          </button>
        </div>
      </div>

      {/* Stat Cards */}
      {loading ? (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {Array.from({ length: 6 }).map((_, i) => <SkeletonCard key={i} />)}
        </div>
      ) : metrics ? (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {/* Total Requests */}
          <div className="bg-slate-900 border border-slate-800 rounded-xl p-5 hover:border-slate-700 transition-colors">
            <div className="flex items-center justify-between mb-3">
              <Activity size={20} className="text-blue-400" />
              <span className="text-xs text-slate-500">{metrics.requests_per_minute}/min</span>
            </div>
            <p className="text-2xl font-bold text-white">{metrics.total_requests.toLocaleString()}</p>
            <p className="text-xs text-slate-500 mt-1">Total Requests</p>
          </div>

          {/* Active Jobs */}
          <div className="bg-slate-900 border border-slate-800 rounded-xl p-5 hover:border-slate-700 transition-colors">
            <div className="flex items-center justify-between mb-3">
              <Zap size={20} className="text-amber-400" />
              <span className={`w-2 h-2 rounded-full animate-pulse ${metrics.active_jobs > 10 ? 'bg-amber-400' : 'bg-emerald-400'}`} />
            </div>
            <p className="text-2xl font-bold text-white">{metrics.active_jobs}</p>
            <p className="text-xs text-slate-500 mt-1">Active Jobs</p>
          </div>

          {/* Queue Depth */}
          <div className="bg-slate-900 border border-slate-800 rounded-xl p-5 hover:border-slate-700 transition-colors">
            <div className="flex items-center justify-between mb-3">
              <Layers size={20} className="text-purple-400" />
              <span className="text-xs text-slate-500">pending</span>
            </div>
            <p className="text-2xl font-bold text-white">{metrics.queue_depth}</p>
            <p className="text-xs text-slate-500 mt-1">Queue Depth</p>
          </div>

          {/* Cache Hit Rate */}
          <div className="bg-slate-900 border border-slate-800 rounded-xl p-5 hover:border-slate-700 transition-colors">
            <div className="flex items-center justify-between mb-3">
              <HardDrive size={20} className="text-emerald-400" />
              <span className={`text-xs ${metrics.cache_hit_rate > 60 ? 'text-emerald-400' : 'text-amber-400'}`}>
                {metrics.cache_hit_rate > 60 ? 'Optimal' : 'Low'}
              </span>
            </div>
            <p className="text-2xl font-bold text-white">{metrics.cache_hit_rate}%</p>
            <p className="text-xs text-slate-500 mt-1">Cache Hit Rate</p>
          </div>

          {/* Avg Latency */}
          <div className="bg-slate-900 border border-slate-800 rounded-xl p-5 hover:border-slate-700 transition-colors">
            <div className="flex items-center justify-between mb-3">
              <Clock size={20} className="text-cyan-400" />
              <span className={`text-xs ${metrics.avg_latency_ms < 100 ? 'text-emerald-400' : metrics.avg_latency_ms < 250 ? 'text-amber-400' : 'text-red-400'}`}>
                {metrics.avg_latency_ms < 100 ? 'Fast' : metrics.avg_latency_ms < 250 ? 'Moderate' : 'Slow'}
              </span>
            </div>
            <p className="text-2xl font-bold text-white">{metrics.avg_latency_ms} ms</p>
            <p className="text-xs text-slate-500 mt-1">Avg Latency</p>
          </div>

          {/* Error Count */}
          <div className="bg-slate-900 border border-slate-800 rounded-xl p-5 hover:border-slate-700 transition-colors">
            <div className="flex items-center justify-between mb-3">
              <AlertTriangle size={20} className="text-red-400" />
              <span className={`text-xs ${metrics.error_count < 1200 ? 'text-emerald-400' : 'text-red-400'}`}>
                {((metrics.error_count / metrics.total_requests) * 100).toFixed(2)}% rate
              </span>
            </div>
            <p className="text-2xl font-bold text-white">{metrics.error_count.toLocaleString()}</p>
            <p className="text-xs text-slate-500 mt-1">Error Count</p>
          </div>
        </div>
      ) : null}

      {/* System Health + Uptime */}
      {metrics && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          {/* Health Status */}
          <div className="bg-slate-900 border border-slate-800 rounded-xl p-5">
            <h3 className="text-sm font-semibold text-white mb-4 flex items-center gap-2">
              <Server size={16} className="text-blue-400" />
              System Health
            </h3>
            <div className="space-y-4">
              {/* DB Status */}
              <div className="flex items-center justify-between p-3 bg-slate-800/50 rounded-lg">
                <div className="flex items-center gap-3">
                  <Database size={18} className="text-slate-400" />
                  <div>
                    <p className="text-sm text-slate-300">Database</p>
                    <p className="text-xs text-slate-500">PostgreSQL</p>
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  <span className={`w-2 h-2 rounded-full animate-pulse ${statusColor(metrics.db_status).dot}`} />
                  <span className={`text-sm font-medium ${statusColor(metrics.db_status).text}`}>
                    {statusLabel(metrics.db_status)}
                  </span>
                </div>
              </div>

              {/* Redis Status */}
              <div className="flex items-center justify-between p-3 bg-slate-800/50 rounded-lg">
                <div className="flex items-center gap-3">
                  <Radio size={18} className="text-slate-400" />
                  <div>
                    <p className="text-sm text-slate-300">Redis</p>
                    <p className="text-xs text-slate-500">Cache & Queue</p>
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  <span className={`w-2 h-2 rounded-full animate-pulse ${statusColor(metrics.redis_status).dot}`} />
                  <span className={`text-sm font-medium ${statusColor(metrics.redis_status).text}`}>
                    {statusLabel(metrics.redis_status)}
                  </span>
                </div>
              </div>

              {/* Uptime */}
              <div className="flex items-center justify-between p-3 bg-slate-800/50 rounded-lg">
                <div className="flex items-center gap-3">
                  <Clock size={18} className="text-slate-400" />
                  <div>
                    <p className="text-sm text-slate-300">Uptime</p>
                    <p className="text-xs text-slate-500">Since last restart</p>
                  </div>
                </div>
                <span className="text-sm font-medium text-emerald-400 font-mono">
                  {formatUptime(metrics.uptime_seconds)}
                </span>
              </div>
            </div>
          </div>

          {/* Recent Errors */}
          <div className="bg-slate-900 border border-slate-800 rounded-xl p-5">
            <h3 className="text-sm font-semibold text-white mb-4 flex items-center gap-2">
              <BarChart3 size={16} className="text-red-400" />
              Recent Errors
            </h3>
            {metrics.recent_errors.length === 0 ? (
              <p className="text-sm text-slate-500 text-center py-8">No recent errors 🎉</p>
            ) : (
              <div className="space-y-2 max-h-64 overflow-y-auto">
                {metrics.recent_errors.map((err, idx) => (
                  <div
                    key={idx}
                    className="flex items-start gap-3 p-3 bg-slate-800/50 rounded-lg hover:bg-slate-800 transition-colors"
                  >
                    <span
                      className={`shrink-0 px-1.5 py-0.5 rounded text-xs font-mono font-medium ${statusCodeColor(err.status_code)}`}
                    >
                      {err.status_code}
                    </span>
                    <div className="min-w-0 flex-1">
                      <p className="text-sm text-slate-300 truncate">{err.message}</p>
                      <div className="flex items-center gap-2 mt-0.5">
                        <code className="text-xs text-slate-500 font-mono">{err.endpoint}</code>
                        <span className="text-xs text-slate-600">·</span>
                        <span className="text-xs text-slate-600">{timeAgo(err.timestamp)}</span>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
};
