import React, { useEffect, useState } from 'react';
import { useAuth } from '../contexts/AuthContext';
import { Zap, Key, Activity, Clock } from 'lucide-react';

interface UsageStats {
  current_usage: number;
  monthly_limit: number;
  percent: number;
  reset_date: string;
}

interface KeyItem {
  id: string;
  label: string;
  tier: string;
  status: string;
  last_used_at: string | null;
  created_at: string;
}

interface ExtractRecord {
  id: string;
  url: string;
  status: string;
  created_at: string;
}

export const OverviewPage: React.FC = () => {
  const { user, apiFetch } = useAuth();
  const [usage, setUsage] = useState<UsageStats | null>(null);
  const [keys, setKeys] = useState<KeyItem[]>([]);
  const [recent, setRecent] = useState<ExtractRecord[]>([]);

  useEffect(() => {
    // Fetch usage stats
    apiFetch('/api/v1/usage').then(setUsage).catch(() => {});
    // Fetch API keys count
    apiFetch('/api/v1/keys').then(setKeys).catch(() => {});
    // Fetch recent activity (extraction history)
    apiFetch('/api/v1/extract/history?limit=5')
      .then(data => setRecent(data.extractions || data || []))
      .catch(() => {});
  }, [apiFetch]);

  return (
    <div>
      <div className="mb-8">
        <h2 className="text-2xl font-bold text-white mb-1">
          Welcome back{user?.name ? `, ${user.name}` : ''}!
        </h2>
        <p className="text-slate-400 text-sm">
          Here's a quick overview of your Kaf Extract account.
        </p>
      </div>

      {/* Stats cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-8">
        <div className="bg-slate-900 border border-slate-800 rounded-lg p-5">
          <div className="flex items-center gap-3 mb-3">
            <div className="p-2 bg-blue-500/10 rounded">
              <Activity size={20} className="text-blue-400" />
            </div>
            <span className="text-sm text-slate-400">Total Extractions</span>
          </div>
          <div className="text-3xl font-bold text-white">
            {usage ? usage.current_usage.toLocaleString() : '—'}
          </div>
          <div className="text-xs text-slate-500 mt-1">
            of {usage ? usage.monthly_limit.toLocaleString() : '—'} monthly limit
          </div>
        </div>

        <div className="bg-slate-900 border border-slate-800 rounded-lg p-5">
          <div className="flex items-center gap-3 mb-3">
            <div className="p-2 bg-green-500/10 rounded">
              <Key size={20} className="text-green-400" />
            </div>
            <span className="text-sm text-slate-400">API Keys</span>
          </div>
          <div className="text-3xl font-bold text-white">{keys.length}</div>
          <div className="text-xs text-slate-500 mt-1">
            {keys.filter(k => k.status === 'active').length} active
          </div>
        </div>

        <div className="bg-slate-900 border border-slate-800 rounded-lg p-5">
          <div className="flex items-center gap-3 mb-3">
            <div className="p-2 bg-purple-500/10 rounded">
              <Clock size={20} className="text-purple-400" />
            </div>
            <span className="text-sm text-slate-400">Usage Reset</span>
          </div>
          <div className="text-3xl font-bold text-white">
            {usage ? Math.max(0, Math.ceil(
              (new Date(usage.reset_date).getTime() - Date.now()) / (1000 * 60 * 60 * 24)
            )) : '—'}
          </div>
          <div className="text-xs text-slate-500 mt-1">days remaining</div>
        </div>
      </div>

      {/* Recent Activity */}
      <div className="bg-slate-900 border border-slate-800 rounded-lg p-5">
        <h3 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
          <Zap size={18} className="text-yellow-400" />
          Recent Activity
        </h3>
        {recent.length === 0 ? (
          <p className="text-slate-500 text-sm">No recent extractions found.</p>
        ) : (
          <div className="space-y-2">
            {recent.slice(0, 5).map((item, i) => (
              <div
                key={item.id || i}
                className="flex items-center justify-between py-2 px-3 bg-slate-800/50 rounded text-sm"
              >
                <div className="flex items-center gap-3 min-w-0">
                  <span
                    className={`w-2 h-2 rounded-full flex-shrink-0 ${
                      item.status === 'success' ? 'bg-green-400' : 'bg-red-400'
                    }`}
                  />
                  <span className="text-slate-300 truncate max-w-xs">{item.url}</span>
                </div>
                <span className="text-slate-500 text-xs ml-4 flex-shrink-0">
                  {item.created_at ? new Date(item.created_at).toLocaleDateString() : ''}
                </span>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
};
