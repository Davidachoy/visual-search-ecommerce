# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Visual Search E-Commerce Engine — FastAPI backend (Google Gemini embeddings + Qdrant vector search) with a React/TypeScript frontend (Vite). Products are searched by text, image, or both (multimodal).

## Development Commands

All backend commands run from the `backend/` directory with the virtual environment activated:

```bash
# Activate virtual environment
source backend/.venv/bin/activate

# Start Qdrant vector database (required before any backend work)
docker compose up -d

# Check Qdrant connectivity
python scripts/health_check.py

# Index sample products into Qdrant
python scripts/index_products.py           # skips already-indexed products
python scripts/index_products.py --force   # re-embeds and overwrites all

# Start API server
uvicorn src.api:app --reload

# Frontend (from frontend/)
npm run dev     # dev server at localhost:5173, proxies /api → localhost:8000
npm run build   # production build

# Run module-level test harnesses
python src/embeddings.py
python src/vector_store.py
```

## Architecture

### Embedding Flow
- `src/embeddings.py` — `GeminiEmbedder` wraps the `google-genai` SDK using model `gemini-embedding-2-preview` (3072-dimensional vectors). Uses **different task types** for indexing vs. querying: `RETRIEVAL_DOCUMENT` when embedding products, `RETRIEVAL_QUERY` when embedding search queries. Multimodal: combines name + description + image bytes into a single vector. Falls back to text-only if no image.

### Vector Store
- `src/vector_store.py` — `ProductVectorStore` wraps the Qdrant client. String product IDs are converted to deterministic UUID v5 so upserts are idempotent. Collection name: `"products"`, distance: COSINE. Search supports optional `category` (exact match) and `max_price` (range) filters.

### Indexing Pipeline
- `src/indexer.py` — `ProductIndexer` orchestrates: check if already indexed → download image via `httpx` → call `GeminiEmbedder` → upsert to Qdrant. Has 3-attempt exponential backoff. Tracks character count and estimates API cost ($0.000002/1K chars).

### API
- `src/api.py` — placeholder (needs implementation). Expected endpoints: `POST /search/text`, `POST /search/image`, `POST /search/multimodal`, `GET /categories`, `GET /health`.

### Frontend
- React + TypeScript (Vite 9). Components in `frontend/src/components/`, API calls in `frontend/src/api/search.ts`.
- **Gotcha:** `react-dropzone` requires `tslib` — must be installed explicitly (`npm install tslib`).
- Uses React 17+ JSX transform — do not add `import React` at the top of files; `tsc` will error on the unused import.

### Data
- `data/sample_products.json` — 10 fashion products (footwear, outerwear, bags, dresses, tops, bottoms, accessories). Image URLs use `picsum.photos` seeds — they are random placeholder images, not actual product photos.

## Environment Setup

Copy `backend/.env.example` to `backend/.env` and set:
- `GEMINI_API_KEY` — required for all embedding operations
- `QDRANT_HOST` / `QDRANT_PORT` — defaults to `localhost:6333`

## Key Technical Decisions

- Python 3.13, no package build system — modules are imported via `sys.path` manipulation in scripts
- No linting or formatting config is present
- No test suite beyond inline `if __name__ == "__main__"` harnesses in each module
