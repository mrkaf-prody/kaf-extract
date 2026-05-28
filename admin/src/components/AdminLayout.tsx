import React from 'react';
import { NavLink, Outlet } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import {
  LayoutDashboard, Users, CreditCard, Settings, Ticket, Activity,
  BarChart3, FileText, LogOut, Shield, User
} from 'lucide-react';

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
      <aside className="w-60 bg-slate-900 border-r border-slate-800 flex flex-col">
        <div className="p-4 border-b border-slate-800">
          <h1 className="text-lg font-bold text-white">Kaf Extract</h1>
          <p className="text-xs text-slate-500 mt-0.5">Admin Panel</p>
        </div>
        <nav className="flex-1 py-2 overflow-y-auto">
          {navItems.map(item => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.end}
              className={({ isActive }) =>
                `flex items-center gap-3 px-4 py-2.5 text-sm transition-colors ${
                  isActive ? 'bg-blue-600/20 text-blue-400 border-r-2 border-blue-500' : 'text-slate-400 hover:text-white hover:bg-slate-800'
                }`
              }
            >
              <item.icon size={18} />
              {item.label}
            </NavLink>
          ))}
        </nav>
        <div className="p-4 border-t border-slate-800">
          <div className="text-sm text-slate-300">{user.email}</div>
          <button onClick={logout} className="flex items-center gap-2 text-xs text-slate-500 hover:text-red-400 mt-1 transition-colors">
            <LogOut size={14} /> Sign out
          </button>
        </div>
      </aside>
      {/* Content */}
      <main className="flex-1 overflow-y-auto bg-slate-950 p-6">
        <Outlet />
      </main>
    </div>
  );
};
