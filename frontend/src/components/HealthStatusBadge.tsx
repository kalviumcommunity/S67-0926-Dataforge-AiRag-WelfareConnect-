import React, { useEffect, useState } from 'react';
import { api, HealthData } from '../services/api';

export const HealthStatusBadge: React.FC = () => {
  const [health, setHealth] = useState<HealthData | null>(null);
  const [error, setError] = useState(false);

  useEffect(() => {
    let mounted = true;

    async function checkHealth() {
      try {
        const data = await api.getHealth();
        if (mounted) {
          setHealth(data);
          setError(false);
        }
      } catch (err) {
        if (mounted) setError(true);
      }
    }

    checkHealth();
    const interval = setInterval(checkHealth, 30000);
    return () => {
      mounted = false;
      clearInterval(interval);
    };
  }, []);

  return (
    <div
      className="health-pill"
      title={
        health
          ? `API Uptime: ${health.uptimeSeconds}s | Version: ${health.version}`
          : 'Connecting...'
      }
    >
      <span
        className="health-dot"
        style={{
          backgroundColor: error ? 'hsl(var(--danger))' : 'hsl(var(--success))',
          boxShadow: error ? '0 0 8px hsl(var(--danger))' : '0 0 8px hsl(var(--success))',
        }}
      />
      <span>{error ? 'API Offline' : health ? 'Services Operational' : 'Checking API...'}</span>
    </div>
  );
};
