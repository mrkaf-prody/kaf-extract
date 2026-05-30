import React, { useEffect, useState, useMemo, useCallback } from 'react';
import { useAuth } from '../contexts/AuthContext';
import {
  Search, RefreshCw, AlertTriangle, CreditCard, Calendar, User,
  ArrowUpCircle, ArrowDownCircle, XCircle, ChevronDown,
} from 'lucide-react';

// ─── Types ───

interface Subscription {
  id: string;
  user_email: string;
  user_name: string;
  plan: 'hobby' | 'pro' | 'enterprise';
  status: 'active' | 'canceled' | 'expired' | 'past_due';
  started_at: string | null;
  expires_at: string | null;
}

const PLANS = ['hobby', 'pro', 'enterprise'] as const;

// ─── Data loaded from /api/v1/admin/subscriptions ───

// ─── Badge styles ───

const planBadge = (plan: Subscription['plan']) => {
  const map: Record<string, string> = {
    free: 'bg-slate-500/10 text-slate-400 border-slate-500/30',
    starter: 'bg-blue-500/10 text-blue-400 border-blue-500/30',
    pro: 'bg-purple-500/10 text-purple-400 border-purple-500/30',
    enterprise: 'bg-amber-500/10 text-amber-400 border-amber-500/30',
  };
  return `px-2 py-0.5 rounded text-xs font-medium border ${map[plan]}`;
};

const statusBadge = (status: Subscription['status']) => {
  const map: Record<string, string> = {
    active: 'bg-emerald-500/10 text-emerald-400 border-emerald-500/30',
    canceled: 'bg-red-500/10 text-red-400 border-red-500/30',
    expired: 'bg-slate-500/10 text-slate-400 border-slate-500/30',
    past_due: 'bg-amber-500/10 text-amber-400 border-amber-500/30',
  };
  return `px-2 py-0.5 rounded text-xs font-medium border ${map[status]}`;
};

// ─── Confirm Modal ───

const ConfirmModal: React.FC<{
  open: boolean;
  title: string;
  message: string;
  actionLabel: string;
  actionClass?: string;
  onConfirm: () => void;
  onCancel: () => void;
}> = ({ open, title, message, actionLabel, actionClass, onConfirm, onCancel }) => {
  if (!open) return null;
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm">
      <div className="bg-slate-900 border border-slate-700 rounded-xl p-6 w-full max-w-md shadow-2xl">
        <h3 className="text-lg font-semibold text-white mb-2">{title}</h3>
        <p className="text-sm text-slate-400 mb-6">{message}</p>
        <div className="flex gap-3 justify-end">
          <button onClick={onCancel} className="px-4 py-2 text-sm text-slate-300 bg-slate-800 rounded-lg hover:bg-slate-700 transition-colors">
            Cancel
          </button>
          <button onClick={onConfirm} className={`px-4 py-2 text-sm text-white rounded-lg transition-colors ${actionClass || 'bg-red-600 hover:bg-red-500'}`}>
            {actionLabel}
          </button>
        </div>
      </div>
    </div>
  );
};

// ─── Page ───

export const SubscriptionsPage: React.FC = () => {
  const { apiFetch } = useAuth();
  const [subscriptions, setSubscriptions] = useState<Subscription[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [search, setSearch] = useState('');
  const [statusFilter, setStatusFilter] = useState<string>('all');
  const [planFilter, setPlanFilter] = useState<string>('all');

  const [confirmCancel, setConfirmCancel] = useState<Subscription | null>(null);

  // Load
  useEffect(() => {
    const fetchData = async () => {
      setLoading(true);
      try {
        const params = new URLSearchParams();
        if (search) params.append('search', search);
        if (statusFilter !== 'all') params.append('status', statusFilter);
        if (planFilter !== 'all') params.append('plan', planFilter);
        const res = await apiFetch(`/api/v1/admin/subscriptions?${params.toString()}`);
        setSubscriptions(res);
      } catch (e: any) {
        setError(e.message);
      } finally {
        setLoading(false);
      }
    };
    fetchData();
  }, [search, statusFilter, planFilter, apiFetch]);

  // Derived
  const filtered = useMemo(() => {
    return subscriptions.filter((s) => {
      const matchSearch = !search ||
        s.user_email.toLowerCase().includes(search.toLowerCase()) ||
        s.user_name.toLowerCase().includes(search.toLowerCase());
      const matchStatus = statusFilter === 'all' || s.status === statusFilter;
      const matchPlan = planFilter === 'all' || s.plan === planFilter;
      return matchSearch && matchStatus && matchPlan;
    });
  }, [subscriptions, search, statusFilter, planFilter]);

  // Change plan
  const handleChangePlan = useCallback(async (subId: string, newPlan: string) => {
    try {
      await apiFetch(`/api/v1/admin/subscriptions/${subId}`, {
        method: 'PATCH',
        body: JSON.stringify({ plan: newPlan }),
      });
      setSubscriptions((prev) =>
        prev.map((s) => (s.id === subId ? { ...s, plan: newPlan as Subscription['plan'] } : s))
      );
    } catch (e: any) {
      setError(e.message || 'Failed to change plan');
    }
  }, [apiFetch]);

  // Cancel
  const handleCancel = useCallback(async (subId: string) => {
    try {
      await apiFetch(`/api/v1/admin/subscriptions/${subId}/cancel`, { method: 'POST' });
      setSubscriptions((prev) =>
        prev.map((s) => (s.id === subId ? { ...s, status: 'canceled' as const } : s))
      );
    } catch (e: any) {
      setError(e.message || 'Failed to cancel subscription');
    }
    setConfirmCancel(null);
  }, [apiFetch]);

  const formatDate = (iso: string | null) =>
    iso ? new Date(iso).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' }) : '—';

  if (error) {
    return (
      <div className="flex flex-col items-center justify-center h-64 text-red-400 gap-2">
        <AlertTriangle size={32} />
        <p>Failed to load subscriptions: {error}</p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h2 className="text-xl font-bold text-white">Subscriptions</h2>
        <p className="text-sm text-slate-400 mt-1">Manage user plans and billing status</p>
      </div>

      {/* Filters */}
      <div className="flex flex-wrap gap-3 items-center">
        <div className="relative flex-1 min-w-[200px] max-w-sm">
          <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-500" />
          <input
            type="text"
            placeholder="Search by user email or name..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-full pl-10 pr-4 py-2 bg-slate-900 border border-slate-700 rounded-lg text-sm text-white placeholder-slate-500 focus:outline-none focus:border-blue-500 transition-colors"
          />
        </div>
        <select
          value={planFilter}
          onChange={(e) => setPlanFilter(e.target.value)}
          className="px-3 py-2 bg-slate-900 border border-slate-700 rounded-lg text-sm text-slate-300 focus:outline-none focus:border-blue-500"
        >
          <option value="all">All Plans</option>
          {PLANS.map((p) => <option key={p} value={p}>{p.charAt(0).toUpperCase() + p.slice(1)}</option>)}
        </select>
        <select
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value)}
          className="px-3 py-2 bg-slate-900 border border-slate-700 rounded-lg text-sm text-slate-300 focus:outline-none focus:border-blue-500"
        >
          <option value="all">All Status</option>
          <option value="active">Active</option>
          <option value="cancelled">Cancelled</option>
          <option value="expired">Expired</option>
          <option value="past_due">Past Due</option>
        </select>
        <button
          onClick={() => {
            const params = new URLSearchParams();
            if (search) params.append('search', search);
            if (statusFilter !== 'all') params.append('status', statusFilter);
            if (planFilter !== 'all') params.append('plan', planFilter);
            setLoading(true);
            apiFetch(`/api/v1/admin/subscriptions?${params.toString()}`)
              .then((data: any) => {
                setSubscriptions(data);
              })
              .catch((e: any) => setError(e.message))
              .finally(() => setLoading(false));
          }}
          className="flex items-center gap-2 px-3 py-2 text-sm text-slate-400 bg-slate-800 rounded-lg hover:bg-slate-700 transition-colors"
        >
          <RefreshCw size={14} className={loading ? 'animate-spin' : ''} />
          Refresh
        </button>
      </div>

      {/* Table */}
      <div className="bg-slate-900 border border-slate-800 rounded-xl overflow-hidden">
        {loading ? (
          <div className="flex items-center justify-center h-48 text-slate-500">
            <RefreshCw size={24} className="animate-spin mr-2" />
            Loading subscriptions...
          </div>
        ) : filtered.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-48 text-slate-500 gap-2">
            <CreditCard size={24} />
            <p>No subscriptions found</p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-slate-800">
                  <th className="text-left py-3 px-4 text-slate-400 font-medium">
                    <span className="flex items-center gap-1"><User size={13} /> User</span>
                  </th>
                  <th className="text-left py-3 px-4 text-slate-400 font-medium">Plan</th>
                  <th className="text-left py-3 px-4 text-slate-400 font-medium">Status</th>
                  <th className="text-left py-3 px-4 text-slate-400 font-medium">
                    <span className="flex items-center gap-1"><Calendar size={13} /> Started</span>
                  </th>
                  <th className="text-left py-3 px-4 text-slate-400 font-medium">Expires</th>
                  <th className="text-right py-3 px-4 text-slate-400 font-medium">Actions</th>
                </tr>
              </thead>
              <tbody>
                {filtered.map((s) => (
                  <tr key={s.id} className="border-b border-slate-800/50 hover:bg-slate-800/30 transition-colors">
                    <td className="py-3 px-4">
                      <p className="text-white text-xs font-mono">{s.user_email}</p>
                      <p className="text-slate-500 text-xs">{s.user_name}</p>
                    </td>
                    <td className="py-3 px-4">
                      <span className={planBadge(s.plan)}>{s.plan}</span>
                    </td>
                    <td className="py-3 px-4">
                      <span className={statusBadge(s.status)}>{s.status.replace('_', ' ')}</span>
                    </td>
                    <td className="py-3 px-4 text-slate-400 text-xs">{formatDate(s.started_at)}</td>
                    <td className="py-3 px-4 text-slate-400 text-xs">{formatDate(s.expires_at)}</td>
                    <td className="py-3 px-4">
                      <div className="flex items-center justify-end gap-2">
                        {/* Upgrade/Downgrade dropdown */}
                        <div className="relative group">
                          <button className="flex items-center gap-1 px-2 py-1.5 text-xs text-slate-400 bg-slate-800 rounded-lg hover:bg-slate-700 transition-colors">
                            <ArrowUpCircle size={13} />
                            Change
                            <ChevronDown size={11} />
                          </button>
                          <div className="absolute right-0 top-full mt-1 bg-slate-800 border border-slate-700 rounded-lg shadow-xl opacity-0 invisible group-hover:opacity-100 group-hover:visible transition-all z-10 min-w-[120px]">
                            {PLANS.filter((p) => p !== s.plan).map((p) => (
                              <button
                                key={p}
                                onClick={() => handleChangePlan(s.id, p)}
                                className="block w-full text-left px-3 py-2 text-xs text-slate-300 hover:bg-slate-700 hover:text-white transition-colors first:rounded-t-lg last:rounded-b-lg"
                              >
                                {p === 'hobby' ? <ArrowDownCircle size={12} className="inline mr-1" /> : <ArrowUpCircle size={12} className="inline mr-1" />}
                                {p.charAt(0).toUpperCase() + p.slice(1)}
                              </button>
                            ))}
                          </div>
                        </div>

                        {/* Cancel */}
                        {s.status === 'active' && (
                          <button
                            onClick={() => setConfirmCancel(s)}
                            className="flex items-center gap-1 px-2 py-1.5 text-xs text-red-400 bg-red-500/10 rounded-lg hover:bg-red-500/20 transition-colors"
                          >
                            <XCircle size={13} />
                            Cancel
                          </button>
                        )}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {!loading && filtered.length > 0 && (
        <p className="text-xs text-slate-600">
          Showing {filtered.length} of {subscriptions.length} subscriptions
        </p>
      )}

      <ConfirmModal
        open={!!confirmCancel}
        title="Cancel Subscription"
        message={`Cancel the ${confirmCancel?.plan} subscription for ${confirmCancel?.user_email}? The user will lose access at the end of the billing period.`}
        actionLabel="Cancel Subscription"
        actionClass="bg-red-600 hover:bg-red-500"
        onConfirm={() => confirmCancel && handleCancel(confirmCancel.id)}
        onCancel={() => setConfirmCancel(null)}
      />
    </div>
  );
};
