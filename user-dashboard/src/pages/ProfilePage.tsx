import { useState } from 'react';
import { useAuth } from '../contexts/AuthContext';
import { User, Lock, Check } from 'lucide-react';

export const ProfilePage = () => {
  const { user, apiFetch, showError, showSuccess } = useAuth();
  const [name, setName] = useState(user?.name || '');
  const [savingName, setSavingName] = useState(false);

  const [currentPassword, setCurrentPassword] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [changingPassword, setChangingPassword] = useState(false);

  const handleUpdateName = async (e: React.FormEvent) => {
    e.preventDefault();
    setSavingName(true);
    try {
      await apiFetch('/auth/me/profile', {
        method: 'PUT',
        body: JSON.stringify({ name: name.trim() || null }),
      });
      showSuccess('Profile updated');
    } catch (err: any) {
      showError(err.message || 'Failed to update profile');
    } finally {
      setSavingName(false);
    }
  };

  const handleChangePassword = async (e: React.FormEvent) => {
    e.preventDefault();
    if (newPassword !== confirmPassword) {
      showError('New passwords do not match');
      return;
    }
    if (newPassword.length < 8) {
      showError('Password must be at least 8 characters');
      return;
    }
    setChangingPassword(true);
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
      setChangingPassword(false);
    }
  };

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold text-[#f0f0f5] mb-1">Profile</h2>
        <p className="text-sm text-[#9a9aae]">Manage your account settings and password.</p>
      </div>

      {/* Account Info */}
      <div className="bg-[#0f0f18] border border-[#1c1c2a] rounded-xl p-5">
        <h3 className="text-lg font-semibold text-[#f0f0f5] mb-4 flex items-center gap-2">
          <User size={18} className="text-[#4494ff]" />
          Account Information
        </h3>
        <div className="space-y-3">
          <div>
            <label className="block text-sm text-[#9a9aae] mb-1">Email</label>
            <div className="text-[#f0f0f5] text-sm">{user?.email}</div>
          </div>
          <div>
            <label className="block text-sm text-[#9a9aae] mb-1">Role</label>
            <span className="px-2 py-0.5 rounded text-xs font-medium border bg-[rgba(68,148,255,0.08)] text-[#4494ff] border-[rgba(68,148,255,0.2)] capitalize">
              {user?.role}
            </span>
          </div>
          <div>
            <label className="block text-sm text-[#9a9aae] mb-1">Status</label>
            <span className={`px-2 py-0.5 rounded text-xs font-medium border capitalize ${
              user?.status === 'active'
                ? 'bg-[rgba(0,212,160,0.08)] text-[#00d4a0] border-[rgba(0,212,160,0.2)]'
                : 'bg-[rgba(255,95,86,0.08)] text-[#ff5f56] border-[rgba(255,95,86,0.2)]'
            }`}>
              {user?.status}
            </span>
          </div>
        </div>
      </div>

      {/* Display Name */}
      <div className="bg-[#0f0f18] border border-[#1c1c2a] rounded-xl p-5">
        <h3 className="text-lg font-semibold text-[#f0f0f5] mb-4">Display Name</h3>
        <form onSubmit={handleUpdateName} className="flex gap-3">
          <input
            type="text"
            value={name}
            onChange={e => setName(e.target.value)}
            placeholder="Your display name"
            className="flex-1 bg-[#14141f] border border-[#1c1c2a] rounded-lg px-3 py-2 text-[#f0f0f5] text-sm
                       focus:outline-none focus:border-[#4494ff] transition-colors"
          />
          <button
            type="submit"
            disabled={savingName}
            className="bg-[#4494ff] hover:bg-[#3680e0] disabled:bg-[#1c1c2a] disabled:cursor-not-allowed
                       text-white rounded-lg px-4 py-2 text-sm font-medium transition-colors flex items-center gap-2"
          >
            {savingName ? 'Saving...' : (<><Check size={14} /> Save</>)}
          </button>
        </form>
      </div>

      {/* Change Password */}
      <div className="bg-[#0f0f18] border border-[#1c1c2a] rounded-xl p-5">
        <h3 className="text-lg font-semibold text-[#f0f0f5] mb-4 flex items-center gap-2">
          <Lock size={18} className="text-[#ffbd2e]" />
          Change Password
        </h3>
        <form onSubmit={handleChangePassword} className="space-y-3 max-w-md">
          <div>
            <label className="block text-sm text-[#9a9aae] mb-1">Current Password</label>
            <input
              type="password"
              value={currentPassword}
              onChange={e => setCurrentPassword(e.target.value)}
              required
              className="w-full bg-[#14141f] border border-[#1c1c2a] rounded-lg px-3 py-2 text-[#f0f0f5] text-sm
                         focus:outline-none focus:border-[#4494ff] transition-colors"
            />
          </div>
          <div>
            <label className="block text-sm text-[#9a9aae] mb-1">New Password</label>
            <input
              type="password"
              value={newPassword}
              onChange={e => setNewPassword(e.target.value)}
              required
              minLength={8}
              className="w-full bg-[#14141f] border border-[#1c1c2a] rounded-lg px-3 py-2 text-[#f0f0f5] text-sm
                         focus:outline-none focus:border-[#4494ff] transition-colors"
            />
          </div>
          <div>
            <label className="block text-sm text-[#9a9aae] mb-1">Confirm New Password</label>
            <input
              type="password"
              value={confirmPassword}
              onChange={e => setConfirmPassword(e.target.value)}
              required
              minLength={8}
              className="w-full bg-[#14141f] border border-[#1c1c2a] rounded-lg px-3 py-2 text-[#f0f0f5] text-sm
                         focus:outline-none focus:border-[#4494ff] transition-colors"
            />
          </div>
          <button
            type="submit"
            disabled={changingPassword}
            className="bg-[#4494ff] hover:bg-[#3680e0] disabled:bg-[#1c1c2a] disabled:cursor-not-allowed
                       text-white rounded-lg px-4 py-2 text-sm font-medium transition-colors"
          >
            {changingPassword ? 'Changing...' : 'Change Password'}
          </button>
        </form>
      </div>
    </div>
  );
};
