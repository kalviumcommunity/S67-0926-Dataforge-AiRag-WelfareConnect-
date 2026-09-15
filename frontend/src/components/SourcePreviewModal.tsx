import React from 'react';
import { CitationItem } from '../services/api';

interface SourcePreviewModalProps {
  citation: CitationItem | null;
  onClose: () => void;
}

export const SourcePreviewModal: React.FC<SourcePreviewModalProps> = ({ citation, onClose }) => {
  if (!citation) return null;

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-content" onClick={e => e.stopPropagation()}>
        <div className="modal-header">
          <div>
            <h3 className="modal-title">Verified Source Document Excerpt</h3>
            <p style={{ fontSize: '0.8rem', color: 'hsl(var(--text-muted))' }}>
              {citation.documentTitle} &bull; Page {citation.pageNumber}
            </p>
          </div>
          <button
            type="button"
            className="modal-close-btn"
            onClick={onClose}
            aria-label="Close modal"
          >
            &times;
          </button>
        </div>
        <div className="modal-body">
          <div className="source-excerpt-box">
            <p>"{citation.snippet}"</p>
          </div>
          <div
            style={{ marginTop: '1.25rem', fontSize: '0.82rem', color: 'hsl(var(--text-muted))' }}
          >
            <strong>Source Document ID:</strong> <code>{citation.documentId}</code>
          </div>
        </div>
      </div>
    </div>
  );
};
