'use client';

import React, { useEffect, useState } from 'react';
import { AuthModal } from '../components/AuthModal';
import { CitationPreviewModal } from '../components/CitationPreviewModal';
import { DisclaimerBanner } from '../components/DisclaimerBanner';
import { HeroSearch } from '../components/HeroSearch';
import { Navbar } from '../components/Navbar';
import { SchemeCatalog } from '../components/SchemeCatalog';
import ApiService from '../lib/api';
import { AuthSessionResponse, Citation, Collection, User } from '../lib/types';

export default function HomePage() {
  const [collections, setCollections] = useState<Collection[]>([]);
  const [user, setUser] = useState<User | null>(null);
  const [isAuthModalOpen, setIsAuthModalOpen] = useState(false);
  const [activeCitation, setActiveCitation] = useState<Citation | null>(null);

  useEffect(() => {
    // Load active collections
    ApiService.getCollections()
      .then((data) => setCollections(data))
      .catch(() => {
        // Fallback demo collections if backend is warming up
        setCollections([
          {
            id: 'col-0000000-0000-4000-8000-000000000001',
            name: 'Housing & Urban Affairs (PMAY)',
            slug: 'housing-urban-affairs',
            description:
              'Official guidelines and circulars for Pradhan Mantri Awas Yojana Urban.',
            department: 'Ministry of Housing and Urban Affairs',
            is_active: true,
            total_documents: 3,
            created_at: new Date().toISOString(),
          },
          {
            id: 'col-0000000-0000-4000-8000-000000000002',
            name: 'Agriculture & Farmer Welfare (PM-Kisan)',
            slug: 'farmer-welfare-pmkisan',
            description:
              'Direct income support and operational circulars for farmer welfare.',
            department: 'Ministry of Agriculture & Farmers Welfare',
            is_active: true,
            total_documents: 2,
            created_at: new Date().toISOString(),
          },
        ]);
      });
  }, []);

  const handleLoginSuccess = (session: AuthSessionResponse) => {
    setUser(session.user);
  };

  const handleLogout = () => {
    setUser(null);
  };

  return (
    <div className="layout-container">
      <DisclaimerBanner />
      <Navbar
        user={user}
        onOpenAuthModal={() => setIsAuthModalOpen(true)}
        onLogout={handleLogout}
      />

      <main className="main-content">
        <HeroSearch
          collections={collections}
          onCitationClick={(citation) => setActiveCitation(citation)}
        />

        <SchemeCatalog collections={collections} />
      </main>

      <footer className="footer">
        <div style={{ maxWidth: '1200px', margin: '0 auto' }}>
          <p>
            <strong>WelfareConnect Document Assistant</strong> • Powered by Grounded Retrieval
            Augmented Generation (RAG)
          </p>
          <p style={{ fontSize: '0.75rem', marginTop: '0.35rem' }}>
            Built for citizens and government helpdesk operators to access verified welfare scheme
            regulations with zero hallucination.
          </p>
        </div>
      </footer>

      <AuthModal
        isOpen={isAuthModalOpen}
        onClose={() => setIsAuthModalOpen(false)}
        onLoginSuccess={handleLoginSuccess}
      />

      <CitationPreviewModal
        citation={activeCitation}
        onClose={() => setActiveCitation(null)}
      />
    </div>
  );
}
