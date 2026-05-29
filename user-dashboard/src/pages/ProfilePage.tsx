import React, { useState, useCallback, useEffect } from 'react';
import { useAuth } from '../contexts/AuthContext';
import { User, Mail, Shield, CheckCircle, Save, Lock, Trash2, X, Smartphone, Copy, Check, AlertCircle } from 'lucide-react';

export const ProfilePage: React.FC = () => {
  const { user, apiFetch, logout, showError, showSuccess } = useAuth();
  const [displayName, setDisplayName] = useState(user?.name || '');
  const [savingName, setSavingName] = useState(false);

  const [currentPassword, setCurrentPassword] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [savingPassword, setSavingPassword] = useState(false);

  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);
  const [deleteConfirmText, setDeleteConfirmText] = useState('');
  const [deleting, setDeleting] = useState(false);

  // 2FA state
  const [showEnable2FA, setShowEnable2FA] = useState(false);
  const [showDisable2FA, setShowDisable2FA] = useState(false);
  const [totpSecret, setTotpSecret] = useState('');
  const [totpUri, setTotpUri] = useState('');
  const [qrDataUri, setQrDataUri] = useState('');
  const [verifyCode, setVerifyCode] = useState('');
  const [disableCode, setDisableCode] = useState('');
  const [disablePassword, setDisablePassword] = useState('');
  const [backupCodes, setBackupCodes] = useState<string[]>([]);
  const [copiedSecret, setCopiedSecret] = useState(false);
  const [loading2FA, setLoading2FA] = useState(false);

  useEffect(() => {
    setDisplayName(user?.name || '');
  }, [user?.name]);

  const handleSaveName = useCallback(async (e: React.FormEvent) => {
    e.preventDefault();
    setSavingName(true);
    try {
      await apiFetch('/auth/me/profile', {
        method: 'PUT',
        body: JSON.stringify({ name: displayName.trim() || null }),
      });
      showSuccess('Display name updated');
    } catch (err: any) {
      showError(err.message || 'Failed to update display name');
    } finally {
      setSavingName(false);
    }
  }, [apiFetch, displayName, showError, showSuccess]);

  const handleChangePassword = useCallback(async (e: React.FormEvent) => {
    e.preventDefault();
    if (newPassword !== confirmPassword) {
      showError('New passwords do not match');
      return;
    }
    setSavingPassword(true);
    try {
      await apiFetch('/auth/me/password', {
        method: 'PUT',
        body: JSON.stringify({ current_password: currentPassword, new_password: newPassword }),
      });
      showSuccess('Password changed successfully');
      setCurrentPassword('');
      setNewPassword('');
      setConfirmPassword('');
    } catch (err: any) {
      showError(err.message || 'Failed to change password');
    } finally {
      setSavingPassword(false);
    }
  }, [apiFetch, currentPassword, newPassword, confirmPassword, showError, showSuccess]);

  const handleDelete = useCallback(async () => {
    if (deleteConfirmText !== 'DELETE') {
      showError('Please type DELETE to confirm');
      return;
    }
    setDeleting(true);
    try {
      await apiFetch('/auth/me', { method: 'DELETE' });
      showSuccess('Account deleted');
      logout();
    } catch (err: any) {
      showError(err.message || 'Failed to delete account');
    } finally {
      setDeleting(false);
    }
  }, [apiFetch, deleteConfirmText, logout, showError, showSuccess]);

  const handleSetup2FA = async () => {
    setLoading2FA(true);
    setBackupCodes([]);
    setVerifyCode('');
    try {
      const data = await apiFetch('/auth/2fa/setup', { method: 'POST' });
      setTotpSecret(data.secret);
      setTotpUri(data.qr_code_uri);
      setQrDataUri(data.qr_code_data_uri || '');
      setShowEnable2FA(true);
    } catch (err: any) {
      showError(err.message || 'Failed to start 2FA setup');
    } finally {
      setLoading2FA(false);
    }
  };

  const handleVerify2FA = async () => {
    if (!verifyCode || verifyCode.length !== 6) { showError('Enter 6 digits'); return; }
    setLoading2FA(true);
    try {
      const data = await apiFetch('/auth/2fa/verify', {
        method: 'POST',
        body: JSON.stringify({ secret: totpSecret, code: verifyCode }),
      });
      showSuccess(data.message || '2FA enabled');
      setBackupCodes(data.backup_codes || []);
      setShowEnable2FA(false);
      // Refresh user info
      const me = await apiFetch('/auth/me');
      if (me) {
        // Update cached user via localStorage
        localStorage.setItem('user_cache', JSON.stringify(me));
      }
    } catch (err: any) {
      showError(err.message || 'Invalid code');
    } finally {
      setLoading2FA(false);
    }
  };

  const handleDisable2FA = async () => {
    if (!disableCode || disableCode.length !== 6) { showError('Enter 6 digits'); return; }
    if (!disablePassword) { showError('Enter your password'); return; }
    setLoading2FA(true);
    try {
      await apiFetch('/auth/2fa/disable', {
        method: 'POST',
        body: JSON.stringify({ password: disablePassword, code: disableCode }),
      });
      showSuccess('2FA disabled');
      setShowDisable2FA(false);
      setDisableCode('');
      setDisablePassword('');
      const me = await apiFetch('/auth/me');
      if (me) localStorage.setItem('user_cache', JSON.stringify(me));
    } catch (err: any) {
      showError(err.message || 'Failed to disable 2FA');
    } finally {
      setLoading2FA(false);
    }
  };

  const copySecret = async () => {
    await navigator.clipboard.writeText(totpSecret);
    setCopiedSecret(true);
    setTimeout(() => setCopiedSecret(false), 2000);
  };

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold text-[#f0f0f5] mb-1">Profile</h2>
        <p className="text-sm text-[#9a9aae]">Manage your account settings and preferences.</p>
      </div>

      {/* Account Info */}
      <div className="bg-[#0f0f18] border border-[#1c1c2a] rounded-xl p-5">
        <h3 className="text-lg font-semibold text-[#f0f0f5] mb-4 flex items-center gap-2">
          <User size={18} className="text-[#4494ff]" />
          Account Information
        </h3>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-[rgba(68,148,255,0.08)] rounded-lg">
              <Mail size={16} className="text-[#4494ff]" />
            </div>
            <div>
              <div className="text-xs text-[#5c5c70]">Email</div>
              <div className="text-sm text-[#f0f0f5]">{user?.email}</div>
            </div>
          </div>
          <div className="flex items-center gap-3">
            <div className="p-2 bg-[rgba(0,212,160,0.08)] rounded-lg">
              <Shield size={16} className="text-[#00d4a0]" />
            </div>
            <div>
              <div className="text-xs text-[#5c5c70]">Role</div>
              <div className="text-sm text-[#f0f0f5] capitalize">{user?.role}</div>
            </div>
          </div>
          <div className="flex items-center gap-3">
            <div className="p-2 bg-[rgba(255,189,46,0.08)] rounded-lg">
              <CheckCircle size={16} className="text-[#ffbd2e]" />
            </div>
            <div>
              <div className="text-xs text-[#5c5c70]">Status</div>
              <div className="text-sm text-[#f0f0f5] capitalize">{user?.status}</div>
            </div>
          </div>
          <div className="flex items-center gap-3">
            <div className="p-2 bg-[rgba(200,200,255,0.08)] rounded-lg">
              <Smartphone size={16} className={user?.totp_enabled ? 'text-[#00d4a0]' : 'text-[#9a9aae]'} />
            </div>
            <div>
              <div className="text-xs text-[#5c5c70]">2FA</div>
              <div className={`text-sm font-medium ${user?.totp_enabled ? 'text-[#00d4a0]' : 'text-[#9a9aae]'}`}>
                {user?.totp_enabled ? 'Enabled' : 'Disabled'}
              </div>
            </div>
          </div>
          <div className="flex items-center gap-3">
            <div className="p-2 bg-[rgba(200,200,255,0.08)] rounded-lg">
              <User size={16} className="text-[#9a9aae]" />
            </div>
            <div>
              <div className="text-xs text-[#5c5c70]">Created</div>
              <div className="text-sm text-[#f0f0f5]">
                {user?.created_at ? new Date(user.created_at).toLocaleDateString() : '—'}
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Two-Factor Authentication */}
      <div className="bg-[#0f0f18] border border-[#1c1c2a] rounded-xl p-5">
        <h3 className="text-lg font-semibold text-[#f0f0f5] mb-4 flex items-center gap-2">
          <Smartphone size={18} className="text-[#4494ff]" />
          Two-Factor Authentication
        </h3>
        {!user?.totp_enabled ? (
          <div className="space-y-4">
            <p className="text-sm text-[#9a9aae]">
              Protect your account with an authenticator app. Recommended for admin users.
            </p>
            <button
              onClick={handleSetup2FA}
              disabled={loading2FA}
              className="flex items-center gap-2 bg-[#00d4a0] hover:bg-[#00b88c] disabled:bg-[#004d3a] disabled:cursor-not-allowed text-[#06060a] rounded-lg px-4 py-2 text-sm font-medium transition-colors"
            >
              <Smartphone size={16} />
              {loading2FA ? 'Loading...' : 'Enable 2FA'}
            </button>

            {showEnable2FA && (
              <div className="mt-4 space-y-4 border-t border-[#1c1c2a] pt-4">
                <div className="text-center space-y-3">
                  <p className="text-sm text-[#9a9aae]">Scan this QR code with your authenticator app</p>
                  {qrDataUri ? (
                    <div className="bg-white p-3 rounded-xl inline-block">
                      <img src={qrDataUri} alt="TOTP QR" className="w-40 h-40" />
                    </div>
                  ) : (
                    <div className="bg-white p-3 rounded-xl inline-block">
                      <img
                        src={`https://api.qrserver.com/v1/create-qr-code/?size=200x200&data=${encodeURIComponent(totpUri)}`}
                        alt="TOTP QR" className="w-40 h-40"
                      />
                    </div>
                  )}
                  <div className="text-sm">
                    <p className="text-[#9a9aae] mb-2">Or enter this secret manually</p>
                    <div className="flex items-center gap-2 bg-[#14141f] rounded-lg p-3 border border-[#1c1c2a]">
                      <code className="text-[#00d4a0] text-xs font-mono flex-1 break-all tracking-wider">{totpSecret}</code>
                      <button onClick={copySecret} className="text-[#5c5c70] hover:text-[#00d4a0] transition-colors p-1 rounded">
                        {copiedSecret ? <Check size={16} className="text-[#00d4a0]" /> : <Copy size={16} />}
                      </button>
                    </div>
                  </div>
                </div>
                <div>
                  <label className="block text-sm font-medium text-[#9a9aae] mb-2">Enter verification code from app</label>
                  <input
                    type="text" value={verifyCode}
                    onChange={e => setVerifyCode(e.target.value.replace(/\D/g, '').slice(0, 6))}
                    maxLength={6}
                    className="w-full bg-[#14141f] border border-[#1c1c2a] rounded-lg px-4 py-3 text-[#f0f0f5] text-lg text-center tracking-[0.5em] font-mono placeholder:text-[#5c5c70] focus:outline-none focus:border-[#00d4a0] focus:ring-1 focus:ring-[rgba(0,212,160,0.4)] transition-all"
                    placeholder="000000"
                  />
                </div>
                <div className="flex gap-3">
                  <button
                    onClick={() => setShowEnable2FA(false)}
                    className="flex-1 bg-transparent hover:bg-[#14141f] text-[#5c5c70] hover:text-[#9a9aae] rounded-lg px-4 py-2.5 text-sm font-medium transition-all border border-[#1c1c2a]"
                  >
                    Cancel
                  </button>
                  <button
                    onClick={handleVerify2FA}
                    disabled={loading2FA || verifyCode.length !== 6}
                    className="flex-1 bg-[#00d4a0] hover:bg-[#00e8b0] disabled:opacity-60 disabled:cursor-not-allowed text-[#06060a] rounded-lg px-4 py-2.5 text-sm font-semibold transition-all flex items-center justify-center gap-2"
                  >
                    <CheckCircle size={16} />
                    {loading2FA ? 'Verifying...' : 'Verify & Enable'}
                  </button>
                </div>

                {backupCodes.length > 0 && (
                  <div className="bg-[rgba(0,212,160,0.06)] border border-[rgba(0,212,160,0.2)] rounded-lg p-4">
                    <div className="flex items-center gap-2 mb-2">
                      <AlertCircle size={14} className="text-[#00d4a0]" />
                      <span className="text-sm font-semibold text-[#00d4a0]">Save your backup codes</span>
                    </div>
                    <p className="text-xs text-[#9a9aae] mb-3">
                      These codes let you recover access if you lose your device. Each code can be used once.
                    </p>
                    <div className="grid grid-cols-2 gap-2">
                      {backupCodes.map((code) => (
                        <div key={code} className="bg-[#14141f] border border-[#1c1c2a] rounded px-2 py-1.5 text-center text-xs font-mono tracking-wider text-[#f0f0f5]">
                          {code}
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            )}
          </div>
        ) : (
          <div className="space-y-4">
            <div className="flex items-center gap-2 text-[#00d4a0]">
              <CheckCircle size={16} />
              <span className="text-sm font-medium">2FA is enabled on your account</span>
            </div>
            {!showDisable2FA ? (
              <button
                onClick={() => setShowDisable2FA(true)}
                className="flex items-center gap-2 bg-red-900/20 hover:bg-red-900/30 text-red-400 border border-red-800 rounded-lg px-4 py-2 text-sm font-medium transition-colors"
              >
                <span className="font-mono">2FA</span> Disable 2FA
              </button>
            ) : (
              <div className="mt-3 space-y-3 border-t border-[#1c1c2a] pt-3">
                <p className="text-sm text-[#9a9aae]">To disable 2FA, enter your current password and a TOTP code.</p>
                <input
                  type="password"
                  value={disablePassword}
                  onChange={e => setDisablePassword(e.target.value)}
                  placeholder="Current password"
                  className="w-full bg-[#14141f] border border-[#1c1c2a] rounded-lg px-3 py-2 text-sm text-[#f0f0f5] placeholder:text-[#5c5c70] focus:outline-none focus:border-red-500 transition-colors"
                />
                <input
                  type="text"
                  value={disableCode}
                  onChange={e => setDisableCode(e.target.value.replace(/\D/g, '').slice(0, 6))}
                  maxLength={6}
                  placeholder="TOTP code"
                  className="w-full bg-[#14141f] border border-[#1c1c2a] rounded-lg px-3 py-2 text-sm text-[#f0f0f5] placeholder:text-[#5c5c70] focus:outline-none focus:border-red-500 transition-colors"
                />
                <div className="flex gap-3">
                  <button
                    onClick={() => { setShowDisable2FA(false); setDisableCode(''); setDisablePassword(''); }}
                    className="flex-1 bg-transparent hover:bg-[#14141f] text-[#5c5c70] hover:text-[#9a9aae] rounded-lg px-4 py-2 text-sm font-medium transition-all border border-[#1c1c2a]"
                  >
                    Cancel
                  </button>
                  <button
                    onClick={handleDisable2FA}
                    disabled={loading2FA}
                    className="flex-1 bg-red-600 hover:bg-red-500 disabled:bg-red-800 disabled:cursor-not-allowed text-white rounded-lg px-4 py-2 text-sm font-medium transition-colors"
                  >
                    {loading2FA ? 'Disabling...' : 'Disable 2FA'}
                  </button>
                </div>
              </div>
            )}
          </div>
        )}
      </div>

      {/* Display Name */}
      <div className="bg-[#0f0f18] border border-[#1c1c2a] rounded-xl p-5">
        <h3 className="text-lg font-semibold text-[#f0f0f5] mb-4 flex items-center gap-2">
          <User size={18} className="text-[#00d4a0]" />
          Display Name
        </h3>
        <form onSubmit={handleSaveName} className="flex gap-3">
          <input
            type="text"
            value={displayName}
            onChange={(e) => setDisplayName(e.target.value)}
            placeholder="Your display name"
            className="flex-1 bg-[#14141f] border border-[#1c1c2a] rounded-lg px-3 py-2 text-sm text-[#f0f0f5] placeholder:text-[#5c5c70] focus:outline-none focus:border-[#00d4a0] focus:ring-1 focus:ring-[rgba(0,212,160,0.4)] transition-colors"
          />
          <button
            type="submit"
            disabled={savingName}
            className="flex items-center gap-2 bg-[#00d4a0] hover:bg-[#00b88c] disabled:bg-[#004d3a] disabled:cursor-not-allowed text-[#06060a] rounded-lg px-4 py-2 text-sm font-medium transition-colors"
          >
            <Save size={16} />
            {savingName ? 'Saving...' : 'Save'}
          </button>
        </form>
      </div>

      {/* Change Password */}
      <div className="bg-[#0f0f18] border border-[#1c1c2a] rounded-xl p-5">
        <h3 className="text-lg font-semibold text-[#f0f0f5] mb-4 flex items-center gap-2">
          <Lock size={18} className="text-[#ffbd2e]" />
          Change Password
        </h3>
        <form onSubmit={handleChangePassword} className="space-y-3">
          <input
            type="password"
            value={currentPassword}
            onChange={(e) => setCurrentPassword(e.target.value)}
            placeholder="Current password"
            required
            className="w-full bg-[#14141f] border border-[#1c1c2a] rounded-lg px-3 py-2 text-sm text-[#f0f0f5] placeholder:text-[#5c5c70] focus:outline-none focus:border-[#ffbd2e] transition-colors"
          />
          <input
            type="password"
            value={newPassword}
            onChange={(e) => setNewPassword(e.target.value)}
            placeholder="New password"
            required
            className="w-full bg-[#14141f] border border-[#1c1c2a] rounded-lg px-3 py-2 text-sm text-[#f0f0f5] placeholder:text-[#5c5c70] focus:outline-none focus:border-[#ffbd2e] transition-colors"
          />
          <input
            type="password"
            value={confirmPassword}
            onChange={(e) => setConfirmPassword(e.target.value)}
            placeholder="Confirm new password"
            required
            className="w-full bg-[#14141f] border border-[#1c1c2a] rounded-lg px-3 py-2 text-sm text-[#f0f0f5] placeholder:text-[#5c5c70] focus:outline-none focus:border-[#ffbd2e] transition-colors"
          />
          <div className="flex justify-end">
            <button
              type="submit"
              disabled={savingPassword}
              className="flex items-center gap-2 bg-[#ffbd2e] hover:bg-[#e6a82a] disabled:bg-[#664d14] disabled:cursor-not-allowed text-[#06060a] rounded-lg px-4 py-2 text-sm font-medium transition-colors"
            >
              <Lock size={16} />
              {savingPassword ? 'Updating...' : 'Update Password'}
            </button>
          </div>
        </form>
      </div>

      {/* Delete Account */}
      <div className="bg-[#0f0f18] border border-[#1c1c2a] rounded-xl p-5">
        <h3 className="text-lg font-semibold text-red-400 mb-2 flex items-center gap-2">
          <Trash2 size={18} />
          Danger Zone
        </h3>
        <p className="text-sm text-[#9a9aae] mb-4">
          Permanently delete your account and all associated data. This action cannot be undone.
        </p>
        <button
          onClick={() => setShowDeleteConfirm(true)}
          className="flex items-center gap-2 bg-red-500/10 hover:bg-red-500/20 text-red-400 border border-red-500/30 rounded-lg px-4 py-2 text-sm font-medium transition-colors"
        >
          <Trash2 size={16} />
          Delete Account
        </button>
      </div>

      {/* Delete Confirmation Modal */}
      {showDeleteConfirm && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm px-4">
          <div className="bg-[#0f0f18] border border-[#1c1c2a] rounded-xl p-6 w-full max-w-md shadow-2xl">
            <div className="flex items-center gap-2 mb-3">
              <AlertCircle size={20} className="text-red-400" />
              <h3 className="text-lg font-semibold text-[#f0f0f5]">Delete Account</h3>
            </div>
            <p className="text-sm text-[#9a9aae] mb-4">
              This will permanently delete your account and all data. Type <span className="text-red-400 font-mono">DELETE</span> below to confirm.
            </p>
            <input
              type="text"
              value={deleteConfirmText}
              onChange={(e) => setDeleteConfirmText(e.target.value)}
              placeholder="Type DELETE to confirm"
              className="w-full bg-[#14141f] border border-[#1c1c2a] rounded-lg px-3 py-2 text-sm text-[#f0f0f5] placeholder:text-[#5c5c70] focus:outline-none focus:border-red-500 transition-colors mb-4"
            />
            <div className="flex justify-end gap-3">
              <button
                onClick={() => { setShowDeleteConfirm(false); setDeleteConfirmText(''); }}
                className="flex items-center gap-1 px-4 py-2 text-sm text-[#9a9aae] bg-[#14141f] rounded-lg hover:bg-[#1c1c2a] transition-colors"
              >
                <X size={16} /> Cancel
              </button>
              <button
                onClick={handleDelete}
                disabled={deleting}
                className="flex items-center gap-1 bg-red-600 hover:bg-red-500 disabled:bg-red-800 disabled:cursor-not-allowed text-white rounded-lg px-4 py-2 text-sm font-medium transition-colors"
              >
                <Trash2 size={16} />
                {deleting ? 'Deleting...' : 'Permanently Delete'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
