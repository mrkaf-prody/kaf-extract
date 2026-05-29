import { NavLink, Outlet } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { useState, useEffect } from 'react';
import {
  LayoutDashboard, Key, BarChart3, CreditCard, LogOut, Zap, User,
  ChevronLeft, ChevronRight
} from 'lucide-react';

const navItems = [
  { to: '/dashboard', icon: LayoutDashboard, label: 'Overview', end: true },
  { to: '/dashboard/keys', icon: Key, label: 'API Keys' },
  { to: '/dashboard/usage', icon: BarChart3, label: 'Usage' },
  { to: '/dashboard/profile', icon: User, label: 'Profile' },
  { to: '/dashboard/billing', icon: CreditCard, label: 'Billing' },
];

export const DashboardLayout = () => {
  const { user, logout } = useAuth();
  const [collapsed, setCollapsed] = useState(() => {
    try { return JSON.parse(localStorage.getItem('sidebar_collapsed') || 'false'); }
    catch { return false; }
  });

  useEffect(() => {
    localStorage.setItem('sidebar_collapsed', JSON.stringify(collapsed));
  }, [collapsed]);

  return (
    <div className="flex h-screen bg-[#06060a]">
      {/* Sidebar */}
      <aside className={`${collapsed ? 'w-[60px]' : 'w-[240px]'} bg-[#0a0a12] border-r border-[#1c1c2a] flex flex-col transition-all duration-300`}>
        <div className={`p-4 border-b border-[#1c1c2a] ${collapsed ? 'px-2' : ''}`}>
          <div className="flex items-center gap-3">
            <div className={`rounded-xl bg-[rgba(0,212,160,0.08)] border border-[rgba(0,212,160,0.15)] flex items-center justify-center ${collapsed ? 'w-9 h-9 mx-auto' : 'w-9 h-9'}`}>
              <Zap size={18} className="text-[#00d4a0]" />
            </div>
            {!collapsed && (
              <div>
                <h1 className="text-base font-bold text-[#f0f0f5] tracking-tight">Kaf Extract</h1>
                <p className="text-[10px] text-[#5c5c70] uppercase tracking-wider">User Dashboard</p>
              </div>
            )}
          </div>
        </div>

        <nav className="flex-1 py-2 overflow-y-auto">
          {navItems.map(item => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.end}
              title={collapsed ? item.label : undefined}
              className={({ isActive }) =>
                `flex items-center ${collapsed ? 'justify-center' : 'gap-3 px-4'} py-2.5 text-sm transition-all ${
                  isActive
                    ? 'bg-[rgba(0,212,160,0.08)] text-[#00d4a0] border-r-2 border-[#00d4a0]'
                    : 'text-[#9a9aae] hover:text-[#f0f0f5] hover:bg-[#14141f]'
                }`
              }
            >
              <item.icon size={18} />
              {!collapsed && item.label}
            </NavLink>
          ))}
        </nav>

        <div className={`p-4 border-t border-[#1c1c2a] ${collapsed ? 'px-2' : ''}`}>
          {!collapsed && (
            <div className="flex items-center gap-3 mb-3">
              <div className="w-8 h-8 rounded-lg bg-[#14141f] border border-[#1c1c2a] flex items-center justify-center">
                <User size={14} className="text-[#9a9aae]" />
              </div>
              <div className="min-w-0">
                <div className="text-sm text-[#f0f0f5] truncate">{user?.name || user?.email}</div>
                <div className="text-[10px] text-[#5c5c70] truncate">{user?.email}</div>
              </div>
            </div>
          )}
          <button
            onClick={logout}
            title="Sign out"
            className={`flex items-center ${collapsed ? 'justify-center' : 'gap-2 px-3'} text-xs text-[#5c5c70] hover:text-[#ff5f56] transition-colors w-full py-2 rounded-lg hover:bg-[rgba(255,95,86,0.05)]`}
          >
            <LogOut size={14} />
            {!collapsed && 'Sign out'}
          </button>
        </div>
      </aside>

      {/* Content */}
      <main className="flex-1 overflow-y-auto bg-[#06060a] p-6 relative">
        {/* Collapse toggle */}
        <button
          onClick={() => setCollapsed(!collapsed)}
          className="absolute top-4 left-4 z-20 w-7 h-7 rounded-lg bg-[#14141f] border border-[#1c1c2a] flex items-center justify-center text-[#9a9aae] hover:text-[#f0f0f5] hover:border-[#2a2a3e] transition-all"
          title={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
        >
          {collapsed ? <ChevronRight size={14} /> : <ChevronLeft size={14} />}
        </button>
        <div className="mt-8">
          <Outlet />
        </div>
      </main>
    </div>
  );
};
