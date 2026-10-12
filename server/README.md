# Healthcare AI Hybrid Graph RAG - Backend

FastAPI service powering the multi-agent Healthcare AI chatbot with Tri-Hybrid Retrieval (Qdrant + BM25 + Neo4j).

## Setup & Running with `uv`

```bash
# Sync dependencies and create virtual environment
uv sync

# Run development server
uv run uvicorn app.main:app --reload --port 8000

# Run Ruff linter and formatter
uv run ruff check .
uv run ruff format .

# Run Pytest
uv run pytest
```
