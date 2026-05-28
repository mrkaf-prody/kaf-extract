import React, { useEffect, useState, useCallback } from 'react';
import { useAuth } from '../contexts/AuthContext';
import { CreditCard, Check, Zap, Clock, ArrowUpCircle } from 'lucide-react';

interface Plan {
  key: string;
  name: string;
  price_cents: number;
  features: string[];
}

interface TrialInfo {
  status: string;
  extractions_total: number;
  extractions_used: number;
  extractions_remaining: number;
  started_at: string;
  expires_at: string;
  days_left: number;
}

interface SubscriptionInfo {
  id: string;
  plan: string;
  status: string;
  provider: string;
  current_period_start: string | null;
  current_period_end: string | null;
  created_at: string;
}

interface SubscriptionStatus {
  subscription: SubscriptionInfo | null;
  trial: TrialInfo | null;
  available_plans: Plan[];
}

export const BillingPage: React.FC = () => {
  const { apiFetch } = useAuth();
  const [data, setData] = useState<SubscriptionStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [actionLoading, setActionLoading] = useState<string | null>(null);
  const [message, setMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null);

  const fetchSubscription = useCallback(() => {
    setLoading(true);
    apiFetch('/api/v1/subscriptions/me')
      .then(d => setData(d))
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [apiFetch]);

  useEffect(() => { fetchSubscription(); }, [fetchSubscription]);

  const handleUpgrade = async (plan: string) => {
    setActionLoading(plan);
    setMessage(null);
    try {
      const res = await apiFetch('/api/v1/subscriptions/checkout', {
        method: 'POST',
        body: JSON.stringify({ plan }),
      });
      if (res.checkout_url) {
        window.open(res.checkout_url, '_blank');
        setMessage({ type: 'success', text: `Checkout opened for ${plan} plan.` });
      }
    } catch (err: any) {
      setMessage({ type: 'error', text: err.message || 'Checkout failed' });
    } finally {
      setActionLoading(null);
    }
  };

  const handleCancel = async () => {
    if (!confirm('Are you sure you want to cancel your subscription?')) return;
    setActionLoading('cancel');
    setMessage(null);
    try {
      await apiFetch('/api/v1/subscriptions/cancel', { method: 'POST' });
      setMessage({ type: 'success', text: 'Subscription canceled.' });
      fetchSubscription();
    } catch (err: any) {
      setMessage({ type: 'error', text: err.message || 'Cancel failed' });
    } finally {
      setActionLoading(null);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20">
        <span className="text-slate-400">Loading billing info...</span>
      </div>
    );
  }

  const sub = data?.subscription;
  const trial = data?.trial;
  const plans = data?.available_plans || [];

  const formatPrice = (cents: number) => {
    if (cents === 0) return 'Free';
    return `$${(cents / 100).toFixed(2)}/mo`;
  };

  return (
    <div>
      <div className="mb-6">
        <h2 className="text-2xl font-bold text-white mb-1">Billing</h2>
        <p className="text-slate-400 text-sm">Manage your subscription and plan.</p>
      </div>

      {message && (
        <div
          className={`border rounded p-3 text-sm mb-4 ${
            message.type === 'success'
              ? 'bg-green-500/10 border-green-500/30 text-green-400'
              : 'bg-red-500/10 border-red-500/30 text-red-400'
          }`}
        >
          {message.text}
        </div>
      )}

      {/* Current plan / trial */}
      <div className="bg-slate-900 border border-slate-800 rounded-lg p-6 mb-6">
        <h3 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
          <CreditCard size={20} className="text-blue-400" />
          Current Plan
        </h3>

        {sub ? (
          <div className="space-y-3">
            <div className="flex items-center justify-between">
              <div>
                <span className="text-2xl font-bold text-white capitalize">{sub.plan}</span>
                <span
                  className={`ml-3 text-xs px-2 py-0.5 rounded-full ${
                    sub.status === 'active'
                      ? 'bg-green-500/10 text-green-400'
                      : 'bg-yellow-500/10 text-yellow-400'
                  }`}
                >
                  {sub.status}
                </span>
              </div>
              {sub.status === 'active' && (
                <button
                  onClick={handleCancel}
                  disabled={actionLoading === 'cancel'}
                  className="text-sm text-slate-400 hover:text-red-400 transition-colors disabled:opacity-50"
                >
                  {actionLoading === 'cancel' ? 'Canceling...' : 'Cancel Subscription'}
                </button>
              )}
            </div>
            <div className="text-sm text-slate-400">
              Provider: <span className="text-slate-300">{sub.provider}</span>
              {sub.current_period_end && (
                <> &middot; Renews: {new Date(sub.current_period_end).toLocaleDateString()}</>
              )}
            </div>
          </div>
        ) : trial ? (
          <div className="space-y-3">
            <div className="flex items-center justify-between">
              <div>
                <span className="text-2xl font-bold text-white">Trial</span>
                <span
                  className={`ml-3 text-xs px-2 py-0.5 rounded-full ${
                    trial.days_left > 0
                      ? 'bg-blue-500/10 text-blue-400'
                      : 'bg-red-500/10 text-red-400'
                  }`}
                >
                  {trial.days_left > 0 ? `${trial.days_left}d left` : 'Expired'}
                </span>
              </div>
            </div>
            <div className="flex items-center gap-4 text-sm text-slate-400">
              <span className="flex items-center gap-1">
                <Zap size={14} /> {trial.extractions_used} / {trial.extractions_total} extractions
              </span>
              <span className="flex items-center gap-1">
                <Clock size={14} /> Expires {new Date(trial.expires_at).toLocaleDateString()}
              </span>
            </div>
            {/* Trial usage bar */}
            <div className="w-full bg-slate-800 rounded-full h-2 overflow-hidden">
              <div
                className="bg-blue-500 h-full rounded-full"
                style={{
                  width: `${Math.min(
                    (trial.extractions_used / trial.extractions_total) * 100,
                    100
                  )}%`,
                }}
              />
            </div>
          </div>
        ) : (
          <p className="text-slate-400 text-sm">No active subscription or trial. Choose a plan below.</p>
        )}
      </div>

      {/* Plan comparison */}
      <div>
        <h3 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
          <ArrowUpCircle size={20} className="text-green-400" />
          {sub ? 'Change Plan' : 'Choose a Plan'}
        </h3>

        {plans.length === 0 ? (
          <p className="text-slate-500 text-sm">No plans available.</p>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            {plans.map(plan => {
              const isCurrent = sub?.plan === plan.key;
              return (
                <div
                  key={plan.key}
                  className={`bg-slate-900 border rounded-lg p-5 flex flex-col ${
                    isCurrent
                      ? 'border-blue-500/50 ring-1 ring-blue-500/20'
                      : 'border-slate-800'
                  }`}
                >
                  <div className="mb-4">
                    <h4 className="text-lg font-bold text-white capitalize">{plan.name}</h4>
                    <div className="text-2xl font-bold text-white mt-1">
                      {formatPrice(plan.price_cents)}
                    </div>
                  </div>

                  <ul className="space-y-2 mb-6 flex-1">
                    {plan.features.map((feat, i) => (
                      <li key={i} className="flex items-start gap-2 text-sm text-slate-400">
                        <Check size={14} className="text-green-400 mt-0.5 flex-shrink-0" />
                        {feat}
                      </li>
                    ))}
                  </ul>

                  {isCurrent ? (
                    <div className="text-center text-sm text-blue-400 font-medium py-2">
                      Current Plan
                    </div>
                  ) : (
                    <button
                      onClick={() => handleUpgrade(plan.key)}
                      disabled={actionLoading === plan.key}
                      className="w-full bg-blue-600 hover:bg-blue-700 disabled:bg-blue-800 disabled:cursor-not-allowed
                                 text-white rounded px-4 py-2 text-sm font-medium transition-colors"
                    >
                      {actionLoading === plan.key
                        ? 'Opening checkout...'
                        : plan.price_cents === 0
                          ? 'Select Free'
                          : 'Upgrade'}
                    </button>
                  )}
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
};
