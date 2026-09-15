import React from 'react';
import { CitationItem } from '../services/api';

interface CitationBadgeProps {
  citation: CitationItem;
  onPreview: (citation: CitationItem) => void;
}

export const CitationBadge: React.FC<CitationBadgeProps> = ({ citation, onPreview }) => {
  return (
    <button
      type="button"
      className="citation-badge"
      onClick={() => onPreview(citation)}
      title={`Click to view source excerpt from ${citation.documentTitle}, Page ${citation.pageNumber}`}
    >
      <svg
        width="12"
        height="12"
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        strokeWidth="2"
      >
        <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
        <polyline points="14 2 14 8 20 8" />
        <line x1="16" y1="13" x2="8" y2="13" />
        <line x1="16" y1="17" x2="8" y2="17" />
        <polyline points="10 9 9 9 8 9" />
      </svg>
      <span>
        {citation.documentTitle.replace('.pdf', '')}, Pg {citation.pageNumber}
      </span>
    </button>
  );
};
