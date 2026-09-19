'use client';

import React, { useEffect, useRef, useState } from 'react';
import ApiService, { AuditLogRecord } from '../lib/api';
import { Collection, SchemeDocument } from '../lib/types';

interface AdminConsoleProps {
  token: string;
  collections: Collection[];
  onRefreshCollections: () => void;
}

const MAX_FILE_SIZE_MB = 50;
const MAX_FILE_SIZE_BYTES = MAX_FILE_SIZE_MB * 1024 * 1024;

export const AdminConsole: React.FC<AdminConsoleProps> = ({
  token,
  collections,
  onRefreshCollections,
}) => {
  const [activeTab, setActiveTab] = useState<'documents' | 'upload' | 'collections' | 'audit'>('documents');
  const [documents, setDocuments] = useState<SchemeDocument[]>([]);
  const [auditLogs, setAuditLogs] = useState<AuditLogRecord[]>([]);
  const [conflicts, setConflicts] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);
  const [statusMessage, setStatusMessage] = useState<{ type: 'success' | 'error' | 'warning'; text: string } | null>(null);

  // Upload Form State
  const [isCreatingInlineCol, setIsCreatingInlineCol] = useState(false);
  const [inlineColName, setInlineColName] = useState('');
  const [inlineColSlug, setInlineColSlug] = useState('');
  const [inlineColDesc, setInlineColDesc] = useState('');

  const [selectedColId, setSelectedColId] = useState('');
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [schemeName, setSchemeName] = useState('');
  const [department, setDepartment] = useState('');
  const [stateOrDistrict, setStateOrDistrict] = useState('National / All States');
  const [language, setLanguage] = useState('en');
  const [publicationDate, setPublicationDate] = useState('');
  const [effectiveDate, setEffectiveDate] = useState('');
  const [versionNumber, setVersionNumber] = useState(1);
  const [visibility, setVisibility] = useState<'public' | 'restricted'>('public');
  const [isOfficialConfirmed, setIsOfficialConfirmed] = useState(false);

  // Upload Progress & Validation States
  const [uploadProgress, setUploadProgress] = useState<number | null>(null);
  const [fileValidationError, setFileValidationError] = useState<string | null>(null);
  const [duplicateWarning, setDuplicateWarning] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement | null>(null);

  // Collection Management Tab State
  const [newColName, setNewColName] = useState('');
  const [newColSlug, setNewColSlug] = useState('');
  const [newColDesc, setNewColDesc] = useState('');

  const loadDocuments = async () => {
    setLoading(true);
    try {
      const [docs, conflictsData] = await Promise.all([
        ApiService.getDocuments(undefined, true, token),
        ApiService.getConflicts(undefined, token).catch(() => []),
      ]);
      setDocuments(docs);
      setConflicts(conflictsData || []);
    } catch (err: any) {
      setStatusMessage({ type: 'error', text: `Failed to load documents: ${err.message}` });
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
      setStatusMessage({ type: 'error', text: `Failed to load audit logs: ${err.message}` });
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadDocuments();
  }, [token]);

  // Handle File Drag & Selection with Validation
  const handleFileChange = (file: File | null) => {
    setFileValidationError(null);
    setDuplicateWarning(null);

    if (!file) {
      setSelectedFile(null);
      return;
    }

    // 1. File Type Check
    if (!file.name.toLowerCase().endsWith('.pdf') && file.type !== 'application/pdf') {
      setFileValidationError('Invalid file type. Only official PDF documents (.pdf) are supported.');
      setSelectedFile(null);
      return;
    }

    // 2. File Size Limit Check
    if (file.size > MAX_FILE_SIZE_BYTES) {
      setFileValidationError(
        `File size (${(file.size / (1024 * 1024)).toFixed(2)} MB) exceeds the maximum allowed limit of ${MAX_FILE_SIZE_MB} MB.`
      );
      setSelectedFile(null);
      return;
    }

    if (file.size === 0) {
      setFileValidationError('The selected PDF file is empty (0 bytes).');
      setSelectedFile(null);
      return;
    }

    setSelectedFile(file);

    // Auto-fill scheme title if empty
    if (!schemeName) {
      const cleanName = file.name.replace(/\.pdf$/i, '').replace(/[-_]+/g, ' ');
      setSchemeName(cleanName);
    }
  };

  const handleUploadSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setFileValidationError(null);
    setDuplicateWarning(null);
    setStatusMessage(null);

    // Frontend Validations
    let targetColId = selectedColId;

    if (isCreatingInlineCol) {
      if (!inlineColName.trim()) {
        setFileValidationError('Please enter a name for the new collection.');
        return;
      }
      try {
        setLoading(true);
        const createdCol = await ApiService.createCollection(
          {
            name: inlineColName.trim(),
            slug: inlineColSlug.trim() || inlineColName.toLowerCase().replace(/[^a-z0-9]+/g, '-'),
            description: inlineColDesc.trim(),
          },
          token
        );
        targetColId = createdCol.id;
        onRefreshCollections();
        setIsCreatingInlineCol(false);
      } catch (err: any) {
        setLoading(false);
        setFileValidationError(`Failed to create collection: ${err.message}`);
        return;
      }
    }

    if (!targetColId) {
      setFileValidationError('Please select or create a target document collection.');
      return;
    }

    if (!selectedFile) {
      setFileValidationError('Please select an official government PDF document to upload.');
      return;
    }

    if (!schemeName.trim()) {
      setFileValidationError('Please specify the scheme name.');
      return;
    }

    if (!department.trim()) {
      setFileValidationError('Please specify the issuing Ministry or Department.');
      return;
    }

    if (!isOfficialConfirmed) {
      setFileValidationError('You must confirm that this is an official government publication.');
      return;
    }

    setLoading(true);
    setUploadProgress(10);

    try {
      const formData = new FormData();
      formData.append('file', selectedFile);
      formData.append('collection_id', targetColId);
      formData.append('scheme_name', schemeName.trim());
      formData.append('department', department.trim());
      formData.append('state_or_district', stateOrDistrict.trim() || 'National / All States');
      formData.append('language', language);
      if (publicationDate) formData.append('publication_date', publicationDate);
      if (effectiveDate) formData.append('effective_date', effectiveDate);
      formData.append('version_number', versionNumber.toString());
      formData.append('visibility', visibility);
      formData.append('is_official_source_confirmed', 'true');

      const uploadedDoc = await ApiService.uploadDocumentFile(
        formData,
        token,
        (percent) => {
          setUploadProgress(percent);
        }
      );

      setUploadProgress(100);

      if (uploadedDoc.duplicate_warning) {
        setDuplicateWarning(uploadedDoc.duplicate_warning);
      }

      setStatusMessage({
        type: uploadedDoc.duplicate_warning ? 'warning' : 'success',
        text: `Official scheme document '${uploadedDoc.title}' uploaded and indexed successfully.`,
      });

      // Reset form
      setSelectedFile(null);
      setSchemeName('');
      setDepartment('');
      setPublicationDate('');
      setEffectiveDate('');
      setVersionNumber(1);
      setIsOfficialConfirmed(false);
      if (fileInputRef.current) fileInputRef.current.value = '';

      await loadDocuments();
      setTimeout(() => {
        setUploadProgress(null);
        setActiveTab('documents');
      }, 1200);
    } catch (err: any) {
      setUploadProgress(null);
      setFileValidationError(err.message || 'Failed to upload document.');
    } finally {
      setLoading(false);
    }
  };

  const handleCreateCollection = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newColName.trim() || !newColSlug.trim()) return;

    setLoading(true);
    setStatusMessage(null);
    try {
      await ApiService.createCollection(
        {
          name: newColName.trim(),
          slug: newColSlug.trim(),
          description: newColDesc.trim(),
        },
        token
      );
      setStatusMessage({
        type: 'success',
        text: `Scheme collection '${newColName}' created successfully.`,
      });
      setNewColName('');
      setNewColSlug('');
      setNewColDesc('');
      onRefreshCollections();
    } catch (err: any) {
      setStatusMessage({
        type: 'error',
        text: `Collection creation failed: ${err.message}`,
      });
    } finally {
      setLoading(false);
    }
  };

  const handleProcess = async (docId: string) => {
    setLoading(true);
    try {
      await ApiService.processDocument(docId, token);
      setStatusMessage({ type: 'success', text: 'Document re-indexing triggered.' });
      await loadDocuments();
    } catch (err: any) {
      setStatusMessage({ type: 'error', text: `Processing error: ${err.message}` });
    } finally {
      setLoading(false);
    }
  };

  const handleArchive = async (docId: string) => {
    setLoading(true);
    try {
      await ApiService.archiveDocument(docId, token);
      setStatusMessage({ type: 'success', text: 'Document archived from public search.' });
      await loadDocuments();
    } catch (err: any) {
      setStatusMessage({ type: 'error', text: `Archive error: ${err.message}` });
    } finally {
      setLoading(false);
    }
  };

  const handleRestore = async (docId: string) => {
    setLoading(true);
    try {
      await ApiService.restoreDocument(docId, token);
      setStatusMessage({ type: 'success', text: 'Archived document restored to active search.' });
      await loadDocuments();
    } catch (err: any) {
      setStatusMessage({ type: 'error', text: `Restore error: ${err.message}` });
    } finally {
      setLoading(false);
    }
  };


  const handleDelete = async (docId: string) => {
    if (!confirm('Are you sure you want to permanently delete this scheme document?')) return;
    setLoading(true);
    try {
      await ApiService.deleteDocument(docId, token);
      setStatusMessage({ type: 'success', text: 'Document removed.' });
      await loadDocuments();
    } catch (err: any) {
      setStatusMessage({ type: 'error', text: `Delete error: ${err.message}` });
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
      {/* Console Header */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          borderBottom: '1px solid var(--border-subtle)',
          paddingBottom: '0.85rem',
          marginBottom: '1.25rem',
          flexWrap: 'wrap',
          gap: '0.75rem',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem' }}>
          <span style={{ fontSize: '1.35rem' }}>⚙️</span>
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
              <h3 style={{ fontSize: '1.2rem', fontWeight: 700, color: 'var(--primary-900)', margin: 0 }}>
                Administrator Management Portal
              </h3>
              <span
                style={{
                  background: '#ffedd5',
                  color: '#9a3412',
                  fontSize: '0.7rem',
                  fontWeight: 700,
                  padding: '0.2rem 0.5rem',
                  borderRadius: 'var(--radius-sm)',
                  letterSpacing: '0.5px',
                }}
              >
                GOVT ADMIN
              </span>
            </div>
            <p style={{ fontSize: '0.8rem', color: 'var(--text-muted)', margin: 0 }}>
              Official scheme PDF ingestion, collections, version control, and audit logs.
            </p>
          </div>
        </div>

        {/* Tab Navigation Buttons */}
        <div style={{ display: 'flex', gap: '0.4rem', flexWrap: 'wrap' }}>
          <button
            type="button"
            onClick={() => setActiveTab('documents')}
            style={{
              padding: '0.4rem 0.85rem',
              borderRadius: 'var(--radius-sm)',
              fontSize: '0.85rem',
              fontWeight: 600,
              background: activeTab === 'documents' ? 'var(--primary-700)' : 'var(--bg-subtle)',
              color: activeTab === 'documents' ? '#ffffff' : 'var(--text-main)',
              border: '1px solid var(--border-subtle)',
              cursor: 'pointer',
            }}
          >
            📋 Documents ({documents.length})
          </button>
          <button
            type="button"
            onClick={() => setActiveTab('upload')}
            style={{
              padding: '0.4rem 0.85rem',
              borderRadius: 'var(--radius-sm)',
              fontSize: '0.85rem',
              fontWeight: 600,
              background: activeTab === 'upload' ? 'var(--primary-700)' : 'var(--bg-subtle)',
              color: activeTab === 'upload' ? '#ffffff' : 'var(--text-main)',
              border: '1px solid var(--border-subtle)',
              cursor: 'pointer',
            }}
          >
            📤 Upload Official PDF
          </button>
          <button
            type="button"
            onClick={() => setActiveTab('collections')}
            style={{
              padding: '0.4rem 0.85rem',
              borderRadius: 'var(--radius-sm)',
              fontSize: '0.85rem',
              fontWeight: 600,
              background: activeTab === 'collections' ? 'var(--primary-700)' : 'var(--bg-subtle)',
              color: activeTab === 'collections' ? '#ffffff' : 'var(--text-main)',
              border: '1px solid var(--border-subtle)',
              cursor: 'pointer',
            }}
          >
            📁 Scheme Collections ({collections.length})
          </button>
          <button
            type="button"
            onClick={loadAuditLogs}
            style={{
              padding: '0.4rem 0.85rem',
              borderRadius: 'var(--radius-sm)',
              fontSize: '0.85rem',
              fontWeight: 600,
              background: activeTab === 'audit' ? 'var(--primary-700)' : 'var(--bg-subtle)',
              color: activeTab === 'audit' ? '#ffffff' : 'var(--text-main)',
              border: '1px solid var(--border-subtle)',
              cursor: 'pointer',
            }}
          >
            🛡️ Audit Logs
          </button>
        </div>
      </div>

      {/* Global Status Banner */}
      {statusMessage && (
        <div
          style={{
            padding: '0.75rem 1rem',
            background:
              statusMessage.type === 'success'
                ? '#f0fdf4'
                : statusMessage.type === 'warning'
                ? '#fffbeb'
                : '#fef2f2',
            color:
              statusMessage.type === 'success'
                ? '#166534'
                : statusMessage.type === 'warning'
                ? '#92400e'
                : '#991b1b',
            border: `1px solid ${
              statusMessage.type === 'success'
                ? '#bbf7d0'
                : statusMessage.type === 'warning'
                ? '#fde68a'
                : '#fecaca'
            }`,
            borderRadius: 'var(--radius-sm)',
            fontSize: '0.85rem',
            marginBottom: '1rem',
            fontWeight: 500,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
          }}
        >
          <span>{statusMessage.text}</span>
          <button
            type="button"
            onClick={() => setStatusMessage(null)}
            style={{ background: 'none', border: 'none', cursor: 'pointer', fontWeight: 700 }}
          >
            ✕
          </button>
        </div>
      )}

      {/* ======================================================== */}
      {/* Tab 1: Documents Catalog & Status Table                   */}
      {/* ======================================================== */}
      {activeTab === 'documents' && (
        <div>
          {/* Active Version Conflicts Warning Banner */}
          {conflicts && conflicts.length > 0 && (
            <div
              style={{
                padding: '0.85rem 1rem',
                background: '#fffbeb',
                border: '1px solid #fde68a',
                color: '#92400e',
                borderRadius: 'var(--radius-sm)',
                marginBottom: '1rem',
                fontSize: '0.85rem',
              }}
            >
              <div style={{ fontWeight: 700, display: 'flex', alignItems: 'center', gap: '0.4rem', marginBottom: '0.35rem' }}>
                <span>⚠️</span> Active Scheme Version Overlap Detected ({conflicts.length})
              </div>
              {conflicts.map((cf, idx) => (
                <div key={idx} style={{ fontSize: '0.8rem', marginTop: '0.2rem' }}>
                  • {cf.message}
                </div>
              ))}
            </div>
          )}

          <div
            style={{
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center',
              marginBottom: '0.75rem',
            }}
          >
            <span style={{ fontSize: '0.85rem', color: 'var(--text-muted)' }}>
              Showing all registered scheme guidelines with active/archived state and last updated timestamps.
            </span>
            <button
              type="button"
              onClick={loadDocuments}
              style={{
                fontSize: '0.8rem',
                color: 'var(--primary-700)',
                background: 'none',
                border: 'none',
                cursor: 'pointer',
                fontWeight: 600,
              }}
            >
              🔄 Refresh List
            </button>
          </div>

          <div style={{ overflowX: 'auto', border: '1px solid var(--border-subtle)', borderRadius: 'var(--radius-md)' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.85rem' }}>
              <thead>
                <tr style={{ background: 'var(--bg-subtle)', textAlign: 'left', borderBottom: '1px solid var(--border-subtle)' }}>
                  <th style={{ padding: '0.65rem' }}>Scheme Title</th>
                  <th style={{ padding: '0.65rem' }}>Department / Jurisdiction</th>
                  <th style={{ padding: '0.65rem' }}>Version</th>
                  <th style={{ padding: '0.65rem' }}>Status & Integrity</th>
                  <th style={{ padding: '0.65rem' }}>Last Updated</th>
                  <th style={{ padding: '0.65rem', textAlign: 'right' }}>Actions</th>
                </tr>
              </thead>
              <tbody>
                {documents.length === 0 ? (
                  <tr>
                    <td colSpan={6} style={{ padding: '2rem', textAlign: 'center', color: 'var(--text-muted)' }}>
                      No scheme documents registered yet. Click <strong>Upload Official PDF</strong> to ingest your first guideline.
                    </td>
                  </tr>
                ) : (
                  documents.map((doc) => (
                    <tr key={doc.id} style={{ borderBottom: '1px solid var(--border-subtle)' }}>
                      <td style={{ padding: '0.65rem' }}>
                        <div style={{ fontWeight: 600, color: 'var(--primary-900)' }}>{doc.title}</div>
                        <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                          Lang: {doc.language?.toUpperCase() || 'EN'} • {doc.total_pages} page(s)
                        </div>
                      </td>
                      <td style={{ padding: '0.65rem' }}>
                        <div>{doc.department || 'General Ministry'}</div>
                        <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                          {doc.state_or_district || 'National'}
                        </div>
                      </td>
                      <td style={{ padding: '0.65rem', fontWeight: 600 }}>v{doc.current_version}</td>
                      <td style={{ padding: '0.65rem' }}>
                        <div style={{ display: 'flex', flexDirection: 'column', gap: '0.2rem' }}>
                          <span
                            style={{
                              display: 'inline-block',
                              width: 'fit-content',
                              padding: '0.2rem 0.5rem',
                              borderRadius: '4px',
                              fontSize: '0.75rem',
                              fontWeight: 700,
                              background:
                                doc.status === 'ACTIVE'
                                  ? '#dcfce7'
                                  : doc.status === 'ARCHIVED'
                                  ? '#fef3c7'
                                  : doc.status === 'PROCESSING'
                                  ? '#e0e7ff'
                                  : '#fee2e2',
                              color:
                                doc.status === 'ACTIVE'
                                  ? '#166534'
                                  : doc.status === 'ARCHIVED'
                                  ? '#92400e'
                                  : doc.status === 'PROCESSING'
                                  ? '#3730a3'
                                  : '#991b1b',
                            }}
                          >
                            {doc.status}
                          </span>
                          {doc.file_hash && (
                            <span
                              style={{
                                fontSize: '0.65rem',
                                color: 'var(--text-muted)',
                                fontFamily: 'monospace',
                              }}
                              title={`SHA-256: ${doc.file_hash}`}
                            >
                              SHA: {doc.file_hash.slice(0, 8)}...
                            </span>
                          )}
                        </div>
                      </td>
                      <td style={{ padding: '0.65rem', fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                        {doc.updated_at ? new Date(doc.updated_at).toLocaleString() : 'N/A'}
                      </td>
                      <td style={{ padding: '0.65rem', textAlign: 'right' }}>
                        <div style={{ display: 'flex', gap: '0.35rem', justifyContent: 'flex-end' }}>
                          <button
                            type="button"
                            onClick={() => handleProcess(doc.id)}
                            style={{
                              padding: '0.25rem 0.5rem',
                              background: 'var(--primary-100)',
                              color: 'var(--primary-700)',
                              borderRadius: '4px',
                              fontSize: '0.75rem',
                              fontWeight: 600,
                              border: 'none',
                              cursor: 'pointer',
                            }}
                            title="Re-run text chunking and vector indexing"
                          >
                            Process
                          </button>
                          {doc.status !== 'ARCHIVED' ? (
                            <button
                              type="button"
                              onClick={() => handleArchive(doc.id)}
                              style={{
                                padding: '0.25rem 0.5rem',
                                background: '#fef3c7',
                                color: '#92400e',
                                borderRadius: '4px',
                                fontSize: '0.75rem',
                                fontWeight: 600,
                                border: 'none',
                                cursor: 'pointer',
                              }}
                              title="Archive from public search"
                            >
                              Archive
                            </button>
                          ) : (
                            <button
                              type="button"
                              onClick={() => handleRestore(doc.id)}
                              style={{
                                padding: '0.25rem 0.5rem',
                                background: '#dcfce7',
                                color: '#166534',
                                borderRadius: '4px',
                                fontSize: '0.75rem',
                                fontWeight: 600,
                                border: 'none',
                                cursor: 'pointer',
                              }}
                              title="Restore archived document to active search"
                            >
                              Restore
                            </button>
                          )}
                          <button
                            type="button"
                            onClick={() => handleDelete(doc.id)}
                            style={{
                              padding: '0.25rem 0.5rem',
                              background: '#fee2e2',
                              color: '#991b1b',
                              borderRadius: '4px',
                              fontSize: '0.75rem',
                              fontWeight: 600,
                              border: 'none',
                              cursor: 'pointer',
                            }}
                          >
                            Delete
                          </button>
                        </div>
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </div>
      )}


      {/* ======================================================== */}
      {/* Tab 2: Document Upload Workflow with Live Progress        */}
      {/* ======================================================== */}
      {activeTab === 'upload' && (
        <form onSubmit={handleUploadSubmit} style={{ maxWidth: '780px', display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
          {/* Validation Error Alert */}
          {fileValidationError && (
            <div
              style={{
                padding: '0.75rem 1rem',
                background: '#fef2f2',
                color: '#991b1b',
                border: '1px solid #fecaca',
                borderRadius: 'var(--radius-sm)',
                fontSize: '0.85rem',
                fontWeight: 600,
              }}
            >
              ⚠️ {fileValidationError}
            </div>
          )}

          {/* Duplicate Warning Alert */}
          {duplicateWarning && (
            <div
              style={{
                padding: '0.75rem 1rem',
                background: '#fffbeb',
                color: '#92400e',
                border: '1px solid #fde68a',
                borderRadius: 'var(--radius-sm)',
                fontSize: '0.85rem',
                fontWeight: 600,
              }}
            >
              ⚠️ {duplicateWarning}
            </div>
          )}

          {/* 1. Collection Selection / Creation */}
          <div style={{ background: 'var(--bg-subtle)', padding: '1rem', borderRadius: 'var(--radius-md)', border: '1px solid var(--border-subtle)' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.5rem' }}>
              <label style={{ fontSize: '0.85rem', fontWeight: 700, color: 'var(--primary-900)' }}>
                1. Target Scheme Collection *
              </label>
              <button
                type="button"
                onClick={() => setIsCreatingInlineCol(!isCreatingInlineCol)}
                style={{
                  fontSize: '0.8rem',
                  color: 'var(--primary-700)',
                  fontWeight: 600,
                  background: 'none',
                  border: 'none',
                  cursor: 'pointer',
                }}
              >
                {isCreatingInlineCol ? '← Select existing collection' : '+ Create new collection'}
              </button>
            </div>

            {!isCreatingInlineCol ? (
              <select
                value={selectedColId}
                onChange={(e) => setSelectedColId(e.target.value)}
                style={{
                  width: '100%',
                  padding: '0.6rem',
                  borderRadius: 'var(--radius-sm)',
                  border: '1px solid var(--border-subtle)',
                  fontSize: '0.9rem',
                }}
              >
                <option value="">Choose a scheme collection...</option>
                {collections.map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.name} {c.department ? `(${c.department})` : ''}
                  </option>
                ))}
              </select>
            ) : (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem', background: '#ffffff', padding: '0.75rem', borderRadius: 'var(--radius-sm)', border: '1px dashed var(--primary-300)' }}>
                <input
                  type="text"
                  placeholder="New Collection Name (e.g., Rural Development & Livelihoods)"
                  value={inlineColName}
                  onChange={(e) => {
                    setInlineColName(e.target.value);
                    setInlineColSlug(e.target.value.toLowerCase().replace(/[^a-z0-9]+/g, '-'));
                  }}
                  style={{ padding: '0.5rem', border: '1px solid var(--border-subtle)', borderRadius: '4px', fontSize: '0.85rem' }}
                />
                <input
                  type="text"
                  placeholder="Slug (e.g., rural-development-livelihoods)"
                  value={inlineColSlug}
                  onChange={(e) => setInlineColSlug(e.target.value)}
                  style={{ padding: '0.5rem', border: '1px solid var(--border-subtle)', borderRadius: '4px', fontSize: '0.85rem' }}
                />
                <input
                  type="text"
                  placeholder="Description (Optional)"
                  value={inlineColDesc}
                  onChange={(e) => setInlineColDesc(e.target.value)}
                  style={{ padding: '0.5rem', border: '1px solid var(--border-subtle)', borderRadius: '4px', fontSize: '0.85rem' }}
                />
              </div>
            )}
          </div>

          {/* 2. PDF File Selection (Drag & Drop or Browse) */}
          <div
            style={{
              border: '2px dashed #cbd5e1',
              borderRadius: 'var(--radius-md)',
              padding: '1.5rem',
              textAlign: 'center',
              background: selectedFile ? '#f0fdf4' : '#fafafa',
              transition: 'background 0.2s',
            }}
          >
            <input
              type="file"
              accept=".pdf,application/pdf"
              ref={fileInputRef}
              onChange={(e) => handleFileChange(e.target.files ? e.target.files[0] : null)}
              style={{ display: 'none' }}
              id="admin-pdf-input"
            />
            <label htmlFor="admin-pdf-input" style={{ cursor: 'pointer' }}>
              <div style={{ fontSize: '2rem', marginBottom: '0.5rem' }}>📄</div>
              {selectedFile ? (
                <div>
                  <div style={{ fontWeight: 700, color: '#166534', fontSize: '0.95rem' }}>
                    {selectedFile.name}
                  </div>
                  <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)', marginTop: '0.25rem' }}>
                    Size: {(selectedFile.size / (1024 * 1024)).toFixed(2)} MB • PDF Verified
                  </div>
                  <div style={{ marginTop: '0.5rem', fontSize: '0.8rem', color: 'var(--primary-700)', textDecoration: 'underline' }}>
                    Click to choose a different PDF
                  </div>
                </div>
              ) : (
                <div>
                  <div style={{ fontWeight: 600, color: 'var(--primary-900)', fontSize: '0.95rem' }}>
                    Choose or Drag & Drop Official Scheme PDF
                  </div>
                  <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)', marginTop: '0.25rem' }}>
                    Strict limit: 50MB per file • Format: .pdf only (Magic bytes validated server-side)
                  </div>
                </div>
              )}
            </label>
          </div>

          {/* Upload Progress Bar */}
          {uploadProgress !== null && (
            <div style={{ marginTop: '0.5rem' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.8rem', fontWeight: 600, marginBottom: '0.25rem' }}>
                <span>Uploading & Generating SHA-256 Hash...</span>
                <span>{uploadProgress}%</span>
              </div>
              <div style={{ height: '8px', background: '#e2e8f0', borderRadius: '4px', overflow: 'hidden' }}>
                <div
                  style={{
                    height: '100%',
                    width: `${uploadProgress}%`,
                    background: 'var(--primary-600)',
                    transition: 'width 0.3s ease',
                  }}
                />
              </div>
            </div>
          )}

          {/* 3. Metadata Fields Grid */}
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))', gap: '1rem' }}>
            <div>
              <label style={{ display: 'block', fontSize: '0.85rem', fontWeight: 600, marginBottom: '0.3rem' }}>
                Scheme Name *
              </label>
              <input
                type="text"
                required
                value={schemeName}
                onChange={(e) => setSchemeName(e.target.value)}
                placeholder="e.g., PM-Kisan Samman Nidhi"
                style={{ width: '100%', padding: '0.55rem', borderRadius: 'var(--radius-sm)', border: '1px solid var(--border-subtle)', fontSize: '0.85rem' }}
              />
            </div>

            <div>
              <label style={{ display: 'block', fontSize: '0.85rem', fontWeight: 600, marginBottom: '0.3rem' }}>
                Department / Sponsoring Ministry *
              </label>
              <input
                type="text"
                required
                value={department}
                onChange={(e) => setDepartment(e.target.value)}
                placeholder="e.g., Ministry of Agriculture"
                style={{ width: '100%', padding: '0.55rem', borderRadius: 'var(--radius-sm)', border: '1px solid var(--border-subtle)', fontSize: '0.85rem' }}
              />
            </div>

            <div>
              <label style={{ display: 'block', fontSize: '0.85rem', fontWeight: 600, marginBottom: '0.3rem' }}>
                State / District Jurisdiction
              </label>
              <input
                type="text"
                value={stateOrDistrict}
                onChange={(e) => setStateOrDistrict(e.target.value)}
                placeholder="e.g., National / All States, Maharashtra"
                style={{ width: '100%', padding: '0.55rem', borderRadius: 'var(--radius-sm)', border: '1px solid var(--border-subtle)', fontSize: '0.85rem' }}
              />
            </div>

            <div>
              <label style={{ display: 'block', fontSize: '0.85rem', fontWeight: 600, marginBottom: '0.3rem' }}>
                Document Language
              </label>
              <select
                value={language}
                onChange={(e) => setLanguage(e.target.value)}
                style={{ width: '100%', padding: '0.55rem', borderRadius: 'var(--radius-sm)', border: '1px solid var(--border-subtle)', fontSize: '0.85rem' }}
              >
                <option value="en">English (en)</option>
                <option value="hi">Hindi (hi)</option>
                <option value="bn">Bengali (bn)</option>
                <option value="ta">Tamil (ta)</option>
                <option value="te">Telugu (te)</option>
                <option value="mr">Marathi (mr)</option>
                <option value="gu">Gujarati (gu)</option>
              </select>
            </div>

            <div>
              <label style={{ display: 'block', fontSize: '0.85rem', fontWeight: 600, marginBottom: '0.3rem' }}>
                Publication Date
              </label>
              <input
                type="date"
                value={publicationDate}
                onChange={(e) => setPublicationDate(e.target.value)}
                style={{ width: '100%', padding: '0.55rem', borderRadius: 'var(--radius-sm)', border: '1px solid var(--border-subtle)', fontSize: '0.85rem' }}
              />
            </div>

            <div>
              <label style={{ display: 'block', fontSize: '0.85rem', fontWeight: 600, marginBottom: '0.3rem' }}>
                Effective Date
              </label>
              <input
                type="date"
                value={effectiveDate}
                onChange={(e) => setEffectiveDate(e.target.value)}
                style={{ width: '100%', padding: '0.55rem', borderRadius: 'var(--radius-sm)', border: '1px solid var(--border-subtle)', fontSize: '0.85rem' }}
              />
            </div>

            <div>
              <label style={{ display: 'block', fontSize: '0.85rem', fontWeight: 600, marginBottom: '0.3rem' }}>
                Version Number
              </label>
              <input
                type="number"
                min="1"
                value={versionNumber}
                onChange={(e) => setVersionNumber(parseInt(e.target.value, 10) || 1)}
                style={{ width: '100%', padding: '0.55rem', borderRadius: 'var(--radius-sm)', border: '1px solid var(--border-subtle)', fontSize: '0.85rem' }}
              />
            </div>

            <div>
              <label style={{ display: 'block', fontSize: '0.85rem', fontWeight: 600, marginBottom: '0.3rem' }}>
                Visibility Scope
              </label>
              <select
                value={visibility}
                onChange={(e) => setVisibility(e.target.value as 'public' | 'restricted')}
                style={{ width: '100%', padding: '0.55rem', borderRadius: 'var(--radius-sm)', border: '1px solid var(--border-subtle)', fontSize: '0.85rem' }}
              >
                <option value="public">Public (Citizens & Helpdesk)</option>
                <option value="restricted">Restricted (Internal Helpdesk / Admin only)</option>
              </select>
            </div>
          </div>

          {/* 4. Official Source Confirmation Checkbox */}
          <div
            style={{
              display: 'flex',
              alignItems: 'flex-start',
              gap: '0.65rem',
              padding: '0.85rem',
              background: '#f8fafc',
              border: '1px solid #e2e8f0',
              borderRadius: 'var(--radius-sm)',
            }}
          >
            <input
              type="checkbox"
              id="confirm-official"
              required
              checked={isOfficialConfirmed}
              onChange={(e) => setIsOfficialConfirmed(e.target.checked)}
              style={{ marginTop: '0.2rem', width: '18px', height: '18px' }}
            />
            <label htmlFor="confirm-official" style={{ fontSize: '0.85rem', color: 'var(--text-main)', cursor: 'pointer', lineHeight: '1.4' }}>
              <strong>Official Source Confirmation:</strong> I certify that this uploaded document is an authentic, uncorrupted official government gazette, guideline, or departmental circular.
            </label>
          </div>

          {/* Submit Action */}
          <button
            type="submit"
            disabled={loading || !isOfficialConfirmed || !selectedFile}
            style={{
              padding: '0.75rem',
              background: loading || !isOfficialConfirmed || !selectedFile ? '#94a3b8' : 'var(--primary-700)',
              color: 'white',
              borderRadius: 'var(--radius-sm)',
              fontWeight: 700,
              fontSize: '0.95rem',
              border: 'none',
              cursor: loading || !isOfficialConfirmed || !selectedFile ? 'not-allowed' : 'pointer',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              gap: '0.5rem',
            }}
          >
            {loading ? 'Processing & Indexing Document...' : 'Ingest Official Scheme PDF'}
          </button>
        </form>
      )}

      {/* ======================================================== */}
      {/* Tab 3: Scheme Collections Management                     */}
      {/* ======================================================== */}
      {activeTab === 'collections' && (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))', gap: '1.5rem' }}>
          {/* Create Collection Form */}
          <form onSubmit={handleCreateCollection} style={{ display: 'flex', flexDirection: 'column', gap: '0.85rem' }}>
            <h4 style={{ fontSize: '1rem', fontWeight: 700, color: 'var(--primary-900)', margin: 0 }}>
              Create Scheme Collection
            </h4>
            <div>
              <label style={{ display: 'block', fontSize: '0.85rem', fontWeight: 600, marginBottom: '0.3rem' }}>
                Collection Name *
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
                style={{ width: '100%', padding: '0.55rem', borderRadius: 'var(--radius-sm)', border: '1px solid var(--border-subtle)', fontSize: '0.85rem' }}
              />
            </div>

            <div>
              <label style={{ display: 'block', fontSize: '0.85rem', fontWeight: 600, marginBottom: '0.3rem' }}>
                Unique Slug *
              </label>
              <input
                type="text"
                required
                value={newColSlug}
                onChange={(e) => setNewColSlug(e.target.value)}
                style={{ width: '100%', padding: '0.55rem', borderRadius: 'var(--radius-sm)', border: '1px solid var(--border-subtle)', fontSize: '0.85rem' }}
              />
            </div>

            <div>
              <label style={{ display: 'block', fontSize: '0.85rem', fontWeight: 600, marginBottom: '0.3rem' }}>
                Description
              </label>
              <textarea
                value={newColDesc}
                onChange={(e) => setNewColDesc(e.target.value)}
                placeholder="Brief summary of schemes in this collection..."
                style={{ width: '100%', padding: '0.55rem', borderRadius: 'var(--radius-sm)', border: '1px solid var(--border-subtle)', minHeight: '80px', fontSize: '0.85rem' }}
              />
            </div>

            <button
              type="submit"
              disabled={loading || !newColName || !newColSlug}
              style={{
                padding: '0.65rem',
                background: 'var(--primary-700)',
                color: 'white',
                borderRadius: 'var(--radius-sm)',
                fontWeight: 600,
                border: 'none',
                cursor: 'pointer',
              }}
            >
              {loading ? 'Creating...' : 'Create Collection'}
            </button>
          </form>

          {/* Existing Collections List */}
          <div>
            <h4 style={{ fontSize: '1rem', fontWeight: 700, color: 'var(--primary-900)', marginBottom: '0.85rem' }}>
              Active Scheme Collections
            </h4>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem', maxHeight: '350px', overflowY: 'auto' }}>
              {collections.map((col) => (
                <div
                  key={col.id}
                  style={{
                    padding: '0.75rem',
                    background: 'var(--bg-subtle)',
                    borderRadius: 'var(--radius-sm)',
                    border: '1px solid var(--border-subtle)',
                  }}
                >
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                    <div>
                      <div style={{ fontWeight: 700, color: 'var(--primary-900)', fontSize: '0.9rem' }}>
                        {col.name}
                      </div>
                      <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                        slug: <code>{col.slug}</code> • {col.total_documents || 0} document(s)
                      </div>
                    </div>
                  </div>
                  {col.description && (
                    <div style={{ fontSize: '0.8rem', color: 'var(--text-main)', marginTop: '0.35rem' }}>
                      {col.description}
                    </div>
                  )}
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* ======================================================== */}
      {/* Tab 4: Audit Logs & Privileged Traceability              */}
      {/* ======================================================== */}
      {activeTab === 'audit' && (
        <div>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.75rem' }}>
            <span style={{ fontSize: '0.85rem', color: 'var(--text-muted)' }}>
              Server-side immutable audit log of administrative logins, uploads, and modifications.
            </span>
            <button
              type="button"
              onClick={loadAuditLogs}
              style={{
                fontSize: '0.8rem',
                color: 'var(--primary-700)',
                background: 'none',
                border: 'none',
                cursor: 'pointer',
                fontWeight: 600,
              }}
            >
              🔄 Refresh Logs
            </button>
          </div>

          <div style={{ overflowX: 'auto', maxHeight: '420px', border: '1px solid var(--border-subtle)', borderRadius: 'var(--radius-md)' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.8rem' }}>
              <thead>
                <tr style={{ background: 'var(--bg-subtle)', textAlign: 'left', borderBottom: '1px solid var(--border-subtle)' }}>
                  <th style={{ padding: '0.6rem' }}>Timestamp</th>
                  <th style={{ padding: '0.6rem' }}>Action Type</th>
                  <th style={{ padding: '0.6rem' }}>Target Entity</th>
                  <th style={{ padding: '0.6rem' }}>IP Address</th>
                </tr>
              </thead>
              <tbody>
                {auditLogs.length === 0 ? (
                  <tr>
                    <td colSpan={4} style={{ padding: '1.5rem', textAlign: 'center', color: 'var(--text-muted)' }}>
                      No audit events recorded yet.
                    </td>
                  </tr>
                ) : (
                  auditLogs.map((log) => (
                    <tr key={log.id} style={{ borderBottom: '1px solid var(--border-subtle)' }}>
                      <td style={{ padding: '0.6rem', color: 'var(--text-muted)' }}>
                        {log.created_at ? new Date(log.created_at).toLocaleString() : 'N/A'}
                      </td>
                      <td style={{ padding: '0.6rem', fontWeight: 700, color: 'var(--primary-800)' }}>
                        {log.action}
                      </td>
                      <td style={{ padding: '0.6rem' }}>
                        <div>{log.entity_type}</div>
                        <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)' }}>{log.entity_id || 'system'}</div>
                      </td>
                      <td style={{ padding: '0.6rem', fontFamily: 'monospace' }}>
                        {log.ip_address || '127.0.0.1'}
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
};
