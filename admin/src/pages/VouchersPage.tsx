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
  plan: 'starter' | 'pro' | 'enterprise';
  status: 'unused' | 'redeemed' | 'expired' | 'invalidated';
  redeemed_by: string | null;
  redeemed_at: string | null;
  created_at: string;
  expires_at: string;
}

const PLANS = ['starter', 'pro', 'enterprise'] as const;

// ─── Mock Data (replace with GET /api/v1/admin/vouchers) ───

const MOCK_VOUCHERS: Voucher[] = [
  { id: 'v1', code: 'KAF-STARTER-ABCD', plan: 'starter', status: 'unused', redeemed_by: null, redeemed_at: null, created_at: '2025-05-01T10:00:00Z', expires_at: '2025-12-31T23:59:59Z' },
  { id: 'v2', code: 'KAF-PRO-XYZ1', plan: 'pro', status: 'redeemed', redeemed_by: 'alice@example.com', redeemed_at: '2025-05-05T14:30:00Z', created_at: '2025-05-01T10:00:00Z', expires_at: '2025-12-31T23:59:59Z' },
  { id: 'v3', code: 'KAF-ENT-BBQ9', plan: 'enterprise', status: 'unused', redeemed_by: null, redeemed_at: null, created_at: '2025-05-10T09:00:00Z', expires_at: '2026-05-10T09:00:00Z' },
  { id: 'v4', code: 'KAF-STARTER-EFGH', plan: 'starter', status: 'expired', redeemed_by: null, redeemed_at: null, created_at: '2024-05-01T10:00:00Z', expires_at: '2024-12-31T23:59:59Z' },
  { id: 'v5', code: 'KAF-PRO-LMN2', plan: 'pro', status: 'invalidated', redeemed_by: null, redeemed_at: null, created_at: '2025-04-15T08:00:00Z', expires_at: '2025-10-15T08:00:00Z' },
  { id: 'v6', code: 'KAF-ENT-QRS3', plan: 'enterprise', status: 'redeemed', redeemed_by: 'bob@acme.com', redeemed_at: '2025-05-12T11:00:00Z', created_at: '2025-05-08T12:00:00Z', expires_at: '2026-05-08T12:00:00Z' },
  { id: 'v7', code: 'KAF-STARTER-TUVW', plan: 'starter', status: 'unused', redeemed_by: null, redeemed_at: null, created_at: '2025-05-20T16:00:00Z', expires_at: '2025-11-20T16:00:00Z' },
  { id: 'v8', code: 'KAF-PRO-HIJ5', plan: 'pro', status: 'unused', redeemed_by: null, redeemed_at: null, created_at: '2025-05-22T07:30:00Z', expires_at: '2026-05-22T07:30:00Z' },
];

// ─── Badge helpers ───

const planBadge = (plan: Voucher['plan']) => {
  const map: Record<string, string> = {
    starter: 'bg-blue-500/10 text-blue-400 border-blue-500/30',
    pro: 'bg-purple-500/10 text-purple-400 border-purple-500/30',
    enterprise: 'bg-amber-500/10 text-amber-400 border-amber-500/30',
  };
  return `px-2 py-0.5 rounded text-xs font-medium border ${map[plan]}`;
};

const statusBadge = (status: Voucher['status']) => {
  const map: Record<string, string> = {
    unused: 'bg-emerald-500/10 text-emerald-400 border-emerald-500/30',
    redeemed: 'bg-blue-500/10 text-blue-400 border-blue-500/30',
    expired: 'bg-slate-500/10 text-slate-400 border-slate-500/30',
    invalidated: 'bg-red-500/10 text-red-400 border-red-500/30',
  };
  return `px-2 py-0.5 rounded text-xs font-medium border ${map[status]}`;
};

// ─── Generate codes helper ───

function generateCodes(plan: string, quantity: number): string[] {
  const prefix = `KAF-${plan.substring(0, 4).toUpperCase()}`;
  return Array.from({ length: quantity }, () =>
    `${prefix}-${Math.random().toString(36).substring(2, 6).toUpperCase()}${Math.random().toString(36).substring(2, 6).toUpperCase()}`
  );
}

// ─── Page ───

export const VouchersPage: React.FC = () => {
  const { apiFetch } = useAuth();
  const [vouchers, setVouchers] = useState<Voucher[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<'list' | 'generate'>('list');

  // Generate form state
  const [genPlan, setGenPlan] = useState<string>('pro');
  const [genQuantity, setGenQuantity] = useState(5);
  const [genExpiry, setGenExpiry] = useState('');
  const [generating, setGenerating] = useState(false);
  const [generatedCodes, setGeneratedCodes] = useState<string[]>([]);
  const [copiedIdx, setCopiedIdx] = useState<number | null>(null);

  // List filters
  const [search, setSearch] = useState('');
  const [statusFilter, setStatusFilter] = useState<string>('all');

  // Load
  useEffect(() => {
    // TODO: Replace with real API: apiFetch('/v1/admin/vouchers')
    const timer = setTimeout(() => {
      setVouchers(MOCK_VOUCHERS);
      setLoading(false);
    }, 700);
    return () => clearTimeout(timer);
  }, []);

  // ─── Generate ───
  const handleGenerate = useCallback(async () => {
    setGenerating(true);
    setGeneratedCodes([]);
    // TODO: Real API call:
    // const res = await apiFetch('/v1/admin/vouchers/generate', {
    //   method: 'POST',
    //   body: JSON.stringify({ plan: genPlan, quantity: genQuantity, expires_at: genExpiry || undefined }),
    // });
    // setGeneratedCodes(res.codes);
    await new Promise((r) => setTimeout(r, 600));
    const codes = generateCodes(genPlan, genQuantity);
    setGeneratedCodes(codes);
    // Add to local list
    const expiry = genExpiry || new Date(Date.now() + 365 * 86400000).toISOString().split('T')[0] + 'T23:59:59Z';
    const newVouchers: Voucher[] = codes.map((code, i) => ({
      id: `gen-${Date.now()}-${i}`,
      code,
      plan: genPlan as Voucher['plan'],
      status: 'unused',
      redeemed_by: null,
      redeemed_at: null,
      created_at: new Date().toISOString(),
      expires_at: expiry,
    }));
    setVouchers((prev) => [...newVouchers, ...prev]);
    setGenerating(false);
  }, [genPlan, genQuantity, genExpiry]);

  const handleCopy = useCallback((code: string, idx: number) => {
    navigator.clipboard.writeText(code);
    setCopiedIdx(idx);
    setTimeout(() => setCopiedIdx(null), 2000);
  }, []);

  // ─── Invalidate ───
  const handleInvalidate = useCallback((voucherId: string) => {
    setVouchers((prev) =>
      prev.map((v) => (v.id === voucherId ? { ...v, status: 'invalidated' as const } : v))
    );
    // TODO: apiFetch(`/v1/admin/vouchers/${voucherId}`, { method: 'DELETE' });
  }, []);

  // ─── Export CSV ───
  const handleExportCSV = useCallback(() => {
    const unused = vouchers.filter((v) => v.status === 'unused');
    const header = 'Code,Plan,Status,Created,Expires\n';
    const rows = unused
      .map((v) => `${v.code},${v.plan},${v.status},${v.created_at},${v.expires_at}`)
      .join('\n');
    const blob = new Blob([header + rows], { type: 'text/csv' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `vouchers-export-${new Date().toISOString().split('T')[0]}.csv`;
    a.click();
    URL.revokeObjectURL(url);
  }, [vouchers]);

  // ─── Filtered list ───
  const filtered = useMemo(() => {
    return vouchers.filter((v) => {
      const matchSearch = !search ||
        v.code.toLowerCase().includes(search.toLowerCase()) ||
        (v.redeemed_by || '').toLowerCase().includes(search.toLowerCase());
      const matchStatus = statusFilter === 'all' || v.status === statusFilter;
      return matchSearch && matchStatus;
    });
  }, [vouchers, search, statusFilter]);

  const formatDate = (iso: string) =>
    new Date(iso).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });

  if (error) {
    return (
      <div className="flex flex-col items-center justify-center h-64 text-red-400 gap-2">
        <AlertTriangle size={32} />
        <p>Failed to load vouchers: {error}</p>
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
                max={100}
                value={genQuantity}
                onChange={(e) => setGenQuantity(Math.min(100, Math.max(1, parseInt(e.target.value) || 1)))}
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
                placeholder="Search by code or email..."
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                className="w-full pl-10 pr-4 py-2 bg-slate-900 border border-slate-700 rounded-lg text-sm text-white placeholder-slate-500 focus:outline-none focus:border-blue-500 transition-colors"
              />
            </div>
            <select
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value)}
              className="px-3 py-2 bg-slate-900 border border-slate-700 rounded-lg text-sm text-slate-300 focus:outline-none focus:border-blue-500"
            >
              <option value="all">All Status</option>
              <option value="unused">Unused</option>
              <option value="redeemed">Redeemed</option>
              <option value="expired">Expired</option>
              <option value="invalidated">Invalidated</option>
            </select>
            <button
              onClick={() => { setLoading(true); setTimeout(() => { setVouchers(MOCK_VOUCHERS); setLoading(false); }, 500); }}
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
                      <th className="text-left py-3 px-4 text-slate-400 font-medium">
                        <span className="flex items-center gap-1"><User size={13} /> Redeemed By</span>
                      </th>
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
                        <td className="py-3 px-4 text-slate-400 text-xs">
                          {v.redeemed_by || '—'}
                          {v.redeemed_at && <span className="block text-slate-600">{formatDate(v.redeemed_at)}</span>}
                        </td>
                        <td className="py-3 px-4 text-slate-400 text-xs">{formatDate(v.created_at)}</td>
                        <td className="py-3 px-4 text-slate-400 text-xs">{formatDate(v.expires_at)}</td>
                        <td className="py-3 px-4">
                          <div className="flex items-center justify-end">
                            {v.status === 'unused' && (
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

          {!loading && filtered.length > 0 && (
            <p className="text-xs text-slate-600">
              Showing {filtered.length} of {vouchers.length} vouchers
            </p>
          )}
        </>
      )}
    </div>
  );
};
