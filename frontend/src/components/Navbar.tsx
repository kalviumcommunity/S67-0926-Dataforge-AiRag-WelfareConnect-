'use client';

import React from 'react';
import { HealthStatusBadge } from './HealthStatusBadge';
import { User } from '../lib/types';

interface NavbarProps {
  user: User | null;
  onOpenAuthModal: () => void;
  onLogout: () => void;
}

export const Navbar: React.FC<NavbarProps> = ({ user, onOpenAuthModal, onLogout }) => {
  return (
    <header className="navbar">
      <div className="navbar-inner">
        <div className="navbar-brand">
          <div className="navbar-logo-icon">WC</div>
          <div>
            <div className="navbar-title">WelfareConnect</div>
            <div className="navbar-subtitle">Government Scheme Document Assistant</div>
          </div>
        </div>

        <div className="navbar-actions">
          <HealthStatusBadge />

          {user ? (
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
              <span
                style={{
                  fontSize: '0.85rem',
                  fontWeight: 600,
                  color: 'var(--primary-800)',
                  background: 'var(--primary-100)',
                  padding: '0.35rem 0.75rem',
                  borderRadius: 'var(--radius-sm)',
                }}
              >
                {user.full_name} ({user.role})
              </span>
              <button
                onClick={onLogout}
                style={{
                  fontSize: '0.85rem',
                  fontWeight: 600,
                  color: 'var(--status-danger)',
                  padding: '0.35rem 0.6rem',
                  border: '1px solid #fee2e2',
                  borderRadius: 'var(--radius-sm)',
                }}
              >
                Sign Out
              </button>
            </div>
          ) : (
            <button
              onClick={onOpenAuthModal}
              style={{
                fontSize: '0.85rem',
                fontWeight: 600,
                color: 'var(--primary-700)',
                border: '1px solid var(--primary-500)',
                padding: '0.4rem 0.85rem',
                borderRadius: 'var(--radius-sm)',
                transition: 'all 0.15s ease',
              }}
            >
              Sign In / Admin Access
            </button>
          )}
        </div>
      </div>
    </header>
  );
};
