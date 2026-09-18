'use client';

import React, { useEffect, useState } from 'react';
import ApiService from '../lib/api';
import { HealthStatus } from '../lib/types';

export const HealthStatusBadge: React.FC = () => {
  const [health, setHealth] = useState<HealthStatus | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let mounted = true;
    ApiService.getHealth()
      .then((data) => {
        if (mounted) {
          setHealth(data);
          setLoading(false);
        }
      })
      .catch(() => {
        if (mounted) {
          setHealth(null);
          setLoading(false);
        }
      });

    return () => {
      mounted = false;
    };
  }, []);

  if (loading) {
    return (
      <span style={{ fontSize: '0.8rem', color: '#64748b' }}>Checking system...</span>
    );
  }

  const isHealthy = health?.status === 'healthy';

  return (
    <div
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        gap: '0.4rem',
        padding: '0.25rem 0.6rem',
        borderRadius: '9999px',
        fontSize: '0.75rem',
        fontWeight: 600,
        background: isHealthy ? '#dcfce7' : '#fee2e2',
        color: isHealthy ? '#166534' : '#991b1b',
        border: `1px solid ${isHealthy ? '#86efac' : '#fca5a5'}`,
      }}
      title={`Backend version ${health?.version || '1.0.0'} (${health?.environment || 'unknown'})`}
    >
      <span
        style={{
          width: '6px',
          height: '6px',
          borderRadius: '50%',
          backgroundColor: isHealthy ? '#16a34a' : '#dc2626',
        }}
      />
      <span>{isHealthy ? 'System Online' : 'System Degraded'}</span>
    </div>
  );
};
