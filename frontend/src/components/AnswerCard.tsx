import React from 'react';
import { QueryResult, CitationItem } from '../services/api';
import { CitationBadge } from './CitationBadge';

interface AnswerCardProps {
  result: QueryResult;
  onPreviewCitation: (citation: CitationItem) => void;
}

export const AnswerCard: React.FC<AnswerCardProps> = ({ result, onPreviewCitation }) => {
  if (result.status === 'NOT_FOUND') {
    return (
      <div className="not-found-card" role="alert">
        <h3 className="not-found-title">
          <svg
            width="20"
            height="20"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
          >
            <circle cx="12" cy="12" r="10" />
            <line x1="12" y1="8" x2="12" y2="12" />
            <line x1="12" y1="16" x2="12.01" y2="16" />
          </svg>
          Information Not Found in Official Repository
        </h3>
        <p>{result.fallbackMessage}</p>
      </div>
    );
  }

  if (!result.answer) return null;

  const { summary, eligibility, requiredDocuments, applicationProcedure, citations } =
    result.answer;

  return (
    <article className="answer-box">
      <header className="answer-header">
        <div>
          <span className="grounded-badge">
            <svg
              width="14"
              height="14"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="3"
            >
              <polyline points="20 6 9 17 4 12" />
            </svg>
            Strictly Grounded in Official Circulars
          </span>
        </div>
        <span style={{ fontSize: '0.8rem', color: 'hsl(var(--text-muted))' }}>
          Response generated in {result.latencyMs}ms
        </span>
      </header>

      {/* Summary */}
      <section className="answer-section">
        <h4 className="section-title">Overview & Summary</h4>
        <p>{summary}</p>
      </section>

      {/* Eligibility */}
      {eligibility && eligibility.length > 0 && (
        <section className="answer-section">
          <h4 className="section-title">Eligibility Criteria</h4>
          <ul className="rule-list">
            {eligibility.map((item, idx) => (
              <li key={idx} className="rule-item">
                {item}
              </li>
            ))}
          </ul>
        </section>
      )}

      {/* Required Documents */}
      {requiredDocuments && requiredDocuments.length > 0 && (
        <section className="answer-section">
          <h4 className="section-title">Required Documents</h4>
          <ul className="rule-list">
            {requiredDocuments.map((item, idx) => (
              <li key={idx} className="rule-item">
                {item}
              </li>
            ))}
          </ul>
        </section>
      )}

      {/* Application Procedure */}
      {applicationProcedure && applicationProcedure.length > 0 && (
        <section className="answer-section">
          <h4 className="section-title">Application Procedure</h4>
          <ul className="rule-list">
            {applicationProcedure.map((item, idx) => (
              <li key={idx} className="rule-item">
                {item}
              </li>
            ))}
          </ul>
        </section>
      )}

      {/* Document Citations */}
      {citations && citations.length > 0 && (
        <section
          className="answer-section"
          style={{
            marginTop: '1.5rem',
            borderTop: '1px solid hsl(var(--border-subtle))',
            paddingTop: '1rem',
          }}
        >
          <h4 className="section-title">Cited Official Documents ({citations.length})</h4>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.5rem', marginTop: '0.5rem' }}>
            {citations.map(c => (
              <CitationBadge key={c.citationId} citation={c} onPreview={onPreviewCitation} />
            ))}
          </div>
        </section>
      )}
    </article>
  );
};
