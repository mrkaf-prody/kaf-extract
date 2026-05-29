import React, { useState, useCallback, useEffect } from 'react';
import { useAuth } from '../contexts/AuthContext';
import { User, Mail, Shield, CheckCircle, AlertTriangle, Save, Lock, Trash2, X } from 'lucide-react';

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
            className="flex-1 bg-[#14141f] border border-[#1c1c2a] rounded-lg px-3 py-2 text-sm text-[#f0f0f5] placeholder-[#5c5c70] focus:outline-none focus:border-[#00d4a0] transition-colors"
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
            className="w-full bg-[#14141f] border border-[#1c1c2a] rounded-lg px-3 py-2 text-sm text-[#f0f0f5] placeholder-[#5c5c70] focus:outline-none focus:border-[#ffbd2e] transition-colors"
          />
          <input
            type="password"
            value={newPassword}
            onChange={(e) => setNewPassword(e.target.value)}
            placeholder="New password"
            required
            className="w-full bg-[#14141f] border border-[#1c1c2a] rounded-lg px-3 py-2 text-sm text-[#f0f0f5] placeholder-[#5c5c70] focus:outline-none focus:border-[#ffbd2e] transition-colors"
          />
          <input
            type="password"
            value={confirmPassword}
            onChange={(e) => setConfirmPassword(e.target.value)}
            placeholder="Confirm new password"
            required
            className="w-full bg-[#14141f] border border-[#1c1c2a] rounded-lg px-3 py-2 text-sm text-[#f0f0f5] placeholder-[#5c5c70] focus:outline-none focus:border-[#ffbd2e] transition-colors"
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
              <AlertTriangle size={20} className="text-red-400" />
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
              className="w-full bg-[#14141f] border border-[#1c1c2a] rounded-lg px-3 py-2 text-sm text-[#f0f0f5] placeholder-[#5c5c70] focus:outline-none focus:border-red-500 transition-colors mb-4"
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
