import React from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { AuthProvider, useAuth } from './contexts/AuthContext';
import { AdminLayout } from './components/AdminLayout';
import { LoginPage } from './pages/LoginPage';
import { OverviewPage } from './pages/OverviewPage';
import { UsersPage } from './pages/UsersPage';
import { ProfilePage } from './pages/ProfilePage';
import { SubscriptionsPage } from './pages/SubscriptionsPage';
import { VouchersPage } from './pages/VouchersPage';
import { PaymentsPage } from './pages/PaymentsPage';
import { AnalyticsPage } from './pages/AnalyticsPage';
import { MonitorPage } from './pages/MonitorPage';
import { AuditLogsPage } from './pages/AuditLogsPage';

const ProtectedRoute = ({ children }: { children: React.ReactNode }) => {
  const { user, loading } = useAuth();
  if (loading && !user) {
    return (
      <div className="flex items-center justify-center h-screen text-slate-400 bg-slate-950">
        Loading admin...
      </div>
    );
  }
  if (!user) return <Navigate to="/admin/login" />;
  return <>{children}</>;
};

const App = () => (
  <BrowserRouter>
    <AuthProvider>
      <Routes>
        <Route path="/admin/login" element={<LoginPage />} />
        <Route
          path="/admin"
          element={
            <ProtectedRoute>
              <AdminLayout />
            </ProtectedRoute>
          }
        >
          <Route index element={<OverviewPage />} />
          <Route path="users" element={<UsersPage />} />
          <Route path="profile" element={<ProfilePage />} />
          <Route path="subscriptions" element={<SubscriptionsPage />} />
          <Route path="vouchers" element={<VouchersPage />} />
          <Route path="payments" element={<PaymentsPage />} />
          <Route path="analytics" element={<AnalyticsPage />} />
          <Route path="monitor" element={<MonitorPage />} />
          <Route path="audit-logs" element={<AuditLogsPage />} />
        </Route>
        <Route path="*" element={<Navigate to="/admin" />} />
      </Routes>
    </AuthProvider>
  </BrowserRouter>
);

export default App;
