# Visual Search E-Commerce

A visual search engine for e-commerce using multimodal embeddings (Gemini) and vector similarity search (Qdrant).

## Stack

- **Backend**: FastAPI + Python
- **Embeddings**: Google Gemini (`google-genai`)
- **Vector DB**: Qdrant
- **Frontend**: TBD

## Quick Start

### 1. Start Qdrant

```bash
docker compose up -d
```

### 2. Set up backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env  # fill in GEMINI_API_KEY
```

### 3. Run the API

```bash
uvicorn src.api:app --reload
```

## Project Structure

```
backend/
├── src/
│   ├── embeddings.py    # Gemini embedding generation
│   ├── vector_store.py  # Qdrant client wrapper
│   ├── indexer.py       # Product indexing pipeline
│   └── api.py           # FastAPI routes
├── data/
│   └── sample_products.json
├── requirements.txt
└── .env.example
frontend/                # TBD
docker-compose.yml       # Qdrant service
```
