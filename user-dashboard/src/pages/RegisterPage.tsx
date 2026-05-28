import React, { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { Zap, UserPlus, Eye, EyeOff } from 'lucide-react';

export const RegisterPage: React.FC = () => {
  const { login } = useAuth();
  const navigate = useNavigate();
  const [name, setName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [totpEnabled, setTotpEnabled] = useState(false);
  const [showPassword, setShowPassword] = useState(false);
  const [showConfirm, setShowConfirm] = useState(false);
  const [error, setError] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [registered, setRegistered] = useState(false);
  const [totpData, setTotpData] = useState<{ secret: string; uri: string } | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');

    if (password !== confirmPassword) {
      setError('Passwords do not match');
      return;
    }
    if (password.length < 8) {
      setError('Password must be at least 8 characters');
      return;
    }

    setSubmitting(true);
    try {
      const res = await fetch('https://extract.kafcenter.com/auth/register', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          name: name || undefined,
          email,
          password,
          confirm_password: confirmPassword,
          totp_enabled: totpEnabled,
        }),
      });
      const data = await res.json();
      if (!res.ok) {
        throw new Error(data.detail || 'Registration failed');
      }

      // Store tokens
      localStorage.setItem('access_token', data.access_token);
      localStorage.setItem('refresh_token', data.refresh_token);

      // If TOTP was requested, show setup
      if (data.totp_required && data.totp_setup) {
        setTotpData({
          secret: data.totp_setup.secret,
          uri: data.totp_setup.provisioning_uri,
        });
        setRegistered(true);
      } else {
        // Auto-login
        await login(email, password);
        navigate('/dashboard');
      }
    } catch (err: any) {
      setError(err.message || 'Registration failed');
    } finally {
      setSubmitting(false);
    }
  };

  // Post-TOTP verification
  const [totpCode, setTotpCode] = useState('');
  const [verifyingTotp, setVerifyingTotp] = useState(false);

  const verifyTotp = async () => {
    if (!totpCode || totpCode.length !== 6) return;
    setVerifyingTotp(true);
    setError('');
    try {
      const res = await fetch('https://extract.kafcenter.com/auth/totp/verify', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${localStorage.getItem('access_token')}`,
        },
        body: JSON.stringify({ code: totpCode }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || 'Invalid code');
      await login(email, password);
      navigate('/dashboard');
    } catch (err: any) {
      setError(err.message);
    } finally {
      setVerifyingTotp(false);
    }
  };

  // TOTP setup screen
  if (registered && totpData) {
    return (
      <div className="flex flex-col items-center justify-center min-h-screen bg-slate-950">
        <div className="w-full max-w-md p-8">
          <div className="flex flex-col items-center mb-8">
            <Zap size={48} className="text-blue-400 mb-3" />
            <h1 className="text-2xl font-bold text-white">Two-Factor Setup</h1>
            <p className="text-slate-400 text-sm mt-1">Scan with your authenticator app</p>
          </div>

          <div className="bg-slate-900 border border-slate-800 rounded-lg p-6 space-y-4 text-center">
            {/* QR Code placeholder – generate with qrcode library or API */}
            <div className="bg-white p-4 rounded-lg inline-block">
              {/* Using a simple data URI pattern for a QR code via API */}
              <img
                src={`https://api.qrserver.com/v1/create-qr-code/?size=200x200&data=${encodeURIComponent(totpData.uri)}`}
                alt="TOTP QR Code"
                className="w-48 h-48 mx-auto"
              />
            </div>

            <div className="text-sm">
              <p className="text-slate-400 mb-2">Or enter this secret manually:</p>
              <code className="bg-slate-800 px-3 py-1.5 rounded text-emerald-400 text-xs font-mono break-all">
                {totpData.secret}
              </code>
            </div>

            <div className="pt-4 border-t border-slate-800">
              <label className="block text-sm text-slate-400 mb-2 text-left">
                Enter 6-digit code from app
              </label>
              <input
                type="text"
                value={totpCode}
                onChange={e => setTotpCode(e.target.value.replace(/\D/g, '').slice(0, 6))}
                maxLength={6}
                className="w-full bg-slate-800 border border-slate-700 rounded px-3 py-2 text-white text-sm
                           text-center text-lg tracking-[0.5em] focus:outline-none focus:border-blue-500 transition-colors"
                placeholder="000000"
              />
              {error && (
                <div className="mt-3 bg-red-500/10 border border-red-500/30 rounded p-3 text-sm text-red-400 text-left">
                  {error}
                </div>
              )}
              <button
                onClick={verifyTotp}
                disabled={verifyingTotp || totpCode.length !== 6}
                className="w-full mt-4 bg-blue-600 hover:bg-blue-700 disabled:bg-blue-800 disabled:cursor-not-allowed
                           text-white rounded px-4 py-2.5 text-sm font-medium transition-colors flex items-center justify-center gap-2"
              >
                {verifyingTotp ? 'Verifying...' : 'Verify & Continue'}
              </button>
            </div>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="flex flex-col items-center justify-center min-h-screen bg-slate-950">
      <div className="w-full max-w-md p-8">
        <div className="flex flex-col items-center mb-8">
          <Zap size={48} className="text-blue-400 mb-3" />
          <h1 className="text-2xl font-bold text-white">Kaf Extract</h1>
          <p className="text-slate-400 text-sm mt-1">Create your account</p>
        </div>

        <form onSubmit={handleSubmit} className="bg-slate-900 border border-slate-800 rounded-lg p-6 space-y-4">
          {error && (
            <div className="bg-red-500/10 border border-red-500/30 rounded p-3 text-sm text-red-400">
              {error}
            </div>
          )}

          <div>
            <label className="block text-sm text-slate-400 mb-1">Full Name <span className="text-slate-600">(optional)</span></label>
            <input
              type="text"
              value={name}
              onChange={e => setName(e.target.value)}
              className="w-full bg-slate-800 border border-slate-700 rounded px-3 py-2 text-white text-sm
                         focus:outline-none focus:border-blue-500 transition-colors"
              placeholder="John Doe"
            />
          </div>

          <div>
            <label className="block text-sm text-slate-400 mb-1">Email</label>
            <input
              type="email"
              value={email}
              onChange={e => setEmail(e.target.value)}
              required
              className="w-full bg-slate-800 border border-slate-700 rounded px-3 py-2 text-white text-sm
                         focus:outline-none focus:border-blue-500 transition-colors"
              placeholder="you@example.com"
            />
          </div>

          <div>
            <label className="block text-sm text-slate-400 mb-1">Password</label>
            <div className="relative">
              <input
                type={showPassword ? 'text' : 'password'}
                value={password}
                onChange={e => setPassword(e.target.value)}
                required
                minLength={8}
                className="w-full bg-slate-800 border border-slate-700 rounded px-3 py-2 pr-10 text-white text-sm
                           focus:outline-none focus:border-blue-500 transition-colors"
                placeholder="Min 8 characters"
              />
              <button
                type="button"
                onClick={() => setShowPassword(!showPassword)}
                className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-500 hover:text-slate-300"
              >
                {showPassword ? <EyeOff size={16} /> : <Eye size={16} />}
              </button>
            </div>
          </div>

          <div>
            <label className="block text-sm text-slate-400 mb-1">Confirm Password</label>
            <div className="relative">
              <input
                type={showConfirm ? 'text' : 'password'}
                value={confirmPassword}
                onChange={e => setConfirmPassword(e.target.value)}
                required
                className="w-full bg-slate-800 border border-slate-700 rounded px-3 py-2 pr-10 text-white text-sm
                           focus:outline-none focus:border-blue-500 transition-colors"
                placeholder="Repeat password"
              />
              <button
                type="button"
                onClick={() => setShowConfirm(!showConfirm)}
                className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-500 hover:text-slate-300"
              >
                {showConfirm ? <EyeOff size={16} /> : <Eye size={16} />}
              </button>
            </div>
          </div>

          <label className="flex items-center gap-2 cursor-pointer">
            <input
              type="checkbox"
              checked={totpEnabled}
              onChange={e => setTotpEnabled(e.target.checked)}
              className="w-4 h-4 rounded border-slate-600 bg-slate-800 text-blue-500 focus:ring-blue-500/20"
            />
            <span className="text-sm text-slate-300">Enable two-factor authentication (TOTP)</span>
          </label>

          <button
            type="submit"
            disabled={submitting}
            className="w-full bg-blue-600 hover:bg-blue-700 disabled:bg-blue-800 disabled:cursor-not-allowed
                       text-white rounded px-4 py-2.5 text-sm font-medium transition-colors flex items-center justify-center gap-2"
          >
            <UserPlus size={16} />
            {submitting ? 'Creating account...' : 'Create Account'}
          </button>

          <p className="text-center text-sm text-slate-500 pt-2">
            Already have an account?{' '}
            <Link to="/dashboard/login" className="text-blue-400 hover:text-blue-300 transition-colors">
              Sign in
            </Link>
          </p>
        </form>
      </div>
    </div>
  );
};
