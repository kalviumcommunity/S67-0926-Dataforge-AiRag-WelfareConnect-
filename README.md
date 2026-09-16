# Government Welfare Scheme Document Assistant

An AI-powered, retrieval-augmented intelligence web application designed for citizens and helpdesk operators to query official government welfare scheme PDF documents. The system strictly grounds all answers in uploaded documents, provides exact page-level citations, handles out-of-corpus queries with explicit negative refusal, and displays prominent non-guarantee legal disclaimers.

---

## 📑 Key Architecture & Operational Principles

1. **Strict Source Grounding**: Responses are generated solely from verified official government PDFs (e.g. gazette notifications, operational guidelines).
2. **Page-Level Citations**: Every factual claim and procedural rule cites the exact source document name and page number (`[Document_Name.pdf, Page X]`).
3. **Deterministic Uncertainty Handling**: When information is absent from the uploaded corpus, the assistant returns an explicit refusal rather than hallucinating.
4. **Non-Guarantee Legal Disclaimer**: Clarifies that generated answers are informational summaries and do not confer legal eligibility or statutory benefit grants.

---

## 🗄️ Database Schema & Architecture

The database is built for **PostgreSQL 16 + pgvector** and implements 14 normalized entities:

| #   | Entity Table            | Key Responsibilities & Capabilities                                                                              |
| :-- | :---------------------- | :--------------------------------------------------------------------------------------------------------------- |
| 1   | `roles`                 | RBAC roles (`SYSTEM_ADMIN`, `SCHEME_ADMIN`, `HELPDESK`, `CITIZEN`) and permissions.                              |
| 2   | `users`                 | User accounts, departments, password hashes, and activity tracking.                                              |
| 3   | `document_collections`  | Scoped collections of schemes (e.g. Agriculture, Healthcare, Senior Citizen Welfare).                            |
| 4   | `documents`             | Official scheme documents with status lifecycle (`ACTIVE`, `ARCHIVED`, `PROCESSING`, `FAILED`, `DELETED`).       |
| 5   | `document_versions`     | Versioned files tracking original filename, storage key, MIME type, SHA-256 hash, publication & effective dates. |
| 6   | `document_metadata`     | Structured scheme attributes: age, income limits, beneficiary categories, checklists.                            |
| 7   | `document_pages`        | Page boundary preservation with layout dimensions, page text, and rendered page images.                          |
| 8   | `extracted_text_chunks` | Hybrid search text chunks with dense embeddings (768d) and lexical GIN tokens (`tsvector`).                      |
| 9   | `processing_jobs`       | Background task tracking for PDF parsing, text extraction, chunking, and embedding.                              |
| 10  | `search_sessions`       | Citizen/Staff search session tracking with collection filters and masked client IP.                              |
| 11  | `questions_and_answers` | Query audit log with generated grounded answers, confidence scores, and latency.                                 |
| 12  | `citations`             | Precise page-level citations linking answers to chunks, versions, and source page numbers.                       |
| 13  | `audit_events`          | Immutable government compliance log with before/after state diffs.                                               |
| 14  | `user_feedback`         | Binary helpful/unhelpful rating and structured feedback tags.                                                    |

### Database Indexes Included:

- `idx_documents_collection_id`: Fast collection scoping.
- `idx_documents_status`: Active/archived lifecycle filter.
- `idx_documents_scheme_name`: Trigram/B-Tree lookup on scheme titles.
- `idx_documents_department`: Departmental query filtering.
- `idx_document_versions_effective_date`: Chronological policy enforcement.
- `idx_document_versions_file_hash`: SHA-256 deduplication and integrity check.
- `idx_extracted_chunks_tsv`: Full-text lexical search index (GIN).
- `idx_extracted_chunks_embedding`: Dense vector cosine similarity index (HNSW).

---

## 🏗️ Project Structure

```
├── backend/
│   ├── src/
│   │   ├── config/          # Zod-validated environment configuration (env.ts)
│   │   ├── controllers/     # API request handlers (health, collections, documents, queries)
│   │   ├── db/              # Migrations, seed scripts, database connector
│   │   │   ├── migrations/  # 001_initial_schema.sql
│   │   │   ├── seeds/       # 001_initial_seed.sql
│   │   │   ├── database.ts
│   │   │   ├── migrator.ts
│   │   │   └── seed.ts
│   │   ├── middlewares/     # Error handlers & request logging
│   │   ├── models/          # Zod schemas (schema.ts) & TypeScript models (types.ts)
│   │   ├── routes/          # Express route definitions
│   │   ├── services/        # Business logic (DocumentService, SearchService, HealthService)
│   │   ├── workers/         # Asynchronous task queues & document processing workers
│   │   ├── app.ts           # Express application factory
│   │   └── server.ts        # Server entry point
│   └── tests/               # Vitest unit & integration test suites
│       ├── config.test.ts
│       ├── health.test.ts
│       ├── migrations.test.ts
│       ├── models.test.ts
│       └── schema.test.ts
├── docs/
│   ├── architecture.md      # Full technical architecture specification
│   ├── data-flow.mmd        # Mermaid end-to-end data flow diagram
│   └── product-requirements.md # Product Requirements Document (PRD)
├── frontend/
│   ├── src/
│   │   ├── components/      # UI components (AnswerCard, CitationBadge, DisclaimerBanner, etc.)
│   │   ├── pages/           # Views (LandingPage.tsx)
│   │   ├── services/        # Frontend API client (api.ts)
│   │   ├── styles/          # Responsive Vanilla CSS design system (index.css)
│   │   ├── App.tsx          # Main React shell
│   │   └── main.tsx         # Frontend DOM mounting
│   └── index.html           # Web entry point
├── .env.example             # Template with placeholder configuration values
├── eslint.config.mjs        # ESLint flat configuration
├── package.json             # Root scripts and dependencies
├── tsconfig.json            # TypeScript configuration
├── vite.config.ts           # Vite build & development proxy setup
└── vitest.config.ts         # Vitest test runner configuration
```

---

## 🚀 Getting Started & Local Development

### 1. Prerequisites

- **Node.js**: `v20+` or `v22+` recommended (Supports `v23.9.0`)
- **npm**: `v10+` or `v11+`

### 2. Environment Configuration

Copy the template configuration file:

```bash
cp .env.example .env
```

> _Note: `.env.example` contains only placeholder values. No real secrets should be committed._

### 3. Installation

Install all runtime and development dependencies:

```bash
npm install
```

### 4. Database Migrations & Seeding

Apply database migrations and load development seed data:

```bash
# Run migrations (creates all 14 tables and indexes)
npm run db:migrate

# Apply initial seed data (roles, dev admin, sample collection & guidelines)
npm run db:seed
```

### 5. Running Locally

Start both backend (Port `4000`) and frontend (Port `3000`) concurrently:

```bash
npm run dev
```

Alternatively, run services independently:

- **Backend Service**:
  ```bash
  npm run dev:backend
  ```
  _Accessible at `http://localhost:4000`_
- **Frontend Web Portal**:
  ```bash
  npm run dev:frontend
  ```
  _Accessible at `http://localhost:3000`_

---

## 🩺 Health-Check Endpoints

The backend provides health-check endpoints for liveness probes, monitoring, and uptime checks:

- `GET /health`
- `GET /api/health`
- `GET /api/v1/health`

#### Sample Response (`200 OK`):

```json
{
  "status": "healthy",
  "timestamp": "2026-09-16T04:19:15.382Z",
  "uptimeSeconds": 42,
  "version": "1.0.0",
  "environment": "development",
  "services": {
    "database": "connected",
    "storage": "connected",
    "taskQueue": "ready"
  }
}
```

---

## 🧪 Testing, Linting & Quality Assurance

Run the automated test suite (5 test suites, 24 tests passing):

```bash
npm test
```

Run TypeScript static type checking:

```bash
npm run typecheck
```

Run ESLint code quality checks:

```bash
npm run lint
```

Verify and fix code formatting (Prettier):

```bash
# Check formatting
npm run format

# Automatically format code
npm run format:fix
```

Build production client assets:

```bash
npm run build
```

---

## 📡 API Overview

| Method | Endpoint                   | Description                                                   |
| :----- | :------------------------- | :------------------------------------------------------------ |
| `GET`  | `/health`                  | System health check and uptime probe.                         |
| `GET`  | `/api/v1/collections`      | Fetch active scheme document collections.                     |
| `GET`  | `/api/v1/collections/:id`  | Fetch specific collection details.                            |
| `GET`  | `/api/v1/documents`        | List uploaded official documents with version metadata.       |
| `POST` | `/api/v1/documents/upload` | Enqueue an official PDF document for background processing.   |
| `POST` | `/api/v1/query`            | Submit natural-language citizen query for grounded retrieval. |
