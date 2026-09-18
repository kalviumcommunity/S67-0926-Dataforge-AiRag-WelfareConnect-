'use client';

import React, { useState } from 'react';
import ApiService from '../lib/api';
import { AuthSessionResponse } from '../lib/types';

interface AuthModalProps {
  isOpen: boolean;
  onClose: () => void;
  onLoginSuccess: (session: AuthSessionResponse) => void;
}

export const AuthModal: React.FC<AuthModalProps> = ({
  isOpen,
  onClose,
  onLoginSuccess,
}) => {
  const [isRegister, setIsRegister] = useState(false);
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [fullName, setFullName] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (!isOpen) return null;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError(null);

    try {
      if (isRegister) {
        const session = await ApiService.registerCitizen(email, password, fullName);
        onLoginSuccess(session);
        onClose();
      } else {
        const session = await ApiService.login(email, password);
        onLoginSuccess(session);
        onClose();
      }
    } catch (err: any) {
      setError(err.message || 'Authentication error');
    } finally {
      setLoading(false);
    }
  };

  const setPresetCredentials = (userEmail: string, userPass: string) => {
    setEmail(userEmail);
    setPassword(userPass);
    setIsRegister(false);
  };

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-content" onClick={(e) => e.stopPropagation()}>
        <button className="modal-close-btn" onClick={onClose}>
          ✕
        </button>

        <h2
          style={{
            fontSize: '1.35rem',
            fontWeight: 700,
            color: 'var(--primary-900)',
            marginBottom: '0.25rem',
          }}
        >
          {isRegister ? 'Register Citizen Account' : 'Portal Sign In'}
        </h2>
        <p style={{ fontSize: '0.85rem', color: 'var(--text-muted)', marginBottom: '1.25rem' }}>
          {isRegister
            ? 'Create an account to save scheme queries and access citizen tools.'
            : 'Sign in to access administrator or helpdesk role workflows.'}
        </p>

        {error && (
          <div
            style={{
              padding: '0.65rem 0.85rem',
              background: 'var(--status-danger-bg)',
              color: 'var(--status-danger)',
              borderRadius: 'var(--radius-sm)',
              fontSize: '0.85rem',
              marginBottom: '1rem',
              fontWeight: 500,
            }}
          >
            {error}
          </div>
        )}

        {/* Quick Dev Demo Accounts */}
        {!isRegister && (
          <div
            style={{
              background: 'var(--bg-subtle)',
              border: '1px solid var(--border-subtle)',
              borderRadius: 'var(--radius-sm)',
              padding: '0.75rem',
              marginBottom: '1.25rem',
              fontSize: '0.8rem',
            }}
          >
            <div style={{ fontWeight: 600, color: 'var(--primary-900)', marginBottom: '0.35rem' }}>
              Quick Test Credentials:
            </div>
            <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap' }}>
              <button
                type="button"
                className="sample-chip-btn"
                onClick={() =>
                  setPresetCredentials('admin.dev@welfareconnect.local', 'Admin@123456')
                }
              >
                Dev Admin
              </button>
              <button
                type="button"
                className="sample-chip-btn"
                onClick={() =>
                  setPresetCredentials('helpdesk.staff@welfareconnect.local', 'Staff@123456')
                }
              >
                Helpdesk Staff
              </button>
            </div>
          </div>
        )}

        <form onSubmit={handleSubmit}>
          {isRegister && (
            <div className="form-group">
              <label className="form-label">Full Name</label>
              <input
                type="text"
                className="form-input"
                required
                value={fullName}
                onChange={(e) => setFullName(e.target.value)}
                placeholder="Enter your full name"
              />
            </div>
          )}

          <div className="form-group">
            <label className="form-label">Email Address</label>
            <input
              type="email"
              className="form-input"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="name@example.gov"
            />
          </div>

          <div className="form-group">
            <label className="form-label">Password</label>
            <input
              type="password"
              className="form-input"
              required
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="••••••••"
            />
          </div>

          <button type="submit" className="form-submit-btn" disabled={loading}>
            {loading ? 'Processing...' : isRegister ? 'Register Account' : 'Sign In'}
          </button>
        </form>

        <div style={{ textAlign: 'center', marginTop: '1rem', fontSize: '0.85rem' }}>
          <button
            type="button"
            onClick={() => {
              setIsRegister(!isRegister);
              setError(null);
            }}
            style={{ color: 'var(--primary-600)', fontWeight: 600 }}
          >
            {isRegister
              ? 'Already registered? Sign in here'
              : 'Citizen registration: Create a free account'}
          </button>
        </div>
      </div>
    </div>
  );
};
