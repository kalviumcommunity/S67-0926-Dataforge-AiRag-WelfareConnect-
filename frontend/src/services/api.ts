export interface HealthData {
  status: string;
  uptimeSeconds: number;
  version: string;
  environment: string;
  services: {
    database: string;
    storage: string;
    taskQueue: string;
  };
}

export type UserRole = 'CITIZEN' | 'HELPDESK' | 'SCHEME_ADMIN' | 'SYSTEM_ADMIN';

export interface UserProfile {
  id: string;
  email: string;
  fullName: string;
  role: UserRole;
  department?: string | null;
  permissions: string[];
}

export interface AuthSession {
  user: UserProfile;
  token: string;
  expiresIn: string;
}

export interface CollectionItem {
  id: string;
  name: string;
  department: string;
  description: string;
  documentCount?: number;
}

export interface CitationItem {
  citationId: string;
  documentId: string;
  documentTitle: string;
  pageNumber: number;
  snippet: string;
}

export interface QueryResult {
  queryId: string;
  status: 'SUCCESS' | 'NOT_FOUND' | 'ERROR';
  isGrounded: boolean;
  answer?: {
    summary: string;
    eligibility: string[];
    requiredDocuments: string[];
    applicationProcedure: string[];
    citations: CitationItem[];
  };
  fallbackMessage?: string;
  disclaimer: string;
  latencyMs: number;
}

export interface AuditEventItem {
  id: string;
  actorUserId?: string | null;
  actionType: string;
  entityTable: string;
  entityId: string;
  clientIpMasked?: string | null;
  metadata?: Record<string, unknown>;
  createdAt: string;
}

function getAuthHeaders(): HeadersInit {
  const token = localStorage.getItem('auth_token');
  const headers: HeadersInit = { 'Content-Type': 'application/json' };
  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }
  return headers;
}

export const api = {
  // Health
  async getHealth(): Promise<HealthData> {
    const res = await fetch('/api/health');
    if (!res.ok) throw new Error(`Health check failed: ${res.status}`);
    return res.json();
  },

  // Auth
  async login(email: string, password: string): Promise<AuthSession> {
    const res = await fetch('/api/v1/auth/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email, password }),
    });
    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.message || 'Login failed');
    }
    const data = await res.json();
    localStorage.setItem('auth_token', data.data.token);
    return data.data;
  },

  async register(email: string, password: string, fullName: string): Promise<AuthSession> {
    const res = await fetch('/api/v1/auth/register', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email, password, fullName }),
    });
    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.message || 'Registration failed');
    }
    const data = await res.json();
    localStorage.setItem('auth_token', data.data.token);
    return data.data;
  },

  async getProfile(): Promise<UserProfile> {
    const res = await fetch('/api/v1/auth/me', {
      headers: getAuthHeaders(),
    });
    if (!res.ok) throw new Error('Session expired');
    const data = await res.json();
    return data.data;
  },

  logout(): void {
    localStorage.removeItem('auth_token');
  },

  // Collections
  async getCollections(): Promise<CollectionItem[]> {
    const res = await fetch('/api/v1/collections', {
      headers: getAuthHeaders(),
    });
    if (!res.ok) throw new Error('Failed to fetch collections');
    const data = await res.json();
    return data.data;
  },

  // Grounded Search Query
  async submitQuery(queryText: string, collectionIds: string[] = []): Promise<QueryResult> {
    const res = await fetch('/api/v1/query', {
      method: 'POST',
      headers: getAuthHeaders(),
      body: JSON.stringify({ queryText, collectionIds }),
    });
    if (!res.ok) throw new Error(`Query failed: ${res.statusText}`);
    return res.json();
  },

  // Feedback
  async submitFeedback(queryId: string, isHelpful: boolean, comments?: string): Promise<void> {
    await fetch('/api/v1/feedback', {
      method: 'POST',
      headers: getAuthHeaders(),
      body: JSON.stringify({ queryId, isHelpful, comments }),
    });
  },

  // Admin Audit Logs
  async getAuditLogs(): Promise<AuditEventItem[]> {
    const res = await fetch('/api/v1/audit/logs', {
      headers: getAuthHeaders(),
    });
    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.message || 'Failed to fetch audit logs');
    }
    const data = await res.json();
    return data.data;
  },

  // Admin Document Upload
  async uploadDocument(formData: {
    title: string;
    collectionId: string;
    department: string;
  }): Promise<any> {
    const res = await fetch('/api/v1/documents/upload', {
      method: 'POST',
      headers: getAuthHeaders(),
      body: JSON.stringify(formData),
    });
    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.message || 'Upload failed');
    }
    return res.json();
  },
};
