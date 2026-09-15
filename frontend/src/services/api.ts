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

export const api = {
  async getHealth(): Promise<HealthData> {
    const res = await fetch('/api/health');
    if (!res.ok) throw new Error(`Health check failed: ${res.status}`);
    return res.json();
  },

  async getCollections(): Promise<CollectionItem[]> {
    const res = await fetch('/api/v1/collections');
    if (!res.ok) throw new Error('Failed to fetch collections');
    const data = await res.json();
    return data.data;
  },

  async submitQuery(queryText: string, collectionIds: string[] = []): Promise<QueryResult> {
    const res = await fetch('/api/v1/query', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ queryText, collectionIds }),
    });
    if (!res.ok) throw new Error(`Query failed: ${res.statusText}`);
    return res.json();
  },
};
