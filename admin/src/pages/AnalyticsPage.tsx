import React, { useEffect, useState, useCallback } from 'react';
import { useAuth } from '../contexts/AuthContext';
import {
  TrendingUp, Users, Percent, Activity, RefreshCw,
  AlertTriangle, DollarSign, BarChart3, PieChart, Calendar,
} from 'lucide-react';
import {
  AreaChart, Area, BarChart, Bar, PieChart as RePieChart, Pie, Cell,
  XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend,
} from 'recharts';

// ─── Types ───

type TimeRange = '7d' | '30d' | '90d';

interface AnalyticsData {
  mrr: number;
  arpu: number;
  churn_rate: number;        // percentage
  trial_conversion: number;  // percentage
  total_customers: number;
  revenue_this_month: number;
  mrr_over_time: { date: string; mrr: number }[];
  revenue_by_plan: { name: string; value: number; color: string }[];
  signups_per_day: { date: string; signups: number }[];
}

// ─── Mock data generators ───

function generateMRRData(range: TimeRange): { date: string; mrr: number }[] {
  const days = range === '7d' ? 7 : range === '30d' ? 30 : 90;
  const data: { date: string; mrr: number }[] = [];
  let mrr = 42000;
  const now = new Date();
  for (let i = days - 1; i >= 0; i--) {
    const d = new Date(now);
    d.setDate(d.getDate() - i);
    mrr += Math.floor((Math.random() - 0.35) * 800);
    if (mrr < 38000) mrr = 38000;
    data.push({
      date: d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' }),
      mrr: Math.round(mrr),
    });
  }
  return data;
}

function generateSignupsData(range: TimeRange): { date: string; signups: number }[] {
  const days = range === '7d' ? 7 : range === '30d' ? 30 : 90;
  const data: { date: string; signups: number }[] = [];
  const now = new Date();
  for (let i = days - 1; i >= 0; i--) {
    const d = new Date(now);
    d.setDate(d.getDate() - i);
    // More signups on weekdays
    const isWeekend = d.getDay() === 0 || d.getDay() === 6;
    data.push({
      date: d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' }),
      signups: Math.floor(Math.random() * (isWeekend ? 20 : 45)) + (isWeekend ? 5 : 15),
    });
  }
  return data;
}

function generateMockAnalytics(range: TimeRange): AnalyticsData {
  return {
    mrr: 45230,
    arpu: 34.21,
    churn_rate: 3.8,
    trial_conversion: 24.5,
    total_customers: 1322,
    revenue_this_month: 18240,
    mrr_over_time: generateMRRData(range),
    revenue_by_plan: [
      { name: 'Starter', value: 8240, color: '#3b82f6' },
      { name: 'Pro', value: 18750, color: '#8b5cf6' },
      { name: 'Business', value: 9620, color: '#06b6d4' },
      { name: 'Enterprise', value: 8620, color: '#f59e0b' },
    ],
    signups_per_day: generateSignupsData(range),
  };
}

// ─── Helpers ───

function formatCurrency(amount: number): string {
  return new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', minimumFractionDigits: 0, maximumFractionDigits: 0 }).format(amount);
}

function formatPercent(value: number): string {
  return `${value.toFixed(1)}%`;
}

const trendColor = (good: boolean) => (good ? 'text-emerald-400' : 'text-red-400');

// ─── Skeleton card ───

const SkeletonCard = () => (
  <div className="bg-slate-900 border border-slate-800 rounded-xl p-5 animate-pulse">
    <div className="flex items-center justify-between mb-3">
      <div className="w-5 h-5 bg-slate-800 rounded" />
      <div className="w-12 h-3 bg-slate-800 rounded" />
    </div>
    <div className="w-20 h-8 bg-slate-800 rounded mb-2" />
    <div className="w-16 h-3 bg-slate-800 rounded" />
  </div>
);

const SkeletonChart = () => (
  <div className="bg-slate-900 border border-slate-800 rounded-xl p-5 animate-pulse">
    <div className="w-32 h-4 bg-slate-800 rounded mb-4" />
    <div className="w-full h-64 bg-slate-800/50 rounded-lg" />
  </div>
);

// ─── Page ───

export const AnalyticsPage: React.FC = () => {
  const { apiFetch } = useAuth();
  const [analytics, setAnalytics] = useState<AnalyticsData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [range, setRange] = useState<TimeRange>('30d');

  const fetchAnalytics = useCallback(async (r: TimeRange) => {
    setLoading(true);
    try {
      // TODO: Replace with real API: const data = await apiFetch(`/v1/admin/analytics?range=${r}`);
      // Simulate network delay
      await new Promise((resolve) => setTimeout(resolve, 600));
      const data = generateMockAnalytics(r);
      setAnalytics(data);
      setError(null);
    } catch (err: any) {
      setError(err.message || 'Failed to load analytics');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchAnalytics(range);
  }, [range, fetchAnalytics]);

  const handleRangeChange = (r: TimeRange) => {
    if (r !== range) setRange(r);
  };

  if (error && !analytics) {
    return (
      <div className="flex flex-col items-center justify-center h-64 text-red-400 gap-2">
        <AlertTriangle size={32} />
        <p>Failed to load analytics: {error}</p>
        <button
          onClick={() => fetchAnalytics(range)}
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
          <h2 className="text-xl font-bold text-white">Analytics</h2>
          <p className="text-sm text-slate-400 mt-1">Revenue metrics and growth trends</p>
        </div>
        {/* Time Range Selector */}
        <div className="flex items-center gap-1 bg-slate-900 border border-slate-800 rounded-lg p-1">
          {(['7d', '30d', '90d'] as TimeRange[]).map((r) => (
            <button
              key={r}
              onClick={() => handleRangeChange(r)}
              className={`px-3 py-1.5 text-xs font-medium rounded-md transition-colors ${
                range === r
                  ? 'bg-blue-600 text-white'
                  : 'text-slate-400 hover:text-white hover:bg-slate-800'
              }`}
            >
              {r}
            </button>
          ))}
          <button
            onClick={() => fetchAnalytics(range)}
            className="ml-1 p-1.5 text-slate-500 hover:text-white rounded-md hover:bg-slate-800 transition-colors"
            title="Refresh"
          >
            <RefreshCw size={14} className={loading ? 'animate-spin' : ''} />
          </button>
        </div>
      </div>

      {/* KPI Cards */}
      {loading && !analytics ? (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          {Array.from({ length: 4 }).map((_, i) => <SkeletonCard key={i} />)}
        </div>
      ) : analytics ? (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          {/* MRR */}
          <div className="bg-slate-900 border border-slate-800 rounded-xl p-5 hover:border-slate-700 transition-colors">
            <div className="flex items-center justify-between mb-3">
              <DollarSign size={20} className="text-emerald-400" />
              <span className="flex items-center gap-0.5 text-xs font-medium text-emerald-400">
                <TrendingUp size={14} />
                +5.2%
              </span>
            </div>
            <p className="text-2xl font-bold text-white">{formatCurrency(analytics.mrr)}</p>
            <p className="text-xs text-slate-500 mt-1">Monthly Recurring Revenue</p>
          </div>

          {/* ARPU */}
          <div className="bg-slate-900 border border-slate-800 rounded-xl p-5 hover:border-slate-700 transition-colors">
            <div className="flex items-center justify-between mb-3">
              <Users size={20} className="text-blue-400" />
              <span className="flex items-center gap-0.5 text-xs font-medium text-emerald-400">
                <TrendingUp size={14} />
                +3.1%
              </span>
            </div>
            <p className="text-2xl font-bold text-white">{formatCurrency(analytics.arpu)}</p>
            <p className="text-xs text-slate-500 mt-1">Avg Revenue Per User</p>
          </div>

          {/* Churn Rate */}
          <div className="bg-slate-900 border border-slate-800 rounded-xl p-5 hover:border-slate-700 transition-colors">
            <div className="flex items-center justify-between mb-3">
              <Percent size={20} className="text-red-400" />
              <span className={`flex items-center gap-0.5 text-xs font-medium ${analytics.churn_rate < 5 ? 'text-emerald-400' : 'text-red-400'}`}>
                {analytics.churn_rate < 5 ? <TrendingUp size={14} /> : <TrendingUp size={14} className="rotate-180" />}
                {analytics.churn_rate < 5 ? '-0.2%' : '+0.5%'}
              </span>
            </div>
            <p className="text-2xl font-bold text-white">{formatPercent(analytics.churn_rate)}</p>
            <p className="text-xs text-slate-500 mt-1">Monthly Churn Rate</p>
          </div>

          {/* Trial Conversion */}
          <div className="bg-slate-900 border border-slate-800 rounded-xl p-5 hover:border-slate-700 transition-colors">
            <div className="flex items-center justify-between mb-3">
              <Activity size={20} className="text-purple-400" />
              <span className="flex items-center gap-0.5 text-xs font-medium text-emerald-400">
                <TrendingUp size={14} />
                +2.4%
              </span>
            </div>
            <p className="text-2xl font-bold text-white">{formatPercent(analytics.trial_conversion)}</p>
            <p className="text-xs text-slate-500 mt-1">Trial Conversion Rate</p>
          </div>
        </div>
      ) : null}

      {/* Charts */}
      {loading && !analytics ? (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          <SkeletonChart />
          <SkeletonChart />
        </div>
      ) : analytics ? (
        <>
          {/* MRR Over Time (Area Chart) + Revenue by Plan (Pie Chart) */}
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
            {/* MRR Area Chart — 2/3 width */}
            <div className="lg:col-span-2 bg-slate-900 border border-slate-800 rounded-xl p-5">
              <h3 className="text-sm font-semibold text-white mb-4 flex items-center gap-2">
                <TrendingUp size={16} className="text-emerald-400" />
                MRR Over Time
              </h3>
              <ResponsiveContainer width="100%" height={300}>
                <AreaChart data={analytics.mrr_over_time}>
                  <defs>
                    <linearGradient id="mrrGradient" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="#10b981" stopOpacity={0.3} />
                      <stop offset="95%" stopColor="#10b981" stopOpacity={0} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
                  <XAxis
                    dataKey="date"
                    stroke="#64748b"
                    fontSize={11}
                    tickLine={false}
                    interval={range === '7d' ? 0 : range === '30d' ? 4 : 14}
                  />
                  <YAxis stroke="#64748b" fontSize={11} tickLine={false} />
                  <Tooltip
                    contentStyle={{
                      background: '#0f172a',
                      border: '1px solid #334155',
                      borderRadius: '8px',
                      color: '#e2e8f0',
                    }}
                    formatter={(value: number) => [formatCurrency(value), 'MRR']}
                  />
                  <Area
                    type="monotone"
                    dataKey="mrr"
                    stroke="#10b981"
                    strokeWidth={2}
                    fill="url(#mrrGradient)"
                    name="MRR"
                  />
                </AreaChart>
              </ResponsiveContainer>
            </div>

            {/* Revenue by Plan (Pie Chart) — 1/3 width */}
            <div className="bg-slate-900 border border-slate-800 rounded-xl p-5">
              <h3 className="text-sm font-semibold text-white mb-4 flex items-center gap-2">
                <PieChart size={16} className="text-purple-400" />
                Revenue by Plan
              </h3>
              <ResponsiveContainer width="100%" height={250}>
                <RePieChart>
                  <Pie
                    data={analytics.revenue_by_plan}
                    cx="50%"
                    cy="50%"
                    innerRadius={55}
                    outerRadius={85}
                    paddingAngle={3}
                    dataKey="value"
                    nameKey="name"
                  >
                    {analytics.revenue_by_plan.map((entry, idx) => (
                      <Cell key={idx} fill={entry.color} />
                    ))}
                  </Pie>
                  <Tooltip
                    contentStyle={{
                      background: '#0f172a',
                      border: '1px solid #334155',
                      borderRadius: '8px',
                      color: '#e2e8f0',
                    }}
                    formatter={(value: number) => [formatCurrency(value), 'Revenue']}
                  />
                </RePieChart>
              </ResponsiveContainer>
              {/* Legend */}
              <div className="flex flex-wrap gap-3 justify-center mt-2">
                {analytics.revenue_by_plan.map((plan) => (
                  <div key={plan.name} className="flex items-center gap-1.5">
                    <span className="w-3 h-3 rounded-full" style={{ backgroundColor: plan.color }} />
                    <span className="text-xs text-slate-400">{plan.name}</span>
                  </div>
                ))}
              </div>
            </div>
          </div>

          {/* New Signups Per Day (Bar Chart) */}
          <div className="bg-slate-900 border border-slate-800 rounded-xl p-5">
            <h3 className="text-sm font-semibold text-white mb-4 flex items-center gap-2">
              <Calendar size={16} className="text-blue-400" />
              New Signups Per Day
            </h3>
            <ResponsiveContainer width="100%" height={300}>
              <BarChart data={analytics.signups_per_day}>
                <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
                <XAxis
                  dataKey="date"
                  stroke="#64748b"
                  fontSize={11}
                  tickLine={false}
                  interval={range === '7d' ? 0 : range === '30d' ? 4 : 14}
                />
                <YAxis stroke="#64748b" fontSize={11} tickLine={false} />
                <Tooltip
                  contentStyle={{
                    background: '#0f172a',
                    border: '1px solid #334155',
                    borderRadius: '8px',
                    color: '#e2e8f0',
                  }}
                  formatter={(value: number) => [value, 'Signups']}
                />
                <Bar dataKey="signups" fill="#3b82f6" radius={[4, 4, 0, 0]} name="Signups" />
              </BarChart>
            </ResponsiveContainer>
          </div>

          {/* Summary stats row */}
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
            <div className="bg-slate-900 border border-slate-800 rounded-xl p-4">
              <p className="text-xs text-slate-500">Total Customers</p>
              <p className="text-lg font-bold text-white mt-1">{analytics.total_customers.toLocaleString()}</p>
            </div>
            <div className="bg-slate-900 border border-slate-800 rounded-xl p-4">
              <p className="text-xs text-slate-500">Revenue This Month</p>
              <p className="text-lg font-bold text-white mt-1">{formatCurrency(analytics.revenue_this_month)}</p>
            </div>
            <div className="bg-slate-900 border border-slate-800 rounded-xl p-4">
              <p className="text-xs text-slate-500">ARPU</p>
              <p className="text-lg font-bold text-white mt-1">{formatCurrency(analytics.arpu)}</p>
            </div>
            <div className="bg-slate-900 border border-slate-800 rounded-xl p-4">
              <p className="text-xs text-slate-500">MRR Growth</p>
              <p className="text-lg font-bold text-emerald-400 mt-1">+5.2%</p>
            </div>
          </div>
        </>
      ) : null}
    </div>
  );
};
