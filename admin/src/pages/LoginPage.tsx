import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { Shield, ArrowLeft } from 'lucide-react';

export const LoginPage: React.FC = () => {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [totpCode, setTotpCode] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const [requires2FA, setRequires2FA] = useState(false);
  const { login, loginWith2FA } = useAuth();
  const navigate = useNavigate();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setLoading(true);

    if (requires2FA) {
      // 2FA authentication step
      try {
        await loginWith2FA(email, password, totpCode);
        navigate('/admin');
      } catch (err: any) {
        setError(err.message || 'Invalid 2FA code');
      } finally {
        setLoading(false);
      }
      return;
    }

    // Normal login step
    try {
      await login(email, password);
      navigate('/admin');
    } catch (err: any) {
      if (err.requires_2fa) {
        setRequires2FA(true);
        setError('');
      } else {
        setError(err.message);
      }
    } finally {
      setLoading(false);
    }
  };

  const handleBack = () => {
    setRequires2FA(false);
    setTotpCode('');
    setError('');
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-slate-950">
      <div className="w-full max-w-md p-8 bg-slate-900 rounded-xl border border-slate-800">
        <h1 className="text-2xl font-bold text-white mb-1">Kaf Extract</h1>
        <p className="text-slate-500 text-sm mb-6">
          {requires2FA ? 'Two-Factor Authentication' : 'Admin Panel — Sign in'}
        </p>

        {error && (
          <div className="bg-red-900/30 border border-red-800 text-red-400 p-3 rounded-lg mb-4 text-sm">
            {error}
          </div>
        )}

        <form onSubmit={handleSubmit}>
          {!requires2FA ? (
            <>
              <input
                type="email"
                placeholder="Email"
                value={email}
                onChange={e => setEmail(e.target.value)}
                className="w-full p-3 bg-slate-800 border border-slate-700 rounded-lg text-white mb-3 focus:outline-none focus:border-blue-600"
                required
                autoFocus
              />
              <input
                type="password"
                placeholder="Password"
                value={password}
                onChange={e => setPassword(e.target.value)}
                className="w-full p-3 bg-slate-800 border border-slate-700 rounded-lg text-white mb-4 focus:outline-none focus:border-blue-600"
                required
              />
              <button
                type="submit"
                disabled={loading}
                className="w-full p-3 bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white rounded-lg font-medium transition-colors"
              >
                {loading ? 'Signing in...' : 'Sign in'}
              </button>
            </>
          ) : (
            <>
              <div className="flex items-center gap-3 p-3 bg-blue-500/10 border border-blue-500/20 rounded-lg mb-4">
                <Shield size={18} className="text-blue-400 flex-shrink-0" />
                <p className="text-sm text-blue-300">
                  Enter the 6-digit code from your authenticator app, or a backup code.
                </p>
              </div>

              <input
                type="text"
                placeholder="000000"
                value={totpCode}
                onChange={e => setTotpCode(e.target.value.replace(/\D/g, '').slice(0, 6))}
                className="w-full p-3 bg-slate-800 border border-slate-700 rounded-lg text-white text-center text-2xl tracking-[0.5em] font-mono mb-4 focus:outline-none focus:border-blue-600"
                required
                autoFocus
                autoComplete="one-time-code"
                maxLength={6}
              />

              <button
                type="submit"
                disabled={loading || (totpCode.length !== 6 && totpCode.length < 8)}
                className="w-full p-3 bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white rounded-lg font-medium transition-colors mb-3"
              >
                {loading ? 'Verifying...' : 'Verify'}
              </button>

              <button
                type="button"
                onClick={handleBack}
                className="flex items-center gap-2 text-sm text-slate-500 hover:text-slate-300 transition-colors mx-auto"
              >
                <ArrowLeft size={14} />
                Back to login
              </button>
            </>
          )}
        </form>
      </div>
    </div>
  );
};
