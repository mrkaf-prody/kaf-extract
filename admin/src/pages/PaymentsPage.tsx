import React, { useEffect, useState, useCallback } from 'react';
import { useAuth } from '../contexts/AuthContext';
import {
  CreditCard, Key, Save, AlertTriangle, RefreshCw,
  CheckCircle, XCircle, Clock, ExternalLink, Eye, EyeOff,
  Shield, Zap,
} from 'lucide-react';

// ─── Types ───

type Provider = 'lemonsqueezy' | 'paddle' | 'stripe' | 'manual';

interface ProviderInfo {
  api_key: string;
  webhook_secret: string;
  enabled: boolean;
}

interface PaymentConfig {
  active_provider: string;
  test_mode: boolean;
  providers: Record<string, ProviderInfo>;
}

interface Transaction {
  id: string;
  date: string;
  user_email: string;
  amount: number;
  currency: string;
  provider: Provider;
  status: 'completed' | 'pending' | 'failed' | 'refunded';
  description: string;
}

// ─── Helpers ───

const providerLabel = (p: string): string => {
  switch (p) {
    case 'lemonsqueezy': return 'Lemon Squeezy';
    case 'paddle': return 'Paddle';
    case 'stripe': return 'Stripe';
    case 'manual': return 'Manual';
    default: return p;
  }
};

const providerIconColor = (p: string): string => {
  switch (p) {
    case 'lemonsqueezy': return 'text-yellow-400';
    case 'paddle': return 'text-cyan-400';
    case 'stripe': return 'text-indigo-400';
    case 'manual': return 'text-slate-400';
    default: return 'text-slate-400';
  }
};

const statusBadge = (status: Transaction['status']) => {
  const map = {
    completed: 'bg-emerald-500/10 text-emerald-400 border-emerald-500/30',
    pending: 'bg-amber-500/10 text-amber-400 border-amber-500/30',
    failed: 'bg-red-500/10 text-red-400 border-red-500/30',
    refunded: 'bg-purple-500/10 text-purple-400 border-purple-500/30',
  };
  const icon = {
    completed: <CheckCircle size={12} />,
    pending: <Clock size={12} />,
    failed: <XCircle size={12} />,
    refunded: <RefreshCw size={12} />,
  };
  return (
    <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-medium border ${map[status]}`}>
      {icon[status]}
      {status.charAt(0).toUpperCase() + status.slice(1)}
    </span>
  );
};

function formatCurrency(amount: number, currency: string): string {
  return new Intl.NumberFormat('en-US', { style: 'currency', currency }).format(amount);
}

function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString('en-US', {
    month: 'short', day: 'numeric', year: 'numeric', hour: '2-digit', minute: '2-digit',
  });
}

// ─── Skeleton ───

const SkeletonBlock = ({ lines = 3 }: { lines?: number }) => (
  <div className="animate-pulse space-y-3">
    {Array.from({ length: lines }).map((_, i) => (
      <div key={i} className="h-10 bg-slate-800 rounded-lg" />
    ))}
  </div>
);

// ─── Toast ───

const Toast: React.FC<{ message: string; type: 'success' | 'error'; onClose: () => void }> = ({ message, type, onClose }) => {
  useEffect(() => {
    const t = setTimeout(onClose, 4000);
    return () => clearTimeout(t);
  }, [onClose]);

  return (
    <div className={`fixed bottom-6 right-6 z-50 flex items-center gap-3 px-4 py-3 rounded-lg shadow-lg border ${
      type === 'success'
        ? 'bg-emerald-900/90 border-emerald-700 text-emerald-200'
        : 'bg-red-900/90 border-red-700 text-red-200'
    }`}>
      {type === 'success' ? <CheckCircle size={16} /> : <AlertTriangle size={16} />}
      <span className="text-sm">{message}</span>
      <button onClick={onClose} className="ml-2 text-current opacity-60 hover:opacity-100">
        <XCircle size={14} />
      </button>
    </div>
  );
};

// ─── Page ───

export const PaymentsPage: React.FC = () => {
  const { apiFetch } = useAuth();

  // Config state
  const [config, setConfig] = useState<PaymentConfig | null>(null);
  const [configLoading, setConfigLoading] = useState(true);
  const [configError, setConfigError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [saveSuccess, setSaveSuccess] = useState(false);

  // Editable fields
  const [activeProvider, setActiveProvider] = useState<string>('manual');
  const [testMode, setTestMode] = useState(false);
  const [apiKeys, setApiKeys] = useState<Record<string, string>>({
    lemonsqueezy: '', paddle: '', stripe: '', manual: '',
  });
  const [webhookSecrets, setWebhookSecrets] = useState<Record<string, string>>({
    lemonsqueezy: '', paddle: '', stripe: '', manual: '',
  });
  const [showKey, setShowKey] = useState<Record<string, boolean>>({
    lemonsqueezy: false, paddle: false, stripe: false, manual: false,
  });

  // Transactions state
  const [transactions, setTransactions] = useState<Transaction[]>([]);
  const [txLoading, setTxLoading] = useState(true);
  const [txError, setTxError] = useState<string | null>(null);

  // Toast
  const [toast, setToast] = useState<{ message: string; type: 'success' | 'error' } | null>(null);

  // ─── Load config ───
  const loadConfig = useCallback(async () => {
    try {
      const data: PaymentConfig = await apiFetch('/v1/admin/payments');
      setConfig(data);
      setActiveProvider(data.active_provider);
      setTestMode(data.test_mode);
      const keys: Record<string, string> = {};
      const secrets: Record<string, string> = {};
      for (const [p, info] of Object.entries(data.providers)) {
        keys[p] = info.api_key || '';
        secrets[p] = info.webhook_secret || '';
      }
      setApiKeys(keys);
      setWebhookSecrets(secrets);
      setConfigError(null);
    } catch (err: any) {
      setConfigError(err.message || 'Failed to load payment config');
    } finally {
      setConfigLoading(false);
    }
  }, [apiFetch]);

  // ─── Load transactions (placeholder — no dedicated endpoint yet) ───
  const loadTransactions = useCallback(async () => {
    try {
      // No transactions endpoint yet — keep empty for now
      setTransactions([]);
      setTxError(null);
    } catch (err: any) {
      setTxError(err.message || 'Failed to load transactions');
    } finally {
      setTxLoading(false);
    }
  }, []);

  useEffect(() => {
    loadConfig();
    loadTransactions();
  }, [loadConfig, loadTransactions]);

  // ─── Save handler ───
  const handleSave = async () => {
    setSaving(true);
    setSaveSuccess(false);
    setConfigError(null);
    try {
      const payload: any = {
        active_provider: activeProvider,
        test_mode: testMode,
      };
      // Only send providers if they have values
      const providers: Record<string, { api_key: string; webhook_secret: string; enabled: boolean }> = {};
      for (const p of ['lemonsqueezy', 'paddle', 'stripe', 'manual'] as const) {
        providers[p] = {
          api_key: apiKeys[p] || '',
          webhook_secret: webhookSecrets[p] || '',
          enabled: config?.providers?.[p]?.enabled ?? true,
        };
      }
      payload.providers = providers;

      await apiFetch('/v1/admin/payments', {
        method: 'PATCH',
        body: JSON.stringify(payload),
      });
      setSaveSuccess(true);
      setToast({ message: 'Payment configuration saved', type: 'success' });
      setTimeout(() => setSaveSuccess(false), 2500);
      // Reload config to get masked values
      await loadConfig();
    } catch (err: any) {
      setConfigError(err.message || 'Failed to save config');
      setToast({ message: err.message || 'Save failed', type: 'error' });
    } finally {
      setSaving(false);
    }
  };

  // ─── Configuration Error ───
  if (configError && !config) {
    return (
      <div className="flex flex-col items-center justify-center h-64 text-red-400 gap-2">
        <AlertTriangle size={32} />
        <p>Failed to load payment settings: {configError}</p>
        <button
          onClick={loadConfig}
          className="mt-2 px-4 py-2 text-sm bg-slate-800 text-slate-300 rounded-lg hover:bg-slate-700 transition-colors"
        >
          Retry
        </button>
      </div>
    );
  }

  const providers = config?.providers || {};

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xl font-bold text-white">Payment Settings</h2>
          <p className="text-sm text-slate-400 mt-1">Configure payment providers and view transaction history</p>
        </div>
      </div>

      {/* ─── Provider Configuration ─── */}
      <div className="bg-slate-900 border border-slate-800 rounded-xl p-6">
        <h3 className="text-sm font-semibold text-white mb-5 flex items-center gap-2">
          <Shield size={16} className="text-blue-400" />
          Payment Provider Configuration
        </h3>

        {configLoading ? (
          <SkeletonBlock lines={4} />
        ) : (
          <>
            {/* Active provider selector */}
            <div className="mb-6">
              <label className="block text-sm text-slate-400 mb-3">Active Provider</label>
              <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
                {(Object.keys(apiKeys) as Provider[]).map((provider) => (
                  <label
                    key={provider}
                    className={`relative flex items-center gap-3 p-3 rounded-lg border cursor-pointer transition-all ${
                      activeProvider === provider
                        ? 'bg-blue-500/10 border-blue-500/50 ring-1 ring-blue-500/20'
                        : 'bg-slate-800/50 border-slate-700 hover:border-slate-600'
                    }`}
                  >
                    <input
                      type="radio"
                      name="active_provider"
                      value={provider}
                      checked={activeProvider === provider}
                      onChange={() => setActiveProvider(provider)}
                      className="sr-only"
                    />
                    <CreditCard size={18} className={activeProvider === provider ? 'text-blue-400' : 'text-slate-500'} />
                    <div>
                      <p className={`text-sm font-medium ${activeProvider === provider ? 'text-white' : 'text-slate-400'}`}>
                        {providerLabel(provider)}
                      </p>
                      <p className="text-xs text-slate-600">
                        {providers[provider]?.enabled ? 'Enabled' : 'Disabled'}
                      </p>
                    </div>
                    {/* Active dot */}
                    {activeProvider === provider && (
                      <span className="absolute top-2 right-2 w-2 h-2 rounded-full bg-blue-400" />
                    )}
                  </label>
                ))}
              </div>
            </div>

            {/* API Keys per provider */}
            <div className="space-y-4 mb-6">
              {(Object.keys(apiKeys) as Provider[]).map((provider) => (
                <div key={provider} className="p-4 bg-slate-800/50 rounded-lg border border-slate-700/50">
                  <div className="flex items-center gap-2 mb-3">
                    <CreditCard size={14} className={providerIconColor(provider)} />
                    <span className="text-sm font-medium text-slate-300">{providerLabel(provider)}</span>
                    {!providers[provider]?.enabled && (
                      <span className="text-xs px-2 py-0.5 rounded bg-slate-700 text-slate-500">Disabled</span>
                    )}
                  </div>
                  <div className="grid grid-cols-1 lg:grid-cols-2 gap-3">
                    {/* API Key */}
                    <div>
                      <label className="block text-xs text-slate-500 mb-1">API Key</label>
                      <div className="relative">
                        <input
                          type={showKey[provider] ? 'text' : 'password'}
                          value={apiKeys[provider] || ''}
                          onChange={(e) => setApiKeys((prev) => ({ ...prev, [provider]: e.target.value }))}
                          placeholder={
                            providers[provider]?.enabled
                              ? `Enter ${providerLabel(provider)} API key...`
                              : 'Provider disabled'
                          }
                          disabled={!providers[provider]?.enabled}
                          className="w-full pl-3 pr-10 py-2 bg-slate-900 border border-slate-700 rounded-lg text-sm text-white placeholder-slate-600 font-mono focus:outline-none focus:border-blue-500 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                        />
                        <button
                          type="button"
                          onClick={() => setShowKey((prev) => ({ ...prev, [provider]: !prev[provider] }))}
                          className="absolute right-2 top-1/2 -translate-y-1/2 text-slate-500 hover:text-slate-300 transition-colors"
                          disabled={!providers[provider]?.enabled}
                        >
                          {showKey[provider] ? <EyeOff size={14} /> : <Eye size={14} />}
                        </button>
                      </div>
                    </div>
                    {/* Webhook Secret */}
                    <div>
                      <label className="block text-xs text-slate-500 mb-1">Webhook Secret</label>
                      <input
                        type="password"
                        value={webhookSecrets[provider] || ''}
                        onChange={(e) => setWebhookSecrets((prev) => ({ ...prev, [provider]: e.target.value }))}
                        placeholder={
                          providers[provider]?.enabled
                            ? `Enter webhook secret...`
                            : 'Provider disabled'
                        }
                        disabled={!providers[provider]?.enabled}
                        className="w-full px-3 py-2 bg-slate-900 border border-slate-700 rounded-lg text-sm text-white placeholder-slate-600 font-mono focus:outline-none focus:border-blue-500 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                      />
                    </div>
                  </div>
                </div>
              ))}
            </div>

            {/* Test mode toggle */}
            <div className="flex items-center justify-between p-4 bg-slate-800/50 rounded-lg border border-slate-700/50 mb-6">
              <div className="flex items-center gap-3">
                <Zap size={18} className={testMode ? 'text-amber-400' : 'text-slate-500'} />
                <div>
                  <p className="text-sm text-slate-300">Test Mode</p>
                  <p className="text-xs text-slate-500">
                    {testMode ? 'Using sandbox/test environments' : 'Processing real payments'}
                  </p>
                </div>
              </div>
              <button
                onClick={() => setTestMode((prev) => !prev)}
                className={`relative w-11 h-6 rounded-full transition-colors ${
                  testMode ? 'bg-amber-600' : 'bg-slate-700'
                }`}
              >
                <span
                  className={`absolute top-0.5 left-0.5 w-5 h-5 bg-white rounded-full shadow transition-transform ${
                    testMode ? 'translate-x-5' : 'translate-x-0'
                  }`}
                />
              </button>
            </div>

            {/* Save button + feedback */}
            <div className="flex items-center gap-4">
              <button
                onClick={handleSave}
                disabled={saving}
                className="flex items-center gap-2 px-5 py-2.5 text-sm font-medium text-white bg-blue-600 rounded-lg hover:bg-blue-500 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
              >
                {saving ? (
                  <RefreshCw size={15} className="animate-spin" />
                ) : (
                  <Save size={15} />
                )}
                {saving ? 'Saving...' : 'Save Configuration'}
              </button>

              {saveSuccess && (
                <span className="flex items-center gap-1 text-sm text-emerald-400 animate-pulse">
                  <CheckCircle size={14} />
                  Saved successfully
                </span>
              )}

              {configError && (
                <span className="flex items-center gap-1 text-sm text-red-400">
                  <AlertTriangle size={14} />
                  {configError}
                </span>
              )}
            </div>
          </>
        )}
      </div>

      {/* ─── Transaction History ─── */}
      <div className="bg-slate-900 border border-slate-800 rounded-xl overflow-hidden">
        <div className="p-5 border-b border-slate-800 flex items-center justify-between">
          <h3 className="text-sm font-semibold text-white flex items-center gap-2">
            <CreditCard size={16} className="text-emerald-400" />
            Transaction History
          </h3>
          <button
            onClick={() => { setTxLoading(true); loadTransactions(); }}
            className="flex items-center gap-2 px-3 py-1.5 text-sm text-slate-400 bg-slate-800 rounded-lg hover:bg-slate-700 transition-colors"
          >
            <RefreshCw size={14} className={txLoading ? 'animate-spin' : ''} />
            Refresh
          </button>
        </div>

        {txLoading ? (
          <div className="flex items-center justify-center h-48 text-slate-500">
            <RefreshCw size={24} className="animate-spin mr-2" />
            Loading transactions...
          </div>
        ) : txError ? (
          <div className="flex flex-col items-center justify-center h-48 text-red-400 gap-2">
            <AlertTriangle size={24} />
            <p className="text-sm">{txError}</p>
          </div>
        ) : transactions.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-48 text-slate-500 gap-2">
            <CreditCard size={24} />
            <p>No transactions found</p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-slate-800">
                  <th className="text-left py-3 px-4 text-slate-400 font-medium">Date</th>
                  <th className="text-left py-3 px-4 text-slate-400 font-medium">User</th>
                  <th className="text-left py-3 px-4 text-slate-400 font-medium">Description</th>
                  <th className="text-right py-3 px-4 text-slate-400 font-medium">Amount</th>
                  <th className="text-left py-3 px-4 text-slate-400 font-medium">Provider</th>
                  <th className="text-left py-3 px-4 text-slate-400 font-medium">Status</th>
                </tr>
              </thead>
              <tbody>
                {transactions.map((txn) => (
                  <tr key={txn.id} className="border-b border-slate-800/50 hover:bg-slate-800/30 transition-colors">
                    <td className="py-3 px-4 text-slate-300 text-xs font-mono">{formatDate(txn.date)}</td>
                    <td className="py-3 px-4 text-slate-300 text-xs">{txn.user_email}</td>
                    <td className="py-3 px-4 text-slate-400 text-xs">{txn.description}</td>
                    <td className="py-3 px-4 text-right text-white font-mono text-xs font-medium">
                      {formatCurrency(txn.amount, txn.currency)}
                    </td>
                    <td className="py-3 px-4">
                      <span className={`text-xs font-medium ${providerIconColor(txn.provider)}`}>
                        {providerLabel(txn.provider)}
                      </span>
                    </td>
                    <td className="py-3 px-4">{statusBadge(txn.status)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {/* Row count */}
        {!txLoading && transactions.length > 0 && (
          <div className="p-3 border-t border-slate-800">
            <p className="text-xs text-slate-600">
              Showing {transactions.length} transactions
            </p>
          </div>
        )}
      </div>

      {/* Toast notifications */}
      {toast && (
        <Toast
          message={toast.message}
          type={toast.type}
          onClose={() => setToast(null)}
        />
      )}
    </div>
  );
};
