'use client';

import React, { useEffect, useState } from 'react';
import ApiService, { AuditLogRecord } from '../lib/api';
import { Collection, SchemeDocument } from '../lib/types';

interface AdminConsoleProps {
  token: string;
  collections: Collection[];
  onRefreshCollections: () => void;
}

export const AdminConsole: React.FC<AdminConsoleProps> = ({
  token,
  collections,
  onRefreshCollections,
}) => {
  const [activeTab, setActiveTab] = useState<'documents' | 'upload' | 'collections' | 'audit'>('documents');
  const [documents, setDocuments] = useState<SchemeDocument[]>([]);
  const [auditLogs, setAuditLogs] = useState<AuditLogRecord[]>([]);
  const [loading, setLoading] = useState(false);
  const [statusMessage, setStatusMessage] = useState<string | null>(null);

  // Upload Form State
  const [schemeName, setSchemeName] = useState('');
  const [department, setDepartment] = useState('');
  const [collectionId, setCollectionId] = useState('');
  const [filename, setFilename] = useState('');

  // Collection Form State
  const [newColName, setNewColName] = useState('');
  const [newColSlug, setNewColSlug] = useState('');
  const [newColDesc, setNewColDesc] = useState('');

  const loadDocuments = async () => {
    setLoading(true);
    try {
      const docs = await ApiService.getDocuments(undefined, true, token);
      setDocuments(docs);
    } catch (err: any) {
      setStatusMessage(`Error: ${err.message}`);
    } finally {
      setLoading(false);
    }
  };

  const loadAuditLogs = async () => {
    setActiveTab('audit');
    setLoading(true);
    try {
      const logs = await ApiService.getAuditLogs(token);
      setAuditLogs(logs);
    } catch (err: any) {
      setStatusMessage(`Error: ${err.message}`);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadDocuments();
  }, [token]);

  const handleUpload = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!collectionId || !schemeName || !department || !filename) return;

    setLoading(true);
    setStatusMessage(null);
    try {
      await ApiService.uploadDocument(
        {
          collection_id: collectionId,
          scheme_name: schemeName,
          department,
          original_filename: filename,
        },
        token
      );
      setStatusMessage(`Document '${schemeName}' uploaded successfully.`);
      setSchemeName('');
      setDepartment('');
      setFilename('');
      loadDocuments();
      setActiveTab('documents');
    } catch (err: any) {
      setStatusMessage(`Upload failed: ${err.message}`);
    } finally {
      setLoading(false);
    }
  };

  const handleCreateCollection = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newColName || !newColSlug) return;

    setLoading(true);
    setStatusMessage(null);
    try {
      await ApiService.createCollection(
        {
          name: newColName,
          slug: newColSlug,
          description: newColDesc,
        },
        token
      );
      setStatusMessage(`Collection '${newColName}' created successfully.`);
      setNewColName('');
      setNewColSlug('');
      setNewColDesc('');
      onRefreshCollections();
    } catch (err: any) {
      setStatusMessage(`Collection creation failed: ${err.message}`);
    } finally {
      setLoading(false);
    }
  };

  const handleProcess = async (docId: string) => {
    setLoading(true);
    try {
      await ApiService.processDocument(docId, token);
      setStatusMessage('Document re-indexing triggered.');
      loadDocuments();
    } catch (err: any) {
      setStatusMessage(`Processing error: ${err.message}`);
    } finally {
      setLoading(false);
    }
  };

  const handleArchive = async (docId: string) => {
    setLoading(true);
    try {
      await ApiService.archiveDocument(docId, token);
      setStatusMessage('Document archived.');
      loadDocuments();
    } catch (err: any) {
      setStatusMessage(`Archive error: ${err.message}`);
    } finally {
      setLoading(false);
    }
  };

  const handleDelete = async (docId: string) => {
    if (!confirm('Are you sure you want to delete this official document?')) return;
    setLoading(true);
    try {
      await ApiService.deleteDocument(docId, token);
      setStatusMessage('Document deleted.');
      loadDocuments();
    } catch (err: any) {
      setStatusMessage(`Delete error: ${err.message}`);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div
      style={{
        background: '#ffffff',
        border: '1px solid #fed7aa',
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
          <span style={{ fontSize: '1.25rem' }}>⚙️</span>
          <h3 style={{ fontSize: '1.15rem', fontWeight: 700, color: 'var(--primary-900)' }}>
            Administrator Management Console
          </h3>
          <span
            style={{
              background: '#ffedd5',
              color: '#9a3412',
              fontSize: '0.75rem',
              fontWeight: 700,
              padding: '0.2rem 0.5rem',
              borderRadius: 'var(--radius-sm)',
            }}
          >
            PRIVILEGED ACCESS
          </span>
        </div>

        <div style={{ display: 'flex', gap: '0.5rem' }}>
          <button
            onClick={() => setActiveTab('documents')}
            style={{
              padding: '0.35rem 0.75rem',
              borderRadius: 'var(--radius-sm)',
              fontSize: '0.85rem',
              fontWeight: 600,
              background: activeTab === 'documents' ? 'var(--primary-700)' : 'var(--bg-subtle)',
              color: activeTab === 'documents' ? '#ffffff' : 'var(--text-main)',
            }}
          >
            Documents ({documents.length})
          </button>
          <button
            onClick={() => setActiveTab('upload')}
            style={{
              padding: '0.35rem 0.75rem',
              borderRadius: 'var(--radius-sm)',
              fontSize: '0.85rem',
              fontWeight: 600,
              background: activeTab === 'upload' ? 'var(--primary-700)' : 'var(--bg-subtle)',
              color: activeTab === 'upload' ? '#ffffff' : 'var(--text-main)',
            }}
          >
            Upload PDF
          </button>
          <button
            onClick={() => setActiveTab('collections')}
            style={{
              padding: '0.35rem 0.75rem',
              borderRadius: 'var(--radius-sm)',
              fontSize: '0.85rem',
              fontWeight: 600,
              background: activeTab === 'collections' ? 'var(--primary-700)' : 'var(--bg-subtle)',
              color: activeTab === 'collections' ? '#ffffff' : 'var(--text-main)',
            }}
          >
            Collections
          </button>
          <button
            onClick={loadAuditLogs}
            style={{
              padding: '0.35rem 0.75rem',
              borderRadius: 'var(--radius-sm)',
              fontSize: '0.85rem',
              fontWeight: 600,
              background: activeTab === 'audit' ? 'var(--primary-700)' : 'var(--bg-subtle)',
              color: activeTab === 'audit' ? '#ffffff' : 'var(--text-main)',
            }}
          >
            Audit Logs
          </button>
        </div>
      </div>

      {statusMessage && (
        <div
          style={{
            padding: '0.65rem 0.85rem',
            background: 'var(--primary-50)',
            color: 'var(--primary-800)',
            borderRadius: 'var(--radius-sm)',
            fontSize: '0.85rem',
            marginBottom: '1rem',
          }}
        >
          {statusMessage}
        </div>
      )}

      {/* Tab 1: Documents List */}
      {activeTab === 'documents' && (
        <div style={{ overflowX: 'auto' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.85rem' }}>
            <thead>
              <tr style={{ background: 'var(--bg-subtle)', textAlign: 'left' }}>
                <th style={{ padding: '0.6rem' }}>Scheme Title</th>
                <th style={{ padding: '0.6rem' }}>Department</th>
                <th style={{ padding: '0.6rem' }}>Version</th>
                <th style={{ padding: '0.6rem' }}>Status</th>
                <th style={{ padding: '0.6rem' }}>Actions</th>
              </tr>
            </thead>
            <tbody>
              {documents.map((doc) => (
                <tr key={doc.id} style={{ borderBottom: '1px solid var(--border-subtle)' }}>
                  <td style={{ padding: '0.6rem', fontWeight: 600 }}>{doc.title}</td>
                  <td style={{ padding: '0.6rem' }}>{doc.department || 'N/A'}</td>
                  <td style={{ padding: '0.6rem' }}>v{doc.current_version}</td>
                  <td style={{ padding: '0.6rem' }}>
                    <span
                      style={{
                        padding: '0.2rem 0.5rem',
                        borderRadius: '4px',
                        fontSize: '0.75rem',
                        fontWeight: 700,
                        background:
                          doc.status === 'ACTIVE'
                            ? '#dcfce7'
                            : doc.status === 'ARCHIVED'
                            ? '#fef3c7'
                            : '#fee2e2',
                        color:
                          doc.status === 'ACTIVE'
                            ? '#166534'
                            : doc.status === 'ARCHIVED'
                            ? '#92400e'
                            : '#991b1b',
                      }}
                    >
                      {doc.status}
                    </span>
                  </td>
                  <td style={{ padding: '0.6rem', display: 'flex', gap: '0.35rem' }}>
                    <button
                      onClick={() => handleProcess(doc.id)}
                      style={{
                        padding: '0.25rem 0.5rem',
                        background: 'var(--primary-100)',
                        color: 'var(--primary-700)',
                        borderRadius: '4px',
                        fontSize: '0.75rem',
                        fontWeight: 600,
                      }}
                    >
                      Process
                    </button>
                    {doc.status !== 'ARCHIVED' && (
                      <button
                        onClick={() => handleArchive(doc.id)}
                        style={{
                          padding: '0.25rem 0.5rem',
                          background: '#fef3c7',
                          color: '#92400e',
                          borderRadius: '4px',
                          fontSize: '0.75rem',
                          fontWeight: 600,
                        }}
                      >
                        Archive
                      </button>
                    )}
                    <button
                      onClick={() => handleDelete(doc.id)}
                      style={{
                        padding: '0.25rem 0.5rem',
                        background: '#fee2e2',
                        color: '#991b1b',
                        borderRadius: '4px',
                        fontSize: '0.75rem',
                        fontWeight: 600,
                      }}
                    >
                      Delete
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Tab 2: Upload Document */}
      {activeTab === 'upload' && (
        <form onSubmit={handleUpload} style={{ display: 'flex', flexDirection: 'column', gap: '1rem', maxWidth: '600px' }}>
          <div>
            <label style={{ display: 'block', fontSize: '0.85rem', fontWeight: 600, marginBottom: '0.3rem' }}>
              Select Scheme Collection
            </label>
            <select
              value={collectionId}
              onChange={(e) => setCollectionId(e.target.value)}
              required
              style={{ width: '100%', padding: '0.5rem', borderRadius: 'var(--radius-sm)', border: '1px solid var(--border-subtle)' }}
            >
              <option value="">Choose a collection...</option>
              {collections.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.name}
                </option>
              ))}
            </select>
          </div>

          <div>
            <label style={{ display: 'block', fontSize: '0.85rem', fontWeight: 600, marginBottom: '0.3rem' }}>
              Scheme Title
            </label>
            <input
              type="text"
              required
              value={schemeName}
              onChange={(e) => setSchemeName(e.target.value)}
              placeholder="e.g., National Apprenticeship Training Scheme"
              style={{ width: '100%', padding: '0.5rem', borderRadius: 'var(--radius-sm)', border: '1px solid var(--border-subtle)' }}
            />
          </div>

          <div>
            <label style={{ display: 'block', fontSize: '0.85rem', fontWeight: 600, marginBottom: '0.3rem' }}>
              Issuing Ministry / Department
            </label>
            <input
              type="text"
              required
              value={department}
              onChange={(e) => setDepartment(e.target.value)}
              placeholder="e.g., Ministry of Skill Development"
              style={{ width: '100%', padding: '0.5rem', borderRadius: 'var(--radius-sm)', border: '1px solid var(--border-subtle)' }}
            />
          </div>

          <div>
            <label style={{ display: 'block', fontSize: '0.85rem', fontWeight: 600, marginBottom: '0.3rem' }}>
              Official PDF Filename
            </label>
            <input
              type="text"
              required
              value={filename}
              onChange={(e) => setFilename(e.target.value)}
              placeholder="e.g., NATS_Operational_Manual_2024.pdf"
              style={{ width: '100%', padding: '0.5rem', borderRadius: 'var(--radius-sm)', border: '1px solid var(--border-subtle)' }}
            />
          </div>

          <button
            type="submit"
            disabled={loading}
            style={{
              padding: '0.65rem',
              background: 'var(--primary-700)',
              color: 'white',
              borderRadius: 'var(--radius-sm)',
              fontWeight: 600,
            }}
          >
            {loading ? 'Uploading & Indexing...' : 'Upload Official Document'}
          </button>
        </form>
      )}

      {/* Tab 3: Create Collection */}
      {activeTab === 'collections' && (
        <form onSubmit={handleCreateCollection} style={{ display: 'flex', flexDirection: 'column', gap: '1rem', maxWidth: '600px' }}>
          <div>
            <label style={{ display: 'block', fontSize: '0.85rem', fontWeight: 600, marginBottom: '0.3rem' }}>
              Collection Name
            </label>
            <input
              type="text"
              required
              value={newColName}
              onChange={(e) => {
                setNewColName(e.target.value);
                setNewColSlug(e.target.value.toLowerCase().replace(/[^a-z0-9]+/g, '-'));
              }}
              placeholder="e.g., Skill Development & Livelihood"
              style={{ width: '100%', padding: '0.5rem', borderRadius: 'var(--radius-sm)', border: '1px solid var(--border-subtle)' }}
            />
          </div>

          <div>
            <label style={{ display: 'block', fontSize: '0.85rem', fontWeight: 600, marginBottom: '0.3rem' }}>
              Slug
            </label>
            <input
              type="text"
              required
              value={newColSlug}
              onChange={(e) => setNewColSlug(e.target.value)}
              style={{ width: '100%', padding: '0.5rem', borderRadius: 'var(--radius-sm)', border: '1px solid var(--border-subtle)' }}
            />
          </div>

          <div>
            <label style={{ display: 'block', fontSize: '0.85rem', fontWeight: 600, marginBottom: '0.3rem' }}>
              Description
            </label>
            <textarea
              value={newColDesc}
              onChange={(e) => setNewColDesc(e.target.value)}
              placeholder="Brief description of schemes in this collection..."
              style={{ width: '100%', padding: '0.5rem', borderRadius: 'var(--radius-sm)', border: '1px solid var(--border-subtle)', minHeight: '80px' }}
            />
          </div>

          <button
            type="submit"
            disabled={loading}
            style={{
              padding: '0.65rem',
              background: 'var(--primary-700)',
              color: 'white',
              borderRadius: 'var(--radius-sm)',
              fontWeight: 600,
            }}
          >
            Create Scheme Collection
          </button>
        </form>
      )}

      {/* Tab 4: Audit Logs */}
      {activeTab === 'audit' && (
        <div style={{ overflowX: 'auto', maxHeight: '400px' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.8rem' }}>
            <thead>
              <tr style={{ background: 'var(--bg-subtle)', textAlign: 'left' }}>
                <th style={{ padding: '0.5rem' }}>Timestamp</th>
                <th style={{ padding: '0.5rem' }}>Action</th>
                <th style={{ padding: '0.5rem' }}>Entity</th>
                <th style={{ padding: '0.5rem' }}>IP</th>
              </tr>
            </thead>
            <tbody>
              {auditLogs.map((log) => (
                <tr key={log.id} style={{ borderBottom: '1px solid var(--border-subtle)' }}>
                  <td style={{ padding: '0.5rem' }}>{log.created_at ? new Date(log.created_at).toLocaleString() : 'N/A'}</td>
                  <td style={{ padding: '0.5rem', fontWeight: 700, color: 'var(--primary-800)' }}>{log.action}</td>
                  <td style={{ padding: '0.5rem' }}>{log.entity_type} ({log.entity_id || 'system'})</td>
                  <td style={{ padding: '0.5rem' }}>{log.ip_address || '127.0.0.1'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
};
