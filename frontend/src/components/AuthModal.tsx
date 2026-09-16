import React, { useState } from 'react';
import { api, UserProfile } from '../services/api';

interface AuthModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSuccess: (user: UserProfile) => void;
}

export const AuthModal: React.FC<AuthModalProps> = ({ isOpen, onClose, onSuccess }) => {
  const [isRegister, setIsRegister] = useState(false);
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [fullName, setFullName] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  if (!isOpen) return null;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setLoading(true);

    try {
      if (isRegister) {
        const session = await api.register(email, password, fullName);
        onSuccess(session.user);
      } else {
        const session = await api.login(email, password);
        onSuccess(session.user);
      }
      onClose();
    } catch (err: any) {
      setError(err.message || 'Authentication failed');
    } finally {
      setLoading(false);
    }
  };

  const handleQuickLogin = async (roleEmail: string, rolePass: string) => {
    setError(null);
    setLoading(true);
    try {
      const session = await api.login(roleEmail, rolePass);
      onSuccess(session.user);
      onClose();
    } catch (err: any) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div
        className="modal-content"
        style={{ maxWidth: '460px' }}
        onClick={e => e.stopPropagation()}
      >
        <div className="modal-header">
          <div>
            <h3 className="modal-title">{isRegister ? 'Citizen Registration' : 'Account Login'}</h3>
            <p style={{ fontSize: '0.8rem', color: 'hsl(var(--text-muted))' }}>
              {isRegister
                ? 'Create a public citizen inquiry account'
                : 'Access your role-based portal'}
            </p>
          </div>
          <button type="button" className="modal-close-btn" onClick={onClose}>
            &times;
          </button>
        </div>

        <div className="modal-body">
          {error && (
            <div
              className="not-found-card"
              style={{ padding: '0.75rem', marginBottom: '1rem', fontSize: '0.85rem' }}
            >
              {error}
            </div>
          )}

          <form
            onSubmit={handleSubmit}
            style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}
          >
            {isRegister && (
              <div>
                <label className="collection-label">Full Name</label>
                <input
                  type="text"
                  className="search-input"
                  style={{ padding: '0.65rem 0.85rem', fontSize: '0.95rem' }}
                  required
                  placeholder="e.g. Ramesh Kumar"
                  value={fullName}
                  onChange={e => setFullName(e.target.value)}
                />
              </div>
            )}

            <div>
              <label className="collection-label">Email Address</label>
              <input
                type="email"
                className="search-input"
                style={{ padding: '0.65rem 0.85rem', fontSize: '0.95rem' }}
                required
                placeholder="name@welfareconnect.local"
                value={email}
                onChange={e => setEmail(e.target.value)}
              />
            </div>

            <div>
              <label className="collection-label">Password</label>
              <input
                type="password"
                className="search-input"
                style={{ padding: '0.65rem 0.85rem', fontSize: '0.95rem' }}
                required
                placeholder="••••••••"
                value={password}
                onChange={e => setPassword(e.target.value)}
              />
            </div>

            <button
              type="submit"
              className="search-btn"
              style={{
                position: 'static',
                width: '100%',
                justifyContent: 'center',
                marginTop: '0.5rem',
              }}
              disabled={loading}
            >
              {loading ? 'Processing...' : isRegister ? 'Register Citizen Account' : 'Log In'}
            </button>
          </form>

          <div style={{ textAlign: 'center', marginTop: '1rem', fontSize: '0.85rem' }}>
            <button
              type="button"
              style={{
                background: 'none',
                border: 'none',
                color: 'hsl(var(--primary))',
                cursor: 'pointer',
                textDecoration: 'underline',
              }}
              onClick={() => setIsRegister(!isRegister)}
            >
              {isRegister
                ? 'Already have an account? Log in'
                : "Don't have an account? Register as Citizen"}
            </button>
          </div>

          {/* Development Quick Role Switcher */}
          <div
            style={{
              marginTop: '1.5rem',
              borderTop: '1px solid hsl(var(--border-subtle))',
              paddingTop: '1rem',
            }}
          >
            <label className="collection-label">Quick Demo Logins (Pre-Seeded Roles)</label>
            <div
              style={{
                display: 'flex',
                flexDirection: 'column',
                gap: '0.4rem',
                marginTop: '0.5rem',
              }}
            >
              <button
                type="button"
                className="chip"
                style={{ textAlign: 'left', width: '100%' }}
                onClick={() => handleQuickLogin('admin.dev@welfareconnect.local', 'Admin@123456')}
              >
                🔐 <strong>System Administrator</strong> (admin.dev@welfareconnect.local)
              </button>
              <button
                type="button"
                className="chip"
                style={{ textAlign: 'left', width: '100%' }}
                onClick={() =>
                  handleQuickLogin('helpdesk.staff@welfareconnect.local', 'Staff@123456')
                }
              >
                🎧 <strong>Helpdesk Staff</strong> (helpdesk.staff@welfareconnect.local)
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
