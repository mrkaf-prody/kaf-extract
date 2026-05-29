import { NavLink, Outlet } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { LayoutDashboard, Key, BarChart3, CreditCard, LogOut, Zap, User } from 'lucide-react';

const navItems = [
  { to: '/dashboard', icon: LayoutDashboard, label: 'Overview', end: true },
  { to: '/dashboard/keys', icon: Key, label: 'API Keys' },
  { to: '/dashboard/usage', icon: BarChart3, label: 'Usage' },
  { to: '/dashboard/profile', icon: User, label: 'Profile' },
  { to: '/dashboard/billing', icon: CreditCard, label: 'Billing' },
];

export const DashboardLayout = () => {
  const { user, logout } = useAuth();
  return (
    <div className="flex h-screen bg-[#06060a]">
      {/* Sidebar */}
      <aside className="w-[240px] bg-[#0a0a12] border-r border-[#1c1c2a] flex flex-col">
        <div className="p-4 border-b border-[#1c1c2a]">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-xl bg-[rgba(0,212,160,0.08)] border border-[rgba(0,212,160,0.15)] flex items-center justify-center">
              <Zap size={18} className="text-[#00d4a0]" />
            </div>
            <div>
              <h1 className="text-base font-bold text-[#f0f0f5] tracking-tight">Kaf Extract</h1>
              <p className="text-[10px] text-[#5c5c70] uppercase tracking-wider">User Dashboard</p>
            </div>
          </div>
        </div>
        <nav className="flex-1 py-2 overflow-y-auto">
          {navItems.map(item => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.end}
              className={({ isActive }) =>
                `flex items-center gap-3 px-4 py-2.5 text-sm transition-all ${
                  isActive
                    ? 'bg-[rgba(0,212,160,0.08)] text-[#00d4a0] border-r-2 border-[#00d4a0]'
                    : 'text-[#9a9aae] hover:text-[#f0f0f5] hover:bg-[#14141f]'
                }`
              }
            >
              <item.icon size={18} />
              {item.label}
            </NavLink>
          ))}
        </nav>
        <div className="p-4 border-t border-[#1c1c2a] space-y-3">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-lg bg-[#14141f] border border-[#1c1c2a] flex items-center justify-center">
              <User size={14} className="text-[#9a9aae]" />
            </div>
            <div className="min-w-0">
              <div className="text-sm text-[#f0f0f5] truncate">{user?.name || user?.email}</div>
              <div className="text-[10px] text-[#5c5c70] truncate">{user?.email}</div>
            </div>
          </div>
          <button
            onClick={logout}
            className="flex items-center gap-2 text-xs text-[#5c5c70] hover:text-[#ff5f56] transition-colors w-full px-3 py-2 rounded-lg hover:bg-[rgba(255,95,86,0.05)]"
          >
            <LogOut size={14} /> Sign out
          </button>
        </div>
      </aside>
      {/* Content */}
      <main className="flex-1 overflow-y-auto bg-[#06060a] p-6">
        <Outlet />
      </main>
    </div>
  );
};
