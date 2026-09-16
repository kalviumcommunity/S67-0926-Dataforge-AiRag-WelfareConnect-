import React, { useEffect, useState } from 'react';
import { api, AuditEventItem, CollectionItem } from '../services/api';

interface AdminConsoleProps {
  collections: CollectionItem[];
  onRefreshCollections: () => void;
}

export const AdminConsole: React.FC<AdminConsoleProps> = ({
  collections,
  onRefreshCollections,
}) => {
  const [activeTab, setActiveTab] = useState<'upload' | 'audit'>('upload');
  const [auditLogs, setAuditLogs] = useState<AuditEventItem[]>([]);
  const [title, setTitle] = useState('');
  const [selectedCol, setSelectedCol] = useState(collections[0]?.id || '');
  const [department, setDepartment] = useState('Department of Agriculture & Farmers Welfare');
  const [uploadStatus, setUploadStatus] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (activeTab === 'audit') {
      loadAuditLogs();
    }
  }, [activeTab]);

  const loadAuditLogs = async () => {
    try {
      const logs = await api.getAuditLogs();
      setAuditLogs(logs);
    } catch (err: any) {
      console.error('Audit fetch error:', err);
    }
  };

  const handleUpload = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!title || !selectedCol) return;
    setLoading(true);
    setUploadStatus(null);

    try {
      const res = await api.uploadDocument({
        title,
        collectionId: selectedCol,
        department,
      });
      setUploadStatus(
        `Document accepted (Job ID: ${res.jobId}). Processing started in background.`
      );
      setTitle('');
      onRefreshCollections();
    } catch (err: any) {
      setUploadStatus(`Upload failed: ${err.message}`);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="answer-box" style={{ marginTop: '2rem' }}>
      <div className="answer-header">
        <div>
          <h3 style={{ fontSize: '1.25rem', color: 'hsl(var(--primary))' }}>
            Administrator Management Console
          </h3>
          <p style={{ fontSize: '0.82rem', color: 'hsl(var(--text-muted))' }}>
            Privileged document ingestion pipeline, collection management, and security audit log
            inspection.
          </p>
        </div>
        <div style={{ display: 'flex', gap: '0.5rem' }}>
          <button
            type="button"
            className={`chip ${activeTab === 'upload' ? 'active' : ''}`}
            onClick={() => setActiveTab('upload')}
          >
            📄 Document Ingestion
          </button>
          <button
            type="button"
            className={`chip ${activeTab === 'audit' ? 'active' : ''}`}
            onClick={() => setActiveTab('audit')}
          >
            🛡️ Security Audit Logs
          </button>
        </div>
      </div>

      {activeTab === 'upload' && (
        <form
          onSubmit={handleUpload}
          style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}
        >
          {uploadStatus && (
            <div className="disclaimer-banner" style={{ borderRadius: 'var(--radius-sm)' }}>
              {uploadStatus}
            </div>
          )}

          <div>
            <label className="collection-label">Official Document Title / Circular</label>
            <input
              type="text"
              className="search-input"
              style={{ fontSize: '0.95rem', padding: '0.75rem 1rem' }}
              placeholder="e.g. National Social Assistance Programme Circular 2026.pdf"
              value={title}
              onChange={e => setTitle(e.target.value)}
              required
            />
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem' }}>
            <div>
              <label className="collection-label">Target Collection</label>
              <select
                className="search-input"
                style={{ fontSize: '0.95rem', padding: '0.75rem 1rem' }}
                value={selectedCol}
                onChange={e => setSelectedCol(e.target.value)}
                required
              >
                {collections.map(c => (
                  <option key={c.id} value={c.id}>
                    {c.name}
                  </option>
                ))}
              </select>
            </div>

            <div>
              <label className="collection-label">Issuing Department</label>
              <input
                type="text"
                className="search-input"
                style={{ fontSize: '0.95rem', padding: '0.75rem 1rem' }}
                value={department}
                onChange={e => setDepartment(e.target.value)}
                required
              />
            </div>
          </div>

          <button
            type="submit"
            className="search-btn"
            style={{
              position: 'static',
              width: '220px',
              justifyContent: 'center',
              marginTop: '0.5rem',
            }}
            disabled={loading}
          >
            {loading ? 'Submitting...' : 'Upload & Process PDF'}
          </button>
        </form>
      )}

      {activeTab === 'audit' && (
        <div>
          <div style={{ maxHeight: '350px', overflowY: 'auto' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.82rem' }}>
              <thead>
                <tr style={{ background: 'hsl(var(--bg-main))', textAlign: 'left' }}>
                  <th style={{ padding: '0.6rem' }}>Timestamp</th>
                  <th style={{ padding: '0.6rem' }}>Action Type</th>
                  <th style={{ padding: '0.6rem' }}>Entity Table</th>
                  <th style={{ padding: '0.6rem' }}>Actor User ID</th>
                  <th style={{ padding: '0.6rem' }}>Client IP</th>
                </tr>
              </thead>
              <tbody>
                {auditLogs.map((log, idx) => (
                  <tr
                    key={log.id || idx}
                    style={{ borderBottom: '1px solid hsl(var(--border-subtle))' }}
                  >
                    <td style={{ padding: '0.6rem' }}>
                      {new Date(log.createdAt).toLocaleString()}
                    </td>
                    <td style={{ padding: '0.6rem' }}>
                      <span
                        className="disclaimer-badge"
                        style={{ background: 'hsl(var(--primary))' }}
                      >
                        {log.actionType}
                      </span>
                    </td>
                    <td style={{ padding: '0.6rem' }}>
                      <code>{log.entityTable}</code>
                    </td>
                    <td style={{ padding: '0.6rem' }}>
                      {log.actorUserId ? (
                        <code>{log.actorUserId.slice(0, 8)}...</code>
                      ) : (
                        'Anonymous'
                      )}
                    </td>
                    <td style={{ padding: '0.6rem' }}>{log.clientIpMasked || '127.0.0.1'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
};
