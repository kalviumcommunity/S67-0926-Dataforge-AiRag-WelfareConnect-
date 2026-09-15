import React from 'react';
import { DisclaimerBanner } from './components/DisclaimerBanner';
import { Navbar } from './components/Navbar';
import { LandingPage } from './pages/LandingPage';

export const App: React.FC = () => {
  return (
    <>
      <DisclaimerBanner />
      <Navbar />
      <LandingPage />
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
