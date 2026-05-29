import React, { useState } from 'react';
import { useAuth } from '../contexts/AuthContext';
import { User, Lock, Save, AlertTriangle, CheckCircle, Shield } from 'lucide-react';

export const ProfilePage: React.FC = () => {
  const { user, login } = useAuth();

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
      const token = localStorage.getItem('access_token');
      const res = await fetch('/auth/me/password', {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({ current_password: currentPassword, new_password: newPassword }),
      });
      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || 'Failed to change password');
      }
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
      const token = localStorage.getItem('access_token');
      const res = await fetch('/auth/me/profile', {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({ name: name || null }),
      });
      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || 'Failed to update profile');
      }
      // Re-login to refresh the user context
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
        <p className="text-slate-500 text-sm mt-1">Manage your account details and password</p>
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

      {/* 2FA Section — Coming Soon */}
      <div className="bg-slate-900 border border-slate-800 rounded-xl p-6">
        <div className="flex items-center gap-3 mb-4">
          <Shield size={20} className="text-amber-400" />
          <h3 className="text-lg font-semibold text-white">Two-Factor Authentication</h3>
          <span className="px-2 py-0.5 rounded text-[10px] font-medium bg-amber-500/10 text-amber-400 border border-amber-500/30">
            Coming soon
          </span>
        </div>
        <p className="text-sm text-slate-500 mb-4">
          Add an extra layer of security to your admin account with TOTP-based 2FA. 
          Once enabled, you'll need to enter a code from your authenticator app each time you sign in.
        </p>
        <div className="bg-slate-800/50 rounded-lg p-4 border border-slate-700/50">
          <div className="flex items-center gap-3">
            <div className="w-2 h-2 rounded-full bg-slate-600" />
            <p className="text-sm text-slate-500">Status: <span className="text-slate-400">Not configured</span></p>
          </div>
        </div>
      </div>
    </div>
  );
};
