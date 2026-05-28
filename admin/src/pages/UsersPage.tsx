import React, { useEffect, useState, useCallback, useMemo } from 'react';
import { useAuth } from '../contexts/AuthContext';
import {
  Search, Filter, ChevronDown, UserX, UserCheck, Trash2,
  RefreshCw, AlertTriangle, X, Mail, Calendar, Shield,
} from 'lucide-react';

// ─── Types ───

interface User {
  id: string;
  email: string;
  name: string;
  role: 'admin' | 'user' | 'moderator';
  status: 'active' | 'suspended' | 'pending';
  created_at: string;
}

// ─── Mock Data (replace with GET /api/v1/admin/users) ───

const MOCK_USERS: User[] = [
  { id: '1', email: 'admin@kaf.io', name: 'Admin User', role: 'admin', status: 'active', created_at: '2025-01-10T08:00:00Z' },
  { id: '2', email: 'alice@example.com', name: 'Alice Johnson', role: 'user', status: 'active', created_at: '2025-02-14T12:30:00Z' },
  { id: '3', email: 'bob@acme.com', name: 'Bob Smith', role: 'user', status: 'active', created_at: '2025-02-20T09:15:00Z' },
  { id: '4', email: 'carol@demo.io', name: 'Carol Williams', role: 'user', status: 'suspended', created_at: '2025-03-01T14:00:00Z' },
  { id: '5', email: 'dave@test.com', name: 'Dave Brown', role: 'user', status: 'pending', created_at: '2025-03-10T16:45:00Z' },
  { id: '6', email: 'eve@corp.net', name: 'Eve Davis', role: 'moderator', status: 'active', created_at: '2025-03-15T11:20:00Z' },
  { id: '7', email: 'frank@startup.io', name: 'Frank Miller', role: 'user', status: 'active', created_at: '2025-04-01T07:00:00Z' },
  { id: '8', email: 'grace@enterprise.co', name: 'Grace Wilson', role: 'user', status: 'suspended', created_at: '2025-04-05T13:30:00Z' },
  { id: '9', email: 'henry@freelance.dev', name: 'Henry Taylor', role: 'user', status: 'active', created_at: '2025-04-12T10:00:00Z' },
  { id: '10', email: 'iris@agency.com', name: 'Iris Anderson', role: 'moderator', status: 'pending', created_at: '2025-04-20T15:00:00Z' },
];

// ─── Badge styles ───

const statusBadge = (status: User['status']) => {
  const map = {
    active: 'bg-emerald-500/10 text-emerald-400 border-emerald-500/30',
    suspended: 'bg-red-500/10 text-red-400 border-red-500/30',
    pending: 'bg-amber-500/10 text-amber-400 border-amber-500/30',
  };
  return `px-2 py-0.5 rounded text-xs font-medium border ${map[status]}`;
};

const roleBadge = (role: User['role']) => {
  const map = {
    admin: 'bg-purple-500/10 text-purple-400 border-purple-500/30',
    moderator: 'bg-blue-500/10 text-blue-400 border-blue-500/30',
    user: 'bg-slate-500/10 text-slate-400 border-slate-500/30',
  };
  return `px-2 py-0.5 rounded text-xs font-medium border ${map[role]}`;
};

// ─── Confirmation Modal ───

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

export const UsersPage: React.FC = () => {
  const { apiFetch } = useAuth();
  const [users, setUsers] = useState<User[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Filters
  const [search, setSearch] = useState('');
  const [roleFilter, setRoleFilter] = useState<string>('all');
  const [statusFilter, setStatusFilter] = useState<string>('all');

  // Confirm modal
  const [confirm, setConfirm] = useState<{
    user: User; action: 'activate' | 'suspend' | 'delete';
  } | null>(null);

  // Load
  useEffect(() => {
    // TODO: Replace with real API: apiFetch('/v1/admin/users')
    const timer = setTimeout(() => {
      setUsers(MOCK_USERS);
      setLoading(false);
    }, 700);
    return () => clearTimeout(timer);
  }, []);

  // Derived filtered list
  const filtered = useMemo(() => {
    return users.filter((u) => {
      const matchSearch = !search ||
        u.email.toLowerCase().includes(search.toLowerCase()) ||
        u.name.toLowerCase().includes(search.toLowerCase());
      const matchRole = roleFilter === 'all' || u.role === roleFilter;
      const matchStatus = statusFilter === 'all' || u.status === statusFilter;
      return matchSearch && matchRole && matchStatus;
    });
  }, [users, search, roleFilter, statusFilter]);

  // Actions
  const handleAction = useCallback((action: 'activate' | 'suspend' | 'delete', userId: string) => {
    setUsers((prev) => {
      if (action === 'delete') return prev.filter((u) => u.id !== userId);
      return prev.map((u) =>
        u.id === userId
          ? { ...u, status: action === 'activate' ? 'active' : 'suspended' }
          : u
      );
    });
    setConfirm(null);
    // TODO: Real API call:
    // if (action === 'delete') await apiFetch(`/v1/admin/users/${userId}`, { method: 'DELETE' });
    // else await apiFetch(`/v1/admin/users/${userId}`, { method: 'PATCH', body: JSON.stringify({ status: action === 'activate' ? 'active' : 'suspended' }) });
  }, []);

  const formatDate = (iso: string) =>
    new Date(iso).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });

  if (error) {
    return (
      <div className="flex flex-col items-center justify-center h-64 text-red-400 gap-2">
        <AlertTriangle size={32} />
        <p>Failed to load users: {error}</p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xl font-bold text-white">Users</h2>
          <p className="text-sm text-slate-400 mt-1">Manage user accounts and permissions</p>
        </div>
      </div>

      {/* Filters bar */}
      <div className="flex flex-wrap gap-3 items-center">
        {/* Search */}
        <div className="relative flex-1 min-w-[200px] max-w-sm">
          <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-500" />
          <input
            type="text"
            placeholder="Search by email or name..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-full pl-10 pr-4 py-2 bg-slate-900 border border-slate-700 rounded-lg text-sm text-white placeholder-slate-500 focus:outline-none focus:border-blue-500 transition-colors"
          />
        </div>

        {/* Role filter */}
        <select
          value={roleFilter}
          onChange={(e) => setRoleFilter(e.target.value)}
          className="px-3 py-2 bg-slate-900 border border-slate-700 rounded-lg text-sm text-slate-300 focus:outline-none focus:border-blue-500"
        >
          <option value="all">All Roles</option>
          <option value="admin">Admin</option>
          <option value="moderator">Moderator</option>
          <option value="user">User</option>
        </select>

        {/* Status filter */}
        <select
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value)}
          className="px-3 py-2 bg-slate-900 border border-slate-700 rounded-lg text-sm text-slate-300 focus:outline-none focus:border-blue-500"
        >
          <option value="all">All Status</option>
          <option value="active">Active</option>
          <option value="suspended">Suspended</option>
          <option value="pending">Pending</option>
        </select>

        {/* Refresh */}
        <button
          onClick={() => { setLoading(true); setTimeout(() => { setUsers(MOCK_USERS); setLoading(false); }, 500); }}
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
            Loading users...
          </div>
        ) : filtered.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-48 text-slate-500 gap-2">
            <Search size={24} />
            <p>No users found matching your filters</p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-slate-800">
                  <th className="text-left py-3 px-4 text-slate-400 font-medium">
                    <span className="flex items-center gap-1"><Mail size={13} /> Email</span>
                  </th>
                  <th className="text-left py-3 px-4 text-slate-400 font-medium">Name</th>
                  <th className="text-left py-3 px-4 text-slate-400 font-medium">
                    <span className="flex items-center gap-1"><Shield size={13} /> Role</span>
                  </th>
                  <th className="text-left py-3 px-4 text-slate-400 font-medium">Status</th>
                  <th className="text-left py-3 px-4 text-slate-400 font-medium">
                    <span className="flex items-center gap-1"><Calendar size={13} /> Created</span>
                  </th>
                  <th className="text-right py-3 px-4 text-slate-400 font-medium">Actions</th>
                </tr>
              </thead>
              <tbody>
                {filtered.map((u) => (
                  <tr key={u.id} className="border-b border-slate-800/50 hover:bg-slate-800/30 transition-colors">
                    <td className="py-3 px-4 text-white font-mono text-xs">{u.email}</td>
                    <td className="py-3 px-4 text-slate-300">{u.name}</td>
                    <td className="py-3 px-4"><span className={roleBadge(u.role)}>{u.role}</span></td>
                    <td className="py-3 px-4"><span className={statusBadge(u.status)}>{u.status}</span></td>
                    <td className="py-3 px-4 text-slate-500 text-xs">{formatDate(u.created_at)}</td>
                    <td className="py-3 px-4">
                      <div className="flex items-center justify-end gap-1">
                        {u.status !== 'active' && (
                          <button
                            onClick={() => setConfirm({ user: u, action: 'activate' })}
                            className="p-1.5 rounded-lg text-slate-400 hover:text-emerald-400 hover:bg-emerald-500/10 transition-colors"
                            title="Activate"
                          >
                            <UserCheck size={15} />
                          </button>
                        )}
                        {u.status === 'active' && u.role !== 'admin' && (
                          <button
                            onClick={() => setConfirm({ user: u, action: 'suspend' })}
                            className="p-1.5 rounded-lg text-slate-400 hover:text-amber-400 hover:bg-amber-500/10 transition-colors"
                            title="Suspend"
                          >
                            <UserX size={15} />
                          </button>
                        )}
                        {u.role !== 'admin' && (
                          <button
                            onClick={() => setConfirm({ user: u, action: 'delete' })}
                            className="p-1.5 rounded-lg text-slate-400 hover:text-red-400 hover:bg-red-500/10 transition-colors"
                            title="Delete"
                          >
                            <Trash2 size={15} />
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
      {!loading && filtered.length > 0 && (
        <p className="text-xs text-slate-600">
          Showing {filtered.length} of {users.length} users
        </p>
      )}

      {/* Confirm Modal */}
      <ConfirmModal
        open={!!confirm}
        title={
          confirm?.action === 'delete' ? 'Delete User'
          : confirm?.action === 'suspend' ? 'Suspend User'
          : 'Activate User'
        }
        message={
          confirm?.action === 'delete'
            ? `Are you sure you want to permanently delete ${confirm?.user.email}? This action cannot be undone.`
            : confirm?.action === 'suspend'
            ? `Suspend ${confirm?.user.email}? They will lose access until reactivated.`
            : `Activate ${confirm?.user.email}? They will regain full access.`
        }
        actionLabel={
          confirm?.action === 'delete' ? 'Delete'
          : confirm?.action === 'suspend' ? 'Suspend'
          : 'Activate'
        }
        actionClass={
          confirm?.action === 'delete' ? 'bg-red-600 hover:bg-red-500'
          : confirm?.action === 'suspend' ? 'bg-amber-600 hover:bg-amber-500'
          : 'bg-emerald-600 hover:bg-emerald-500'
        }
        onConfirm={() => confirm && handleAction(confirm.action, confirm.user.id)}
        onCancel={() => setConfirm(null)}
      />
    </div>
  );
};
