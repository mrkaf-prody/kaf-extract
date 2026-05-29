import React, { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { Zap, LogIn, Loader2, Eye, EyeOff, Copy, Check, AlertCircle } from 'lucide-react';

export const RegisterPage = () => {
  const { initSession } = useAuth();
  const navigate = useNavigate();

  // Step 1: Registration form
  const [name, setName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [showConfirm, setShowConfirm] = useState(false);
  const [error, setError] = useState('');
  const [submitting, setSubmitting] = useState(false);

  // Step 2: 2FA Setup
  const [step, setStep] = useState<'register' | '2fa'>('register');
  const [totpSecret, setTotpSecret] = useState('');
  const [totpUri, setTotpUri] = useState('');
  const [verifyCode, setVerifyCode] = useState('');
  const [setupError, setSetupError] = useState('');
  const [verifying, setVerifying] = useState(false);
  const [copied, setCopied] = useState(false);

  const API_BASE = 'https://extract.kafcenter.com';

  const handleRegister = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    if (password !== confirmPassword) { setError('Passwords do not match'); return; }
    if (password.length < 8) { setError('Password must be at least 8 characters'); return; }
    setSubmitting(true);
    try {
      const res = await fetch(`${API_BASE}/auth/register`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email, password, name: name || undefined }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || 'Registration failed');

      // Initialize session directly (tokens already available from registration)
      await initSession(data.access_token);

      // Now user is logged in — fetch 2FA setup
      const setupRes = await fetch(`${API_BASE}/auth/2fa/setup`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${data.access_token}` },
      });
      const setupData = await setupRes.json();
      if (setupRes.ok) {
        setTotpSecret(setupData.secret);
        setTotpUri(setupData.qr_code_uri);
        setStep('2fa');
      } else {
        // TOTP already configured or error — just redirect to dashboard
        navigate('/dashboard');
      }
    } catch (err: any) {
      setError(err.message || 'Registration failed');
    } finally {
      setSubmitting(false);
    }
  };

  const handleVerify = async () => {
    if (!verifyCode || verifyCode.length !== 6) { setSetupError('Enter 6 digits'); return; }
    setVerifying(true);
    setSetupError('');
    try {
      const token = localStorage.getItem('access_token') || '';
      const res = await fetch(`${API_BASE}/auth/2fa/verify`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
        body: JSON.stringify({ secret: totpSecret, code: verifyCode }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || 'Invalid code');
      navigate('/dashboard');
    } catch (err: any) {
      setSetupError(err.message);
    } finally {
      setVerifying(false);
    }
  };

  const skip2FA = () => navigate('/dashboard');

  const copySecret = async () => {
    await navigator.clipboard.writeText(totpSecret);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  // ─── STEP 1: Registration ───
  if (step === 'register') {
    return (
      <div className="flex flex-col items-center justify-center min-h-screen bg-[#06060a] relative overflow-hidden">
        <div className="absolute inset-0 opacity-20 pointer-events-none">
          <div className="absolute top-[-10%] right-[-10%] w-[600px] h-[600px] rounded-full blur-[120px] bg-[#00d4a0] animate-pulse" />
          <div className="absolute bottom-[-10%] left-[-10%] w-[500px] h-[500px] rounded-full blur-[120px] bg-[#4494ff] animate-pulse" style={{ animationDelay: '2s' }} />
        </div>
        <div className="w-full max-w-md p-6 animate-reveal">
          <div className="flex flex-col items-center mb-8">
            <div className="w-14 h-14 rounded-2xl bg-[rgba(0,212,160,0.08)] border border-[rgba(0,212,160,0.15)] flex items-center justify-center mb-4 shadow-[0_0_20px_rgba(0,212,160,0.15)]">
              <Zap size={28} className="text-[#00d4a0]" />
            </div>
            <h1 className="text-2xl font-bold text-[#f0f0f5] tracking-tight">Kaf Extract</h1>
            <p className="text-sm text-[#9a9aae] mt-1">Create your account</p>
          </div>

          <form onSubmit={handleRegister} className="bg-[#0f0f18] border border-[#1c1c2a] rounded-2xl p-6 space-y-4 shadow-[0_0_40px_rgba(0,0,0,0.3)]">
            {error && (
              <div className="bg-[rgba(255,95,86,0.08)] border border-[rgba(255,95,86,0.2)] rounded-lg p-3 text-sm text-[#ff5f56] flex items-center gap-2">
                <AlertCircle size={14} /><span>{error}</span>
              </div>
            )}
            <div>
              <label className="block text-sm text-[#9a9aae] mb-1.5 font-medium">Full Name <span className="text-[#5c5c70]">(optional)</span></label>
              <input type="text" value={name} onChange={e => setName(e.target.value)}
                className="w-full bg-[#14141f] border border-[#1c1c2a] rounded-lg px-4 py-2.5 text-[#f0f0f5] text-sm placeholder:text-[#5c5c70] focus:outline-none focus:border-[#00d4a0] focus:ring-1 focus:ring-[rgba(0,212,160,0.4)] transition-all"
                placeholder="John Doe" />
            </div>
            <div>
              <label className="block text-sm text-[#9a9aae] mb-1.5 font-medium">Email Address</label>
              <input type="email" value={email} onChange={e => setEmail(e.target.value)} required
                className="w-full bg-[#14141f] border border-[#1c1c2a] rounded-lg px-4 py-2.5 text-[#f0f0f5] text-sm placeholder:text-[#5c5c70] focus:outline-none focus:border-[#00d4a0] focus:ring-1 focus:ring-[rgba(0,212,160,0.4)] transition-all"
                placeholder="you@example.com" />
            </div>
            <div>
              <label className="block text-sm text-[#9a9aae] mb-1.5 font-medium">Password</label>
              <div className="relative">
                <input type={showPassword ? 'text' : 'password'} value={password} onChange={e => setPassword(e.target.value)} required minLength={8}
                  className="w-full bg-[#14141f] border border-[#1c1c2a] rounded-lg px-4 py-2.5 pr-10 text-[#f0f0f5] text-sm placeholder:text-[#5c5c70] focus:outline-none focus:border-[#00d4a0] focus:ring-1 focus:ring-[rgba(0,212,160,0.4)] transition-all"
                  placeholder="Min 8 characters" />
                <button type="button" onClick={() => setShowPassword(!showPassword)} className="absolute right-3 top-1/2 -translate-y-1/2 text-[#5c5c70] hover:text-[#9a9aae]">
                  {showPassword ? <EyeOff size={16} /> : <Eye size={16} />}
                </button>
              </div>
            </div>
            <div>
              <label className="block text-sm text-[#9a9aae] mb-1.5 font-medium">Confirm Password</label>
              <div className="relative">
                <input type={showConfirm ? 'text' : 'password'} value={confirmPassword} onChange={e => setConfirmPassword(e.target.value)} required
                  className="w-full bg-[#14141f] border border-[#1c1c2a] rounded-lg px-4 py-2.5 pr-10 text-[#f0f0f5] text-sm placeholder:text-[#5c5c70] focus:outline-none focus:border-[#00d4a0] focus:ring-1 focus:ring-[rgba(0,212,160,0.4)] transition-all"
                  placeholder="Repeat password" />
                <button type="button" onClick={() => setShowConfirm(!showConfirm)} className="absolute right-3 top-1/2 -translate-y-1/2 text-[#5c5c70] hover:text-[#9a9aae]">
                  {showConfirm ? <EyeOff size={16} /> : <Eye size={16} />}
                </button>
              </div>
            </div>
            <button type="submit" disabled={submitting}
              className="w-full bg-[#00d4a0] hover:bg-[#00e8b0] disabled:opacity-60 disabled:cursor-not-allowed text-[#06060a] rounded-lg px-4 py-2.5 text-sm font-semibold transition-all flex items-center justify-center gap-2 shadow-[0_0_20px_rgba(0,212,160,0.2)]"
            >
              {submitting ? <Loader2 size={18} className="animate-spin" /> : <LogIn size={18} />}
              {submitting ? 'Creating account...' : 'Create Account'}
            </button>
            <p className="text-center text-sm text-[#5c5c70] pt-1">
              Already have an account? <Link to="/dashboard/login" className="text-[#00d4a0] hover:text-[#00e8b0] transition-colors font-medium">Sign in</Link>
            </p>
          </form>
        </div>
      </div>
    );
  }

  // ─── STEP 2: 2FA Setup ───
  return (
    <div className="flex flex-col items-center justify-center min-h-screen bg-[#06060a] relative overflow-hidden">
      <div className="absolute inset-0 opacity-20 pointer-events-none">
        <div className="absolute top-[-10%] right-[-10%] w-[600px] h-[600px] rounded-full blur-[120px] bg-[#00d4a0] animate-pulse" />
        <div className="absolute bottom-[-10%] left-[-10%] w-[500px] h-[500px] rounded-full blur-[120px] bg-[#4494ff] animate-pulse" style={{ animationDelay: '2s' }} />
      </div>

      <div className="w-full max-w-md p-6 animate-reveal">
        <div className="flex flex-col items-center mb-6">
          <h2 className="text-xl font-bold text-[#f0f0f5] tracking-tight">Two-Factor Authentication</h2>
          <p className="text-sm text-[#9a9aae] mt-1">Set up with your authenticator app</p>
        </div>

        <div className="bg-[#0f0f18] border border-[#1c1c2a] rounded-2xl p-6 space-y-5 shadow-[0_0_40px_rgba(0,0,0,0.3)]">
          {/* QR + Secret */}
          <div className="text-center space-y-4">
            <p className="text-sm text-[#9a9aae]">Scan this QR code with Google Authenticator, Authy, or 1Password</p>
            <div className="bg-white p-3 rounded-xl inline-block shadow-[0_0_20px_rgba(0,0,0,0.3)]">
              <img
                src={`https://api.qrserver.com/v1/create-qr-code/?size=200x200&data=${encodeURIComponent(totpUri)}`}
                alt="TOTP QR Code" className="w-44 h-44"
              />
            </div>

            <div className="text-sm">
              <p className="text-[#9a9aae] mb-2">Or enter this secret key manually</p>
              <div className="flex items-center gap-2 bg-[#14141f] rounded-lg p-3 border border-[#1c1c2a]">
                <code className="text-[#00d4a0] text-xs font-mono flex-1 break-all tracking-wider">{totpSecret}</code>
                <button onClick={copySecret} className="text-[#5c5c70] hover:text-[#00d4a0] transition-colors p-1 rounded">
                  {copied ? <Check size={16} className="text-[#00d4a0]" /> : <Copy size={16} />}
                </button>
              </div>
            </div>
          </div>

          {/* Divider */}
          <div className="border-t border-[#1c1c2a]" />

          {/* Verification code */}
          <div>
            <label className="block text-sm font-medium text-[#9a9aae] mb-2">Enter verification code from app</label>
            <input
              type="text" value={verifyCode}
              onChange={e => setVerifyCode(e.target.value.replace(/\D/g, '').slice(0, 6))}
              maxLength={6}
              className="w-full bg-[#14141f] border border-[#1c1c2a] rounded-lg px-4 py-3 text-[#f0f0f5] text-lg text-center tracking-[0.5em] font-mono
                         placeholder:text-[#5c5c70] focus:outline-none focus:border-[#00d4a0] focus:ring-1 focus:ring-[rgba(0,212,160,0.4)] transition-all"
              placeholder="000000"
            />
            {setupError && (
              <div className="mt-2 bg-[rgba(255,95,86,0.08)] border border-[rgba(255,95,86,0.2)] rounded-lg p-2 text-sm text-[#ff5f56] flex items-center gap-2">
                <AlertCircle size={12} /><span>{setupError}</span>
              </div>
            )}
          </div>

          <div className="flex flex-col gap-3">
            <button onClick={handleVerify} disabled={verifying || verifyCode.length !== 6}
              className="w-full bg-[#00d4a0] hover:bg-[#00e8b0] disabled:opacity-60 disabled:cursor-not-allowed text-[#06060a] rounded-lg px-4 py-2.5 text-sm font-semibold transition-all flex items-center justify-center gap-2 shadow-[0_0_20px_rgba(0,212,160,0.2)]"
            >
              {verifying ? <Loader2 size={18} className="animate-spin" /> : <Check size={18} />}
              {verifying ? 'Verifying...' : 'Verify & Enable 2FA'}
            </button>
            <button onClick={skip2FA}
              className="w-full bg-transparent hover:bg-[#14141f] text-[#5c5c70] hover:text-[#9a9aae] rounded-lg px-4 py-2.5 text-sm font-medium transition-all border border-[#1c1c2a]"
            >
              Skip for now
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};
