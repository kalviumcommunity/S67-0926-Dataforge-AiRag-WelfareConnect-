'use client';

import React, { useState } from 'react';
import ApiService from '../lib/api';
import { Citation, Collection, QueryResponse, User } from '../lib/types';

interface HeroSearchProps {
  collections: Collection[];
  onCitationClick: (citation: Citation) => void;
  user?: User | null;
  token?: string | null;
}

export const HeroSearch: React.FC<HeroSearchProps> = ({
  collections,
  onCitationClick,
  user,
  token,
}) => {
  const [query, setQuery] = useState('');
  const [selectedCollection, setSelectedCollection] = useState<string>('');
  const [includeHistorical, setIncludeHistorical] = useState(false);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<QueryResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  const isAdmin = user && (user.role === 'SYSTEM_ADMIN' || user.role === 'SCHEME_ADMIN');

  const sampleQueries = [
    'What is the maximum income limit for PMAY-U housing subsidy?',
    'What are the eligibility criteria for PM-Kisan financial support?',
    'Are non-resident citizens eligible for welfare benefits from abroad?',
  ];

  const handleSearch = async (queryText?: string) => {
    const q = queryText !== undefined ? queryText : query;
    if (!q.trim()) return;

    setLoading(true);
    setError(null);
    try {
      const response = await ApiService.executeQuery(
        q,
        selectedCollection || undefined,
        token || undefined,
        isAdmin ? includeHistorical : false
      );
      setResult(response);
    } catch (err: any) {
      setError(err.message || 'Failed to search scheme documentation');
    } finally {
      setLoading(false);
    }
  };

  return (
    <section className="hero-section">
      <div className="hero-badge">
        <span>⚡</span>
        <span>Grounded Scheme Intelligence with Exact Page & Version Citations</span>
      </div>

      <h1 className="hero-title">
        Official Government Welfare <span>Document Assistant</span>
      </h1>

      <p className="hero-description">
        Ask natural-language questions across official government guidelines, circulars, and gazettes.
        Every answer is strictly grounded in verified source PDFs with document name, active version, and page numbers.
      </p>

      {/* Search Input Box */}
      <div className="search-container">
        <div className="search-input-wrapper">
          <select
            className="search-select"
            value={selectedCollection}
            onChange={(e) => setSelectedCollection(e.target.value)}
            aria-label="Filter by Scheme Collection"
          >
            <option value="">All Active Schemes</option>
            {collections.map((col) => (
              <option key={col.id} value={col.id}>
                {col.name}
              </option>
            ))}
          </select>

          <input
            type="text"
            className="search-input"
            placeholder="E.g., What documents are required for housing subsidy?"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && handleSearch()}
          />

          <button
            className="search-btn"
            onClick={() => handleSearch()}
            disabled={loading || !query.trim()}
          >
            {loading ? 'Searching...' : 'Search Scheme'}
          </button>
        </div>

        {/* Administrator Historical Search Toggle */}
        {isAdmin && (
          <div style={{ marginTop: '0.65rem', display: 'flex', alignItems: 'center', gap: '0.5rem', fontSize: '0.8rem', color: '#9a3412', background: '#ffedd5', padding: '0.35rem 0.75rem', borderRadius: 'var(--radius-sm)', width: 'fit-content' }}>
            <input
              type="checkbox"
              id="historical-search-toggle"
              checked={includeHistorical}
              onChange={(e) => setIncludeHistorical(e.target.checked)}
            />
            <label htmlFor="historical-search-toggle" style={{ cursor: 'pointer', fontWeight: 600 }}>
              🛡️ Admin Mode: Search Historical & Archived Guidelines
            </label>
          </div>
        )}

        {/* Sample Query Chips */}
        <div className="sample-chips">
          <span style={{ fontSize: '0.75rem', fontWeight: 600, color: 'var(--text-muted)' }}>
            Suggested Queries:
          </span>
          {sampleQueries.map((sq, idx) => (
            <button
              key={idx}
              className="sample-chip-btn"
              onClick={() => {
                setQuery(sq);
                handleSearch(sq);
              }}
            >
              {sq}
            </button>
          ))}
        </div>
      </div>

      {/* Error state */}
      {error && (
        <div
          style={{
            maxWidth: '800px',
            margin: '1.5rem auto 0',
            padding: '1rem',
            background: 'var(--status-danger-bg)',
            color: 'var(--status-danger)',
            borderRadius: 'var(--radius-md)',
            fontWeight: 500,
          }}
        >
          {error}
        </div>
      )}

      {/* Answer & Citations Card */}
      {result && (
        <div className="answer-card">
          <div className="answer-header">
            <div className="answer-title">
              <span>📋</span> Grounded Scheme Analysis
            </div>
            <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
              Response latency: {result.latency_ms}ms
            </span>
          </div>

          {result.is_refusal ? (
            <div className="answer-refusal">{result.answer}</div>
          ) : (
            <div className="answer-body">{result.answer}</div>
          )}

          {result.citations.length > 0 && (
            <div className="citations-container">
              <div className="citations-label">Verified Official Source Citations (Active Version Grounding)</div>
              <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap' }}>
                {result.citations.map((c, idx) => (
                  <button
                    key={idx}
                    className="citation-badge"
                    onClick={() => onCitationClick(c)}
                    title="Click to preview official PDF page excerpt"
                    style={{
                      display: 'inline-flex',
                      alignItems: 'center',
                      gap: '0.35rem',
                    }}
                  >
                    <span>📄</span>
                    <span>
                      {c.document_title} (Page {c.page_number})
                    </span>
                  </button>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </section>
  );
};
