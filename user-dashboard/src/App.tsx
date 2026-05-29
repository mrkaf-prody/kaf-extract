import React from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { AuthProvider, useAuth } from './contexts/AuthContext';
import { DashboardLayout } from './components/DashboardLayout';
import { LoginPage } from './pages/LoginPage';
import { RegisterPage } from './pages/RegisterPage';
import { OverviewPage } from './pages/OverviewPage';
import { ApiKeysPage } from './pages/ApiKeysPage';
import { UsagePage } from './pages/UsagePage';
import { BillingPage } from './pages/BillingPage';

const ProtectedRoute = ({ children }: { children: React.ReactNode }) => {
  const { user, loading } = useAuth();
  // Show cached user immediately, don't block if we have data
  if (loading && !user) {
    return (
      <div className="flex items-center justify-center h-screen text-[#9a9aae] bg-[#06060a]">
        <div className="w-8 h-8 border-2 border-[#00d4a0] border-t-transparent rounded-full animate-spin mr-3"></div>
        Loading...
      </div>
    );
  }
  if (!user) return <Navigate to="/dashboard/login" />;
  return <>{children}</>;
};

const App = () => (
  <BrowserRouter>
    <AuthProvider>
      <Routes>
        <Route path="/dashboard/login" element={<LoginPage />} />
        <Route path="/dashboard/register" element={<RegisterPage />} />
        <Route
          path="/dashboard"
          element={
            <ProtectedRoute>
              <DashboardLayout />
            </ProtectedRoute>
          }
        >
          <Route index element={<OverviewPage />} />
          <Route path="keys" element={<ApiKeysPage />} />
          <Route path="usage" element={<UsagePage />} />
          <Route path="billing" element={<BillingPage />} />
        </Route>
        <Route path="*" element={<Navigate to="/dashboard" />} />
      </Routes>
    </AuthProvider>
  </BrowserRouter>
);

export default App;
