import React, { useEffect, useState, useMemo, useCallback } from 'react';
import { useAuth } from '../contexts/AuthContext';
import {
  ToggleLeft, ToggleRight, RefreshCw, AlertTriangle, Shield,
  User, Search, Settings, X,
} from 'lucide-react';

// ─── Types ───

interface Feature {
  id: string;
  name: string;
  description: string;
  enabled: boolean;
  tier_required: 'free' | 'starter' | 'pro' | 'enterprise';
}

interface UserOverride {
  id: string;
  user_email: string;
  feature_id: string;
  enabled: boolean;
}

// ─── Mock Data ───

const MOCK_FEATURES: Feature[] = [
  { id: 'f1', name: 'Data Extraction', description: 'Core data extraction engine with AI-powered parsing', enabled: true, tier_required: 'starter' },
  { id: 'f2', name: 'Batch Processing', description: 'Process multiple documents simultaneously', enabled: true, tier_required: 'pro' },
  { id: 'f3', name: 'Custom Pipelines', description: 'Build and save custom extraction pipelines', enabled: true, tier_required: 'pro' },
  { id: 'f4', name: 'API Access', description: 'Programmatic access via REST API', enabled: true, tier_required: 'starter' },
  { id: 'f5', name: 'Webhook Integration', description: 'Receive extraction results via webhooks', enabled: false, tier_required: 'enterprise' },
  { id: 'f6', name: 'Advanced Analytics', description: 'Detailed extraction analytics and reporting', enabled: true, tier_required: 'enterprise' },
  { id: 'f7', name: 'Export to Cloud', description: 'Export results directly to S3/GCS/Azure', enabled: false, tier_required: 'pro' },
  { id: 'f8', name: 'Team Collaboration', description: 'Share and collaborate on extraction projects', enabled: true, tier_required: 'starter' },
  { id: 'f9', name: 'Custom Models', description: 'Train and deploy custom extraction models', enabled: false, tier_required: 'enterprise' },
  { id: 'f10', name: 'Dark Mode', description: 'Dark theme support across the application', enabled: true, tier_required: 'free' },
];

// Users available for override
const MOCK_USERS = [
  { id: 'u1', email: 'alice@example.com', name: 'Alice Johnson' },
  { id: 'u2', email: 'bob@acme.com', name: 'Bob Smith' },
  { id: 'u3', email: 'carol@demo.io', name: 'Carol Williams' },
  { id: 'u4', email: 'dave@test.com', name: 'Dave Brown' },
];

const MOCK_OVERRIDES: UserOverride[] = [
  { id: 'o1', user_email: 'alice@example.com', feature_id: 'f5', enabled: true },
  { id: 'o2', user_email: 'bob@acme.com', feature_id: 'f7', enabled: true },
  { id: 'o3', user_email: 'alice@example.com', feature_id: 'f9', enabled: true },
];

// ─── Badge helpers ───

const tierBadge = (tier: Feature['tier_required']) => {
  const map: Record<string, string> = {
    free: 'bg-slate-500/10 text-slate-400 border-slate-500/30',
    starter: 'bg-blue-500/10 text-blue-400 border-blue-500/30',
    pro: 'bg-purple-500/10 text-purple-400 border-purple-500/30',
    enterprise: 'bg-amber-500/10 text-amber-400 border-amber-500/30',
  };
  return `px-2 py-0.5 rounded text-xs font-medium border ${map[tier]}`;
};

// ─── Page ───

export const FeaturesPage: React.FC = () => {
  const { apiFetch } = useAuth();
  const [features, setFeatures] = useState<Feature[]>([]);
  const [overrides, setOverrides] = useState<UserOverride[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<'features' | 'overrides'>('features');

  // Override form
  const [selectedUser, setSelectedUser] = useState('');
  const [selectedFeature, setSelectedFeature] = useState('');
  const [overrideEnabled, setOverrideEnabled] = useState(true);

  // Load
  useEffect(() => {
    // TODO: Replace with real APIs:
    // apiFetch('/v1/admin/features') → setFeatures
    // apiFetch('/v1/admin/features/overrides') → setOverrides
    const timer = setTimeout(() => {
      setFeatures(MOCK_FEATURES);
      setOverrides(MOCK_OVERRIDES);
      setLoading(false);
    }, 700);
    return () => clearTimeout(timer);
  }, []);

  // ─── Toggle feature globally ───
  const handleToggleFeature = useCallback((featureId: string) => {
    setFeatures((prev) =>
      prev.map((f) => (f.id === featureId ? { ...f, enabled: !f.enabled } : f))
    );
    // TODO: apiFetch(`/v1/admin/features/${featureId}`, { method: 'PATCH', body: JSON.stringify({ enabled: !enabled }) });
  }, []);

  // ─── Add override ───
  const handleAddOverride = useCallback(() => {
    if (!selectedUser || !selectedFeature) return;
    const user = MOCK_USERS.find((u) => u.id === selectedUser);
    if (!user) return;

    // Check existing
    const existing = overrides.find(
      (o) => o.user_email === user.email && o.feature_id === selectedFeature
    );
    if (existing) {
      setOverrides((prev) =>
        prev.map((o) =>
          o.id === existing.id ? { ...o, enabled: overrideEnabled } : o
        )
      );
    } else {
      const newOverride: UserOverride = {
        id: `o${Date.now()}`,
        user_email: user.email,
        feature_id: selectedFeature,
        enabled: overrideEnabled,
      };
      setOverrides((prev) => [...prev, newOverride]);
    }
    // TODO: apiFetch('/v1/admin/features/overrides', { method: 'POST', body: JSON.stringify({ user_email: user.email, feature_id: selectedFeature, enabled: overrideEnabled }) });
  }, [selectedUser, selectedFeature, overrideEnabled, overrides]);

  // ─── Remove override ───
  const handleRemoveOverride = useCallback((overrideId: string) => {
    setOverrides((prev) => prev.filter((o) => o.id !== overrideId));
    // TODO: apiFetch(`/v1/admin/features/overrides/${overrideId}`, { method: 'DELETE' });
  }, []);

  const featureMap = useMemo(() => {
    const map: Record<string, Feature> = {};
    features.forEach((f) => (map[f.id] = f));
    return map;
  }, [features]);

  if (error) {
    return (
      <div className="flex flex-col items-center justify-center h-64 text-red-400 gap-2">
        <AlertTriangle size={32} />
        <p>Failed to load features: {error}</p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h2 className="text-xl font-bold text-white">Feature Flags</h2>
        <p className="text-sm text-slate-400 mt-1">Toggle features globally or override per user</p>
      </div>

      {/* Tabs */}
      <div className="flex gap-1 bg-slate-900 rounded-lg p-1 w-fit border border-slate-800">
        <button
          onClick={() => setActiveTab('features')}
          className={`px-4 py-1.5 text-sm rounded-md transition-colors ${
            activeTab === 'features' ? 'bg-blue-600 text-white' : 'text-slate-400 hover:text-white'
          }`}
        >
          <Shield size={14} className="inline mr-1" />
          Feature Toggles
        </button>
        <button
          onClick={() => setActiveTab('overrides')}
          className={`px-4 py-1.5 text-sm rounded-md transition-colors ${
            activeTab === 'overrides' ? 'bg-blue-600 text-white' : 'text-slate-400 hover:text-white'
          }`}
        >
          <User size={14} className="inline mr-1" />
          User Overrides
        </button>
      </div>

      {/* ─── Feature Toggles ─── */}
      {activeTab === 'features' && (
        <div className="bg-slate-900 border border-slate-800 rounded-xl overflow-hidden">
          {loading ? (
            <div className="flex items-center justify-center h-48 text-slate-500">
              <RefreshCw size={24} className="animate-spin mr-2" />
              Loading features...
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-slate-800">
                    <th className="text-left py-3 px-4 text-slate-400 font-medium">Feature</th>
                    <th className="text-left py-3 px-4 text-slate-400 font-medium">Description</th>
                    <th className="text-center py-3 px-4 text-slate-400 font-medium">Status</th>
                    <th className="text-left py-3 px-4 text-slate-400 font-medium">Min Tier</th>
                  </tr>
                </thead>
                <tbody>
                  {features.map((f) => (
                    <tr key={f.id} className="border-b border-slate-800/50 hover:bg-slate-800/30 transition-colors">
                      <td className="py-3 px-4">
                        <span className="text-white font-medium">{f.name}</span>
                      </td>
                      <td className="py-3 px-4 text-slate-400 max-w-xs truncate">
                        {f.description}
                      </td>
                      <td className="py-3 px-4 text-center">
                        <button
                          onClick={() => handleToggleFeature(f.id)}
                          className="inline-flex items-center gap-1.5 px-2 py-1 rounded-lg transition-colors"
                        >
                          {f.enabled ? (
                            <>
                              <ToggleRight size={20} className="text-emerald-400" />
                              <span className="text-xs text-emerald-400">On</span>
                            </>
                          ) : (
                            <>
                              <ToggleLeft size={20} className="text-slate-600" />
                              <span className="text-xs text-slate-500">Off</span>
                            </>
                          )}
                        </button>
                      </td>
                      <td className="py-3 px-4">
                        <span className={tierBadge(f.tier_required)}>{f.tier_required}</span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {/* ─── User Overrides ─── */}
      {activeTab === 'overrides' && (
        <div className="space-y-6">
          {/* New Override Form */}
          <div className="bg-slate-900 border border-slate-800 rounded-xl p-5">
            <h3 className="text-sm font-semibold text-white mb-4 flex items-center gap-2">
              <Settings size={15} /> Add User Override
            </h3>
            <div className="grid grid-cols-1 sm:grid-cols-4 gap-3 items-end">
              <div>
                <label className="block text-xs text-slate-500 mb-1">User</label>
                <select
                  value={selectedUser}
                  onChange={(e) => setSelectedUser(e.target.value)}
                  className="w-full px-3 py-2 bg-slate-800 border border-slate-700 rounded-lg text-sm text-white focus:outline-none focus:border-blue-500"
                >
                  <option value="">Select user...</option>
                  {MOCK_USERS.map((u) => (
                    <option key={u.id} value={u.id}>{u.email}</option>
                  ))}
                </select>
              </div>
              <div>
                <label className="block text-xs text-slate-500 mb-1">Feature</label>
                <select
                  value={selectedFeature}
                  onChange={(e) => setSelectedFeature(e.target.value)}
                  className="w-full px-3 py-2 bg-slate-800 border border-slate-700 rounded-lg text-sm text-white focus:outline-none focus:border-blue-500"
                >
                  <option value="">Select feature...</option>
                  {features.map((f) => (
                    <option key={f.id} value={f.id}>{f.name}</option>
                  ))}
                </select>
              </div>
              <div>
                <label className="block text-xs text-slate-500 mb-1">Toggle</label>
                <button
                  onClick={() => setOverrideEnabled(!overrideEnabled)}
                  className={`flex items-center gap-1.5 px-3 py-2 rounded-lg border transition-colors text-sm w-full justify-center ${
                    overrideEnabled
                      ? 'bg-emerald-500/10 border-emerald-500/30 text-emerald-400'
                      : 'bg-slate-800 border-slate-700 text-slate-500'
                  }`}
                >
                  {overrideEnabled ? <ToggleRight size={16} /> : <ToggleLeft size={16} />}
                  {overrideEnabled ? 'Enable' : 'Disable'}
                </button>
              </div>
              <button
                onClick={handleAddOverride}
                disabled={!selectedUser || !selectedFeature}
                className="px-4 py-2 text-sm font-medium text-white bg-blue-600 rounded-lg hover:bg-blue-500 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
              >
                Apply Override
              </button>
            </div>
          </div>

          {/* Existing Overrides */}
          <div className="bg-slate-900 border border-slate-800 rounded-xl overflow-hidden">
            {loading ? (
              <div className="flex items-center justify-center h-32 text-slate-500">
                <RefreshCw size={20} className="animate-spin mr-2" />
                Loading overrides...
              </div>
            ) : overrides.length === 0 ? (
              <div className="flex flex-col items-center justify-center h-32 text-slate-500 gap-2">
                <Shield size={20} />
                <p className="text-sm">No user overrides configured</p>
              </div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-slate-800">
                      <th className="text-left py-3 px-4 text-slate-400 font-medium">User</th>
                      <th className="text-left py-3 px-4 text-slate-400 font-medium">Feature</th>
                      <th className="text-center py-3 px-4 text-slate-400 font-medium">Override</th>
                      <th className="text-right py-3 px-4 text-slate-400 font-medium">Actions</th>
                    </tr>
                  </thead>
                  <tbody>
                    {overrides.map((o) => (
                      <tr key={o.id} className="border-b border-slate-800/50 hover:bg-slate-800/30 transition-colors">
                        <td className="py-3 px-4 text-white font-mono text-xs">{o.user_email}</td>
                        <td className="py-3 px-4 text-slate-300">
                          {featureMap[o.feature_id]?.name || o.feature_id}
                        </td>
                        <td className="py-3 px-4 text-center">
                          <span
                            className={`px-2 py-0.5 rounded text-xs font-medium border ${
                              o.enabled
                                ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/30'
                                : 'bg-red-500/10 text-red-400 border-red-500/30'
                            }`}
                          >
                            {o.enabled ? 'Enabled' : 'Disabled'}
                          </span>
                        </td>
                        <td className="py-3 px-4">
                          <div className="flex justify-end">
                            <button
                              onClick={() => handleRemoveOverride(o.id)}
                              className="flex items-center gap-1 px-2 py-1.5 text-xs text-red-400 bg-red-500/10 rounded-lg hover:bg-red-500/20 transition-colors"
                            >
                              <X size={12} />
                              Remove
                            </button>
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Legend */}
      <div className="flex flex-wrap gap-4 text-xs text-slate-500 bg-slate-900 border border-slate-800 rounded-lg p-4">
        <p>
          <span className="text-emerald-400 font-medium">● Enabled</span> — feature is globally on (subject to user tier)
        </p>
        <p>
          <span className="text-slate-600 font-medium">● Disabled</span> — feature is globally off for all users
        </p>
        <p>
          <span className="text-blue-400 font-medium">● Override</span> — user-specific toggle overrides tier/global settings
        </p>
      </div>
    </div>
  );
};
