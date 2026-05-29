import React, { useState, useEffect } from 'react';
import { NavLink, Outlet } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import {
  LayoutDashboard, Users, CreditCard, Settings, Ticket, Activity,
  BarChart3, FileText, LogOut, Shield, User, ChevronLeft, ChevronRight
} from 'lucide-react';

const KafLogo: React.FC<{ size?: number }> = ({ size = 20 }) => (
  <svg width={size} height={size} viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
    <rect width="24" height="24" rx="6" fill="#0f172a" />
    <path d="M7 6L14 12L7 18" stroke="#22d3ee" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" />
    <path d="M13 6L20 12L13 18" stroke="#3b82f6" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" />
  </svg>
);

const navItems = [
  { to: '/admin', icon: LayoutDashboard, label: 'Overview', end: true },
  { to: '/admin/users', icon: Users, label: 'Users' },
  { to: '/admin/profile', icon: User, label: 'Profile' },
  { to: '/admin/subscriptions', icon: CreditCard, label: 'Subscriptions' },
  { to: '/admin/vouchers', icon: Ticket, label: 'Vouchers' },
  { to: '/admin/monitor', icon: Activity, label: 'API Monitor' },
  { to: '/admin/features', icon: Shield, label: 'Features' },
  { to: '/admin/analytics', icon: BarChart3, label: 'Analytics' },
  { to: '/admin/payments', icon: Settings, label: 'Payments' },
  { to: '/admin/logs', icon: FileText, label: 'Audit Logs' },
];

export const AdminLayout: React.FC = () => {
  const { user, logout } = useAuth();
  const [collapsed, setCollapsed] = useState(() => {
    try { return JSON.parse(localStorage.getItem('admin_sidebar_collapsed') || 'false'); }
    catch { return false; }
  });

  useEffect(() => {
    localStorage.setItem('admin_sidebar_collapsed', JSON.stringify(collapsed));
  }, [collapsed]);

  if (!user || user.role !== 'admin') {
    return (
      <div className="flex flex-col items-center justify-center h-screen text-slate-400 bg-slate-950 gap-4">
        <Shield size={48} className="text-slate-600" />
        <p className="text-lg">Access Denied — Admin only</p>
        <a href="/dashboard" className="text-blue-400 hover:text-blue-300 text-sm">
          Go to Dashboard
        </a>
      </div>
    );
  }

  return (
    <div className="flex h-screen">
      {/* Sidebar */}
      <aside className={`${collapsed ? 'w-[60px]' : 'w-60'} bg-slate-900 border-r border-slate-800 flex flex-col transition-all duration-300`}>
        <div className={`p-4 border-b border-slate-800 flex items-center gap-2.5 ${collapsed ? 'px-2 justify-center' : ''}`}>
          <KafLogo size={collapsed ? 18 : 22} />
          <div className={`${collapsed ? 'hidden' : 'block'}`}>
            <h1 className="text-lg font-bold text-white tracking-tight leading-none">Kaf Extract</h1>
            <p className="text-[10px] text-cyan-400/80 mt-0.5 font-medium tracking-wide uppercase">Admin Panel</p>
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
                `flex items-center ${collapsed ? 'justify-center' : 'gap-3 px-4'} py-2.5 text-sm transition-colors ${
                  isActive ? 'bg-blue-600/20 text-blue-400 border-r-2 border-blue-500' : 'text-slate-400 hover:text-white hover:bg-slate-800'
                }`
              }
            >
              <item.icon size={18} />
              {!collapsed && item.label}
            </NavLink>
          ))}
        </nav>
        <div className={`p-4 border-t border-slate-800 ${collapsed ? 'px-2' : ''}`}>
          {!collapsed && <div className="text-sm text-slate-300">{user.email}</div>}
          <button
            onClick={logout}
            title="Sign out"
            className={`flex items-center ${collapsed ? 'justify-center' : 'gap-2'} text-xs text-slate-500 hover:text-red-400 mt-1 transition-colors w-full py-2 ${collapsed ? '' : 'px-2'}`}
          >
            <LogOut size={14} />
            {!collapsed && 'Sign out'}
          </button>
        </div>
      </aside>
      {/* Content */}
      <main className="flex-1 overflow-y-auto bg-slate-950 p-6 relative">
        <button
          onClick={() => setCollapsed(!collapsed)}
          className="absolute top-4 left-4 z-20 w-7 h-7 rounded-lg bg-slate-800 border border-slate-700 flex items-center justify-center text-slate-400 hover:text-white hover:border-slate-600 transition-all"
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
