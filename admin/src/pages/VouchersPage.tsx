import React, { useEffect, useState, useMemo, useCallback, useRef } from 'react';
import { useAuth } from '../contexts/AuthContext';
import {
  Ticket, Plus, RefreshCw, AlertTriangle, Download, Trash2,
  Copy, Check, X, Calendar, User, Search,
} from 'lucide-react';

// ─── Types ───

interface Voucher {
  id: string;
  code: string;
  plan: 'hobby' | 'pro' | 'enterprise';
  status: 'active' | 'expired' | 'exhausted' | 'revoked';
  redeemed_by: string | null;
  redeemed_at: string | null;
  created_at: string;
  expires_at: string;
}

const PLANS = ['hobby', 'pro', 'enterprise'] as const;

// ─── Badge helpers ───

const planBadge = (plan: Voucher['plan']) => {
  const map: Record<string, string> = {
    hobby: 'bg-blue-500/10 text-blue-400 border-blue-500/30',
    pro: 'bg-purple-500/10 text-purple-400 border-purple-500/30',
    enterprise: 'bg-amber-500/10 text-amber-400 border-amber-500/30',
  };
  return `px-2 py-0.5 rounded text-xs font-medium border ${map[plan] || map.hobby}`;
};

const statusBadge = (status: Voucher['status']) => {
  const map: Record<string, string> = {
    active: 'bg-emerald-500/10 text-emerald-400 border-emerald-500/30',
    expired: 'bg-slate-500/10 text-slate-400 border-slate-500/30',
    exhausted: 'bg-yellow-500/10 text-yellow-400 border-yellow-500/30',
    revoked: 'bg-red-500/10 text-red-400 border-red-500/30',
  };
  return `px-2 py-0.5 rounded text-xs font-medium border ${map[status] || map.active}`;
};

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
      {type === 'success' ? <Check size={16} /> : <AlertTriangle size={16} />}
      <span className="text-sm">{message}</span>
      <button onClick={onClose} className="ml-2 text-current opacity-60 hover:opacity-100">
        <X size={14} />
      </button>
    </div>
  );
};

// ─── Page ───

export const VouchersPage: React.FC = () => {
  const { apiFetch } = useAuth();
  const [vouchers, setVouchers] = useState<Voucher[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<'list' | 'generate'>('list');

  // Toast state
  const [toast, setToast] = useState<{ message: string; type: 'success' | 'error' } | null>(null);

  // Generate form state
  const [genPlan, setGenPlan] = useState<string>('pro');
  const [genQuantity, setGenQuantity] = useState(5);
  const [genDuration, setGenDuration] = useState(30); // days
  const [genExpiry, setGenExpiry] = useState('');
  const [genMaxUses, setGenMaxUses] = useState(1);
  const [generating, setGenerating] = useState(false);
  const [generatedCodes, setGeneratedCodes] = useState<string[]>([]);
  const [copiedIdx, setCopiedIdx] = useState<number | null>(null);

  // List filters
  const [search, setSearch] = useState('');
  const [statusFilter, setStatusFilter] = useState<string>('all');
  const [total, setTotal] = useState(0);
  const [offset, setOffset] = useState(0);
  const pageSize = 50;

  // ─── Load vouchers ───
  const loadVouchers = useCallback(async (newOffset?: number) => {
    setLoading(true);
    setError(null);
    const off = newOffset ?? offset;
    try {
      const params = new URLSearchParams();
      params.set('offset', String(off));
      params.set('limit', String(pageSize));
      if (statusFilter !== 'all') params.set('status', statusFilter);
      if (search) params.set('search', search);

      const data = await apiFetch(`/v1/admin/vouchers?${params.toString()}`);
      // Map backend response to frontend shape
      const mapped: Voucher[] = data.vouchers.map((v: any) => ({
        id: v.id,
        code: v.code,
        plan: v.plan,
        status: v.status,
        redeemed_by: null,  // not returned in list endpoint; could be resolved via redemption lookup
        redeemed_at: null,
        created_at: v.created_at,
        expires_at: v.expires_at,
      }));
      setVouchers(mapped);
      setTotal(data.total);
      setOffset(off);
    } catch (err: any) {
      setError(err.message || 'Failed to load vouchers');
    } finally {
      setLoading(false);
    }
  }, [apiFetch, offset, statusFilter, search]);

  // Initial load and reload on filters
  useEffect(() => {
    loadVouchers(0);
  }, [statusFilter, search]); // eslint-disable-line react-hooks/exhaustive-deps

  // ─── Generate ───
  const handleGenerate = useCallback(async () => {
    setGenerating(true);
    setGeneratedCodes([]);
    setError(null);
    try {
      const payload: any = {
        plan: genPlan,
        quantity: genQuantity,
        duration_days: genDuration,
        max_uses: genMaxUses,
      };
      if (genExpiry) payload.expiry_date = genExpiry;

      const res = await apiFetch('/v1/admin/vouchers/generate', {
        method: 'POST',
        body: JSON.stringify(payload),
      });
      setGeneratedCodes(res.codes || []);
      setToast({ message: `${res.quantity} voucher(s) generated successfully`, type: 'success' });
      // Refresh list
      loadVouchers(0);
    } catch (err: any) {
      setToast({ message: err.message || 'Generation failed', type: 'error' });
    } finally {
      setGenerating(false);
    }
  }, [genPlan, genQuantity, genDuration, genMaxUses, genExpiry, apiFetch, loadVouchers]);

  const handleCopy = useCallback((code: string, idx: number) => {
    navigator.clipboard.writeText(code);
    setCopiedIdx(idx);
    setTimeout(() => setCopiedIdx(null), 2000);
  }, []);

  // ─── Invalidate ───
  const handleInvalidate = useCallback(async (voucherId: string) => {
    try {
      await apiFetch(`/v1/admin/vouchers/${voucherId}`, { method: 'DELETE' });
      setToast({ message: 'Voucher invalidated', type: 'success' });
      // Update local state
      setVouchers((prev) =>
        prev.map((v) => (v.id === voucherId ? { ...v, status: 'revoked' as const } : v))
      );
    } catch (err: any) {
      setToast({ message: err.message || 'Failed to invalidate', type: 'error' });
    }
  }, [apiFetch]);

  // ─── Export CSV ───
  const handleExportCSV = useCallback(async () => {
    try {
      const token = localStorage.getItem('access_token');
      const res = await fetch('/api/v1/admin/vouchers/export', {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!res.ok) throw new Error('Export failed');
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `vouchers-export-${new Date().toISOString().split('T')[0]}.csv`;
      a.click();
      URL.revokeObjectURL(url);
      setToast({ message: 'CSV exported', type: 'success' });
    } catch (err: any) {
      setToast({ message: err.message || 'Export failed', type: 'error' });
    }
  }, []);

  // ─── Refresh ───
  const handleRefresh = useCallback(() => {
    loadVouchers(offset);
  }, [loadVouchers, offset]);

  // ─── Filtered list (client-side for search refinement) ───
  const filtered = useMemo(() => {
    return vouchers.filter((v) => {
      const matchSearch = !search ||
        v.code.toLowerCase().includes(search.toLowerCase());
      return matchSearch;
    });
  }, [vouchers, search]);

  const formatDate = (iso: string) =>
    new Date(iso).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });

  if (error && vouchers.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center h-64 text-red-400 gap-2">
        <AlertTriangle size={32} />
        <p>Failed to load vouchers: {error}</p>
        <button onClick={() => loadVouchers(0)} className="mt-2 px-4 py-2 text-sm bg-slate-800 text-slate-300 rounded-lg hover:bg-slate-700">
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
          <h2 className="text-xl font-bold text-white">Vouchers</h2>
          <p className="text-sm text-slate-400 mt-1">Generate and manage promotional vouchers</p>
        </div>
        <div className="flex gap-2">
          <button
            onClick={handleExportCSV}
            className="flex items-center gap-2 px-3 py-2 text-sm text-slate-300 bg-slate-800 rounded-lg hover:bg-slate-700 transition-colors"
          >
            <Download size={14} />
            Export CSV
          </button>
        </div>
      </div>

      {/* Tabs */}
      <div className="flex gap-1 bg-slate-900 rounded-lg p-1 w-fit border border-slate-800">
        <button
          onClick={() => setActiveTab('list')}
          className={`px-4 py-1.5 text-sm rounded-md transition-colors ${
            activeTab === 'list' ? 'bg-blue-600 text-white' : 'text-slate-400 hover:text-white'
          }`}
        >
          Voucher List
        </button>
        <button
          onClick={() => setActiveTab('generate')}
          className={`px-4 py-1.5 text-sm rounded-md transition-colors ${
            activeTab === 'generate' ? 'bg-blue-600 text-white' : 'text-slate-400 hover:text-white'
          }`}
        >
          <Plus size={14} className="inline mr-1" />
          Generate
        </button>
      </div>

      {/* ─── Generate Panel ─── */}
      {activeTab === 'generate' && (
        <div className="bg-slate-900 border border-slate-800 rounded-xl p-6 space-y-5">
          <h3 className="text-sm font-semibold text-white">Generate Vouchers</h3>
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
            <div>
              <label className="block text-xs text-slate-500 mb-1">Plan</label>
              <select
                value={genPlan}
                onChange={(e) => setGenPlan(e.target.value)}
                className="w-full px-3 py-2 bg-slate-800 border border-slate-700 rounded-lg text-sm text-white focus:outline-none focus:border-blue-500"
              >
                {PLANS.map((p) => (
                  <option key={p} value={p}>{p.charAt(0).toUpperCase() + p.slice(1)}</option>
                ))}
              </select>
            </div>
            <div>
              <label className="block text-xs text-slate-500 mb-1">Quantity</label>
              <input
                type="number"
                min={1}
                max={500}
                value={genQuantity}
                onChange={(e) => setGenQuantity(Math.min(500, Math.max(1, parseInt(e.target.value) || 1)))}
                className="w-full px-3 py-2 bg-slate-800 border border-slate-700 rounded-lg text-sm text-white focus:outline-none focus:border-blue-500"
              />
            </div>
            <div>
              <label className="block text-xs text-slate-500 mb-1">Duration (days)</label>
              <input
                type="number"
                min={1}
                max={3650}
                value={genDuration}
                onChange={(e) => setGenDuration(Math.min(3650, Math.max(1, parseInt(e.target.value) || 30)))}
                className="w-full px-3 py-2 bg-slate-800 border border-slate-700 rounded-lg text-sm text-white focus:outline-none focus:border-blue-500"
              />
            </div>
            <div>
              <label className="block text-xs text-slate-500 mb-1">Max Uses</label>
              <input
                type="number"
                min={1}
                max={10000}
                value={genMaxUses}
                onChange={(e) => setGenMaxUses(Math.min(10000, Math.max(1, parseInt(e.target.value) || 1)))}
                className="w-full px-3 py-2 bg-slate-800 border border-slate-700 rounded-lg text-sm text-white focus:outline-none focus:border-blue-500"
              />
            </div>
            <div>
              <label className="block text-xs text-slate-500 mb-1">Expiry Date (optional)</label>
              <input
                type="date"
                value={genExpiry}
                onChange={(e) => setGenExpiry(e.target.value)}
                className="w-full px-3 py-2 bg-slate-800 border border-slate-700 rounded-lg text-sm text-white focus:outline-none focus:border-blue-500 [color-scheme:dark]"
              />
            </div>
          </div>
          <button
            onClick={handleGenerate}
            disabled={generating}
            className="flex items-center gap-2 px-4 py-2 text-sm font-medium text-white bg-blue-600 rounded-lg hover:bg-blue-500 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          >
            {generating ? (
              <>
                <RefreshCw size={14} className="animate-spin" />
                Generating...
              </>
            ) : (
              <>
                <Ticket size={14} />
                Generate {genQuantity} Voucher{genQuantity > 1 ? 's' : ''}
              </>
            )}
          </button>

          {/* Generated codes */}
          {generatedCodes.length > 0 && (
            <div className="mt-4 p-4 bg-slate-800 rounded-lg border border-slate-700 space-y-2">
              <p className="text-sm font-medium text-emerald-400">
                ✓ {generatedCodes.length} voucher{generatedCodes.length > 1 ? 's' : ''} generated
              </p>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                {generatedCodes.map((code, idx) => (
                  <div
                    key={idx}
                    className="flex items-center justify-between bg-slate-950 rounded-lg px-3 py-2 border border-slate-700"
                  >
                    <code className="text-xs text-white font-mono">{code}</code>
                    <button
                      onClick={() => handleCopy(code, idx)}
                      className="p-1 rounded text-slate-400 hover:text-white hover:bg-slate-700 transition-colors"
                    >
                      {copiedIdx === idx ? <Check size={14} className="text-emerald-400" /> : <Copy size={14} />}
                    </button>
                  </div>
                ))}
              </div>
              <button
                onClick={() => {
                  navigator.clipboard.writeText(generatedCodes.join('\n'));
                }}
                className="text-xs text-blue-400 hover:text-blue-300 transition-colors"
              >
                Copy all to clipboard
              </button>
            </div>
          )}
        </div>
      )}

      {/* ─── Voucher List Panel ─── */}
      {activeTab === 'list' && (
        <>
          {/* Filters */}
          <div className="flex flex-wrap gap-3 items-center">
            <div className="relative flex-1 min-w-[200px] max-w-sm">
              <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-500" />
              <input
                type="text"
                placeholder="Search by code..."
                value={search}
                onChange={(e) => { setSearch(e.target.value); setOffset(0); }}
                className="w-full pl-10 pr-4 py-2 bg-slate-900 border border-slate-700 rounded-lg text-sm text-white placeholder-slate-500 focus:outline-none focus:border-blue-500 transition-colors"
              />
            </div>
            <select
              value={statusFilter}
              onChange={(e) => { setStatusFilter(e.target.value); setOffset(0); }}
              className="px-3 py-2 bg-slate-900 border border-slate-700 rounded-lg text-sm text-slate-300 focus:outline-none focus:border-blue-500"
            >
              <option value="all">All Status</option>
              <option value="active">Active</option>
              <option value="expired">Expired</option>
              <option value="exhausted">Exhausted</option>
              <option value="revoked">Revoked</option>
            </select>
            <button
              onClick={handleRefresh}
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
                Loading vouchers...
              </div>
            ) : filtered.length === 0 ? (
              <div className="flex flex-col items-center justify-center h-48 text-slate-500 gap-2">
                <Ticket size={24} />
                <p>No vouchers found</p>
              </div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-slate-800">
                      <th className="text-left py-3 px-4 text-slate-400 font-medium">Code</th>
                      <th className="text-left py-3 px-4 text-slate-400 font-medium">Plan</th>
                      <th className="text-left py-3 px-4 text-slate-400 font-medium">Status</th>
                      <th className="text-left py-3 px-4 text-slate-400 font-medium">Uses</th>
                      <th className="text-left py-3 px-4 text-slate-400 font-medium">
                        <span className="flex items-center gap-1"><Calendar size={13} /> Created</span>
                      </th>
                      <th className="text-left py-3 px-4 text-slate-400 font-medium">Expires</th>
                      <th className="text-right py-3 px-4 text-slate-400 font-medium">Actions</th>
                    </tr>
                  </thead>
                  <tbody>
                    {filtered.map((v) => (
                      <tr key={v.id} className="border-b border-slate-800/50 hover:bg-slate-800/30 transition-colors">
                        <td className="py-3 px-4">
                          <div className="flex items-center gap-2">
                            <code className="text-xs text-white font-mono">{v.code}</code>
                            <button
                              onClick={() => handleCopy(v.code, -1)}
                              className="p-0.5 rounded text-slate-600 hover:text-slate-300 transition-colors"
                            >
                              {copiedIdx === -1 ? <Check size={12} className="text-emerald-400" /> : <Copy size={12} />}
                            </button>
                          </div>
                        </td>
                        <td className="py-3 px-4"><span className={planBadge(v.plan)}>{v.plan}</span></td>
                        <td className="py-3 px-4"><span className={statusBadge(v.status)}>{v.status}</span></td>
                        <td className="py-3 px-4 text-slate-400 text-xs">{v.used_count ?? '—'}</td>
                        <td className="py-3 px-4 text-slate-400 text-xs">{formatDate(v.created_at)}</td>
                        <td className="py-3 px-4 text-slate-400 text-xs">{formatDate(v.expires_at)}</td>
                        <td className="py-3 px-4">
                          <div className="flex items-center justify-end">
                            {(v.status === 'active') && (
                              <button
                                onClick={() => handleInvalidate(v.id)}
                                className="flex items-center gap-1 px-2 py-1.5 text-xs text-red-400 bg-red-500/10 rounded-lg hover:bg-red-500/20 transition-colors"
                              >
                                <X size={12} />
                                Invalidate
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

          {/* Pagination info */}
          {!loading && (
            <div className="flex items-center justify-between">
              <p className="text-xs text-slate-600">
                Showing {vouchers.length > 0 ? offset + 1 : 0}–{offset + vouchers.length} of {total} vouchers
              </p>
              <div className="flex gap-2">
                <button
                  disabled={offset === 0}
                  onClick={() => loadVouchers(Math.max(0, offset - pageSize))}
                  className="px-3 py-1 text-xs text-slate-400 bg-slate-800 rounded hover:bg-slate-700 disabled:opacity-40 disabled:cursor-not-allowed"
                >
                  Previous
                </button>
                <button
                  disabled={offset + pageSize >= total}
                  onClick={() => loadVouchers(offset + pageSize)}
                  className="px-3 py-1 text-xs text-slate-400 bg-slate-800 rounded hover:bg-slate-700 disabled:opacity-40 disabled:cursor-not-allowed"
                >
                  Next
                </button>
              </div>
            </div>
          )}
        </>
      )}

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
