import React, { useState } from 'react';
import { api, QueryResult } from '../services/api';

interface HelpdeskToolbarProps {
  currentResult: QueryResult | null;
}

export const HelpdeskToolbar: React.FC<HelpdeskToolbarProps> = ({ currentResult }) => {
  const [feedbackSubmitted, setFeedbackSubmitted] = useState(false);
  const [copied, setCopied] = useState(false);

  if (!currentResult) return null;

  const handleFeedback = async (isHelpful: boolean) => {
    try {
      await api.submitFeedback(currentResult.queryId, isHelpful, 'Helpdesk Operator Evaluation');
      setFeedbackSubmitted(true);
      setTimeout(() => setFeedbackSubmitted(false), 3000);
    } catch (err) {
      console.error('Feedback error:', err);
    }
  };

  const handleCopyAnswer = () => {
    if (!currentResult.answer) return;
    const text = `SUMMARY:\n${currentResult.answer.summary}\n\nELIGIBILITY:\n${currentResult.answer.eligibility.join('\n')}\n\nREQUIRED DOCUMENTS:\n${currentResult.answer.requiredDocuments.join('\n')}\n\nCITATIONS:\n${currentResult.answer.citations.map(c => `• ${c.documentTitle} (Page ${c.pageNumber})`).join('\n')}\n\n${currentResult.disclaimer}`;
    navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div
      style={{
        background: 'hsl(var(--primary-light) / 0.5)',
        border: '1px solid hsl(var(--primary) / 0.2)',
        borderRadius: 'var(--radius-md)',
        padding: '0.85rem 1.25rem',
        marginTop: '1rem',
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center',
        flexWrap: 'wrap',
        gap: '0.75rem',
      }}
    >
      <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', fontSize: '0.85rem' }}>
        <strong>Frontline Helpdesk Tools:</strong>
        <button
          type="button"
          className="chip"
          style={{ background: '#fff', fontSize: '0.78rem', padding: '0.25rem 0.65rem' }}
          onClick={handleCopyAnswer}
        >
          {copied ? '✅ Formatted Answer Copied!' : '📋 Copy Formatted Answer with Citations'}
        </button>
      </div>

      <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', fontSize: '0.82rem' }}>
        <span>Rate Answer Grounding:</span>
        <button
          type="button"
          className="chip"
          style={{ background: '#fff', padding: '0.2rem 0.6rem' }}
          onClick={() => handleFeedback(true)}
          disabled={feedbackSubmitted}
        >
          👍 Accurate Citations
        </button>
        <button
          type="button"
          className="chip"
          style={{ background: '#fff', padding: '0.2rem 0.6rem' }}
          onClick={() => handleFeedback(false)}
          disabled={feedbackSubmitted}
        >
          👎 Missing Detail
        </button>
        {feedbackSubmitted && (
          <span style={{ color: 'hsl(var(--success))', fontWeight: 600 }}>Logged!</span>
        )}
      </div>
    </div>
  );
};
