'use client';

import React, { useState } from 'react';
import ApiService, { EligibilityResult, QueryHistoryRecord } from '../lib/api';

interface HelpdeskToolbarProps {
  token: string;
}

export const HelpdeskToolbar: React.FC<HelpdeskToolbarProps> = ({ token }) => {
  const [activeTab, setActiveTab] = useState<'eligibility' | 'history'>('eligibility');
  const [annualIncome, setAnnualIncome] = useState<string>('250000');
  const [landholding, setLandholding] = useState<string>('1.5');
  const [eligResult, setEligResult] = useState<EligibilityResult | null>(null);
  const [historyRecords, setHistoryRecords] = useState<QueryHistoryRecord[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleEvaluateEligibility = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError(null);
    try {
      const res = await ApiService.checkEligibility(
        {
          annual_income: annualIncome ? parseFloat(annualIncome) : undefined,
          landholding_hectares: landholding ? parseFloat(landholding) : undefined,
        },
        token
      );
      setEligResult(res);
    } catch (err: any) {
      setError(err.message || 'Eligibility calculation failed');
    } finally {
      setLoading(false);
    }
  };

  const loadHistory = async () => {
    setActiveTab('history');
    setLoading(true);
    setError(null);
    try {
      const history = await ApiService.getQueryHistory(token);
      setHistoryRecords(history);
    } catch (err: any) {
      setError(err.message || 'Failed to fetch query history');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div
      style={{
        background: '#ffffff',
        border: '1px solid #bfdbfe',
        borderRadius: 'var(--radius-lg)',
        padding: '1.5rem',
        marginTop: '2rem',
        boxShadow: 'var(--shadow-md)',
      }}
    >
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          borderBottom: '1px solid var(--border-subtle)',
          paddingBottom: '0.75rem',
          marginBottom: '1rem',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
          <span style={{ fontSize: '1.25rem' }}>🎧</span>
          <h3 style={{ fontSize: '1.15rem', fontWeight: 700, color: 'var(--primary-900)' }}>
            Helpdesk Officer Toolkit
          </h3>
          <span
            style={{
              background: '#dbeafe',
              color: '#1e40af',
              fontSize: '0.75rem',
              fontWeight: 700,
              padding: '0.2rem 0.5rem',
              borderRadius: 'var(--radius-sm)',
            }}
          >
            ROLE: HELPDESK
          </span>
        </div>

        <div style={{ display: 'flex', gap: '0.5rem' }}>
          <button
            onClick={() => setActiveTab('eligibility')}
            style={{
              padding: '0.35rem 0.75rem',
              borderRadius: 'var(--radius-sm)',
              fontSize: '0.85rem',
              fontWeight: 600,
              background: activeTab === 'eligibility' ? 'var(--primary-600)' : 'var(--bg-subtle)',
              color: activeTab === 'eligibility' ? '#ffffff' : 'var(--text-main)',
            }}
          >
            Eligibility Calculator
          </button>
          <button
            onClick={loadHistory}
            style={{
              padding: '0.35rem 0.75rem',
              borderRadius: 'var(--radius-sm)',
              fontSize: '0.85rem',
              fontWeight: 600,
              background: activeTab === 'history' ? 'var(--primary-600)' : 'var(--bg-subtle)',
              color: activeTab === 'history' ? '#ffffff' : 'var(--text-main)',
            }}
          >
            Session History
          </button>
        </div>
      </div>

      {error && (
        <div
          style={{
            padding: '0.65rem 0.85rem',
            background: 'var(--status-danger-bg)',
            color: 'var(--status-danger)',
            borderRadius: 'var(--radius-sm)',
            fontSize: '0.85rem',
            marginBottom: '1rem',
          }}
        >
          {error}
        </div>
      )}

      {activeTab === 'eligibility' ? (
        <div>
          <form
            onSubmit={handleEvaluateEligibility}
            style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))',
              gap: '1rem',
              alignItems: 'end',
            }}
          >
            <div>
              <label style={{ display: 'block', fontSize: '0.8rem', fontWeight: 600, marginBottom: '0.3rem' }}>
                Annual Household Income (₹)
              </label>
              <input
                type="number"
                value={annualIncome}
                onChange={(e) => setAnnualIncome(e.target.value)}
                style={{
                  width: '100%',
                  padding: '0.5rem',
                  border: '1px solid var(--border-subtle)',
                  borderRadius: 'var(--radius-sm)',
                }}
                placeholder="250000"
              />
            </div>

            <div>
              <label style={{ display: 'block', fontSize: '0.8rem', fontWeight: 600, marginBottom: '0.3rem' }}>
                Cultivable Land (Hectares)
              </label>
              <input
                type="number"
                step="0.1"
                value={landholding}
                onChange={(e) => setLandholding(e.target.value)}
                style={{
                  width: '100%',
                  padding: '0.5rem',
                  border: '1px solid var(--border-subtle)',
                  borderRadius: 'var(--radius-sm)',
                }}
                placeholder="1.5"
              />
            </div>

            <div>
              <button
                type="submit"
                disabled={loading}
                style={{
                  width: '100%',
                  padding: '0.55rem',
                  background: 'var(--primary-700)',
                  color: 'white',
                  borderRadius: 'var(--radius-sm)',
                  fontWeight: 600,
                  fontSize: '0.9rem',
                }}
              >
                {loading ? 'Evaluating...' : 'Screen Eligibility'}
              </button>
            </div>
          </form>

          {eligResult && (
            <div
              style={{
                marginTop: '1.25rem',
                padding: '1rem',
                background: 'var(--bg-subtle)',
                borderRadius: 'var(--radius-md)',
              }}
            >
              <h4 style={{ fontSize: '0.95rem', fontWeight: 700, color: 'var(--primary-900)' }}>
                Evaluation Result Summary
              </h4>
              <p style={{ fontSize: '0.85rem', color: 'var(--text-muted)', marginBottom: '0.75rem' }}>
                {eligResult.evaluation_summary}
              </p>

              {eligResult.eligible_schemes.map((s, idx) => (
                <div
                  key={idx}
                  style={{
                    background: '#ffffff',
                    border: '1px solid #bbf7d0',
                    borderRadius: 'var(--radius-sm)',
                    padding: '0.75rem',
                    marginBottom: '0.5rem',
                  }}
                >
                  <div style={{ fontWeight: 700, color: '#15803d', fontSize: '0.9rem' }}>
                    ✓ {s.scheme_name}
                  </div>
                  <div style={{ fontSize: '0.8rem', color: 'var(--text-main)', marginTop: '0.2rem' }}>
                    <strong>Entitlement:</strong> {s.benefit}
                  </div>
                  <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginTop: '0.2rem' }}>
                    <strong>Source Rule:</strong> {s.citation}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      ) : (
        <div>
          <h4 style={{ fontSize: '0.95rem', fontWeight: 700, marginBottom: '0.75rem' }}>
            Recent Citizen Queries
          </h4>
          {historyRecords.length === 0 ? (
            <p style={{ fontSize: '0.85rem', color: 'var(--text-muted)' }}>No recent queries recorded.</p>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem', maxHeight: '300px', overflowY: 'auto' }}>
              {historyRecords.map((item) => (
                <div
                  key={item.id}
                  style={{
                    background: 'var(--bg-subtle)',
                    padding: '0.65rem 0.85rem',
                    borderRadius: 'var(--radius-sm)',
                    fontSize: '0.85rem',
                  }}
                >
                  <div style={{ fontWeight: 600, color: 'var(--primary-900)' }}>Q: {item.question}</div>
                  <div style={{ color: 'var(--text-muted)', marginTop: '0.2rem', fontSize: '0.8rem' }}>
                    A: {item.answer.substring(0, 150)}...
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
};
