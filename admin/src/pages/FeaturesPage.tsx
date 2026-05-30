import React, { useEffect, useState, useCallback } from 'react';
import { useAuth } from '../contexts/AuthContext';
import {
  ToggleLeft, ToggleRight, RefreshCw, AlertTriangle, Shield,
  User, Settings, X, CheckCircle, Plus, Edit3, Trash2,
  CreditCard, Package,
} from 'lucide-react';

// ─── Types ───
interface Feature {
  id: string;
  key: string;
  name: string;
  description: string | null;
  default_enabled: boolean;
  requires_plan: string | null;
}

interface Plan {
  id: string;
  key: string;
  name: string;
  description: string | null;
  price_cents: number;
  currency: string;
  billing_period: string;
  extractions_per_month: number;
  is_active: boolean;
  sort_order: number;
  features: string[];
}

interface UserOverride {
  user_id: string;
  feature_key: string;
  enabled: boolean;
}

// ─── Helpers ───
const formatPrice = (cents: number) => {
  if (cents === 0) return 'Free';
  return `$${(cents / 100).toFixed(0)}/mo`;
};

const tierBadge = (tier: string | null) => {
  if (!tier) return null;
  const map: Record<string, string> = {
    free: 'bg-slate-500/10 text-slate-400 border-slate-500/30',
    hobby: 'bg-green-500/10 text-green-400 border-green-500/30',
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

// ─── Toast ───
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

// ─── Modal: Create/Edit Feature ───
const FeatureModal: React.FC<{
  open: boolean;
  feature: Feature | null;
  onClose: () => void;
  onSave: (data: any) => Promise<void>;
}> = ({ open, feature, onClose, onSave }) => {
  const [key, setKey] = useState('');
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [defaultEnabled, setDefaultEnabled] = useState(true);
  const [requiresPlan, setRequiresPlan] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    if (feature) {
      setKey(feature.key);
      setName(feature.name);
      setDescription(feature.description || '');
      setDefaultEnabled(feature.default_enabled);
      setRequiresPlan(feature.requires_plan || '');
    } else {
      setKey(''); setName(''); setDescription(''); setDefaultEnabled(true); setRequiresPlan('');
    }
    setError('');
  }, [feature, open]);

  if (!open) return null;

  const isEdit = !!feature;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError('');
    try {
      await onSave({
        key, name, description: description || null,
        default_enabled: defaultEnabled,
        requires_plan: requiresPlan || null,
      });
      onClose();
    } catch (err: any) {
      setError(err.message || 'Failed to save feature');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm">
      <div className="bg-slate-900 border border-slate-700 rounded-xl p-6 w-full max-w-md shadow-2xl">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-lg font-bold text-white">{isEdit ? 'Edit Feature' : 'Create Feature'}</h3>
          <button onClick={onClose} className="text-slate-500 hover:text-white"><X size={18} /></button>
        </div>
        <form onSubmit={handleSubmit} className="space-y-3">
          <div>
            <label className="block text-xs text-slate-500 mb-1">Key *</label>
            <input value={key} onChange={e => setKey(e.target.value)} required disabled={isEdit}
              className="w-full px-3 py-2 bg-slate-800 border border-slate-700 rounded-lg text-sm text-white focus:border-blue-500 focus:outline-none disabled:opacity-50" />
          </div>
          <div>
            <label className="block text-xs text-slate-500 mb-1">Name *</label>
            <input value={name} onChange={e => setName(e.target.value)} required
              className="w-full px-3 py-2 bg-slate-800 border border-slate-700 rounded-lg text-sm text-white focus:border-blue-500 focus:outline-none" />
          </div>
          <div>
            <label className="block text-xs text-slate-500 mb-1">Description</label>
            <input value={description} onChange={e => setDescription(e.target.value)}
              className="w-full px-3 py-2 bg-slate-800 border border-slate-700 rounded-lg text-sm text-white focus:border-blue-500 focus:outline-none" />
          </div>
          <div>
            <label className="block text-xs text-slate-500 mb-1">Requires Plan</label>
            <input value={requiresPlan} onChange={e => setRequiresPlan(e.target.value)} placeholder="e.g. pro, enterprise"
              className="w-full px-3 py-2 bg-slate-800 border border-slate-700 rounded-lg text-sm text-white focus:border-blue-500 focus:outline-none" />
          </div>
          <div className="flex items-center gap-2">
            <input type="checkbox" id="defaultEnabled" checked={defaultEnabled} onChange={e => setDefaultEnabled(e.target.checked)}
              className="rounded border-slate-700" />
            <label htmlFor="defaultEnabled" className="text-sm text-slate-400">Enabled by default</label>
          </div>
          {error && <p className="text-xs text-red-400">{error}</p>}
          <div className="flex justify-end gap-2 pt-2">
            <button type="button" onClick={onClose} className="px-4 py-2 text-sm text-slate-300 hover:text-white">Cancel</button>
            <button type="submit" disabled={loading}
              className="px-4 py-2 text-sm font-medium text-white bg-blue-600 rounded-lg hover:bg-blue-500 disabled:opacity-50">
              {loading ? 'Saving...' : (isEdit ? 'Save' : 'Create')}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};

// ─── Modal: Create/Edit Plan ───
const PlanModal: React.FC<{
  open: boolean;
  plan: Plan | null;
  onClose: () => void;
  onSave: (data: any) => Promise<void>;
}> = ({ open, plan, onClose, onSave }) => {
  const [key, setKey] = useState('');
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [priceCents, setPriceCents] = useState(0);
  const [extractions, setExtractions] = useState(0);
  const [isActive, setIsActive] = useState(true);
  const [sortOrder, setSortOrder] = useState(0);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    if (plan) {
      setKey(plan.key); setName(plan.name); setDescription(plan.description || '');
      setPriceCents(plan.price_cents); setExtractions(plan.extractions_per_month);
      setIsActive(plan.is_active); setSortOrder(plan.sort_order);
    } else {
      setKey(''); setName(''); setDescription(''); setPriceCents(0); setExtractions(0);
      setIsActive(true); setSortOrder(0);
    }
    setError('');
  }, [plan, open]);

  if (!open) return null;
  const isEdit = !!plan;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError('');
    try {
      await onSave({
        key, name, description: description || null,
        price_cents: priceCents, extractions_per_month: extractions,
        is_active: isActive, sort_order: sortOrder,
      });
      onClose();
    } catch (err: any) {
      setError(err.message || 'Failed to save plan');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm">
      <div className="bg-slate-900 border border-slate-700 rounded-xl p-6 w-full max-w-md shadow-2xl">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-lg font-bold text-white">{isEdit ? 'Edit Plan' : 'Create Plan'}</h3>
          <button onClick={onClose} className="text-slate-500 hover:text-white"><X size={18} /></button>
        </div>
        <form onSubmit={handleSubmit} className="space-y-3">
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs text-slate-500 mb-1">Key *</label>
              <input value={key} onChange={e => setKey(e.target.value)} required disabled={isEdit} placeholder="pro"
                className="w-full px-3 py-2 bg-slate-800 border border-slate-700 rounded-lg text-sm text-white focus:border-blue-500 focus:outline-none disabled:opacity-50" />
            </div>
            <div>
              <label className="block text-xs text-slate-500 mb-1">Name *</label>
              <input value={name} onChange={e => setName(e.target.value)} required placeholder="Pro"
                className="w-full px-3 py-2 bg-slate-800 border border-slate-700 rounded-lg text-sm text-white focus:border-blue-500 focus:outline-none" />
            </div>
          </div>
          <div>
            <label className="block text-xs text-slate-500 mb-1">Description</label>
            <input value={description} onChange={e => setDescription(e.target.value)}
              className="w-full px-3 py-2 bg-slate-800 border border-slate-700 rounded-lg text-sm text-white focus:border-blue-500 focus:outline-none" />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs text-slate-500 mb-1">Price (cents)</label>
              <input type="number" value={priceCents} onChange={e => setPriceCents(Number(e.target.value))} min={0}
                className="w-full px-3 py-2 bg-slate-800 border border-slate-700 rounded-lg text-sm text-white focus:border-blue-500 focus:outline-none" />
            </div>
            <div>
              <label className="block text-xs text-slate-500 mb-1">Extractions/mo</label>
              <input type="number" value={extractions} onChange={e => setExtractions(Number(e.target.value))} min={0}
                className="w-full px-3 py-2 bg-slate-800 border border-slate-700 rounded-lg text-sm text-white focus:border-blue-500 focus:outline-none" />
            </div>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs text-slate-500 mb-1">Sort Order</label>
              <input type="number" value={sortOrder} onChange={e => setSortOrder(Number(e.target.value))}
                className="w-full px-3 py-2 bg-slate-800 border border-slate-700 rounded-lg text-sm text-white focus:border-blue-500 focus:outline-none" />
            </div>
            <div className="flex items-center gap-2 pt-5">
              <input type="checkbox" id="planActive" checked={isActive} onChange={e => setIsActive(e.target.checked)} />
              <label htmlFor="planActive" className="text-sm text-slate-400">Active</label>
            </div>
          </div>
          {error && <p className="text-xs text-red-400">{error}</p>}
          <div className="flex justify-end gap-2 pt-2">
            <button type="button" onClick={onClose} className="px-4 py-2 text-sm text-slate-300 hover:text-white">Cancel</button>
            <button type="submit" disabled={loading}
              className="px-4 py-2 text-sm font-medium text-white bg-blue-600 rounded-lg hover:bg-blue-500 disabled:opacity-50">
              {loading ? 'Saving...' : (isEdit ? 'Save' : 'Create')}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};

// ─── Page ───
export const FeaturesPage: React.FC = () => {
  const { apiFetch } = useAuth();
  const [features, setFeatures] = useState<Feature[]>([]);
  const [plans, setPlans] = useState<Plan[]>([]);
  const [users, setUsers] = useState<{ id: string; email: string; name: string | null }[]>([]);
  const [overrides, setOverrides] = useState<UserOverride[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<'plans' | 'features' | 'overrides'>('plans');
  const [toast, setToast] = useState<{ message: string; type: 'success' | 'error' } | null>(null);

  // Feature modal
  const [featureModalOpen, setFeatureModalOpen] = useState(false);
  const [editFeature, setEditFeature] = useState<Feature | null>(null);

  // Plan modal
  const [planModalOpen, setPlanModalOpen] = useState(false);
  const [editPlan, setEditPlan] = useState<Plan | null>(null);

  // Override form
  const [selectedUser, setSelectedUser] = useState('');
  const [selectedFeature, setSelectedFeature] = useState('');
  const [overrideEnabled, setOverrideEnabled] = useState(true);

  // ─── Data Loading ───
  const loadFeatures = useCallback(async () => {
    try {
      const data = await apiFetch('/api/v1/admin/features');
      setFeatures(data || []);
    } catch (err: any) {
      setError(err.message || 'Failed to load features');
    }
  }, [apiFetch]);

  const loadPlans = useCallback(async () => {
    try {
      const data = await apiFetch('/api/v1/admin/plans?include_inactive=true');
      setPlans(data || []);
    } catch (err: any) {
      // Plans endpoint may not exist yet
      setPlans([]);
    }
  }, [apiFetch]);

  const loadUsers = useCallback(async () => {
    try {
      const data = await apiFetch('/api/v1/admin/users');
      setUsers((data.users || []).map((u: any) => ({ id: u.id, email: u.email, name: u.name })));
    } catch {}
  }, [apiFetch]);

  useEffect(() => {
    Promise.all([loadFeatures(), loadPlans(), loadUsers()]).finally(() => setLoading(false));
  }, [loadFeatures, loadPlans, loadUsers]);

  // ─── Feature CRUD ───
  const handleToggleFeature = useCallback(async (feature: Feature) => {
    try {
      const updated = await apiFetch(`/api/v1/admin/features/${feature.id}`, {
        method: 'PATCH',
        body: JSON.stringify({ default_enabled: !feature.default_enabled }),
      });
      setFeatures(prev => prev.map(f => f.id === updated.id ? updated : f));
      setToast({ message: `"${feature.name}" ${updated.default_enabled ? 'enabled' : 'disabled'}`, type: 'success' });
    } catch (err: any) {
      setToast({ message: err.message || 'Toggle failed', type: 'error' });
    }
  }, [apiFetch]);

  const handleSaveFeature = useCallback(async (data: any) => {
    if (editFeature) {
      const updated = await apiFetch(`/api/v1/admin/features/${editFeature.id}`, {
        method: 'PATCH',
        body: JSON.stringify(data),
      });
      setFeatures(prev => prev.map(f => f.id === updated.id ? updated : f));
      setToast({ message: 'Feature updated', type: 'success' });
    } else {
      const created = await apiFetch('/api/v1/admin/features', {
        method: 'POST',
        body: JSON.stringify(data),
      });
      setFeatures(prev => [...prev, created]);
      setToast({ message: 'Feature created', type: 'success' });
    }
  }, [apiFetch, editFeature]);

  // ─── Plan CRUD ───
  const handleSavePlan = useCallback(async (data: any) => {
    if (editPlan) {
      const updated = await apiFetch(`/api/v1/admin/plans/${editPlan.id}`, {
        method: 'PATCH',
        body: JSON.stringify(data),
      });
      setPlans(prev => prev.map(p => p.id === updated.id ? updated : p));
      setToast({ message: 'Plan updated', type: 'success' });
    } else {
      const created = await apiFetch('/api/v1/admin/plans', {
        method: 'POST',
        body: JSON.stringify(data),
      });
      setPlans(prev => [...prev, created]);
      setToast({ message: 'Plan created', type: 'success' });
    }
  }, [apiFetch, editPlan]);

  const handleDeletePlan = useCallback(async (plan: Plan) => {
    if (!confirm(`Deactivate plan "${plan.name}"?`)) return;
    try {
      await apiFetch(`/api/v1/admin/plans/${plan.id}`, { method: 'DELETE' });
      setPlans(prev => prev.map(p => p.id === plan.id ? { ...p, is_active: false } : p));
      setToast({ message: `Plan "${plan.name}" deactivated`, type: 'success' });
    } catch (err: any) {
      setToast({ message: err.message || 'Delete failed', type: 'error' });
    }
  }, [apiFetch]);

  // ─── Plan-Feature Assignment ───
  const handleTogglePlanFeature = useCallback(async (plan: Plan, feature: Feature) => {
    const isAssigned = plan.features.includes(feature.key);
    try {
      const updated = await apiFetch(
        `/api/v1/admin/plans/${plan.id}/features/${feature.id}`,
        { method: isAssigned ? 'DELETE' : 'POST' }
      );
      setPlans(prev => prev.map(p => p.id === updated.id ? updated : p));
      setToast({
        message: isAssigned
          ? `"${feature.name}" removed from ${plan.name}`
          : `"${feature.name}" added to ${plan.name}`,
        type: 'success',
      });
    } catch (err: any) {
      setToast({ message: err.message || 'Assignment failed', type: 'error' });
    }
  }, [apiFetch]);

  // ─── User Overrides ───
  const loadOverrides = useCallback(async (userId: string) => {
    try {
      const data = await apiFetch(`/api/v1/admin/features/users/${userId}`);
      setOverrides(data || []);
    } catch { setOverrides([]); }
  }, [apiFetch]);

  useEffect(() => {
    if (selectedUser) loadOverrides(selectedUser);
    else setOverrides([]);
  }, [selectedUser, loadOverrides]);

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
        <p>Failed to load: {error}</p>
        <button onClick={() => { loadFeatures(); loadPlans(); }} className="px-4 py-2 text-sm bg-slate-800 rounded-lg hover:bg-slate-700">Retry</button>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-xl font-bold text-white">Plans & Features</h2>
        <p className="text-sm text-slate-400 mt-1">Manage plans, features, and user overrides</p>
      </div>

      {/* Tabs */}
      <div className="flex gap-1 bg-slate-900 rounded-lg p-1 w-fit border border-slate-800">
        {([['plans', 'Plans', CreditCard], ['features', 'Features', Shield], ['overrides', 'Overrides', User]] as const).map(([tab, label, Icon]) => (
          <button key={tab} onClick={() => setActiveTab(tab as any)}
            className={`px-4 py-1.5 text-sm rounded-md transition-colors flex items-center gap-1.5 ${
              activeTab === tab ? 'bg-blue-600 text-white' : 'text-slate-400 hover:text-white'
            }`}>
            <Icon size={14} /> {label}
          </button>
        ))}
      </div>

      {/* ═══ PLANS TAB ═══ */}
      {activeTab === 'plans' && (
        <div className="space-y-4">
          <div className="flex justify-between items-center">
            <p className="text-sm text-slate-500">{plans.length} plan{plans.length !== 1 ? 's' : ''}</p>
            <button onClick={() => { setEditPlan(null); setPlanModalOpen(true); }}
              className="flex items-center gap-2 px-4 py-2 text-sm font-medium text-white bg-blue-600 rounded-lg hover:bg-blue-500 transition-colors">
              <Plus size={16} /> Add Plan
            </button>
          </div>

          {plans.length === 0 && !loading ? (
            <div className="text-center py-12 text-slate-500">
              <Package size={32} className="mx-auto mb-2" />
              <p>No plans yet. Create your first plan to get started.</p>
            </div>
          ) : (
            <div className="space-y-4">
              {plans.map(plan => (
                <div key={plan.id} className={`bg-slate-900 border rounded-xl p-5 ${plan.is_active ? 'border-slate-800' : 'border-slate-800/50 opacity-60'}`}>
                  <div className="flex items-start justify-between mb-3">
                    <div>
                      <div className="flex items-center gap-2">
                        <h3 className="text-lg font-semibold text-white">{plan.name}</h3>
                        <span className="font-mono text-xs text-slate-600">{plan.key}</span>
                        {!plan.is_active && (
                          <span className="px-2 py-0.5 rounded text-[10px] font-medium bg-red-500/10 text-red-400 border border-red-500/30">Inactive</span>
                        )}
                      </div>
                      {plan.description && <p className="text-sm text-slate-500 mt-1">{plan.description}</p>}
                    </div>
                    <div className="flex items-center gap-1">
                      <button onClick={() => { setEditPlan(plan); setPlanModalOpen(true); }}
                        className="p-1.5 text-slate-500 hover:text-blue-400 hover:bg-blue-500/10 rounded transition-colors" title="Edit">
                        <Edit3 size={14} />
                      </button>
                      {plan.is_active && (
                        <button onClick={() => handleDeletePlan(plan)}
                          className="p-1.5 text-slate-500 hover:text-red-400 hover:bg-red-500/10 rounded transition-colors" title="Deactivate">
                          <Trash2 size={14} />
                        </button>
                      )}
                    </div>
                  </div>

                  <div className="flex items-center gap-6 text-sm mb-4">
                    <span className="text-white font-medium">{formatPrice(plan.price_cents)}</span>
                    <span className="text-slate-500">{plan.extractions_per_month.toLocaleString()} extractions/mo</span>
                  </div>

                  {/* Feature Assignment Matrix */}
                  <div className="border-t border-slate-800 pt-3">
                    <p className="text-xs text-slate-500 mb-2">Assigned Features:</p>
                    <div className="flex flex-wrap gap-2">
                      {features.map(f => {
                        const assigned = plan.features.includes(f.key);
                        return (
                          <button key={f.id} onClick={() => handleTogglePlanFeature(plan, f)}
                            className={`px-2.5 py-1 rounded text-xs font-medium border transition-colors ${
                              assigned
                                ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/30 hover:bg-red-500/10 hover:text-red-400 hover:border-red-500/30'
                                : 'bg-slate-800 text-slate-500 border-slate-700 hover:bg-blue-500/10 hover:text-blue-400 hover:border-blue-500/30'
                            }`}>
                            {f.name} {assigned ? '✓' : ''}
                          </button>
                        );
                      })}
                      {features.length === 0 && <span className="text-xs text-slate-600">No features defined yet</span>}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* ═══ FEATURES TAB ═══ */}
      {activeTab === 'features' && (
        <div className="space-y-4">
          <div className="flex justify-between items-center">
            <p className="text-sm text-slate-500">{features.length} feature{features.length !== 1 ? 's' : ''}</p>
            <button onClick={() => { setEditFeature(null); setFeatureModalOpen(true); }}
              className="flex items-center gap-2 px-4 py-2 text-sm font-medium text-white bg-blue-600 rounded-lg hover:bg-blue-500 transition-colors">
              <Plus size={16} /> Add Feature
            </button>
          </div>

          <div className="bg-slate-900 border border-slate-800 rounded-xl overflow-hidden">
            {loading ? (
              <div className="flex items-center justify-center h-48 text-slate-500">
                <RefreshCw size={24} className="animate-spin mr-2" /> Loading...
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
                      <th className="text-right py-3 px-4 text-slate-400 font-medium">Actions</th>
                    </tr>
                  </thead>
                  <tbody>
                    {features.map(f => (
                      <tr key={f.id} className="border-b border-slate-800/50 hover:bg-slate-800/30 transition-colors">
                        <td className="py-3 px-4">
                          <span className="text-white font-medium">{f.name}</span>
                          <span className="block text-xs text-slate-600 font-mono mt-0.5">{f.key}</span>
                        </td>
                        <td className="py-3 px-4 text-slate-400 max-w-xs truncate">{f.description || '—'}</td>
                        <td className="py-3 px-4 text-center">
                          <button onClick={() => handleToggleFeature(f)} className="inline-flex items-center gap-1.5 px-2 py-1 rounded-lg transition-colors">
                            {f.default_enabled ? (
                              <><ToggleRight size={20} className="text-emerald-400" /><span className="text-xs text-emerald-400">On</span></>
                            ) : (
                              <><ToggleLeft size={20} className="text-slate-600" /><span className="text-xs text-slate-500">Off</span></>
                            )}
                          </button>
                        </td>
                        <td className="py-3 px-4">{tierBadge(f.requires_plan)}</td>
                        <td className="py-3 px-4">
                          <div className="flex items-center justify-end gap-1">
                            <button onClick={() => { setEditFeature(f); setFeatureModalOpen(true); }}
                              className="p-1.5 text-slate-500 hover:text-blue-400 hover:bg-blue-500/10 rounded transition-colors" title="Edit">
                              <Edit3 size={14} />
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

          <div className="flex flex-wrap gap-4 text-xs text-slate-500 bg-slate-900 border border-slate-800 rounded-lg p-4">
            <p><span className="text-emerald-400 font-medium">● On</span> — enabled by default</p>
            <p><span className="text-slate-600 font-medium">● Off</span> — disabled by default</p>
            <p><span className="text-blue-400 font-medium">● Override</span> — user-specific</p>
          </div>
        </div>
      )}

      {/* ═══ OVERRIDES TAB ═══ */}
      {activeTab === 'overrides' && (
        <div className="space-y-6">
          <div className="bg-slate-900 border border-slate-800 rounded-xl p-5">
            <h3 className="text-sm font-semibold text-white mb-4 flex items-center gap-2">
              <Settings size={15} /> Add User Override
            </h3>
            <div className="grid grid-cols-1 sm:grid-cols-4 gap-3 items-end">
              <div>
                <label className="block text-xs text-slate-500 mb-1">User</label>
                <select value={selectedUser} onChange={e => setSelectedUser(e.target.value)}
                  className="w-full px-3 py-2 bg-slate-800 border border-slate-700 rounded-lg text-sm text-white focus:outline-none focus:border-blue-500">
                  <option value="">Select user...</option>
                  {users.map(u => <option key={u.id} value={u.id}>{u.email}</option>)}
                </select>
              </div>
              <div>
                <label className="block text-xs text-slate-500 mb-1">Feature</label>
                <select value={selectedFeature} onChange={e => setSelectedFeature(e.target.value)}
                  className="w-full px-3 py-2 bg-slate-800 border border-slate-700 rounded-lg text-sm text-white focus:outline-none focus:border-blue-500">
                  <option value="">Select feature...</option>
                  {features.map(f => <option key={f.id} value={f.key}>{f.name}</option>)}
                </select>
              </div>
              <div>
                <label className="block text-xs text-slate-500 mb-1">Toggle</label>
                <button onClick={() => setOverrideEnabled(!overrideEnabled)}
                  className={`flex items-center gap-1.5 px-3 py-2 rounded-lg border transition-colors text-sm w-full justify-center ${
                    overrideEnabled ? 'bg-emerald-500/10 border-emerald-500/30 text-emerald-400' : 'bg-slate-800 border-slate-700 text-slate-500'
                  }`}>
                  {overrideEnabled ? <ToggleRight size={16} /> : <ToggleLeft size={16} />}
                  {overrideEnabled ? 'Enable' : 'Disable'}
                </button>
              </div>
              <button onClick={handleAddOverride} disabled={!selectedUser || !selectedFeature}
                className="px-4 py-2 text-sm font-medium text-white bg-blue-600 rounded-lg hover:bg-blue-500 disabled:opacity-50 disabled:cursor-not-allowed transition-colors">
                Apply Override
              </button>
            </div>
          </div>

          <div className="bg-slate-900 border border-slate-800 rounded-xl overflow-hidden">
            {loading ? (
              <div className="flex items-center justify-center h-32 text-slate-500">
                <RefreshCw size={20} className="animate-spin mr-2" /> Loading...
              </div>
            ) : !selectedUser ? (
              <div className="flex flex-col items-center justify-center h-32 text-slate-500 gap-2">
                <User size={20} /><p className="text-sm">Select a user to view overrides</p>
              </div>
            ) : overrides.length === 0 ? (
              <div className="flex flex-col items-center justify-center h-32 text-slate-500 gap-2">
                <Shield size={20} /><p className="text-sm">No overrides for this user</p>
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
                    {overrides.map(o => (
                      <tr key={`${o.user_id}-${o.feature_key}`} className="border-b border-slate-800/50 hover:bg-slate-800/30 transition-colors">
                        <td className="py-3 px-4 text-white">
                          {features.find(f => f.key === o.feature_key)?.name || o.feature_key}
                        </td>
                        <td className="py-3 px-4 text-center">
                          <span className={`px-2 py-0.5 rounded text-xs font-medium border ${
                            o.enabled ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/30' : 'bg-red-500/10 text-red-400 border-red-500/30'
                          }`}>
                            {o.enabled ? 'Enabled' : 'Disabled'}
                          </span>
                        </td>
                        <td className="py-3 px-4">
                          <div className="flex justify-end">
                            <button onClick={() => handleRemoveOverride(o.feature_key)}
                              className="flex items-center gap-1 px-2 py-1.5 text-xs text-red-400 bg-red-500/10 rounded-lg hover:bg-red-500/20 transition-colors">
                              <X size={12} /> Remove
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

      {/* Modals */}
      <FeatureModal
        open={featureModalOpen}
        feature={editFeature}
        onClose={() => { setFeatureModalOpen(false); setEditFeature(null); }}
        onSave={handleSaveFeature}
      />
      <PlanModal
        open={planModalOpen}
        plan={editPlan}
        onClose={() => { setPlanModalOpen(false); setEditPlan(null); }}
        onSave={handleSavePlan}
      />

      {toast && <Toast message={toast.message} type={toast.type} onClose={() => setToast(null)} />}
    </div>
  );
};
