import { useEffect, useState } from 'react';
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

export const OverviewPage = () => {
  const { user, apiFetch } = useAuth();
  const [usage, setUsage] = useState<UsageStats | null>(null);
  const [keys, setKeys] = useState<KeyItem[]>([]);
  const [recent, setRecent] = useState<ExtractRecord[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const [u, kData, h] = await Promise.all([
          apiFetch('/api/v1/usage'),
          apiFetch('/api/v1/keys'),
          apiFetch('/api/v1/extract/history?limit=5').catch(() => null),
        ]);
        if (cancelled) return;
        console.log('Usage:', u);
        console.log('Keys:', kData);
        console.log('History:', h);
        setUsage(u);
        const arr = Array.isArray(kData) ? kData : kData.keys || [];
        setKeys(arr);
        setRecent(h?.extractions || h || []);
      } catch (e) {
        console.error('Overview load error:', e);
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => { cancelled = true; };
  }, [apiFetch]);

  if (loading) {
    return (
      <div className="flex flex-col items-center justify-center h-64 text-[#9a9aae]">
        <div className="w-8 h-8 border-2 border-[#00d4a0] border-t-transparent rounded-full animate-spin mb-3"></div>
        Loading dashboard...
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="animate-reveal">
        <h2 className="text-2xl font-bold text-[#f0f0f5] mb-1">
          Welcome back{user?.name ? `, ${user.name}` : ''}!
        </h2>
        <p className="text-sm text-[#9a9aae]">Here's a quick overview of your Kaf Extract account.</p>
      </div>

      {/* Stats cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4 animate-reveal">
        <div className="bg-[#0f0f18] border border-[#1c1c2a] rounded-xl p-5 hover:border-[rgba(0,212,160,0.2)] transition-colors">
          <div className="flex items-center gap-3 mb-3">
            <div className="p-2 bg-[rgba(68,148,255,0.08)] rounded-lg">
              <Activity size={20} className="text-[#4494ff]" />
            </div>
            <span className="text-sm text-[#9a9aae]">Total Extractions</span>
          </div>
          <div className="text-3xl font-bold text-[#f0f0f5]">
            {usage ? (typeof usage.current_usage === 'number' ? usage.current_usage.toLocaleString() : '0') : '—'}
          </div>
          <div className="text-xs text-[#5c5c70] mt-1">
            of {usage ? (typeof usage.monthly_limit === 'number' ? usage.monthly_limit.toLocaleString() : '0') : '—'} monthly
          </div>
        </div>

        <div className="bg-[#0f0f18] border border-[#1c1c2a] rounded-xl p-5 hover:border-[rgba(0,212,160,0.2)] transition-colors">
          <div className="flex items-center gap-3 mb-3">
            <div className="p-2 bg-[rgba(0,212,160,0.08)] rounded-lg">
              <Key size={20} className="text-[#00d4a0]" />
            </div>
            <span className="text-sm text-[#9a9aae]">API Keys</span>
          </div>
          <div className="text-3xl font-bold text-[#f0f0f5]">{keys.length}</div>
          <div className="text-xs text-[#5c5c70] mt-1">{keys.filter(k => k.status === 'active').length} active</div>
        </div>

        <div className="bg-[#0f0f18] border border-[#1c1c2a] rounded-xl p-5 hover:border-[rgba(255,189,46,0.2)] transition-colors">
          <div className="flex items-center gap-3 mb-3">
            <div className="p-2 bg-[rgba(255,189,46,0.08)] rounded-lg">
              <Clock size={20} className="text-[#ffbd2e]" />
            </div>
            <span className="text-sm text-[#9a9aae]">Usage Reset</span>
          </div>
          <div className="text-3xl font-bold text-[#f0f0f5]">
            {usage && usage.reset_date
              ? Math.max(0, Math.ceil((new Date(usage.reset_date).getTime() - Date.now()) / (1000 * 60 * 60 * 24)))
              : '—'}
          </div>
          <div className="text-xs text-[#5c5c70] mt-1">days remaining</div>
        </div>
      </div>

      {/* Recent Activity */}
      <div className="bg-[#0f0f18] border border-[#1c1c2a] rounded-xl p-5 animate-reveal">
        <h3 className="text-lg font-semibold text-[#f0f0f5] mb-4 flex items-center gap-2">
          <Zap size={18} className="text-[#00d4a0]" />
          Recent Activity
        </h3>
        {recent.length === 0 ? (
          <p className="text-[#5c5c70] text-sm">No recent extractions found. Start extracting!</p>
        ) : (
          <div className="space-y-2">
            {recent.slice(0, 5).map((item, i) => (
              <div key={item.id || i} className="flex items-center justify-between py-2 px-3 bg-[#14141f] rounded-lg text-sm border border-[#12121a]">
                <div className="flex items-center gap-3 min-w-0">
                  <span className={`w-2 h-2 rounded-full flex-shrink-0 ${item.status === 'success' ? 'bg-[#00d4a0]' : 'bg-[#ff5f56]'}`} />
                  <span className="text-[#9a9aae] truncate max-w-xs">{item.url}</span>
                </div>
                <span className="text-[#5c5c70] text-xs ml-4 flex-shrink-0">
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
