import React, { useEffect, useState } from 'react';
import { api, CollectionItem, QueryResult, CitationItem } from '../services/api';
import { CollectionSelector } from '../components/CollectionSelector';
import { QuerySearchBox } from '../components/QuerySearchBox';
import { AnswerCard } from '../components/AnswerCard';
import { SourcePreviewModal } from '../components/SourcePreviewModal';

export const LandingPage: React.FC = () => {
  const [collections, setCollections] = useState<CollectionItem[]>([]);
  const [selectedCollection, setSelectedCollection] = useState<string | null>(null);
  const [queryResult, setQueryResult] = useState<QueryResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [previewCitation, setPreviewCitation] = useState<CitationItem | null>(null);

  useEffect(() => {
    async function loadCatalog() {
      try {
        const data = await api.getCollections();
        setCollections(data);
      } catch (err) {
        console.error('Failed to load collections:', err);
      }
    }
    loadCatalog();
  }, []);

  const handleSearch = async (queryText: string) => {
    setLoading(true);
    setQueryResult(null);
    try {
      const collectionScope = selectedCollection ? [selectedCollection] : [];
      const res = await api.submitQuery(queryText, collectionScope);
      setQueryResult(res);
    } catch (err) {
      console.error('Query execution error:', err);
      setQueryResult({
        queryId: 'err',
        status: 'ERROR',
        isGrounded: false,
        fallbackMessage: 'Unable to process query. Please ensure backend services are active.',
        disclaimer: 'Official documents only.',
        latencyMs: 0,
      });
    } finally {
      setLoading(false);
    }
  };

  return (
    <main className="container">
      {/* Hero Header */}
      <section className="hero-section">
        <h2 className="hero-title">Official Welfare Scheme Intelligence</h2>
        <p className="hero-subtitle">
          Search verified government scheme circulars, eligibility thresholds, mandatory documents,
          and procedures with exact page-level citations.
        </p>
      </section>

      {/* Main Search and Query Interface */}
      <section className="query-card">
        <CollectionSelector
          collections={collections}
          selectedId={selectedCollection}
          onSelect={setSelectedCollection}
        />
        <QuerySearchBox onSearch={handleSearch} isLoading={loading} />
      </section>

      {/* Results Display */}
      {queryResult && <AnswerCard result={queryResult} onPreviewCitation={setPreviewCitation} />}

      {/* Excerpt Modal */}
      <SourcePreviewModal citation={previewCitation} onClose={() => setPreviewCitation(null)} />
    </main>
  );
};
