import React, { useEffect, useState, useCallback } from 'react';
import { useAuth } from '../contexts/AuthContext';
import {
  ToggleLeft, ToggleRight, RefreshCw, AlertTriangle, Shield,
  User, Settings, X, CheckCircle,
} from 'lucide-react';

interface Feature {
  id: string;
  key: string;
  name: string;
  description: string | null;
  default_enabled: boolean;
  requires_plan: string | null;
}

interface UserOverride {
  user_id: string;
  feature_key: string;
  enabled: boolean;
}

const tierBadge = (tier: string | null) => {
  if (!tier) return null;
  const map: Record<string, string> = {
    free: 'bg-slate-500/10 text-slate-400 border-slate-500/30',
    starter: 'bg-blue-500/10 text-blue-400 border-blue-500/30',
    pro: 'bg-purple-500/10 text-purple-400 border-purple-500/30',
    enterprise: 'bg-amber-500/10 text-amber-400 border-amber-500/30',
  };
  return (
    <span className={`px-2 py-0.5 rounded text-xs font-medium border ${map[tier] || map.free}`}>
      {tier}
    </span>
  );
};

const Toast: React.FC<{ message: string; type: 'success' | 'error'; onClose: () => void }> = ({ message, type, onClose }) => {
  useEffect(() => {
    const t = setTimeout(onClose, 3000);
    return () => clearTimeout(t);
  }, [onClose]);
  return (
    <div className={`fixed bottom-6 right-6 z-50 flex items-center gap-2 px-4 py-3 rounded-lg shadow-lg border ${
      type === 'success' ? 'bg-emerald-900/90 border-emerald-700 text-emerald-200' : 'bg-red-900/90 border-red-700 text-red-200'
    }`}>
      {type === 'success' ? <CheckCircle size={16} /> : <AlertTriangle size={16} />}
      <span className="text-sm">{message}</span>
    </div>
  );
};

export const FeaturesPage: React.FC = () => {
  const { apiFetch } = useAuth();
  const [features, setFeatures] = useState<Feature[]>([]);
  const [users, setUsers] = useState<{ id: string; email: string; name: string | null }[]>([]);
  const [overrides, setOverrides] = useState<UserOverride[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<'features' | 'overrides'>('features');
  const [toast, setToast] = useState<{ message: string; type: 'success' | 'error' } | null>(null);

  // Override form state
  const [selectedUser, setSelectedUser] = useState('');
  const [selectedFeature, setSelectedFeature] = useState('');
  const [overrideEnabled, setOverrideEnabled] = useState(true);

  const loadFeatures = useCallback(async () => {
    try {
      const data = await apiFetch('/api/v1/admin/features');
      setFeatures(data || []);
    } catch (err: any) {
      setError(err.message || 'Failed to load features');
    } finally {
      setLoading(false);
    }
  }, [apiFetch]);

  const loadUsers = useCallback(async () => {
    try {
      const data = await apiFetch('/api/v1/admin/users');
      setUsers((data.users || []).map((u: any) => ({ id: u.id, email: u.email, name: u.name })));
    } catch (err: any) {
      // Silently fail — users optional for features tab
    }
  }, [apiFetch]);

  useEffect(() => {
    loadFeatures();
    loadUsers();
  }, [loadFeatures, loadUsers]);

  // Toggle feature globally
  const handleToggleFeature = useCallback(async (feature: Feature) => {
    try {
      const updated = await apiFetch(`/api/v1/admin/features/${feature.id}`, {
        method: 'PATCH',
        body: JSON.stringify({ default_enabled: !feature.default_enabled }),
      });
      setFeatures((prev) => prev.map((f) => (f.id === updated.id ? updated : f)));
      setToast({ message: `"${feature.name}" ${updated.default_enabled ? 'enabled' : 'disabled'}`, type: 'success' });
    } catch (err: any) {
      setToast({ message: err.message || 'Toggle failed', type: 'error' });
    }
  }, [apiFetch]);

  // Load overrides for selected user
  const loadOverrides = useCallback(async (userId: string) => {
    try {
      const data = await apiFetch(`/api/v1/admin/features/users/${userId}`);
      setOverrides(data || []);
    } catch (err: any) {
      setOverrides([]);
    }
  }, [apiFetch]);

  useEffect(() => {
    if (selectedUser) {
      loadOverrides(selectedUser);
    } else {
      setOverrides([]);
    }
  }, [selectedUser, loadOverrides]);

  // Add / update override
  const handleAddOverride = useCallback(async () => {
    if (!selectedUser || !selectedFeature) return;
    try {
      await apiFetch(`/api/v1/admin/features/users/${selectedUser}/override`, {
        method: 'POST',
        body: JSON.stringify({ feature_key: selectedFeature, enabled: overrideEnabled }),
      });
      setToast({ message: 'Override applied', type: 'success' });
      await loadOverrides(selectedUser);
      setSelectedFeature('');
    } catch (err: any) {
      setToast({ message: err.message || 'Override failed', type: 'error' });
    }
  }, [apiFetch, selectedUser, selectedFeature, overrideEnabled, loadOverrides]);

  // Remove override
  const handleRemoveOverride = useCallback(async (featureKey: string) => {
    if (!selectedUser) return;
    try {
      await apiFetch(`/api/v1/admin/features/users/${selectedUser}/override`, {
        method: 'POST',
        body: JSON.stringify({ feature_key: featureKey, enabled: false }),
      });
      setToast({ message: 'Override removed', type: 'success' });
      await loadOverrides(selectedUser);
    } catch (err: any) {
      setToast({ message: err.message || 'Remove failed', type: 'error' });
    }
  }, [apiFetch, selectedUser, loadOverrides]);

  if (error) {
    return (
      <div className="flex flex-col items-center justify-center h-64 text-red-400 gap-2">
        <AlertTriangle size={32} />
        <p>Failed to load features: {error}</p>
        <button onClick={loadFeatures} className="px-4 py-2 text-sm bg-slate-800 rounded-lg hover:bg-slate-700">
          Retry
        </button>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-xl font-bold text-white">Feature Flags</h2>
        <p className="text-sm text-slate-400 mt-1">Toggle features globally or override per user</p>
      </div>

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

      {/* Features Tab */}
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
                    <th className="text-left py-3 px-4 text-slate-400 font-medium">Min Plan</th>
                  </tr>
                </thead>
                <tbody>
                  {features.map((f) => (
                    <tr key={f.id} className="border-b border-slate-800/50 hover:bg-slate-800/30 transition-colors">
                      <td className="py-3 px-4">
                        <span className="text-white font-medium">{f.name}</span>
                        <span className="block text-xs text-slate-600 font-mono mt-0.5">{f.key}</span>
                      </td>
                      <td className="py-3 px-4 text-slate-400 max-w-xs truncate">
                        {f.description || '—'}
                      </td>
                      <td className="py-3 px-4 text-center">
                        <button
                          onClick={() => handleToggleFeature(f)}
                          className="inline-flex items-center gap-1.5 px-2 py-1 rounded-lg transition-colors"
                        >
                          {f.default_enabled ? (
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
                      <td className="py-3 px-4">{tierBadge(f.requires_plan)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {/* Overrides Tab */}
      {activeTab === 'overrides' && (
        <div className="space-y-6">
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
                  {users.map((u) => (
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
                    <option key={f.id} value={f.key}>{f.name}</option>
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

          <div className="bg-slate-900 border border-slate-800 rounded-xl overflow-hidden">
            {loading ? (
              <div className="flex items-center justify-center h-32 text-slate-500">
                <RefreshCw size={20} className="animate-spin mr-2" />
                Loading...
              </div>
            ) : !selectedUser ? (
              <div className="flex flex-col items-center justify-center h-32 text-slate-500 gap-2">
                <User size={20} />
                <p className="text-sm">Select a user to view overrides</p>
              </div>
            ) : overrides.length === 0 ? (
              <div className="flex flex-col items-center justify-center h-32 text-slate-500 gap-2">
                <Shield size={20} />
                <p className="text-sm">No overrides for this user</p>
              </div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-slate-800">
                      <th className="text-left py-3 px-4 text-slate-400 font-medium">Feature</th>
                      <th className="text-center py-3 px-4 text-slate-400 font-medium">Override</th>
                      <th className="text-right py-3 px-4 text-slate-400 font-medium">Actions</th>
                    </tr>
                  </thead>
                  <tbody>
                    {overrides.map((o) => (
                      <tr key={`${o.user_id}-${o.feature_key}`} className="border-b border-slate-800/50 hover:bg-slate-800/30 transition-colors">
                        <td className="py-3 px-4 text-white">
                          {features.find((f) => f.key === o.feature_key)?.name || o.feature_key}
                        </td>
                        <td className="py-3 px-4 text-center">
                          <span className={`px-2 py-0.5 rounded text-xs font-medium border ${
                            o.enabled
                              ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/30'
                              : 'bg-red-500/10 text-red-400 border-red-500/30'
                          }`}>
                            {o.enabled ? 'Enabled' : 'Disabled'}
                          </span>
                        </td>
                        <td className="py-3 px-4">
                          <div className="flex justify-end">
                            <button
                              onClick={() => handleRemoveOverride(o.feature_key)}
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
        <p><span className="text-emerald-400 font-medium">● On</span> — feature enabled by default</p>
        <p><span className="text-slate-600 font-medium">● Off</span> — feature disabled by default</p>
        <p><span className="text-blue-400 font-medium">● Override</span> — user-specific override of default</p>
      </div>

      {toast && <Toast message={toast.message} type={toast.type} onClose={() => setToast(null)} />}
    </div>
  );
};
