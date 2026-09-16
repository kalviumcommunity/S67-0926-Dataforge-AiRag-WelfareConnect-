import React, { useEffect, useState } from 'react';
import { DisclaimerBanner } from './components/DisclaimerBanner';
import { Navbar } from './components/Navbar';
import { LandingPage } from './pages/LandingPage';
import { AuthModal } from './components/AuthModal';
import { api, UserProfile } from './services/api';

export const App: React.FC = () => {
  const [currentUser, setCurrentUser] = useState<UserProfile | null>(null);
  const [isAuthModalOpen, setIsAuthModalOpen] = useState(false);

  useEffect(() => {
    async function checkExistingSession() {
      try {
        const user = await api.getProfile();
        setCurrentUser(user);
      } catch {
        // Guest/unauthenticated citizen session
        setCurrentUser(null);
      }
    }
    checkExistingSession();
  }, []);

  const handleLogout = () => {
    api.logout();
    setCurrentUser(null);
  };

  return (
    <>
      <DisclaimerBanner />
      <Navbar
        currentUser={currentUser}
        onOpenAuthModal={() => setIsAuthModalOpen(true)}
        onLogout={handleLogout}
      />
      <LandingPage currentUser={currentUser} />

      <AuthModal
        isOpen={isAuthModalOpen}
        onClose={() => setIsAuthModalOpen(false)}
        onSuccess={user => setCurrentUser(user)}
      />

      <footer className="footer">
        <div className="container">
          <p>
            &copy; {new Date().getFullYear()} Government Welfare Scheme Document Assistant. All
            scheme rules sourced from uploaded official publications.
          </p>
          <p style={{ fontSize: '0.75rem', marginTop: '0.25rem' }}>
            Answers strictly derived from official repositories with page-level verification.
            Non-statutory guidance.
          </p>
        </div>
      </footer>
    </>
  );
};

export default App;
