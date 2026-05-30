import React, { useState, useEffect } from 'react';
import { useAuth } from '../contexts/AuthContext';
import {
  User, Lock, Save, AlertTriangle, CheckCircle, Shield,
  Eye, EyeOff, Copy, Download, KeyRound,
} from 'lucide-react';

// ─── 2FA Setup Flow ───
const TwoFactorSetup: React.FC<{ onComplete: () => void; onCancel: () => void }> = ({ onComplete, onCancel }) => {
  const { apiFetch } = useAuth();
  const [step, setStep] = useState<'loading' | 'qr' | 'verify' | 'backup'>('loading');
  const [secret, setSecret] = useState('');
  const [qrDataUri, setQrDataUri] = useState('');
  const [code, setCode] = useState('');
  const [backupCodes, setBackupCodes] = useState<string[]>([]);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const [codesCopied, setCodesCopied] = useState(false);
  const [codesSaved, setCodesSaved] = useState(false);

  useEffect(() => {
    const init = async () => {
      try {
        const data = await apiFetch('/auth/2fa/setup', { method: 'POST' });
        setSecret(data.secret);
        setQrDataUri(data.qr_code_data_uri);
        setStep('qr');
      } catch (err: any) {
        setError(err.message || 'Failed to initialize 2FA setup');
      }
    };
    init();
  }, [apiFetch]);

  const handleVerify = async () => {
    if (code.length !== 6) return;
    setError('');
    setLoading(true);
    try {
      const data = await apiFetch('/auth/2fa/verify', {
        method: 'POST',
        body: JSON.stringify({ secret, code }),
      });
      setBackupCodes(data.backup_codes);
      setStep('backup');
    } catch (err: any) {
      setError(err.message || 'Verification failed');
    } finally {
      setLoading(false);
    }
  };

  const handleCopyCodes = () => {
    navigator.clipboard.writeText(backupCodes.join('\n'));
    setCodesCopied(true);
    setTimeout(() => setCodesCopied(false), 2000);
  };

  const handleDownloadCodes = () => {
    const blob = new Blob(
      [`Kaf Extract — Backup Codes\n\n${backupCodes.join('\n')}\n\nKeep these codes safe. Each code can only be used once.`],
      { type: 'text/plain' }
    );
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'kaf-extract-backup-codes.txt';
    a.click();
    URL.revokeObjectURL(url);
    setCodesSaved(true);
  };

  if (step === 'loading') {
    if (error) {
      return (
        <div className="text-center py-6">
          <AlertTriangle className="mx-auto mb-2 text-red-400" size={24} />
          <p className="text-sm text-red-400">{error}</p>
          <button onClick={onCancel} className="mt-4 px-4 py-2 text-sm text-slate-400 hover:text-white">Close</button>
        </div>
      );
    }
    return (
      <div className="flex items-center justify-center py-8">
        <div className="animate-spin w-6 h-6 border-2 border-blue-500 border-t-transparent rounded-full" />
        <span className="ml-3 text-sm text-slate-400">Generating QR code...</span>
      </div>
    );
  }

  if (step === 'qr') {
    return (
      <div className="space-y-4">
        <p className="text-sm text-slate-400">
          Scan this QR code with your authenticator app (Google Authenticator, Authy, etc.):
        </p>
        <div className="flex justify-center p-4 bg-white rounded-lg">
          <img src={qrDataUri} alt="2FA QR Code" className="w-48 h-48" />
        </div>
        <div className="bg-slate-800 rounded-lg p-3">
          <p className="text-xs text-slate-500 mb-1">Manual entry key:</p>
          <p className="font-mono text-sm text-amber-400 break-all select-all">{secret}</p>
        </div>
        {error && (
          <div className="flex items-center gap-2 p-3 bg-red-500/10 border border-red-500/20 rounded-lg text-red-400 text-sm">
            <AlertTriangle size={14} /> {error}
          </div>
        )}
        <div>
          <label className="block text-xs text-slate-500 mb-1">Enter the 6-digit code from your app:</label>
          <input
            type="text"
            value={code}
            onChange={e => setCode(e.target.value.replace(/\D/g, '').slice(0, 6))}
            placeholder="000000"
            className="w-full p-3 bg-slate-800 border border-slate-700 rounded-lg text-white text-center text-xl tracking-[0.5em] font-mono focus:outline-none focus:border-blue-600"
            maxLength={6}
            autoFocus
          />
        </div>
        <div className="flex justify-end gap-2">
          <button onClick={onCancel} className="px-4 py-2 text-sm text-slate-400 hover:text-white">Cancel</button>
          <button
            onClick={handleVerify}
            disabled={code.length !== 6 || loading}
            className="px-4 py-2 text-sm font-medium text-white bg-blue-600 rounded-lg hover:bg-blue-500 disabled:opacity-50"
          >
            {loading ? 'Verifying...' : 'Verify & Enable'}
          </button>
        </div>
      </div>
    );
  }

  // step === 'backup'
  return (
    <div className="space-y-4">
      <div className="flex items-center gap-2 p-3 bg-emerald-500/10 border border-emerald-500/20 rounded-lg text-emerald-400 text-sm">
        <CheckCircle size={16} /> 2FA has been enabled successfully!
      </div>

      <p className="text-sm text-slate-400">
        Save these backup codes in a secure location. Each code can only be used once if you lose access to your authenticator app.
      </p>

      <div className="bg-slate-800 rounded-lg p-4">
        <div className="grid grid-cols-2 gap-2">
          {backupCodes.map((c, i) => (
            <span key={i} className="font-mono text-sm text-amber-400 tracking-wider">{c}</span>
          ))}
        </div>
      </div>

      <div className="flex gap-2">
        <button
          onClick={handleCopyCodes}
          className="flex items-center gap-2 px-3 py-2 text-sm text-slate-400 hover:text-white bg-slate-800 rounded-lg transition-colors"
        >
          <Copy size={14} /> {codesCopied ? 'Copied!' : 'Copy'}
        </button>
        <button
          onClick={handleDownloadCodes}
          className="flex items-center gap-2 px-3 py-2 text-sm text-slate-400 hover:text-white bg-slate-800 rounded-lg transition-colors"
        >
          <Download size={14} /> {codesSaved ? 'Saved!' : 'Download'}
        </button>
      </div>

      <div className="flex justify-end pt-2">
        <button
          onClick={onComplete}
          disabled={!codesSaved && !codesCopied}
          className="px-4 py-2 text-sm font-medium text-white bg-blue-600 rounded-lg hover:bg-blue-500 disabled:opacity-50"
        >
          Done
        </button>
      </div>
    </div>
  );
};

// ─── 2FA Disable Flow ───
const TwoFactorDisable: React.FC<{ onComplete: () => void; onCancel: () => void }> = ({ onComplete, onCancel }) => {
  const { apiFetch } = useAuth();
  const [password, setPassword] = useState('');
  const [code, setCode] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const handleDisable = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setLoading(true);
    try {
      await apiFetch('/auth/2fa/disable', {
        method: 'POST',
        body: JSON.stringify({ password, code }),
      });
      onComplete();
    } catch (err: any) {
      setError(err.message || 'Failed to disable 2FA');
    } finally {
      setLoading(false);
    }
  };

  return (
    <form onSubmit={handleDisable} className="space-y-4">
      <p className="text-sm text-slate-400">
        To disable 2FA, enter your current password and a valid TOTP code.
      </p>

      {error && (
        <div className="flex items-center gap-2 p-3 bg-red-500/10 border border-red-500/20 rounded-lg text-red-400 text-sm">
          <AlertTriangle size={14} /> {error}
        </div>
      )}

      <div>
        <label className="block text-xs text-slate-500 mb-1">Current Password</label>
        <div className="relative">
          <input
            type={showPassword ? 'text' : 'password'}
            value={password}
            onChange={e => setPassword(e.target.value)}
            className="w-full p-3 pr-10 bg-slate-800 border border-slate-700 rounded-lg text-white text-sm focus:outline-none focus:border-blue-600"
            required
          />
          <button type="button" onClick={() => setShowPassword(!showPassword)} className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-500">
            {showPassword ? <EyeOff size={14} /> : <Eye size={14} />}
          </button>
        </div>
      </div>

      <div>
        <label className="block text-xs text-slate-500 mb-1">TOTP Code</label>
        <input
          type="text"
          value={code}
          onChange={e => setCode(e.target.value.replace(/\D/g, '').slice(0, 6))}
          placeholder="000000"
          className="w-full p-3 bg-slate-800 border border-slate-700 rounded-lg text-white text-center text-xl tracking-[0.5em] font-mono focus:outline-none focus:border-blue-600"
          maxLength={6}
          required
        />
      </div>

      <div className="flex justify-end gap-2">
        <button type="button" onClick={onCancel} className="px-4 py-2 text-sm text-slate-400 hover:text-white">Cancel</button>
        <button
          type="submit"
          disabled={loading || code.length !== 6 || !password}
          className="px-4 py-2 text-sm font-medium text-white bg-red-600 rounded-lg hover:bg-red-500 disabled:opacity-50"
        >
          {loading ? 'Disabling...' : 'Disable 2FA'}
        </button>
      </div>
    </form>
  );
};

// ─── Main Profile Page ───
export const ProfilePage: React.FC = () => {
  const { user, apiFetch } = useAuth();

  // Password change state
  const [currentPassword, setCurrentPassword] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [pwError, setPwError] = useState('');
  const [pwSuccess, setPwSuccess] = useState('');
  const [pwLoading, setPwLoading] = useState(false);

  // Profile update state
  const [name, setName] = useState(user?.name || '');
  const [profileError, setProfileError] = useState('');
  const [profileSuccess, setProfileSuccess] = useState('');
  const [profileLoading, setProfileLoading] = useState(false);

  // 2FA state
  const [twoFAEnabled, setTwoFAEnabled] = useState(user?.totp_enabled || false);
  const [twoFAMode, setTwoFAMode] = useState<'idle' | 'setup' | 'disable'>('idle');

  // Refresh 2FA status on mount
  useEffect(() => {
    const check2FA = async () => {
      try {
        const me = await apiFetch('/auth/me');
        setTwoFAEnabled(me.totp_enabled || false);
      } catch {}
    };
    check2FA();
  }, [apiFetch]);

  const handlePasswordChange = async (e: React.FormEvent) => {
    e.preventDefault();
    setPwError('');
    setPwSuccess('');

    if (newPassword !== confirmPassword) {
      setPwError('New passwords do not match');
      return;
    }
    if (newPassword.length < 8) {
      setPwError('Password must be at least 8 characters');
      return;
    }

    setPwLoading(true);
    try {
      await apiFetch('/auth/me/password', {
        method: 'PUT',
        body: JSON.stringify({ current_password: currentPassword, new_password: newPassword }),
      });
      setPwSuccess('Password changed successfully');
      setCurrentPassword('');
      setNewPassword('');
      setConfirmPassword('');
    } catch (err: any) {
      setPwError(err.message);
    } finally {
      setPwLoading(false);
    }
  };

  const handleProfileUpdate = async (e: React.FormEvent) => {
    e.preventDefault();
    setProfileError('');
    setProfileSuccess('');

    setProfileLoading(true);
    try {
      await apiFetch('/auth/me/profile', {
        method: 'PUT',
        body: JSON.stringify({ name: name || null }),
      });
      setProfileSuccess('Profile updated');
    } catch (err: any) {
      setProfileError(err.message);
    } finally {
      setProfileLoading(false);
    }
  };

  return (
    <div className="max-w-2xl space-y-8">
      <div>
        <h2 className="text-xl font-bold text-white">Profile Settings</h2>
        <p className="text-slate-500 text-sm mt-1">Manage your account details and security</p>
      </div>

      {/* Account Info */}
      <div className="bg-slate-900 border border-slate-800 rounded-xl p-6">
        <div className="flex items-center gap-3 mb-6">
          <User size={20} className="text-blue-400" />
          <h3 className="text-lg font-semibold text-white">Account Information</h3>
        </div>
        <div className="grid grid-cols-2 gap-4 text-sm">
          <div>
            <p className="text-slate-500 mb-1">Email</p>
            <p className="text-white font-medium">{user?.email}</p>
          </div>
          <div>
            <p className="text-slate-500 mb-1">Role</p>
            <p className="text-white font-medium capitalize">{user?.role}</p>
          </div>
          <div>
            <p className="text-slate-500 mb-1">Status</p>
            <span className="inline-block px-2 py-0.5 bg-emerald-900/30 text-emerald-400 border border-emerald-800 rounded text-xs font-medium capitalize">
              {user?.status}
            </span>
          </div>
        </div>

        {/* Name Update */}
        <form onSubmit={handleProfileUpdate} className="mt-6 pt-6 border-t border-slate-800">
          {profileError && (
            <div className="bg-red-900/30 border border-red-800 text-red-400 p-3 rounded-lg mb-4 text-sm flex items-center gap-2">
              <AlertTriangle size={16} /> {profileError}
            </div>
          )}
          {profileSuccess && (
            <div className="bg-emerald-900/30 border border-emerald-800 text-emerald-400 p-3 rounded-lg mb-4 text-sm flex items-center gap-2">
              <CheckCircle size={16} /> {profileSuccess}
            </div>
          )}
          <label className="block text-sm text-slate-400 mb-2">Display Name</label>
          <div className="flex gap-3">
            <input
              type="text"
              value={name}
              onChange={e => setName(e.target.value)}
              placeholder="Your name"
              className="flex-1 p-3 bg-slate-800 border border-slate-700 rounded-lg text-white focus:outline-none focus:border-blue-600 text-sm"
            />
            <button
              type="submit"
              disabled={profileLoading || name === user?.name}
              className="px-4 py-2 bg-blue-600 hover:bg-blue-700 disabled:opacity-40 text-white rounded-lg text-sm font-medium transition-colors flex items-center gap-2"
            >
              <Save size={16} />
              {profileLoading ? 'Saving...' : 'Save'}
            </button>
          </div>
        </form>
      </div>

      {/* Password Change */}
      <div className="bg-slate-900 border border-slate-800 rounded-xl p-6">
        <div className="flex items-center gap-3 mb-6">
          <Lock size={20} className="text-blue-400" />
          <h3 className="text-lg font-semibold text-white">Change Password</h3>
        </div>

        {pwError && (
          <div className="bg-red-900/30 border border-red-800 text-red-400 p-3 rounded-lg mb-4 text-sm flex items-center gap-2">
            <AlertTriangle size={16} /> {pwError}
          </div>
        )}
        {pwSuccess && (
          <div className="bg-emerald-900/30 border border-emerald-800 text-emerald-400 p-3 rounded-lg mb-4 text-sm flex items-center gap-2">
            <CheckCircle size={16} /> {pwSuccess}
          </div>
        )}

        <form onSubmit={handlePasswordChange} className="space-y-4">
          <div>
            <label className="block text-sm text-slate-400 mb-2">Current Password</label>
            <input
              type="password"
              value={currentPassword}
              onChange={e => setCurrentPassword(e.target.value)}
              className="w-full p-3 bg-slate-800 border border-slate-700 rounded-lg text-white focus:outline-none focus:border-blue-600 text-sm"
              required
            />
          </div>
          <div>
            <label className="block text-sm text-slate-400 mb-2">New Password</label>
            <input
              type="password"
              value={newPassword}
              onChange={e => setNewPassword(e.target.value)}
              className="w-full p-3 bg-slate-800 border border-slate-700 rounded-lg text-white focus:outline-none focus:border-blue-600 text-sm"
              required
              minLength={8}
            />
          </div>
          <div>
            <label className="block text-sm text-slate-400 mb-2">Confirm New Password</label>
            <input
              type="password"
              value={confirmPassword}
              onChange={e => setConfirmPassword(e.target.value)}
              className="w-full p-3 bg-slate-800 border border-slate-700 rounded-lg text-white focus:outline-none focus:border-blue-600 text-sm"
              required
            />
          </div>
          <button
            type="submit"
            disabled={pwLoading}
            className="px-6 py-2.5 bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white rounded-lg text-sm font-medium transition-colors flex items-center gap-2"
          >
            <Lock size={16} />
            {pwLoading ? 'Changing...' : 'Change Password'}
          </button>
        </form>
      </div>

      {/* 2FA Section */}
      <div className="bg-slate-900 border border-slate-800 rounded-xl p-6">
        <div className="flex items-center gap-3 mb-4">
          <Shield size={20} className={twoFAEnabled ? 'text-emerald-400' : 'text-amber-400'} />
          <h3 className="text-lg font-semibold text-white">Two-Factor Authentication</h3>
          <span className={`px-2 py-0.5 rounded text-[10px] font-medium border ${
            twoFAEnabled
              ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/30'
              : 'bg-slate-500/10 text-slate-400 border-slate-500/30'
          }`}>
            {twoFAEnabled ? 'Enabled' : 'Disabled'}
          </span>
        </div>

        {twoFAMode === 'idle' && (
          <>
            <p className="text-sm text-slate-500 mb-4">
              {twoFAEnabled
                ? 'Your account is protected with TOTP-based two-factor authentication. You\'ll need your authenticator app to sign in.'
                : 'Add an extra layer of security to your admin account with TOTP-based 2FA. Once enabled, you\'ll need a code from your authenticator app each time you sign in.'}
            </p>
            <div className={`rounded-lg p-4 border ${twoFAEnabled ? 'bg-emerald-500/5 border-emerald-500/20' : 'bg-slate-800/50 border-slate-700/50'}`}>
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <div className={`w-2 h-2 rounded-full ${twoFAEnabled ? 'bg-emerald-400' : 'bg-slate-600'}`} />
                  <p className="text-sm text-slate-400">
                    Status: <span className={twoFAEnabled ? 'text-emerald-400' : 'text-slate-500'}>
                      {twoFAEnabled ? 'Active' : 'Not configured'}
                    </span>
                  </p>
                </div>
                <button
                  onClick={() => setTwoFAMode(twoFAEnabled ? 'disable' : 'setup')}
                  className={`px-4 py-2 text-sm font-medium rounded-lg transition-colors ${
                    twoFAEnabled
                      ? 'text-red-400 bg-red-500/10 hover:bg-red-500/20'
                      : 'text-white bg-blue-600 hover:bg-blue-500'
                  }`}
                >
                  {twoFAEnabled ? 'Disable 2FA' : 'Enable 2FA'}
                </button>
              </div>
            </div>
          </>
        )}

        {twoFAMode === 'setup' && (
          <TwoFactorSetup
            onComplete={() => {
              setTwoFAEnabled(true);
              setTwoFAMode('idle');
            }}
            onCancel={() => setTwoFAMode('idle')}
          />
        )}

        {twoFAMode === 'disable' && (
          <TwoFactorDisable
            onComplete={() => {
              setTwoFAEnabled(false);
              setTwoFAMode('idle');
            }}
            onCancel={() => setTwoFAMode('idle')}
          />
        )}
      </div>
    </div>
  );
};
