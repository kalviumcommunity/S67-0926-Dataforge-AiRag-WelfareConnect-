import React from 'react';
import { HealthStatusBadge } from './HealthStatusBadge';
import { UserProfile } from '../services/api';

interface NavbarProps {
  currentUser: UserProfile | null;
  onOpenAuthModal: () => void;
  onLogout: () => void;
}

export const Navbar: React.FC<NavbarProps> = ({ currentUser, onOpenAuthModal, onLogout }) => {
  return (
    <header className="navbar">
      <div className="container navbar-inner">
        <div className="brand-logo">
          <div className="brand-icon-wrapper">
            <svg
              width="20"
              height="20"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2.5"
              strokeLinecap="round"
              strokeLinejoin="round"
            >
              <path d="M12 2L2 7l10 5 10-5-10-5z" />
              <path d="M2 17l10 5 10-5" />
              <path d="M2 12l10 5 10-5" />
            </svg>
          </div>
          <div>
            <h1 className="brand-title">WelfareConnect AI</h1>
            <p className="brand-subtitle">Official Scheme Document Intelligence</p>
          </div>
        </div>

        <div className="nav-actions">
          <HealthStatusBadge />

          {currentUser ? (
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.65rem' }}>
              <div style={{ textAlign: 'right', fontSize: '0.8rem' }}>
                <div style={{ fontWeight: 600 }}>{currentUser.fullName}</div>
                <span
                  className="disclaimer-badge"
                  style={{ fontSize: '0.65rem', padding: '0.1rem 0.35rem' }}
                >
                  {currentUser.role}
                </span>
              </div>
              <button
                type="button"
                className="chip"
                style={{
                  padding: '0.35rem 0.75rem',
                  fontSize: '0.8rem',
                  background: 'hsl(var(--bg-main))',
                }}
                onClick={onLogout}
              >
                Log Out
              </button>
            </div>
          ) : (
            <button
              type="button"
              className="search-btn"
              style={{ position: 'static', padding: '0.45rem 0.95rem', fontSize: '0.85rem' }}
              onClick={onOpenAuthModal}
            >
              Sign In / Register
            </button>
          )}
        </div>
      </div>
    </header>
  );
};
