'use client';

import React from 'react';

export const DisclaimerBanner: React.FC = () => {
  return (
    <div className="disclaimer-banner" role="alert">
      <span>🛡️</span>
      <span>
        <strong>Official Notice:</strong> This assistant provides automated summaries derived strictly from uploaded official government documents. It does not replace legal scrutiny. Final eligibility is determined by designated government authorities.
      </span>
    </div>
  );
};
