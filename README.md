# Helios — Healthcare AI Hybrid Graph RAG Platform

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-009688.svg)](https://fastapi.tiangolo.com)
[![React 19](https://img.shields.io/badge/React-19-61DAFB.svg)](https://react.dev/)
[![TypeScript](https://img.shields.io/badge/TypeScript-5.x-3178C6.svg)](https://www.typescriptlang.org/)
[![Qdrant](https://img.shields.io/badge/Qdrant-v1.19.1-DC2626.svg)](https://qdrant.tech/)
[![Neo4j](https://img.shields.io/badge/Neo4j-v5.23.0-008CC1.svg)](https://neo4j.com/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

> **Helios** is an enterprise-grade clinical decision-support and medical document intelligence platform powered by a **Tri-Hybrid Retrieval Engine** (Dense Vector Search via Qdrant, Lexical BM25, and Relational Knowledge Graph Subgraphs via Neo4j) with Reciprocal Rank Fusion (RRF), FlashRank Cross-Encoder reranking, and four specialized autonomous healthcare agents.

---

> [!CAUTION]
> **Clinical Safety & Research Advisory**: Helios is designed strictly as an assistive clinical research and medical document exploration platform. It is **not** clinically validated, FDA/CE-cleared, or intended for autonomous diagnostic or treatment decisions. All synthesized recommendations, risk stratifications, and dosages must be independently verified by a licensed healthcare professional.

---

## Table of Contents

- [Key Capabilities](#key-capabilities)
  - [1. Domain-Specialized Healthcare Agents](#1-domain-specialized-healthcare-agents)
  - [2. Tri-Hybrid Retrieval Engine](#2-tri-hybrid-retrieval-engine)
  - [3. Multimodal Clinical Document Ingestion](#3-multimodal-clinical-document-ingestion)
  - [4. Rich Clinical Visualization UI](#4-rich-clinical-visualization-ui)
- [Prerequisites](#prerequisites)
- [Quickstart: Step-by-Step Setup](#quickstart-step-by-step-setup)
  - [Step 1: Clone & Configure Environment](#step-1-clone--configure-environment)
  - [Step 2: Start Infrastructure Services (Docker)](#step-2-start-infrastructure-services-docker)
  - [Step 3: Launch the Backend API](#step-3-launch-the-backend-api)
  - [Step 4: Launch the Frontend Web App](#step-4-launch-the-frontend-web-app)
- [Service Ports & Endpoints](#service-ports--endpoints)
- [Environment Configuration](#environment-configuration)
- [Testing & Code Quality](#testing--code-quality)
- [Troubleshooting & FAQ](#troubleshooting--faq)

---

## Key Capabilities

### 1. Domain-Specialized Healthcare Agents

Helios implements four distinct, non-interchangeable clinical agents with strict reasoning hierarchies and guideline protocols:

| Agent             | Focus & Guidelines                                     | Clinical Decision Hierarchy & Red Flags                                                                                                                                                                                                                                                                 |
| :---------------- | :----------------------------------------------------- | :------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| **Dr. Cardio**    | **Cardiology & Hemodynamics**<br>_(ACC/AHA Protocols)_ | Evaluates arterial blood pressure, MAP, rhythm, telemetry, and signs of cardiogenic shock. Mandates 12-lead ECG, high-sensitivity Troponin, BNP/NT-proBNP, TTE/TEE echo parameters, and validated risk scoring (HEART, TIMI, CHA₂DS₂-VASc).                                                             |
| **Dr. Neuro**     | **Neurology & Neurovascular**<br>_(AAN Standards)_     | Mandates **Neuro-Anatomical Localization ("Where is the lesion?")** (CNS vs. PNS). Evaluates cranial nerves, motor/sensory tracts, and NIHSS. Enforces hyperacute ischemic stroke windows (IV thrombolysis < 4.5h, endovascular thrombectomy < 24h), emergent NCCT/MRI DWI-ADC, and SAH/PRES red flags. |
| **Dr. Gynae**     | **Obstetrics & Gynaecology**<br>_(ACOG Protocols)_     | Enforces mandatory **Beta-hCG first-line testing** for females of reproductive age (12–55y). Evaluates gestational age, obstetric triage, preeclampsia with severe features/HELLP, ectopic pregnancy, PALM-COEIN classification for AUB, and Briggs/ACOG teratogenicity.                                |
| **Dr. Internist** | **Internal & General Medicine**<br>_(ACP Standards)_   | Synthesizes complex multi-organ interactions, metabolic/electrolyte homeostasis, and atypical presentations. Directs baseline diagnostic workup (CBC with differential, CMP, TSH, Urinalysis, ESR/CRP), polypharmacy reconciliation, and Beers Criteria toxicity audits.                                |

### 2. Tri-Hybrid Retrieval Engine

1. **Dense Vector Retrieval (Qdrant)**: High-dimensional semantic embeddings (OpenAI `text-embedding-3-small` / Gemini 768-dim) capture nuanced clinical natural language and synonym matching.
2. **Lexical Keyword Search (BM25)**: Exact nomenclature matching for pharmacotherapy dosages, chemical compounds, anatomical terms, and ICD-10/CPT codes.
3. **Relational Knowledge Graph Subgraphs (Neo4j)**: Multi-hop graph traversals across clinical entities (`Disease`, `Symptom`, `Medication`, `Treatment`, `LabTest`) linked by verified clinical edges (`TREATS`, `CONTRAINDICATES`, `CAUSES`, `INDICATES`).
4. **Reciprocal Rank Fusion (RRF)**: Merges disparate rank lists objectively without arbitrary score-scale distortion.
5. **FlashRank Cross-Encoder Reranker**: Performs lightning-fast local reranking over candidate chunks to maximize evidence precision.

### 3. Multimodal Clinical Document Ingestion

- **Multi-Format Ingestion**: Supports `.pdf`, `.docx`, `.xlsx`, `.pptx`, `.txt`, and `.csv`.
- **Medical Domain Guardrail**: Pre-ingestion validation rejects non-medical files (financial reports, marketing slides, general code) to protect knowledge base integrity.
- **Hierarchical Medical Chunker**: Preserves clinical document structure, diagnostic headings, sub-headings, and Markdown table layouts.
- **Multimodal Extraction**: Automatically extracts embedded ECG strips, histology figures, ultrasound charts, and diagrams via PyMuPDF; indexes visual assets alongside text passages with multimodal vision summaries.
- **Multi-Doc Synthesis & Contradiction Detection**: Detects and highlights clinical disagreements or conflicting lab values across uploaded records.

### 4. Rich Clinical Visualization UI

- **Mermaid.js Flowcharts**: Interactive diagnostic pathways, clinical triage algorithms, and treatment decision trees.
- **KaTeX Equation Engine**: Formatted clinical calculators (e.g., eGFR CKD-EPI, MELD score, anion gap, CHA₂DS₂-VASc).
- **Recharts Biomarker Trendlines**: Dynamic lab panel visualizers for longitudinal patient tracking.
- **Evidence Drawer & Lightbox**: Side-by-side citation drawer showing chunk provenance, similarity scores, and full-resolution image inspection.
- **Persistent Chat History**: Session switching and full audit trail backed by PostgreSQL.

---

## Prerequisites

Ensure you have the following installed on your host system:

- **Docker & Docker Compose** (Docker Desktop on Windows/macOS or Docker Engine on Linux)
- **Python 3.11+** with Astral [`uv`](https://github.com/astral-sh/uv) (recommended for dependency management)
- **Node.js 20+** and **npm 10+**
- **Git**
- An active API key for **OpenAI** (`OPENAI_API_KEY`), **Groq** (`GROQ_API_KEY`), or **Google Gemini** (`GEMINI_API_KEY`)

---

---

## Quickstart: Step-by-Step Setup

### Step 1: Clone & Configure Environment

Clone the repository and copy the environment configuration:

```bash
git clone https://github.com/your-org/healthcare_hybrid_rag.git
cd healthcare_hybrid_rag

# Copy example environment configuration
cp .env.example .env
```

Open `.env` in your text editor and ensure your API keys (`OPENAI_API_KEY`, `GROQ_API_KEY`, or `GEMINI_API_KEY`) are populated.

---

### Option A: Run Full Platform in Docker (Recommended)

To launch the complete platform — **Frontend**, **Backend**, **PostgreSQL**, **Qdrant**, and **Neo4j** — in Docker with a single command:

```bash
# From repository root:
docker compose up --build -d
```

Verify all 5 services are healthy and running:

```bash
docker ps --filter "name=healthcare_"
```

Expected running containers:

- `healthcare_frontend` (Port `5173:80` - React Web App with Nginx & reverse proxy)
- `healthcare_backend` (Port `8000:8000` - FastAPI + Grounded RAG Coordinator)
- `healthcare_postgres` (Port `5433:5432` - PostgreSQL 16)
- `healthcare_qdrant` (Port `6333:6333` - Qdrant Vector DB & Web Dashboard)
- `healthcare_neo4j` (Port `7687:7687`, `7474:7474` - Neo4j Graph DB & Cypher Browser)

Once running, access the web app immediately at:
**`http://localhost:5173`**

To stop all services:

```bash
docker compose down
```

---

### Option B: Local Development Setup (Manual)

If you prefer developing locally with hot reload:

#### 1. Start Infrastructure Databases

```bash
docker compose -f infra/docker-compose.yml up -d postgres qdrant neo4j
```

#### 2. Start Backend API

```bash
cd server
uv sync
uv run uvicorn app.main:app --reload --port 8000
```

#### 3. Start Frontend Web Client

```bash
cd client
npm install
npm run dev
```

Log in using the private access key configured in your `.env` (`admin` or your custom key).

---

## Service Ports & Endpoints

| Service                  | Port   | Description                                | Health / Test Endpoint            |
| :----------------------- | :----- | :----------------------------------------- | :-------------------------------- |
| **Helios Web Client**    | `5173` | React 19 / Vite Frontend Interface         | `http://localhost:5173`           |
| **FastAPI Backend**      | `8000` | REST API, SSE Streaming & Chat Agents      | `http://localhost:8000/health`    |
| **Swagger UI**           | `8000` | Interactive OpenAPI documentation          | `http://localhost:8000/docs`      |
| **PostgreSQL**           | `5433` | Relational DB (sessions, chunks, metadata) | `pg_isready -p 5433`              |
| **Qdrant Web Dashboard** | `6333` | Dense Vector Search & Embeddings Web UI    | `http://localhost:6333/dashboard` |
| **Neo4j Graph (Bolt)**   | `7687` | Relational Knowledge Graph Protocol        | `bolt://localhost:7687`           |
| **Neo4j Browser (HTTP)** | `7474` | Interactive Cypher Query Web Console       | `http://localhost:7474`           |

---

## Environment Configuration

| Variable                    | Default Value                    | Description                                                    |
| :-------------------------- | :------------------------------- | :------------------------------------------------------------- |
| `ENVIRONMENT`               | `development`                    | Deployment environment (`development` / `production`).         |
| `PROJECT_NAME`              | `Healthcare AI Hybrid Graph RAG` | Application display name.                                      |
| `API_V1_STR`                | `/api/v1`                        | Base route prefix for API endpoints.                           |
| `API_KEYS`                  | `{"admin":"..."}`                | JSON dictionary mapping access keys to user roles.             |
| `POSTGRES_SERVER`           | `localhost`                      | Host address for PostgreSQL database.                          |
| `POSTGRES_PORT`             | `5433`                           | Host port for PostgreSQL database.                             |
| `POSTGRES_USER`             | `postgres`                       | PostgreSQL username.                                           |
| `POSTGRES_PASSWORD`         | `postgres`                       | PostgreSQL user password.                                      |
| `POSTGRES_DB`               | `hybrid_rag`                     | PostgreSQL database name.                                      |
| `DATABASE_URL`              | `postgresql+asyncpg://...`       | Async SQLAlchemy database connection URL.                      |
| `QDRANT_HOST`               | `localhost`                      | Qdrant host URL.                                               |
| `QDRANT_PORT`               | `6333`                           | Qdrant REST API port.                                          |
| `QDRANT_COLLECTION_NAME`    | `healthcare_knowledge`           | Collection name for dense vector chunk embeddings.             |
| `NEO4J_URI`                 | `bolt://localhost:7687`          | Neo4j Bolt connection string.                                  |
| `NEO4J_USER`                | `neo4j`                          | Neo4j database username.                                       |
| `NEO4J_PASSWORD`            | `password123`                    | Neo4j database authentication password.                        |
| `OPENAI_API_KEY`            | _(None)_                         | Primary OpenAI API key for generation and embeddings.          |
| `OPENAI_MODEL_NAME`         | `gpt-4o-mini`                    | Default OpenAI chat completion model.                          |
| `OPENAI_EMBEDDING_MODEL`    | `text-embedding-3-small`         | Default OpenAI vector embedding model.                         |
| `GROQ_API_KEY`              | _(None)_                         | Groq API key for low-latency inference, fallback, and Whisper. |
| `GROQ_MODEL_NAME`           | `openai/gpt-oss-120b`            | Default Groq model for reasoning and fallback.                 |
| `GEMINI_API_KEY`            | _(None)_                         | Google Gemini API key for fallback inference and embeddings.   |
| `DEFAULT_LLM_PROVIDER`      | `openai`                         | Primary LLM inference provider (`openai` / `groq` / `gemini`). |
| `DEFAULT_MODEL_NAME`        | `gpt-4o-mini`                    | Primary LLM model identifier.                                  |
| `EMBEDDING_MODEL`           | `text-embedding-3-small`         | Semantic embedding model identifier.                           |
| `VOICE_TRANSCRIBE_PROVIDER` | `groq`                           | Provider for audio dictation transcription (Whisper).          |
| `MAX_UPLOAD_BYTES`          | `26214400`                       | Maximum allowed file upload size (25 MiB).                     |

---

## Testing & Code Quality

Helios enforces strict linting, formatting, and test suites across both the server and client.

### Unified Repository Check

Run all quality checks in a single automated command:

```bash
# Runs Python linting, formatting checks, client linting, server pytest suite, and client build
npm --prefix infra run check
```

### Individual Check Commands

```bash
# 1. Python Linting (Ruff)
npm --prefix infra run lint:python

# 2. Python Code Formatting (Ruff)
npm --prefix infra run format:python

# 3. Server Unit & Integration Tests (Pytest)
npm --prefix infra run test:server
# Or directly:
cd server && uv run pytest

# 4. Frontend Linting (ESLint)
npm --prefix infra run lint:client

# 5. Frontend Production Build Check (TypeScript + Vite)
npm --prefix infra run build

# 6. Prettier Global Code Formatting
npm --prefix infra run format
```

> **Note on Testing**: The Pytest suite runs in complete isolation utilizing an in-memory SQLite database, in-memory Qdrant, and mocked graph/provider responses. It does not consume live LLM API quota or require live Docker services to pass.

---

## Troubleshooting & FAQ

### 1. Port 5433 or 6333 already in use

If local instances of PostgreSQL or Qdrant are already running on your machine:

- Edit the mapped port in `.env` (e.g., `POSTGRES_PORT=5434`).
- Update `DATABASE_URL` in `.env` to match the new port.

### 2. Neo4j authentication failure

If Neo4j fails to connect with authentication errors:

- Ensure `NEO4J_PASSWORD` in `.env` matches what is set in `infra/docker-compose.yml`.
- If resetting passwords, stop the container and clear the volume:
  ```bash
  docker compose -f infra/docker-compose.yml down -v
  docker compose -f infra/docker-compose.yml up -d
  ```

### 3. File ingestion rejected ("Non-healthcare document")

Helios includes a medical relevance guardrail to keep the clinical vector index clean. If a document is rejected:

- Confirm the file is a clinical report, medical textbook excerpt, clinical trial paper, or healthcare guideline.
- Generic spreadsheets, financial slides, or personal resumes are purposefully filtered out by design.

### 4. LLM API Rate Limits (429)

- If you hit rate limits on OpenAI, Helios automatically cascades to Groq or Google Gemini.
- Check your provider quota in `.env` or set `DEFAULT_LLM_PROVIDER=groq`.

---

## License

This project is licensed under the MIT License — see the [LICENSE](LICENSE) file for details.
