import React, { useEffect, useState, useCallback } from 'react';
import { useAuth } from '../contexts/AuthContext';
import { CreditCard, Check, Zap, Clock, ArrowUpCircle, Ticket } from 'lucide-react';

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

interface UsageStats {
  current_usage: number;
  monthly_limit: number;
  hard_cap: number | null;
  percent: number;
  reset_date: string;
}

interface RedemptionResult {
  subscription_id: string;
  plan: string;
  duration_days: number;
  period_end: string;
  extraction_credits: number;
}

const planBadgeColors: Record<string, string> = {
  hobby: 'bg-[#5c5c70]/20 text-[#9a9aae] border-[#5c5c70]/30',
  pro: 'bg-[#00d4a0]/15 text-[#00d4a0] border-[#00d4a0]/30',
  enterprise: 'bg-purple-500/15 text-purple-400 border-purple-500/30',
};

export const BillingPage: React.FC = () => {
  const { apiFetch, showError } = useAuth();
  const [data, setData] = useState<SubscriptionStatus | null>(null);
  const [usage, setUsage] = useState<UsageStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [actionLoading, setActionLoading] = useState<string | null>(null);
  const [message, setMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null);

  // Voucher redemption
  const [voucherCode, setVoucherCode] = useState('');
  const [redeeming, setRedeeming] = useState(false);
  const [redeemResult, setRedeemResult] = useState<RedemptionResult | null>(null);

  const fetchSubscription = useCallback(() => {
    setLoading(true);
    Promise.all([
      apiFetch('/api/v1/subscriptions/me'),
      apiFetch('/api/v1/usage').catch(() => null),
    ])
      .then(([subData, usageData]) => {
        setData(subData);
        if (usageData) setUsage(usageData);
      })
      .catch((err: any) => showError(err.message || 'Failed to load billing info'))
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

  const handleRedeem = async () => {
    const code = voucherCode.trim();
    if (!code) return;
    setRedeeming(true);
    setMessage(null);
    setRedeemResult(null);
    try {
      const res = await apiFetch('/api/v1/vouchers/redeem', {
        method: 'POST',
        body: JSON.stringify({ code }),
      });
      setRedeemResult(res);
      setMessage({ type: 'success', text: `Voucher redeemed! ${res.plan} plan activated.` });
      fetchSubscription();
    } catch (err: any) {
      setMessage({ type: 'error', text: err.message || 'Voucher redemption failed' });
    } finally {
      setRedeeming(false);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20">
        <span className="text-[#9a9aae]">Loading billing info...</span>
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

  // Determine current plan key
  const currentPlanKey = sub?.plan || (trial ? 'trial' : null);

  // Get extraction usage for progress bar
  const extractionUsed = trial
    ? trial.extractions_used
    : usage?.current_usage ?? 0;
  const extractionLimit = trial
    ? trial.extractions_total
    : usage?.monthly_limit ?? 0;
  const usagePercent = extractionLimit > 0
    ? Math.min((extractionUsed / extractionLimit) * 100, 100)
    : 0;

  // Find current plan object for features
  const currentPlanObj = plans.find(p => p.key === currentPlanKey);

  // Determine plan badge
  const getPlanBadge = (planKey: string) => {
    const key = planKey?.toLowerCase() || '';
    if (key.includes('enterprise')) return planBadgeColors.enterprise;
    if (key.includes('pro')) return planBadgeColors.pro;
    return planBadgeColors.hobby;
  };

  return (
    <div>
      <div className="mb-6">
        <h2 className="text-2xl font-bold text-[#f0f0f5] mb-1">Billing</h2>
        <p className="text-[#9a9aae] text-sm">Manage your subscription and plan.</p>
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

      {/* ── Current Plan Card (prominent, full-width) ── */}
      <div className="bg-[#0a0a12] border border-[#1c1c2a] rounded-xl p-6 mb-6">
        <div className="flex items-start justify-between mb-5">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-[#00d4a0]/10 flex items-center justify-center">
              <CreditCard size={20} className="text-[#00d4a0]" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h3 className="text-lg font-semibold text-[#f0f0f5]">
                  {sub ? sub.plan : trial ? 'Trial' : 'No Plan'}
                </h3>
                <span className={`text-xs px-2.5 py-0.5 rounded-full border capitalize ${getPlanBadge(sub?.plan || 'hobby')}`}>
                  {sub ? sub.status : trial ? (trial.days_left > 0 ? `${trial.days_left}d left` : 'Expired') : 'Inactive'}
                </span>
              </div>
              <p className="text-sm text-[#9a9aae] mt-0.5">
                {sub
                  ? `${sub.provider} billing`
                  : trial
                    ? 'Free trial period'
                    : 'No active subscription or trial'}
              </p>
            </div>
          </div>

          {sub?.status === 'active' && (
            <button
              onClick={handleCancel}
              disabled={actionLoading === 'cancel'}
              className="text-sm text-[#9a9aae] hover:text-red-400 transition-colors disabled:opacity-50 border border-[#1c1c2a] hover:border-red-500/30 rounded-lg px-4 py-2"
            >
              {actionLoading === 'cancel' ? 'Canceling...' : 'Cancel Subscription'}
            </button>
          )}
        </div>

        {/* Usage progress */}
        {(sub || trial) && extractionLimit > 0 && (
          <div className="mb-5">
            <div className="flex items-center justify-between mb-2">
              <span className="text-sm text-[#9a9aae]">
                <Zap size={14} className="inline mr-1 text-[#00d4a0]" />
                Extractions this month
              </span>
              <span className="text-sm font-medium text-[#b8b8c8]">
                {extractionUsed.toLocaleString()} / {extractionLimit.toLocaleString()}
              </span>
            </div>
            <div className="w-full bg-[#14141f] rounded-full h-2.5 overflow-hidden">
              <div
                className={`h-full rounded-full transition-all duration-500 ${
                  usagePercent >= 90 ? 'bg-red-500' :
                  usagePercent >= 80 ? 'bg-yellow-500' :
                  'bg-[#00d4a0]'
                }`}
                style={{ width: `${usagePercent}%` }}
              />
            </div>
          </div>
        )}

        {/* Billing period / expiry info */}
        {(sub?.current_period_end || trial?.expires_at) && (
          <div className="flex items-center gap-2 text-sm text-[#9a9aae] mb-5">
            <Clock size={14} />
            {sub?.current_period_end && (
              <span>Renews {new Date(sub.current_period_end).toLocaleDateString('en-US', { year: 'numeric', month: 'long', day: 'numeric' })}</span>
            )}
            {trial?.expires_at && !sub && (
              <span>Trial expires {new Date(trial.expires_at).toLocaleDateString('en-US', { year: 'numeric', month: 'long', day: 'numeric' })}</span>
            )}
          </div>
        )}

        {/* Features list */}
        {currentPlanObj && currentPlanObj.features.length > 0 && (
          <div>
            <h4 className="text-sm font-medium text-[#b8b8c8] mb-2">Plan Features</h4>
            <ul className="grid grid-cols-1 sm:grid-cols-2 gap-1.5">
              {currentPlanObj.features.map((feat, i) => (
                <li key={i} className="flex items-start gap-2 text-sm text-[#9a9aae]">
                  <Check size={14} className="text-[#00d4a0] mt-0.5 flex-shrink-0" />
                  {feat}
                </li>
              ))}
            </ul>
          </div>
        )}

        {!sub && !trial && (
          <p className="text-[#9a9aae] text-sm">Choose a plan below to get started.</p>
        )}
      </div>

      {/* ── Quick Actions ── */}
      {(sub || trial) && (
        <div className="flex flex-wrap gap-3 mb-6">
          <a
            href="/dashboard/billing#upgrade"
            className="inline-flex items-center gap-2 bg-[#00d4a0] hover:bg-[#00b88a] text-white rounded-xl px-5 py-2.5 text-sm font-medium transition-colors"
          >
            <ArrowUpCircle size={16} />
            Upgrade Plan
          </a>
        </div>
      )}

      {/* ── Voucher Redemption ── */}
      <div className="bg-[#0a0a12] border border-[#1c1c2a] rounded-xl p-6 mb-6">
        <h3 className="text-lg font-semibold text-[#f0f0f5] mb-4 flex items-center gap-2">
          <Ticket size={20} className="text-amber-400" />
          Redeem Voucher
        </h3>
        <p className="text-sm text-[#9a9aae] mb-4">
          Got a voucher code? Enter it below to activate your subscription.
        </p>

        <div className="flex gap-3 flex-col sm:flex-row">
          <input
            type="text"
            placeholder="Enter voucher code (e.g., SWORD-STAR-EMBER)"
            value={voucherCode}
            onChange={e => setVoucherCode(e.target.value.toUpperCase())}
            disabled={redeeming}
            className="flex-1 px-4 py-2.5 bg-[#14141f] border border-[#1c1c2a] rounded-xl text-[#f0f0f5]
                       placeholder:text-[#5c5c70] focus:outline-none focus:border-amber-500/50 transition-colors
                       disabled:opacity-50 disabled:cursor-not-allowed"
          />
          <button
            onClick={handleRedeem}
            disabled={redeeming || !voucherCode.trim()}
            className="px-6 py-2.5 bg-amber-600 hover:bg-amber-500 disabled:bg-amber-800/50 disabled:cursor-not-allowed
                       text-white rounded-xl text-sm font-medium transition-colors whitespace-nowrap"
          >
            {redeeming ? 'Redeeming...' : 'Redeem Voucher'}
          </button>
        </div>

        {redeemResult && (
          <div className="mt-4 p-4 bg-green-500/10 border border-green-500/30 rounded-xl">
            <div className="flex items-start gap-3">
              <Check size={18} className="text-green-400 mt-0.5" />
              <div className="space-y-1">
                <p className="text-sm text-green-300 font-medium">
                  Voucher redeemed successfully!
                </p>
                <p className="text-xs text-green-400/80">
                  Plan: <span className="text-green-300 capitalize">{redeemResult.plan}</span> • Duration: {redeemResult.duration_days} days
                </p>
                {redeemResult.extraction_credits > 0 && (
                  <p className="text-xs text-green-400/80">
                    Bonus credits: {redeemResult.extraction_credits} extractions
                  </p>
                )}
                <p className="text-xs text-[#9a9aae]">
                  Active until {new Date(redeemResult.period_end).toLocaleDateString('en-US', {
                    year: 'numeric', month: 'long', day: 'numeric'
                  })}
                </p>
              </div>
            </div>
          </div>
        )}
      </div>

      {/* ── Compare Plans (compact grid) ── */}
      <div id="upgrade">
        <h3 className="text-lg font-semibold text-[#f0f0f5] mb-4 flex items-center gap-2">
          <ArrowUpCircle size={20} className="text-[#00d4a0]" />
          {sub ? 'Compare Plans' : 'Choose a Plan'}
        </h3>

        {plans.length === 0 ? (
          <p className="text-[#5c5c70] text-sm">No plans available.</p>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            {plans.map(plan => {
              const isCurrent = sub?.plan === plan.key;
              return (
                <div
                  key={plan.key}
                  className={`bg-[#0a0a12] border rounded-xl p-5 flex flex-col ${
                    isCurrent
                      ? 'border-[#00d4a0]/50 ring-1 ring-[#00d4a0]/20'
                      : 'border-[#1c1c2a]'
                  }`}
                >
                  <div className="mb-3">
                    <div className="flex items-center justify-between">
                      <h4 className="text-lg font-bold text-[#f0f0f5] capitalize">{plan.name}</h4>
                      {isCurrent && (
                        <span className="text-[10px] bg-[#00d4a0]/15 text-[#00d4a0] border border-[#00d4a0]/30 px-2 py-0.5 rounded-full font-medium">
                          Current
                        </span>
                      )}
                    </div>
                    <div className="text-xl font-bold text-[#f0f0f5] mt-1">
                      {formatPrice(plan.price_cents)}
                    </div>
                  </div>

                  <ul className="space-y-1.5 mb-5 flex-1">
                    {plan.features.slice(0, 4).map((feat, i) => (
                      <li key={i} className="flex items-start gap-2 text-sm text-[#9a9aae]">
                        <Check size={13} className="text-[#00d4a0] mt-0.5 flex-shrink-0" />
                        {feat}
                      </li>
                    ))}
                    {plan.features.length > 4 && (
                      <li className="text-xs text-[#5c5c70] pl-5">
                        +{plan.features.length - 4} more
                      </li>
                    )}
                  </ul>

                  {isCurrent ? (
                    <div className="text-center text-sm text-[#00d4a0] font-medium py-2 border border-[#00d4a0]/20 rounded-lg">
                      Current Plan
                    </div>
                  ) : (
                    <button
                      onClick={() => handleUpgrade(plan.key)}
                      disabled={actionLoading === plan.key}
                      className="w-full bg-[#00d4a0] hover:bg-[#00b88a] disabled:bg-[#00d4a0]/30 disabled:cursor-not-allowed
                                 text-white rounded-lg px-4 py-2 text-sm font-medium transition-colors"
                    >
                      {actionLoading === plan.key
                        ? 'Opening checkout...'
                        : plan.price_cents === 0
                          ? 'Select Free'
                          : plan.price_cents > (currentPlanObj?.price_cents ?? 0)
                            ? 'Upgrade'
                            : 'Downgrade'}
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
