import React from 'react';
import { CollectionItem } from '../services/api';

interface CollectionSelectorProps {
  collections: CollectionItem[];
  selectedId: string | null;
  onSelect: (id: string | null) => void;
}

export const CollectionSelector: React.FC<CollectionSelectorProps> = ({
  collections,
  selectedId,
  onSelect,
}) => {
  return (
    <div className="collection-bar">
      <label className="collection-label">Select Scheme Collection Scope</label>
      <div className="chips-container">
        <button
          type="button"
          className={`chip ${selectedId === null ? 'active' : ''}`}
          onClick={() => onSelect(null)}
        >
          All Active Collections ({collections.reduce((acc, c) => acc + (c.documentCount || 0), 0)}{' '}
          Docs)
        </button>
        {collections.map(col => (
          <button
            key={col.id}
            type="button"
            className={`chip ${selectedId === col.id ? 'active' : ''}`}
            onClick={() => onSelect(col.id)}
          >
            {col.name} ({col.documentCount || 0})
          </button>
        ))}
      </div>
    </div>
  );
};
