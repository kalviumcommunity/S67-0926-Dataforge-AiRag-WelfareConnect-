# Government Welfare Scheme Document Assistant

An AI-powered, retrieval-augmented intelligence web application designed for citizens and helpdesk operators to query official government welfare scheme PDF documents. The system strictly grounds all answers in uploaded documents, provides exact page-level citations, handles out-of-corpus queries with explicit negative refusal, and displays prominent non-guarantee legal disclaimers.

---

## 📑 Key Architecture & Operational Principles

1. **Strict Source Grounding**: Responses are generated solely from verified official government PDFs (e.g. gazette notifications, operational guidelines).
2. **Page-Level Citations**: Every factual claim and procedural rule cites the exact source document name and page number (`[Document_Name.pdf, Page X]`).
3. **Deterministic Uncertainty Handling**: When information is absent from the uploaded corpus, the assistant returns an explicit refusal rather than hallucinating.
4. **Non-Guarantee Legal Disclaimer**: Clarifies that generated answers are informational summaries and do not confer legal eligibility or statutory benefit grants.

---

## 🏗️ Project Structure

```
├── backend/
│   ├── src/
│   │   ├── config/          # Zod-validated environment configuration (env.ts)
│   │   ├── controllers/     # API request handlers (health, collections, documents, queries)
│   │   ├── middlewares/     # Error handlers & request logging
│   │   ├── models/          # TypeScript domain models and schemas (types.ts)
│   │   ├── routes/          # Express route definitions
│   │   ├── services/        # Business logic (DocumentService, SearchService, HealthService)
│   │   ├── workers/         # Asynchronous task queues & document processing workers
│   │   ├── app.ts           # Express application factory
│   │   └── server.ts        # Server entry point
│   └── tests/               # Vitest unit & integration test suites
│       ├── config.test.ts
│       ├── health.test.ts
│       └── models.test.ts
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

### 4. Running Locally

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
  "timestamp": "2026-09-15T07:11:27.077Z",
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

Run the automated test suite:

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
