import React, { useEffect, useState, useCallback } from 'react';
import { useAuth } from '../contexts/AuthContext';
import { Key, Plus, Copy, Trash2, Check, X, AlertTriangle } from 'lucide-react';

interface KeyItem {
  id: string;
  label: string;
  tier: string;
  status: string;
  last_used_at: string | null;
  created_at: string;
  user_id: string;
  user_email: string;
  rate_limit: number;
}

export const ApiKeysPage: React.FC = () => {
  const { apiFetch } = useAuth();
  const [keys, setKeys] = useState<KeyItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [showCreate, setShowCreate] = useState(false);
  const [newLabel, setNewLabel] = useState('');
  const [creating, setCreating] = useState(false);
  const [newKeyRaw, setNewKeyRaw] = useState<string | null>(null);
  const [copied, setCopied] = useState<string | null>(null);
  const [error, setError] = useState('');
  const [successMsg, setSuccessMsg] = useState('');

  const fetchKeys = useCallback(() => {
    setLoading(true);
    setError('');
    apiFetch('/api/v1/keys')
      .then(data => setKeys(Array.isArray(data) ? data : data.keys || []))
      .catch((err: any) => setError(err.message || 'Failed to load keys'))
      .finally(() => setLoading(false));
  }, [apiFetch]);

  useEffect(() => { fetchKeys(); }, [fetchKeys]);

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newLabel.trim()) return;
    setError('');
    setSuccessMsg('');
    setCreating(true);
    try {
      const res = await apiFetch('/api/v1/keys', {
        method: 'POST',
        body: JSON.stringify({ label: newLabel.trim() }),
      });
      setNewKeyRaw(res.api_key || '');
      setNewLabel('');
      setShowCreate(false);
      setSuccessMsg('Key created successfully. Copy it now — it will not be shown again.');
      fetchKeys();
    } catch (err: any) {
      setError(err.message || 'Failed to create key');
    } finally {
      setCreating(false);
    }
  };

  const handleDelete = async (id: string) => {
    if (!confirm('Are you sure you want to revoke this API key?')) return;
    setError('');
    try {
      await apiFetch(`/api/v1/keys/${id}`, { method: 'DELETE' });
      setSuccessMsg('Key revoked successfully.');
      fetchKeys();
    } catch (err: any) {
      setError(err.message || 'Failed to delete key');
    }
  };

  const copyToClipboard = async (text: string, id: string) => {
    await navigator.clipboard.writeText(text);
    setCopied(id);
    setTimeout(() => setCopied(null), 2000);
  };

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <div>
          <h2 className="text-2xl font-bold text-white mb-1">API Keys</h2>
          <p className="text-slate-400 text-sm">Manage your API keys for programmatic access.</p>
        </div>
        <button
          onClick={() => { setShowCreate(true); setNewKeyRaw(null); setError(''); setSuccessMsg(''); }}
          className="flex items-center gap-2 bg-blue-600 hover:bg-blue-700 text-white rounded px-4 py-2 text-sm font-medium transition-colors"
        >
          <Plus size={16} />
          Create Key
        </button>
      </div>

      {error && (
        <div className="bg-red-500/10 border border-red-500/30 rounded p-3 text-sm text-red-400 mb-4 flex items-center gap-2">
          <AlertTriangle size={16} />
          {error}
        </div>
      )}

      {successMsg && (
        <div className="bg-green-500/10 border border-green-500/30 rounded p-3 text-sm text-green-400 mb-4 flex items-center gap-2">
          <Check size={16} />
          {successMsg}
          <button onClick={() => setSuccessMsg('')} className="ml-auto text-slate-500 hover:text-slate-300">
            <X size={14} />
          </button>
        </div>
      )}

      {/* New key raw display */}
      {newKeyRaw && (
        <div className="bg-green-500/10 border border-green-500/30 rounded-lg p-4 mb-4">
          <div className="flex items-center justify-between mb-2">
            <span className="text-green-400 font-medium text-sm">Key Created Successfully</span>
            <button onClick={() => setNewKeyRaw(null)} className="text-slate-500 hover:text-slate-300">
              <X size={16} />
            </button>
          </div>
          <p className="text-xs text-slate-400 mb-2">
            Store this key securely. It will not be shown again.
          </p>
          <div className="flex items-center gap-2">
            <code className="flex-1 bg-slate-800 rounded px-3 py-2 text-sm text-slate-300 break-all">
              {newKeyRaw}
            </code>
            <button
              onClick={() => copyToClipboard(newKeyRaw, 'new-key')}
              className="p-2 bg-slate-800 hover:bg-slate-700 rounded transition-colors"
              title="Copy to clipboard"
            >
              {copied === 'new-key' ? <Check size={16} className="text-green-400" /> : <Copy size={16} className="text-slate-400" />}
            </button>
          </div>
        </div>
      )}

      {/* Create form */}
      {showCreate && (
        <div className="bg-slate-900 border border-slate-800 rounded-lg p-5 mb-4">
          <h3 className="text-lg font-semibold text-white mb-3">Create New API Key</h3>
          <form onSubmit={handleCreate} className="flex gap-3">
            <input
              type="text"
              value={newLabel}
              onChange={e => setNewLabel(e.target.value)}
              placeholder="Key label (e.g., 'Production', 'Testing')"
              className="flex-1 bg-slate-800 border border-slate-700 rounded px-3 py-2 text-white text-sm
                         focus:outline-none focus:border-blue-500 transition-colors"
              autoFocus
            />
            <button
              type="submit"
              disabled={creating || !newLabel.trim()}
              className="bg-blue-600 hover:bg-blue-700 disabled:bg-blue-800 disabled:cursor-not-allowed
                         text-white rounded px-4 py-2 text-sm font-medium transition-colors"
            >
              {creating ? 'Creating...' : 'Create'}
            </button>
            <button
              type="button"
              onClick={() => setShowCreate(false)}
              className="bg-slate-700 hover:bg-slate-600 text-slate-300 rounded px-4 py-2 text-sm transition-colors"
            >
              Cancel
            </button>
          </form>
        </div>
      )}

      {/* Keys list */}
      {loading ? (
        <div className="text-slate-400 text-sm py-8 text-center">Loading...</div>
      ) : keys.length === 0 ? (
        <div className="bg-slate-900 border border-slate-800 rounded-lg p-8 text-center">
          <Key size={40} className="text-slate-600 mx-auto mb-3" />
          <p className="text-slate-400 mb-2">No API keys yet</p>
          <p className="text-slate-500 text-sm">Create your first API key to start extracting data.</p>
        </div>
      ) : (
        <div className="space-y-3">
          {keys.map(key => (
            <div
              key={key.id}
              className="bg-slate-900 border border-slate-800 rounded-lg p-4 flex items-center justify-between"
            >
              <div className="min-w-0 flex-1">
                <div className="flex items-center gap-2 mb-1">
                  <span className="text-white font-medium text-sm">{key.label}</span>
                  <span
                    className={`text-xs px-2 py-0.5 rounded-full ${
                      key.status === 'active'
                        ? 'bg-green-500/10 text-green-400'
                        : 'bg-slate-500/10 text-slate-400'
                    }`}
                  >
                    {key.status}
                  </span>
                  <span className="text-xs bg-blue-500/10 text-blue-400 px-2 py-0.5 rounded-full">
                    {key.tier}
                  </span>
                </div>
                <div className="flex items-center gap-4 text-xs text-slate-500">
                  <span>ID: {key.id.slice(0, 8)}...</span>
                  <span>Rate limit: {key.rate_limit}/min</span>
                  {key.last_used_at && (
                    <span>Last used: {new Date(key.last_used_at).toLocaleDateString()}</span>
                  )}
                  <span>Created: {new Date(key.created_at).toLocaleDateString()}</span>
                </div>
              </div>
              <div className="flex items-center gap-2 ml-4">
                {key.status === 'active' && (
                  <button
                    onClick={() => handleDelete(key.id)}
                    className="p-2 text-slate-500 hover:text-red-400 hover:bg-red-500/10 rounded transition-colors"
                    title="Revoke key"
                  >
                    <Trash2 size={16} />
                  </button>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};
