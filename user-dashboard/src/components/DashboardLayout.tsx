import React from 'react';
import { NavLink, Outlet } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { LayoutDashboard, Key, BarChart3, CreditCard, LogOut, Zap } from 'lucide-react';

const navItems = [
  { to: '/dashboard', icon: LayoutDashboard, label: 'Overview', end: true },
  { to: '/dashboard/keys', icon: Key, label: 'API Keys' },
  { to: '/dashboard/usage', icon: BarChart3, label: 'Usage' },
  { to: '/dashboard/billing', icon: CreditCard, label: 'Billing' },
];

export const DashboardLayout: React.FC = () => {
  const { user, logout } = useAuth();

  return (
    <div className="flex h-screen">
      {/* Sidebar */}
      <aside className="w-60 bg-slate-900 border-r border-slate-800 flex flex-col">
        <div className="p-4 border-b border-slate-800">
          <div className="flex items-center gap-2">
            <Zap size={22} className="text-blue-400" />
            <h1 className="text-lg font-bold text-white">Kaf Extract</h1>
          </div>
          <p className="text-xs text-slate-500 mt-0.5">User Dashboard</p>
        </div>
        <nav className="flex-1 py-2 overflow-y-auto">
          {navItems.map(item => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.end}
              className={({ isActive }) =>
                `flex items-center gap-3 px-4 py-2.5 text-sm transition-colors ${
                  isActive
                    ? 'bg-blue-600/20 text-blue-400 border-r-2 border-blue-500'
                    : 'text-slate-400 hover:text-white hover:bg-slate-800'
                }`
              }
            >
              <item.icon size={18} />
              {item.label}
            </NavLink>
          ))}
        </nav>
        <div className="p-4 border-t border-slate-800">
          <div className="text-sm text-slate-300 truncate">{user?.email}</div>
          <button
            onClick={logout}
            className="flex items-center gap-2 text-xs text-slate-500 hover:text-red-400 mt-1 transition-colors"
          >
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
