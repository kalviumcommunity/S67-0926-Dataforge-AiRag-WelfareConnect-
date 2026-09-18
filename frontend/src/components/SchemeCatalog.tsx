'use client';

import React from 'react';
import { Collection } from '../lib/types';

interface SchemeCatalogProps {
  collections: Collection[];
}

export const SchemeCatalog: React.FC<SchemeCatalogProps> = ({ collections }) => {
  return (
    <section className="catalog-section">
      <div className="section-header">
        <div>
          <h2 className="section-title">Indexed Official Scheme Collections</h2>
          <p style={{ fontSize: '0.9rem', color: 'var(--text-muted)', marginTop: '0.25rem' }}>
            Authorized document repositories available for grounded search and verification.
          </p>
        </div>
      </div>

      <div className="scheme-grid">
        {collections.map((col) => (
          <div key={col.id} className="scheme-card">
            <div>
              <div className="scheme-dept">{col.department || 'Government Department'}</div>
              <h3 className="scheme-name">{col.name}</h3>
              <p className="scheme-desc">
                {col.description || 'Comprehensive guidelines, eligibility clauses, and circulars.'}
              </p>
            </div>

            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                paddingTop: '0.75rem',
                borderTop: '1px solid var(--border-subtle)',
                fontSize: '0.75rem',
                color: 'var(--text-muted)',
              }}
            >
              <span>{col.total_documents} Official Documents</span>
              <span
                style={{
                  color: 'var(--status-success)',
                  fontWeight: 600,
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: '0.25rem',
                }}
              >
                ● Active Index
              </span>
            </div>
          </div>
        ))}
      </div>
    </section>
  );
};
