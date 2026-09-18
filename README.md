# WelfareConnect — Government Welfare Scheme Document Assistant

**WelfareConnect** is a web-only, AI-powered Retrieval-Augmented Generation (RAG) assistant designed for citizens, helpdesk operators, and government nodal officers. It enables searching and questioning across official government welfare scheme circulars, gazettes, and operational guidelines with **strict source grounding**, **exact page-level citations**, and **zero rule hallucination**.

---

## Key Capabilities & Constraints

- **Web-Only Architecture:** Responsive web interface optimized for citizen mobile browsers and helpdesk counter terminals.
- **Strict Closed-World Grounding:** Generates answers derived 100% from official uploaded documents.
- **Exact Page-Level Citations:** Every factual response includes clickable `[Doc: <Scheme Name>, Page: <N>]` citations with page preview.
- **Negative Fallback:** Automatically states when information is not found in indexed documents instead of inventing rules.
- **Legal Non-Guarantee:** Non-dismissible disclaimers clarifying that answers do not constitute legal eligibility guarantees.
- **Preserved Prompt 05 Auth & RBAC:** Complete multi-role matrix (`SYSTEM_ADMIN`, `SCHEME_ADMIN`, `HELPDESK`, `CITIZEN`).

---

## Technology Stack

| Layer | Technology |
| :--- | :--- |
| **Frontend** | Next.js 14, React 18, TypeScript, Vanilla CSS (High-trust design system) |
| **Backend API** | Python 3.11+, FastAPI, Pydantic v2, SQLAlchemy ORM |
| **Vector Database** | Pinecone (`pinecone-client>=3.0.0`) |
| **Relational Database** | PostgreSQL 16 (Production) / SQLite (Local Development) |
| **Task Queue** | Redis (BullMQ / Celery worker abstractions) |
| **Testing & Quality** | Pytest, FastAPI TestClient, Ruff, MyPy, Prettier |

---

## Project Structure

```
├── .env.example                      # Environment variables template (placeholders only)
├── .gitignore                        # Git exclusion configuration
├── .prettierrc                       # Prettier formatting rules
├── pyproject.toml                    # Python tooling configuration (Ruff, MyPy, Pytest)
├── package.json                      # Workspace orchestrator scripts
├── README.md                         # Project documentation and setup guide
│
├── docs/                             # Architecture & Product Specifications
│   ├── product-requirements.md       # Product Requirements Document (PRD)
│   ├── architecture.md               # Technical Architecture Specification
│   └── data-flow.mmd                 # End-to-end Mermaid Data-Flow Diagram
│
├── backend/                          # Python FastAPI Backend
│   ├── requirements.txt              # Python package dependencies
│   ├── app/
│   │   ├── main.py                   # FastAPI app entrypoint & middleware
│   │   ├── config.py                 # Pydantic BaseSettings environment config
│   │   ├── core/
│   │   │   ├── security.py           # Bcrypt password hashing & JWT encoding/decoding
│   │   │   ├── dependencies.py       # FastAPI auth/RBAC dependency injection
│   │   │   └── audit.py              # Audit logging helper
│   │   ├── db/
│   │   │   ├── session.py            # SQLAlchemy engine & session factory
│   │   │   └── init_db.py            # Database schema creation & seeding
│   │   ├── models/
│   │   │   ├── db_models.py          # SQLAlchemy relational ORM models
│   │   │   └── schemas.py            # Pydantic v2 request/response schemas
│   │   ├── routers/
│   │   │   ├── health.py             # Health check endpoint (/api/v1/health)
│   │   │   ├── auth.py               # Authentication & RBAC routes (/api/v1/auth)
│   │   │   ├── collections.py        # Scheme collection routes (/api/v1/collections)
│   │   │   ├── documents.py          # Document catalog routes (/api/v1/documents)
│   │   │   ├── search.py             # Search & RAG query routes (/api/v1/query)
│   │   │   └── audit.py              # Administrative audit logs (/api/v1/admin/audit-logs)
│   │   ├── services/
│   │   │   ├── auth_service.py       # Auth & role management (Prompt 05 preserved)
│   │   │   ├── document_service.py   # Document metadata & version management
│   │   │   ├── search_service.py     # Grounded retrieval & citation synthesis
│   │   │   ├── pinecone_service.py   # Pinecone vector store integration
│   │   │   └── audit_service.py      # Immutable audit trail recording
│   │   └── workers/
│   │       ├── background_jobs.py    # Background task dispatcher
│   │       └── document_processor.py # PDF parsing, page splitting & chunking worker
│   └── tests/
│       ├── conftest.py               # Pytest database fixtures & TestClient
│       ├── test_config.py            # Settings validation tests
│       ├── test_health.py            # Health check integration tests
│       └── test_auth.py              # Auth and RBAC permission tests
│
└── frontend/                         # Next.js TypeScript Frontend
    ├── package.json                  # Next.js dependencies and scripts
    ├── tsconfig.json                 # TypeScript compiler configuration
    ├── next.config.js                # Next.js build and environment config
    └── src/
        ├── app/
        │   ├── layout.tsx            # Root HTML layout with typography & metadata
        │   └── page.tsx              # Minimal responsive landing page
        ├── components/
        │   ├── Navbar.tsx            # Header with role badge and sign-in trigger
        │   ├── HeroSearch.tsx        # Scheme search bar with category filter
        │   ├── SchemeCatalog.tsx     # Card grid of indexed scheme collections
        │   ├── CitationPreviewModal.tsx # PDF page verification modal
        │   ├── DisclaimerBanner.tsx  # Legal eligibility notice banner
        │   ├── HealthStatusBadge.tsx # Real-time backend connectivity badge
        │   └── AuthModal.tsx         # Multi-role login and registration dialog
        ├── lib/
        │   ├── api.ts                # Typed fetch API client
        │   └── types.ts              # TypeScript interfaces
        └── styles/
            └── globals.css           # High-trust design system and CSS stylesheet
```

---

## Local Development Instructions

### 1. Prerequisites
- **Python:** Version 3.11 or higher
- **Node.js:** Version 18.0 or higher
- **npm:** Version 9.0 or higher

### 2. Environment Configuration
Copy the placeholder environment configuration template:
```bash
cp .env.example .env
```

### 3. Backend Setup & Startup
Install Python dependencies:
```bash
pip install -r backend/requirements.txt
```

Initialize and seed the local SQLite database:
```bash
python -m backend.app.db.init_db
```

Start the FastAPI development server:
```bash
python -m uvicorn backend.app.main:app --host 0.0.0.0 --port 8000 --reload
```
The backend API is accessible at `http://localhost:8000`.  
Interactive Swagger API documentation is available at `http://localhost:8000/docs`.

### 4. Frontend Setup & Startup
In a separate terminal, install dependencies and start the Next.js development server:
```bash
cd frontend
npm install
npm run dev
```
The web portal will be accessible at `http://localhost:3000`.

---

## Pre-Seeded Development Accounts

For local evaluation and testing of role-based features, the database is pre-seeded with the following credentials:

| Role | Email | Password | Permissions |
| :--- | :--- | :--- | :--- |
| **System Administrator** | `admin.dev@welfareconnect.local` | `Admin@123456` | Full administrative control (`admin:all`, `users:manage`, `audit:read`, `docs:all`) |
| **Helpdesk Officer** | `helpdesk.staff@welfareconnect.local` | `Staff@123456` | Frontline counter service (`query:execute`, `citations:preview`, `eligibility:check`) |
| **Citizen (New)** | Register via UI | Min 6 chars | Public query execution and citation review |

---

## Verification & Testing

### Run Backend Unit & Integration Tests
```bash
python -m pytest backend/tests -v
```
Or via workspace script:
```bash
npm test
```

### Run Formatting, Linting & Type-Checking
```bash
# Lint Python codebase
npm run lint:backend

# Type-check Python backend
npm run type-check:backend

# Format codebase
npm run format
```

### Test Health Check Endpoint
```bash
curl http://localhost:8000/api/v1/health
```
Example response:
```json
{
  "status": "healthy",
  "version": "1.0.0",
  "environment": "development",
  "components": {
    "database": {
      "status": "healthy",
      "message": "Database connection active and responsive."
    },
    "vector_store": {
      "status": "healthy",
      "message": "Pinecone index: welfareconnect-schemes-index (configured_placeholder)"
    },
    "storage": {
      "status": "healthy",
      "message": "Storage type: local"
    }
  },
  "timestamp": "2026-09-18T12:45:00.000000"
}
```

---

## Architecture Documentation

- **[Product Requirements Document](file:///e:/S67-0926-Dataforge-AiRag-WelfareConnect-/docs/product-requirements.md)**: User roles, user journeys, MVP functional/non-functional requirements, safety constraints, and success metrics.
- **[Architecture Specification](file:///e:/S67-0926-Dataforge-AiRag-WelfareConnect-/docs/architecture.md)**: Frontend components, backend services, database schema, Pinecone vector indexing, RAG retrieval flow, and security model.
- **[Data-Flow Diagram](file:///e:/S67-0926-Dataforge-AiRag-WelfareConnect-/docs/data-flow.mmd)**: Visual Mermaid diagram mapping document ingestion, semantic chunking, and grounded query execution.
