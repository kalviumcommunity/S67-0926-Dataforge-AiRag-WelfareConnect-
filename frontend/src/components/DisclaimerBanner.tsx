import React from 'react';

export const DisclaimerBanner: React.FC = () => {
  return (
    <aside className="disclaimer-banner" aria-label="Official Non-Guarantee Legal Disclaimer">
      <div className="container">
        <span className="disclaimer-badge">Official Disclaimer</span>
        <span>
          This assistant provides informational guidance derived solely from published official PDF
          documents. It does not constitute statutory legal advice, nor does it guarantee scheme
          eligibility.
        </span>
      </div>
    </aside>
  );
};
