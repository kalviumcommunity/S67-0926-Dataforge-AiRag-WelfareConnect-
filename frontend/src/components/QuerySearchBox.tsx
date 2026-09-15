import React, { useState } from 'react';

interface QuerySearchBoxProps {
  onSearch: (query: string) => void;
  isLoading: boolean;
}

const SAMPLE_QUESTIONS = [
  'What is the land limit for PM-Kisan farmer subsidy?',
  'What documents are needed for senior citizen pension?',
  'Who is excluded from PM-Kisan benefits?',
];

export const QuerySearchBox: React.FC<QuerySearchBoxProps> = ({ onSearch, isLoading }) => {
  const [query, setQuery] = useState('');

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (query.trim() && !isLoading) {
      onSearch(query.trim());
    }
  };

  const handleSuggestionClick = (sample: string) => {
    setQuery(sample);
    onSearch(sample);
  };

  return (
    <form className="search-form" onSubmit={handleSubmit}>
      <div className="search-input-wrapper">
        <input
          type="text"
          className="search-input"
          placeholder="Ask a question about government welfare schemes (e.g. eligibility, documents, rules)..."
          value={query}
          onChange={e => setQuery(e.target.value)}
          disabled={isLoading}
        />
        <button type="submit" className="search-btn" disabled={isLoading || !query.trim()}>
          {isLoading ? (
            <span>Searching...</span>
          ) : (
            <>
              <svg
                width="16"
                height="16"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="2.5"
              >
                <circle cx="11" cy="11" r="8" />
                <line x1="21" y1="21" x2="16.65" y2="16.65" />
              </svg>
              <span>Search</span>
            </>
          )}
        </button>
      </div>

      <div className="suggestions-container">
        <span>Suggested Queries:</span>
        {SAMPLE_QUESTIONS.map((q, idx) => (
          <button
            key={idx}
            type="button"
            className="suggestion-pill"
            onClick={() => handleSuggestionClick(q)}
          >
            {q}
          </button>
        ))}
      </div>
    </form>
  );
};
