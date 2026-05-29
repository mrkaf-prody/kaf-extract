import { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { Zap, LogIn, Loader2, AlertCircle } from 'lucide-react';
export const LoginPage = () => {
  const { login } = useAuth();
  const navigate = useNavigate();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setSubmitting(true);
    try {
      await login(email, password);
      navigate('/dashboard', { replace: true });
    } catch (err: any) {
      setError(err.message || 'Login failed');
    } finally {
      setSubmitting(false);
    }
  };
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
          <p className="text-sm text-[#9a9aae] mt-1">Sign in to your account</p>
        </div>
        <form onSubmit={handleSubmit} className="bg-[#0f0f18] border border-[#1c1c2a] rounded-2xl p-6 space-y-5 shadow-[0_0_40px_rgba(0,0,0,0.3)]">
          {error && (
            <div className="bg-[rgba(255,95,86,0.08)] border border-[rgba(255,95,86,0.2)] rounded-lg p-3 text-sm text-[#ff5f56] flex items-center gap-2">
              <AlertCircle size={14} /><span>{error}</span>
            </div>
          )}
          <div>
            <label className="block text-sm text-[#9a9aae] mb-1.5 font-medium">Email Address</label>
            <input type="email" value={email} onChange={e => setEmail(e.target.value)} required autoFocus
              className="w-full bg-[#14141f] border border-[#1c1c2a] rounded-lg px-4 py-2.5 text-[#f0f0f5] text-sm placeholder:text-[#5c5c70] focus:outline-none focus:border-[#00d4a0] focus:ring-1 focus:ring-[rgba(0,212,160,0.4)] transition-all"
              placeholder="you@example.com" />
          </div>
          <div>
            <label className="block text-sm text-[#9a9aae] mb-1.5 font-medium">Password</label>
            <input type="password" value={password} onChange={e => setPassword(e.target.value)} required
              className="w-full bg-[#14141f] border border-[#1c1c2a] rounded-lg px-4 py-2.5 text-[#f0f0f5] text-sm placeholder:text-[#5c5c70] focus:outline-none focus:border-[#00d4a0] focus:ring-1 focus:ring-[rgba(0,212,160,0.4)] transition-all"
              placeholder="Enter your password" />
          </div>
          <button type="submit" disabled={submitting}
            className="w-full bg-[#00d4a0] hover:bg-[#00e8b0] disabled:opacity-60 disabled:cursor-not-allowed text-[#06060a] rounded-lg px-4 py-2.5 text-sm font-semibold transition-all flex items-center justify-center gap-2 shadow-[0_0_20px_rgba(0,212,160,0.2)]">
            {submitting ? <Loader2 size={18} className="animate-spin" /> : <LogIn size={18} />}
            {submitting ? 'Signing in...' : 'Sign In'}
          </button>
          <p className="text-center text-sm text-[#5c5c70] pt-1">
            Don't have an account? <Link to="/dashboard/register" className="text-[#00d4a0] hover:text-[#00e8b0] transition-colors font-medium">Create one</Link>
          </p>
        </form>
        <p className="text-center text-xs text-[#5c5c70] mt-6">Secured with JWT + optional TOTP 2FA</p>
      </div>
    </div>
  );
};
