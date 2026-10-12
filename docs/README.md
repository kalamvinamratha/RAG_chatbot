# Healthcare AI – Hybrid Graph RAG Platform

> A healthcare document-assistance prototype using Qdrant vectors, BM25 lexical search, and Neo4j graph retrieval with RRF fusion, reranking, and clinical visualizations. It is not clinically validated and must not replace professional judgment.

---

## 🌟 Key Capabilities

### 1. Domain-Specialized Healthcare Agents

- **Cardiology Agent**: Specialized in AHA/ACC guidelines, arrhythmia (AFib), heart failure, and cardiovascular pharmacotherapy.
- **Gynaecology Agent**: Tailored to ACOG protocols, obstetric triage, maternal-fetal care, and reproductive endocrinology.
- **Neurology Agent**: Aligned with AAN standards for stroke pathways (tPA window), neurodegenerative syndromes, and epilepsy management.
- **General Medicine Agent**: Primary care, triage, internal medicine, and multidisease management.

### 2. Multi-Format Clinical Document Ingestion

- Ingests **PDF**, **Word (.docx)**, **Excel (.xlsx)**, **PowerPoint (.pptx)**, and **Plain Text (.txt)**.
- Medical structure-preserving semantic chunker retaining hierarchical clinical sections and Markdown table layouts.
- Automated medical entity and relationship extraction (`Disease`, `Symptom`, `Medication`, `Treatment`, `LabTest`, `TREATS`, `CONTRAINDICATES`, `CAUSES`, `INDICATES`) directly mapped into **Neo4j**.

### 3. Tri-Hybrid Retrieval Engine

1. **Dense Vector Search (Qdrant)**: High-dimensional semantic embeddings understanding symptoms in clinical natural language.
2. **Lexical Keyword Search (BM25)**: Exact nomenclature matching for medication dosages, anatomical terms, and ICD codes.
3. **Knowledge Graph Subgraph Search (Neo4j)**: Multi-hop relational discovery (e.g., contraindications and causal interactions).

- **Reciprocal Rank Fusion (RRF)**: Merges all 3 ranking streams.
- **Cross-Encoder Reranker (FlashRank)**: Re-scores top-k chunks with high precision.

### 4. Built-in Add-On Features

1. **Multimodal Clinical Figure & Chart Extraction**:
   - PyMuPDF extraction of embedded charts, ECG strips, and medical figures.
   - Vision AI interpretation indexed alongside textual passages with high-resolution image lightboxes.
2. **Clinical Voice Input & Audio Dictation**:
   - Web Speech API dictation with a configured transcription-provider backend fallback.
3. **Cross-Document Multi-Doc Synthesis & Contradiction Detection**:
   - Multi-document query scoping with automated cross-document reconciliation and contradiction alerts.
4. **AI-Generated Clinical Follow-Up Question Suggestions**:
   - Specialty-tailored next-step clinical inquiries presented as interactive pills below every response.

### 5. Clinical UI Toolset

- **Mermaid.js Flowcharts**: Interactive diagnostic pathways and clinical decision trees.
- **KaTeX Equations**: Medical calculations and clinical formulas (e.g., eGFR, MELD).
- **Recharts Biomarker Trendlines**: Dynamic lab panel visualizers.
- **Evidence Drawer & Lightbox**: Interactive citation drawers with relevance scores and full-resolution image inspection.

---

## 🚀 Quickstart Guide

### Prerequisites

- **Python 3.11+** with [`uv`](https://github.com/astral-sh/uv)
- **Node.js 20+** with `npm`
- **PostgreSQL 16+** (Local or Docker)
- **Qdrant & Neo4j** (via Docker Compose in `infra/docker-compose.yml`)

### 1. Infrastructure Services

Run the commands below from the repository root, using separate terminals for the server and client.
Copy `.env.example` to `.env` in the repository root and configure your credentials.
Compose starts PostgreSQL, Qdrant, and Neo4j on localhost-only ports.

Set `API_KEYS` to a JSON object mapping workspace owner IDs to long, unique private
access keys (for example, `{"admin":"your-random-key"}`). Sign in to the client using
that key. API clients can send `Authorization: Bearer <key>`. Browser sessions use
an HttpOnly, SameSite cookie; production requires HTTPS and `ENVIRONMENT=production`.
Set `CORS_ORIGINS` to the exact browser origins allowed to access the server.

Documents, extracted assets, chats, and retrieval results are private to each owner.
Existing documents and sessions are assigned to `admin` by the startup ownership
migration. Specialty definitions are shared workspace configuration.

`GEMINI_API_KEY` is required for new document embeddings. Failed indexing is shown
as `failed`, and can be retried with the document's **Retry** button. Use **Reindex**
on previously uploaded documents to replace the old hash embeddings and graph
relationships with correctly scoped evidence. An empty document selection means
no document evidence; it never silently expands to all documents.

The default embedding model is `gemini-embedding-001` with an explicit 768-dimensional
output. The retired `text-embedding-004` model is not supported. Local Qdrant uses
HTTP on a loopback-only port; remote deployments should use HTTPS (`QDRANT_HTTPS=true`).

Deleting a document purges its vector entries, graph provenance, source file, and
extracted assets. If cleanup fails, the document remains in `deleting` status and
is excluded from retrieval; retry its delete action after services recover.
Uploads are limited to 25 MiB by default (`MAX_UPLOAD_BYTES`). CSV is supported;
legacy DOC, XLS, and PPT files must first be converted to DOCX, XLSX, and PPTX.

```powershell
# Start local PostgreSQL, Qdrant, and Neo4j using the root environment file
docker compose --env-file .env -p healthcare-hybrid-rag -f infra/docker-compose.yml up -d
```

### 2. Backend Setup

```powershell
cd server

# Install dependencies and sync virtualenv
uv sync

# Run development server
uv run uvicorn app.main:app --reload --port 8000
```

Interactive Swagger API docs: `http://localhost:8000/docs`

### 3. Frontend Setup

```powershell
cd client

# Install dependencies
npm install

# Run Vite development server
npm run dev
```

Access the Clinical Web Application at: `http://localhost:5173`

---

## 🧪 Testing & Code Quality

### Backend

```powershell
# Run Ruff linting and formatting
npm --prefix infra run lint:python
npm --prefix infra run check:python-format

# Run full Pytest test suite
cd server
uv run pytest
```

### Frontend & Pre-commit Hooks

```powershell
# Install repository tooling and register the Git hooks
npm --prefix infra ci

# Prettier formatting check
npm --prefix infra run lint:format

# Production build validation
npm --prefix client run build
```

The root `.husky/pre-commit` hook runs `lint-staged`, then checks Python linting and
formatting, repository formatting, client ESLint, server and client tests, and the
client TypeScript/Vite build. Tests use an isolated SQLite database, in-memory
Qdrant, and mocked provider/graph calls; they require no API keys or running services.
Live PostgreSQL, Neo4j, and provider checks are still needed when deploying.

Repository tooling lives in `infra/`. Use `npm --prefix infra run check` for all checks,
or `npm --prefix infra run format` to format files. Run `npm --prefix infra ci` to
install the tooling and register the root Husky hooks.
