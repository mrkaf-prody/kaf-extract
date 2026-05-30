import React, { useEffect, useState, useCallback } from 'react';
import { useAuth } from '../contexts/AuthContext';
import { BarChart3, Zap, Clock } from 'lucide-react';

interface UsageStats {
  current_usage: number;
  monthly_limit: number;
  hard_cap: number | null;
  percent: number;
  reset_date: string;
  alerts_sent: Record<string, boolean>;
}

interface ExtractRecord {
  id: string;
  url: string;
  status: string;
  created_at: string;
}

export const UsagePage: React.FC = () => {
  const { apiFetch, showError } = useAuth();
  const [usage, setUsage] = useState<UsageStats | null>(null);
  const [recent, setRecent] = useState<ExtractRecord[]>([]);
  const [loading, setLoading] = useState(true);

  const fetchData = useCallback(() => {
    setLoading(true);
    Promise.all([
      apiFetch('/api/v1/usage'),
      apiFetch('/api/v1/extract/history?limit=20'),
    ])
      .then(([u, h]) => {
        setUsage(u);
        const recentList = Array.isArray(h)
          ? h
          : h?.history || h?.extractions || [];
        setRecent(recentList);
      })
      .catch((err: any) => showError(err.message || 'Failed to load usage data'))
      .finally(() => setLoading(false));
  }, [apiFetch]);

  useEffect(() => { fetchData(); }, [fetchData]);

  const percent = usage?.percent ?? 0;
  const barColor =
    percent >= 90 ? 'bg-red-500' :
    percent >= 80 ? 'bg-yellow-500' :
    'bg-[#00d4a0]';

  const daysRemaining = usage
    ? Math.max(0, Math.ceil(
        (new Date(usage.reset_date).getTime() - Date.now()) / (1000 * 60 * 60 * 24)
      ))
    : 0;

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20">
        <span className="text-[#9a9aae]">Loading usage data...</span>
      </div>
    );
  }

  return (
    <div>
      <div className="mb-6">
        <h2 className="text-2xl font-bold text-[#f0f0f5] mb-1">Usage</h2>
        <p className="text-[#9a9aae] text-sm">Monitor your monthly extraction usage and limits.</p>
      </div>

      {/* Usage bar */}
      <div className="bg-[#0a0a12] border border-[#1c1c2a] rounded-xl p-6 mb-6">
        <div className="flex items-center justify-between mb-3">
          <h3 className="text-lg font-semibold text-[#f0f0f5] flex items-center gap-2">
            <BarChart3 size={20} className="text-[#00d4a0]" />
            Current Month Usage
          </h3>
          <span className="text-sm text-[#9a9aae]">
            Resets in <span className="text-[#f0f0f5] font-medium">{daysRemaining}</span> days
          </span>
        </div>

        <div className="flex items-end gap-2 mb-2">
          <span className="text-3xl font-bold text-[#f0f0f5]">
            {usage ? usage.current_usage.toLocaleString() : '0'}
          </span>
          <span className="text-[#5c5c70] text-lg mb-0.5">
            / {usage ? usage.monthly_limit.toLocaleString() : '0'}
          </span>
          <span className="text-sm text-[#5c5c70] mb-0.5 ml-1">extractions</span>
        </div>

        {usage?.hard_cap && (
          <p className="text-xs text-[#5c5c70] mb-3">Hard cap: {usage.hard_cap.toLocaleString()}</p>
        )}

        {/* Progress bar */}
        <div className="w-full bg-[#14141f] rounded-full h-3 mb-2 overflow-hidden">
          <div
            className={`${barColor} h-full rounded-full transition-all duration-500`}
            style={{ width: `${Math.min(percent, 100)}%` }}
          />
        </div>
        <div className="flex justify-between text-xs text-[#5c5c70]">
          <span>{percent}% used</span>
          <span>{100 - percent}% remaining</span>
        </div>

        {/* Alert indicators */}
        {usage?.alerts_sent && Object.keys(usage.alerts_sent).length > 0 && (
          <div className="mt-4 flex gap-2">
            {Object.entries(usage.alerts_sent).map(([threshold, sent]) => (
              <span
                key={threshold}
                className={`text-xs px-2 py-1 rounded ${
                  sent ? 'bg-yellow-500/10 text-yellow-400 border border-yellow-500/30' : 'bg-[#14141f] text-[#5c5c70]'
                }`}
              >
                {threshold}% alert {sent ? 'sent' : 'pending'}
              </span>
            ))}
          </div>
        )}
      </div>

      {/* Reset date card */}
      <div className="bg-[#0a0a12] border border-[#1c1c2a] rounded-xl p-5 mb-6">
        <div className="flex items-center gap-3">
          <Clock size={20} className="text-purple-400" />
          <div>
            <div className="text-[#f0f0f5] font-medium">Monthly Reset</div>
            <div className="text-sm text-[#9a9aae]">
              {usage ? new Date(usage.reset_date).toLocaleDateString('en-US', {
                year: 'numeric', month: 'long', day: 'numeric',
              }) : 'Unknown'}
            </div>
          </div>
        </div>
      </div>

      {/* Recent extractions */}
      <div className="bg-[#0a0a12] border border-[#1c1c2a] rounded-xl p-5">
        <h3 className="text-lg font-semibold text-[#f0f0f5] mb-4 flex items-center gap-2">
          <Zap size={18} className="text-yellow-400" />
          Recent Extractions
        </h3>
        {recent.length === 0 ? (
          <p className="text-[#5c5c70] text-sm">No recent extractions found.</p>
        ) : (
          <div className="space-y-2">
            {recent.map((item, i) => (
              <div
                key={item.id || i}
                className="flex items-center justify-between py-2 px-3 bg-[#14141f]/50 rounded text-sm"
              >
                <div className="flex items-center gap-3 min-w-0 flex-1">
                  <span
                    className={`w-2 h-2 rounded-full flex-shrink-0 ${
                      item.status === 'success' ? 'bg-green-400' :
                      item.status === 'queued' ? 'bg-yellow-400' : 'bg-red-400'
                    }`}
                  />
                  <span className="text-[#b8b8c8] truncate">{item.url}</span>
                </div>
                <div className="flex items-center gap-3 ml-4 flex-shrink-0">
                  <span
                    className={`text-xs px-2 py-0.5 rounded ${
                      item.status === 'success' ? 'bg-green-500/10 text-green-400' :
                      item.status === 'queued' ? 'bg-yellow-500/10 text-yellow-400' : 'bg-red-500/10 text-red-400'
                    }`}
                  >
                    {item.status}
                  </span>
                  <span className="text-[#5c5c70] text-xs">
                    {item.created_at ? new Date(item.created_at).toLocaleString() : ''}
                  </span>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
};
