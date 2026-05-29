import React, { useEffect, useState } from 'react';
import { useAuth } from '../contexts/AuthContext';
import {
  Users, CreditCard, Activity, AlertTriangle,
  TrendingUp, TrendingDown, RefreshCw,
} from 'lucide-react';

interface StatsData {
  total_users: number;
  active_subscriptions: number;
  api_calls_today: number;
  error_rate_percent: number;
}

interface StatCardProps {
  label: string;
  value: string;
  icon: React.FC<{ size?: number; className?: string }>;
}

const StatCard: React.FC<StatCardProps> = ({ label, value, icon: Icon }) => (
  <div className="bg-slate-900 border border-slate-800 rounded-xl p-5 hover:border-slate-700 transition-colors">
    <div className="flex items-center justify-between mb-3">
      <Icon size={20} className="text-blue-400" />
    </div>
    <p className="text-2xl font-bold text-white">{value}</p>
    <p className="text-xs text-slate-500 mt-1">{label}</p>
  </div>
);

export const OverviewPage: React.FC = () => {
  const { apiFetch } = useAuth();
  const [metrics, setMetrics] = useState<StatsData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchStats = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await apiFetch('/api/v1/admin/stats');
      setMetrics(data);
    } catch (err: any) {
      setError(err.message || 'Failed to load stats');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchStats();
  }, []);

  if (error) {
    return (
      <div className="flex flex-col items-center justify-center h-64 text-red-400 gap-2">
        <AlertTriangle size={32} />
        <p>Failed to load dashboard: {error}</p>
        <button
          onClick={fetchStats}
          className="mt-2 px-4 py-2 text-sm bg-slate-800 text-slate-300 rounded-lg hover:bg-slate-700"
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
          <h2 className="text-xl font-bold text-white">Overview</h2>
          <p className="text-sm text-slate-400 mt-1">Key metrics and system activity</p>
        </div>
        <button
          onClick={fetchStats}
          className="flex items-center gap-2 px-3 py-1.5 text-sm text-slate-400 bg-slate-800 rounded-lg hover:bg-slate-700 transition-colors"
        >
          <RefreshCw size={14} className={loading ? 'animate-spin' : ''} />
          Refresh
        </button>
      </div>

      {/* Stat Cards */}
      {loading ? (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          {Array.from({ length: 4 }).map((_, i) => (
            <div key={i} className="bg-slate-900 border border-slate-800 rounded-xl p-5 animate-pulse">
              <div className="w-5 h-5 bg-slate-800 rounded mb-3" />
              <div className="w-16 h-8 bg-slate-800 rounded mb-2" />
              <div className="w-24 h-3 bg-slate-800 rounded" />
            </div>
          ))}
        </div>
      ) : metrics ? (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          <StatCard
            label="Total Users"
            value={metrics.total_users?.toLocaleString() || '0'}
            icon={Users}
          />
          <StatCard
            label="Active Subscriptions"
            value={metrics.active_subscriptions?.toLocaleString() || '0'}
            icon={CreditCard}
          />
          <StatCard
            label="API Calls Today"
            value={metrics.api_calls_today?.toLocaleString() || '0'}
            icon={Activity}
          />
          <StatCard
            label="Error Rate"
            value={`${metrics.error_rate_percent?.toFixed(2) || '0'}%`}
            icon={AlertTriangle}
          />
        </div>
      ) : null}

      {/* Empty state when no data */}
      {!loading && !metrics && !error && (
        <div className="flex flex-col items-center justify-center h-48 text-slate-500 gap-2">
          <AlertTriangle size={24} />
          <p>No metrics available</p>
        </div>
      )}
    </div>
  );
};
