import logging
import os
import time
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from embeddings import GeminiEmbedder
from vector_store import COLLECTION_NAME, ProductVectorStore

load_dotenv()

logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    datefmt="%H:%M:%S",
)

# ---------------------------------------------------------------------------
# Application state (initialized once at startup)
# ---------------------------------------------------------------------------

_embedder: GeminiEmbedder | None = None
_store: ProductVectorStore | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _embedder, _store

    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY environment variable is not set.")

    qdrant_host = os.environ.get("QDRANT_HOST", "localhost")
    qdrant_port = int(os.environ.get("QDRANT_PORT", 6333))

    logger.info("Connecting to Qdrant at %s:%d", qdrant_host, qdrant_port)
    _store = ProductVectorStore(host=qdrant_host, port=qdrant_port)

    logger.info("Initializing Gemini embedder...")
    _embedder = GeminiEmbedder(api_key=api_key)

    logger.info("API ready.")
    yield

    _embedder = None
    _store = None


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

app = FastAPI(
    title="Visual Search API",
    description="Multimodal product search powered by Gemini embeddings and Qdrant.",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Request logging middleware
# ---------------------------------------------------------------------------

@app.middleware("http")
async def log_requests(request: Request, call_next):
    start = time.perf_counter()
    response = await call_next(request)
    elapsed_ms = (time.perf_counter() - start) * 1000
    logger.info(
        "%s %s → %d  (%.1f ms)",
        request.method,
        request.url.path,
        response.status_code,
        elapsed_ms,
    )
    return response


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------

class TextSearchRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=1000)
    category: str | None = None
    max_price: float | None = Field(default=None, gt=0)
    limit: int = Field(default=10, ge=1, le=100)


class ProductResult(BaseModel):
    id: str
    name: str
    description: str
    category: str
    price: float
    image_url: str
    similarity_score: float


class SearchResponse(BaseModel):
    results: list[ProductResult]
    query_time_ms: float
    total_found: int


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_deps() -> tuple[GeminiEmbedder, ProductVectorStore]:
    if _embedder is None or _store is None:
        raise HTTPException(status_code=503, detail="Service not initialized.")
    return _embedder, _store


def _to_search_response(
    raw: list[dict], start: float
) -> SearchResponse:
    results = [
        ProductResult(
            id=r["id"],
            name=r["name"] or "",
            description=r["description"] or "",
            category=r["category"] or "",
            price=r["price"] or 0.0,
            image_url=r["image_url"] or "",
            similarity_score=round(r["score"], 6),
        )
        for r in raw
    ]
    return SearchResponse(
        results=results,
        query_time_ms=round((time.perf_counter() - start) * 1000, 2),
        total_found=len(results),
    )


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@app.get("/health", tags=["ops"])
async def health():
    """Liveness + readiness check."""
    qdrant_ok = False
    vectors_count = 0

    if _store is not None:
        try:
            info = _store.get_collection_info()
            qdrant_ok = info["status"] == "green"
            vectors_count = info["vectors_count"] or 0
        except Exception:
            qdrant_ok = False

    return {
        "status": "ok",
        "qdrant": qdrant_ok,
        "vectors_count": vectors_count,
    }


@app.get("/categories", tags=["catalog"])
async def get_categories():
    """Returns the list of unique categories present in the index."""
    _, store = _get_deps()

    categories: set[str] = set()
    offset = None

    while True:
        records, next_offset = store.client.scroll(
            collection_name=COLLECTION_NAME,
            limit=100,
            offset=offset,
            with_payload=["category"],
            with_vectors=False,
        )
        for record in records:
            cat = (record.payload or {}).get("category")
            if cat:
                categories.add(cat)

        if next_offset is None:
            break
        offset = next_offset

    return {"categories": sorted(categories)}


@app.post("/search/text", response_model=SearchResponse, tags=["search"])
async def search_text(body: TextSearchRequest):
    """Text search using Gemini embeddings."""
    embedder, store = _get_deps()
    start = time.perf_counter()

    try:
        query_vector = embedder.embed_query(body.query)
    except Exception as exc:
        logger.exception("Embedding failed")
        raise HTTPException(status_code=502, detail=f"Embedding error: {exc}")

    try:
        raw = store.search(
            query_vector=query_vector,
            k=body.limit,
            category=body.category,
            max_price=body.max_price,
        )
    except Exception as exc:
        logger.exception("Qdrant search failed")
        raise HTTPException(status_code=502, detail=f"Search error: {exc}")

    return _to_search_response(raw, start)


@app.post("/search/image", response_model=SearchResponse, tags=["search"])
async def search_image(
    file: UploadFile = File(...),
    limit: int = Form(default=10, ge=1, le=100),
    category: str | None = Form(default=None),
    max_price: float | None = Form(default=None),
):
    """Image search: upload a photo and find visually similar products."""
    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(
            status_code=422,
            detail=f"File must be an image, got: {file.content_type}",
        )

    embedder, store = _get_deps()
    start = time.perf_counter()

    image_bytes = await file.read()
    if not image_bytes:
        raise HTTPException(status_code=422, detail="Uploaded file is empty.")

    try:
        query_vector = embedder.embed_image(image_bytes)
    except Exception as exc:
        logger.exception("Image embedding failed")
        raise HTTPException(status_code=502, detail=f"Embedding error: {exc}")

    try:
        raw = store.search(
            query_vector=query_vector,
            k=limit,
            category=category,
            max_price=max_price,
        )
    except Exception as exc:
        logger.exception("Qdrant search failed")
        raise HTTPException(status_code=502, detail=f"Search error: {exc}")

    return _to_search_response(raw, start)


@app.post("/search/multimodal", response_model=SearchResponse, tags=["search"])
async def search_multimodal(
    query: str | None = Form(default=None),
    file: UploadFile | None = File(default=None),
    limit: int = Form(default=10, ge=1, le=100),
    category: str | None = Form(default=None),
    max_price: float | None = Form(default=None),
):
    """
    Multimodal search: text and/or image.

    - Text + image → embed_product (single multimodal call)
    - Text only    → embed_query
    - Image only   → embed_image
    """
    has_text = bool(query and query.strip())
    has_file = file is not None and file.filename

    if not has_text and not has_file:
        raise HTTPException(
            status_code=422,
            detail="Provide at least one of: query (text) or file (image).",
        )

    embedder, store = _get_deps()
    start = time.perf_counter()

    image_bytes: bytes | None = None
    if has_file:
        if not file.content_type or not file.content_type.startswith("image/"):
            raise HTTPException(
                status_code=422,
                detail=f"File must be an image, got: {file.content_type}",
            )
        image_bytes = await file.read()
        if not image_bytes:
            raise HTTPException(status_code=422, detail="Uploaded file is empty.")

    try:
        if has_text and has_file:
            # Multimodal: text + image in a single call
            query_vector = embedder.embed_product(
                name=query.strip(),
                description="",
                image_bytes=image_bytes,
            )
        elif has_text:
            query_vector = embedder.embed_query(query.strip())
        else:
            query_vector = embedder.embed_image(image_bytes)
    except Exception as exc:
        logger.exception("Multimodal embedding failed")
        raise HTTPException(status_code=502, detail=f"Embedding error: {exc}")

    try:
        raw = store.search(
            query_vector=query_vector,
            k=limit,
            category=category,
            max_price=max_price,
        )
    except Exception as exc:
        logger.exception("Qdrant search failed")
        raise HTTPException(status_code=502, detail=f"Search error: {exc}")

    return _to_search_response(raw, start)
