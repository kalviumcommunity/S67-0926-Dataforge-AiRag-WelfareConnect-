import React from 'react';
import { HealthStatusBadge } from './HealthStatusBadge';

export const Navbar: React.FC = () => {
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
        </div>
      </div>
    </header>
  );
};
