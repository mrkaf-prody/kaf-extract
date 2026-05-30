import React, { useEffect, useState, useCallback, useMemo } from 'react';
import { useAuth } from '../contexts/AuthContext';
import {
  FileText, Search, Filter, ChevronLeft, ChevronRight,
  RefreshCw, AlertTriangle, Download, Calendar, User, Globe,
  Hash, Info, ChevronDown, X,
} from 'lucide-react';

// ─── Types ───

interface AuditLogEntry {
  id: string;
  timestamp: string;
  admin_email: string;
  action: string;
  target_type: string;
  target_id: string;
  details: string;
  ip_address: string;
}

interface PaginatedResponse {
  items: AuditLogEntry[];
  total: number;
  page: number;
  limit: number;
  total_pages: number;
}

// ─── Helpers ───

function formatTimestamp(iso: string): string {
  return new Date(iso).toLocaleString('en-US', {
    month: 'short', day: 'numeric', year: 'numeric',
    hour: '2-digit', minute: '2-digit', second: '2-digit',
  });
}

const actionColor = (action: string) => {
  if (action.startsWith('user.')) return 'bg-blue-500/10 text-blue-400 border-blue-500/30';
  if (action.startsWith('subscription.')) return 'bg-emerald-500/10 text-emerald-400 border-emerald-500/30';
  if (action.startsWith('voucher.')) return 'bg-amber-500/10 text-amber-400 border-amber-500/30';
  if (action.startsWith('payment.')) return 'bg-purple-500/10 text-purple-400 border-purple-500/30';
  if (action.startsWith('api_key.')) return 'bg-red-500/10 text-red-400 border-red-500/30';
  if (action.startsWith('admin.')) return 'bg-cyan-500/10 text-cyan-400 border-cyan-500/30';
  return 'bg-slate-500/10 text-slate-400 border-slate-500/30';
};

const targetTypeColor = (type: string) => {
  const map: Record<string, string> = {
    user: 'bg-blue-500/10 text-blue-400 border-blue-500/30',
    subscription: 'bg-emerald-500/10 text-emerald-400 border-emerald-500/30',
    voucher: 'bg-amber-500/10 text-amber-400 border-amber-500/30',
    feature: 'bg-indigo-500/10 text-indigo-400 border-indigo-500/30',
    payment: 'bg-purple-500/10 text-purple-400 border-purple-500/30',
    api_key: 'bg-red-500/10 text-red-400 border-red-500/30',
    settings: 'bg-slate-500/10 text-slate-400 border-slate-500/30',
    admin: 'bg-cyan-500/10 text-cyan-400 border-cyan-500/30',
  };
  return map[type] || 'bg-slate-500/10 text-slate-400 border-slate-500/30';
};

// ─── CSV Export ───

function exportToCSV(items: AuditLogEntry[]): void {
  const headers = ['Timestamp', 'Admin Email', 'Action', 'Target Type', 'Target ID', 'Details', 'IP Address'];
  const rows = items.map((entry) => [
    entry.timestamp,
    entry.admin_email,
    entry.action,
    entry.target_type,
    entry.target_id,
    `"${entry.details.replace(/"/g, '""')}"`,
    entry.ip_address,
  ]);

  const csv = [headers.join(','), ...rows.map((r) => r.join(','))].join('\n');
  const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = `audit-logs-${new Date().toISOString().slice(0, 10)}.csv`;
  link.click();
  URL.revokeObjectURL(url);
}

// ─── Skeleton ───

const SkeletonRow = () => (
  <tr className="border-b border-slate-800/50 animate-pulse">
    {Array.from({ length: 7 }).map((_, i) => (
      <td key={i} className="py-3 px-4">
        <div className="h-4 bg-slate-800 rounded w-3/4" />
      </td>
    ))}
  </tr>
);

// ─── Page ───

export const AuditLogsPage: React.FC = () => {
  const { apiFetch } = useAuth();
  const [data, setData] = useState<PaginatedResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Filters
  const [actionFilter, setActionFilter] = useState('');
  const [adminSearch, setAdminSearch] = useState('');
  const [dateFrom, setDateFrom] = useState('');
  const [dateTo, setDateTo] = useState('');

  // Pagination
  const [page, setPage] = useState(1);
  const limit = 50;

  // Export state
  const [exporting, setExporting] = useState(false);

  const fetchLogs = useCallback(async () => {
    setLoading(true);
    try {
      // Build query params
      const params = new URLSearchParams({
        page: String(page),
        limit: String(limit),
      });
      if (actionFilter) params.set('action', actionFilter);
      if (adminSearch) params.set('admin', adminSearch);
      if (dateFrom) params.set('from', dateFrom);
      if (dateTo) params.set('to', dateTo);

        const result = await apiFetch(`/api/v1/admin/logs?${params.toString()}`);
      // Map backend format to frontend format
      const mapped: PaginatedResponse = {
        items: (result.items || []).map((item: any) => ({
          id: item.id,
          timestamp: item.created_at || item.timestamp,
          admin_email: item.admin_email || 'unknown',
          action: item.action,
          target_type: item.target_type,
          target_id: item.target_id,
          details: item.details || '',
          ip_address: item.ip_address || '-',
        })),
        total: result.total || 0,
        page: page,
        limit: limit,
        total_pages: Math.ceil((result.total || 0) / limit),
      };
      setData(mapped);
      setError(null);
    } catch (err: any) {
      setError(err.message || 'Failed to load audit logs');
    } finally {
      setLoading(false);
    }
  }, [page, actionFilter, adminSearch, dateFrom, dateTo]);

  useEffect(() => {
    fetchLogs();
  }, [fetchLogs]);

  // Reset page when filters change
  const handleFilterChange = useCallback((setter: React.Dispatch<React.SetStateAction<any>>, value: any) => {
    setter(value);
    setPage(1);
  }, []);

  const handleExport = async () => {
    setExporting(true);
    try {
      // TODO: Real API — fetch all records for export or use server-side export
      // For now, export current page as a demo
      if (data?.items) {
        await new Promise((r) => setTimeout(r, 300));
        exportToCSV(data.items);
      }
    } finally {
      setExporting(false);
    }
  };

  const clearFilters = () => {
    setActionFilter('');
    setAdminSearch('');
    setDateFrom('');
    setDateTo('');
    setPage(1);
  };

  const hasFilters = actionFilter || adminSearch || dateFrom || dateTo;

  if (error && !data) {
    return (
      <div className="flex flex-col items-center justify-center h-64 text-red-400 gap-2">
        <AlertTriangle size={32} />
        <p>Failed to load audit logs: {error}</p>
        <button
          onClick={fetchLogs}
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
          <h2 className="text-xl font-bold text-white">Audit Logs</h2>
          <p className="text-sm text-slate-400 mt-1">
            Track admin actions and system changes
          </p>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={fetchLogs}
            className="flex items-center gap-2 px-3 py-1.5 text-sm text-slate-400 bg-slate-800 rounded-lg hover:bg-slate-700 transition-colors"
          >
            <RefreshCw size={14} className={loading ? 'animate-spin' : ''} />
            Refresh
          </button>
          <button
            onClick={handleExport}
            disabled={exporting || !data?.items.length}
            className="flex items-center gap-2 px-3 py-1.5 text-sm text-slate-300 bg-slate-800 border border-slate-700 rounded-lg hover:bg-slate-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          >
            <Download size={14} className={exporting ? 'animate-spin' : ''} />
            {exporting ? 'Exporting...' : 'Export CSV'}
          </button>
        </div>
      </div>

      {/* Filters Bar */}
      <div className="bg-slate-900 border border-slate-800 rounded-xl p-4">
        <div className="flex flex-wrap gap-3 items-end">
          {/* Action filter dropdown */}
          <div className="flex flex-col gap-1 min-w-[180px]">
            <label className="text-xs text-slate-500 flex items-center gap-1">
              <Filter size={11} /> Action Type
            </label>
            <select
              value={actionFilter}
              onChange={(e) => handleFilterChange(setActionFilter, e.target.value)}
              className="px-3 py-2 bg-slate-800 border border-slate-700 rounded-lg text-sm text-slate-300 focus:outline-none focus:border-blue-500"
            >
              <option value="">All Actions</option>
              <option value="user.">User Actions</option>
              <option value="subscription.">Subscription Actions</option>
              <option value="voucher.">Voucher Actions</option>
              <option value="payment.">Payment Actions</option>
              <option value="feature.">Feature Actions</option>
              <option value="api_key.">API Key Actions</option>
              <option value="admin.">Admin Actions</option>
              <option value="settings.">Settings Actions</option>
            </select>
          </div>

          {/* Admin search */}
          <div className="flex flex-col gap-1 min-w-[200px]">
            <label className="text-xs text-slate-500 flex items-center gap-1">
              <User size={11} /> Admin Email
            </label>
            <div className="relative">
              <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-500" />
              <input
                type="text"
                placeholder="Search admin..."
                value={adminSearch}
                onChange={(e) => handleFilterChange(setAdminSearch, e.target.value)}
                className="w-full pl-9 pr-4 py-2 bg-slate-800 border border-slate-700 rounded-lg text-sm text-white placeholder-slate-500 focus:outline-none focus:border-blue-500 transition-colors"
              />
            </div>
          </div>

          {/* Date range */}
          <div className="flex flex-col gap-1">
            <label className="text-xs text-slate-500 flex items-center gap-1">
              <Calendar size={11} /> From
            </label>
            <input
              type="date"
              value={dateFrom}
              onChange={(e) => handleFilterChange(setDateFrom, e.target.value)}
              className="px-3 py-2 bg-slate-800 border border-slate-700 rounded-lg text-sm text-slate-300 focus:outline-none focus:border-blue-500 [color-scheme:dark]"
            />
          </div>

          <div className="flex flex-col gap-1">
            <label className="text-xs text-slate-500 flex items-center gap-1">
              <Calendar size={11} /> To
            </label>
            <input
              type="date"
              value={dateTo}
              onChange={(e) => handleFilterChange(setDateTo, e.target.value)}
              className="px-3 py-2 bg-slate-800 border border-slate-700 rounded-lg text-sm text-slate-300 focus:outline-none focus:border-blue-500 [color-scheme:dark]"
            />
          </div>

          {/* Clear filters */}
          {hasFilters && (
            <button
              onClick={clearFilters}
              className="flex items-center gap-1 px-3 py-2 text-xs text-slate-400 hover:text-white bg-slate-800 border border-slate-700 rounded-lg hover:bg-slate-700 transition-colors"
            >
              <X size={12} />
              Clear
            </button>
          )}
        </div>
      </div>

      {/* Table */}
      <div className="bg-slate-900 border border-slate-800 rounded-xl overflow-hidden">
        {loading ? (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-slate-800">
                  <th className="text-left py-3 px-4 text-slate-400 font-medium">Timestamp</th>
                  <th className="text-left py-3 px-4 text-slate-400 font-medium">Admin</th>
                  <th className="text-left py-3 px-4 text-slate-400 font-medium">Action</th>
                  <th className="text-left py-3 px-4 text-slate-400 font-medium">Target</th>
                  <th className="text-left py-3 px-4 text-slate-400 font-medium">Details</th>
                  <th className="text-left py-3 px-4 text-slate-400 font-medium">IP</th>
                </tr>
              </thead>
              <tbody>
                {Array.from({ length: 5 }).map((_, i) => <SkeletonRow key={i} />)}
              </tbody>
            </table>
          </div>
        ) : !data || data.items.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-48 text-slate-500 gap-2">
            <FileText size={24} />
            <p className="text-sm">No audit logs found</p>
            {hasFilters && (
              <button onClick={clearFilters} className="text-xs text-blue-400 hover:text-blue-300 transition-colors">
                Clear filters
              </button>
            )}
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-slate-800">
                  <th className="text-left py-3 px-4 text-slate-400 font-medium">
                    <span className="flex items-center gap-1"><Calendar size={12} /> Timestamp</span>
                  </th>
                  <th className="text-left py-3 px-4 text-slate-400 font-medium">
                    <span className="flex items-center gap-1"><User size={12} /> Admin</span>
                  </th>
                  <th className="text-left py-3 px-4 text-slate-400 font-medium">
                    <span className="flex items-center gap-1"><Hash size={12} /> Action</span>
                  </th>
                  <th className="text-left py-3 px-4 text-slate-400 font-medium">
                    <span className="flex items-center gap-1"><Info size={12} /> Target</span>
                  </th>
                  <th className="text-left py-3 px-4 text-slate-400 font-medium w-64">Details</th>
                  <th className="text-left py-3 px-4 text-slate-400 font-medium">
                    <span className="flex items-center gap-1"><Globe size={12} /> IP</span>
                  </th>
                </tr>
              </thead>
              <tbody>
                {data.items.map((entry) => (
                  <tr
                    key={entry.id}
                    className="border-b border-slate-800/50 hover:bg-slate-800/30 transition-colors"
                  >
                    <td className="py-3 px-4 text-slate-300 text-xs font-mono whitespace-nowrap">
                      {formatTimestamp(entry.timestamp)}
                    </td>
                    <td className="py-3 px-4 text-slate-300 text-xs font-mono">
                      {entry.admin_email}
                    </td>
                    <td className="py-3 px-4">
                      <span className={`px-2 py-0.5 rounded text-xs font-medium border ${actionColor(entry.action)}`}>
                        {entry.action}
                      </span>
                    </td>
                    <td className="py-3 px-4">
                      <div className="flex flex-col gap-0.5">
                        <span className={`px-2 py-0.5 rounded text-xs font-medium border w-fit ${targetTypeColor(entry.target_type)}`}>
                          {entry.target_type}
                        </span>
                        <span className="text-xs text-slate-600 font-mono">{entry.target_id}</span>
                      </div>
                    </td>
                    <td className="py-3 px-4 text-slate-400 text-xs max-w-xs truncate" title={entry.details}>
                      {entry.details}
                    </td>
                    <td className="py-3 px-4 text-slate-500 text-xs font-mono whitespace-nowrap">
                      {entry.ip_address}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {/* Pagination */}
        {data && data.total > 0 && (
          <div className="flex items-center justify-between p-4 border-t border-slate-800">
            <p className="text-xs text-slate-500">
              Showing {(data.page - 1) * data.limit + 1}–{Math.min(data.page * data.limit, data.total)} of{' '}
              {data.total.toLocaleString()} entries
            </p>
            <div className="flex items-center gap-1">
              <button
                onClick={() => setPage((p) => Math.max(1, p - 1))}
                disabled={page <= 1}
                className="p-2 rounded-lg text-slate-400 hover:text-white hover:bg-slate-800 disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
              >
                <ChevronLeft size={16} />
              </button>

              {/* Page numbers */}
              {(() => {
                const pages: number[] = [];
                const totalPages = data.total_pages;
                const start = Math.max(1, page - 2);
                const end = Math.min(totalPages, page + 2);

                if (start > 1) {
                  pages.push(1);
                  if (start > 2) pages.push(-1); // ellipsis
                }
                for (let i = start; i <= end; i++) pages.push(i);
                if (end < totalPages) {
                  if (end < totalPages - 1) pages.push(-1); // ellipsis
                  pages.push(totalPages);
                }

                return pages.map((p, idx) =>
                  p === -1 ? (
                    <span key={`ellipsis-${idx}`} className="px-2 text-slate-600">...</span>
                  ) : (
                    <button
                      key={p}
                      onClick={() => setPage(p)}
                      className={`w-8 h-8 rounded-lg text-xs font-medium transition-colors ${
                        page === p
                          ? 'bg-blue-600 text-white'
                          : 'text-slate-400 hover:text-white hover:bg-slate-800'
                      }`}
                    >
                      {p}
                    </button>
                  )
                );
              })()}

              <button
                onClick={() => setPage((p) => Math.min(data.total_pages, p + 1))}
                disabled={page >= data.total_pages}
                className="p-2 rounded-lg text-slate-400 hover:text-white hover:bg-slate-800 disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
              >
                <ChevronRight size={16} />
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};
