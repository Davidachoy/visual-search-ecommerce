"""
Shared fixtures for API tests.

Isolation strategy:
- GeminiEmbedder: mocked — returns deterministic vectors without calling the API.
- ProductVectorStore: real — points to Qdrant in Docker, collection "products_test".
- The test collection is created at session start and deleted at session end.
- The FastAPI lifespan is replaced by one that injects the mock embedder and test
  store, so no real GEMINI_API_KEY is required.
"""

import os
import random
import sys
from contextlib import asynccontextmanager
from io import BytesIO
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from PIL import Image

# Allow pytest to find modules in src/
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import api as api_module
import vector_store as vs_module
from api import app
from vector_store import ProductVectorStore

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

TEST_COLLECTION = "products_test"
VECTOR_SIZE = 3072

# Test products with an intentional spread of categories and prices:
#   max_price=100  → prod_t001, prod_t004, prod_t006, prod_t007, prod_t008, prod_t009
#   category=bags  → prod_t003, prod_t009
TEST_PRODUCTS = [
    {
        "id": "prod_t001",
        "name": "White Canvas Sneakers",
        "description": "Minimalist white sneakers for everyday use.",
        "category": "footwear",
        "price": 89.99,
        "image_url": "https://picsum.photos/seed/sneakers/400/400",
    },
    {
        "id": "prod_t002",
        "name": "Vintage Denim Jacket",
        "description": "Washed blue denim jacket with button front.",
        "category": "outerwear",
        "price": 129.99,
        "image_url": "https://picsum.photos/seed/denim/400/400",
    },
    {
        "id": "prod_t003",
        "name": "Leather Crossbody Bag",
        "description": "Compact genuine leather bag with gold hardware.",
        "category": "bags",
        "price": 175.00,
        "image_url": "https://picsum.photos/seed/leatherbag/400/400",
    },
    {
        "id": "prod_t004",
        "name": "Floral Summer Dress",
        "description": "Lightweight floral print midi dress.",
        "category": "dresses",
        "price": 64.99,
        "image_url": "https://picsum.photos/seed/floraldress/400/400",
    },
    {
        "id": "prod_t005",
        "name": "Wool Blend Overcoat",
        "description": "Tailored camel overcoat with double-breasted front.",
        "category": "outerwear",
        "price": 299.00,
        "image_url": "https://picsum.photos/seed/overcoat/400/400",
    },
    {
        "id": "prod_t006",
        "name": "Slim Fit Chino Pants",
        "description": "Stretch cotton slim fit chinos in khaki.",
        "category": "bottoms",
        "price": 59.99,
        "image_url": "https://picsum.photos/seed/chinos/400/400",
    },
    {
        "id": "prod_t007",
        "name": "Aviator Sunglasses",
        "description": "Metal frame aviator sunglasses with UV400 lenses.",
        "category": "accessories",
        "price": 49.99,
        "image_url": "https://picsum.photos/seed/aviators/400/400",
    },
    {
        "id": "prod_t008",
        "name": "Ribbed Turtleneck Sweater",
        "description": "Cozy ribbed knit turtleneck in ivory.",
        "category": "tops",
        "price": 79.99,
        "image_url": "https://picsum.photos/seed/turtleneck/400/400",
    },
    {
        "id": "prod_t009",
        "name": "Canvas Tote Bag",
        "description": "Large natural canvas tote with reinforced handles.",
        "category": "bags",
        "price": 34.99,
        "image_url": "https://picsum.photos/seed/tote/400/400",
    },
    {
        "id": "prod_t010",
        "name": "Running Sports Watch",
        "description": "Digital sports watch with GPS and heart rate monitor.",
        "category": "accessories",
        "price": 199.99,
        "image_url": "https://picsum.photos/seed/sportswatch/400/400",
    },
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_vector(seed: int) -> list[float]:
    """Returns a deterministic VECTOR_SIZE-dimensional vector for the given seed."""
    rng = random.Random(seed)
    return [rng.uniform(-1, 1) for _ in range(VECTOR_SIZE)]


FIXED_VECTOR = _make_vector(42)


# ---------------------------------------------------------------------------
# Session fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def mock_embedder() -> MagicMock:
    """
    Mocked GeminiEmbedder that returns deterministic vectors.
    The same input always produces the same vector across calls.
    """
    m = MagicMock()
    m.embed_text.side_effect = lambda text: _make_vector(hash(text) % 9999)
    m.embed_query.side_effect = lambda text: _make_vector(hash(text) % 9999)
    m.embed_image.return_value = FIXED_VECTOR
    m.embed_product.side_effect = lambda name, description, image_bytes=None: _make_vector(
        hash(name) % 9999
    )
    return m


@pytest.fixture(scope="session")
def test_store():
    """
    Real ProductVectorStore pointing to the 'products_test' collection.
    The collection is created at session start and deleted at session end.

    Two references to COLLECTION_NAME are patched:
    - vs_module: used internally by ProductVectorStore methods.
    - api_module: used by endpoints (imported via 'from vector_store import').
    """
    with (
        patch.object(vs_module, "COLLECTION_NAME", TEST_COLLECTION),
        patch.object(api_module, "COLLECTION_NAME", TEST_COLLECTION),
    ):
        store = ProductVectorStore()
        yield store
        store.client.delete_collection(TEST_COLLECTION)


@pytest.fixture(scope="session", autouse=True)
def indexed_products(test_store, mock_embedder):
    """Indexes TEST_PRODUCTS into the test collection before any test runs."""
    for product in TEST_PRODUCTS:
        embedding = mock_embedder.embed_product(
            name=product["name"],
            description=product["description"],
            image_bytes=None,
        )
        test_store.upsert_product(
            product_id=product["id"],
            embedding=embedding,
            payload={k: v for k, v in product.items() if k != "id"},
        )


@pytest.fixture(scope="session")
def client(mock_embedder, test_store, indexed_products):
    """
    FastAPI TestClient with the mock embedder and test store injected.
    The original lifespan is replaced to avoid real connections to Gemini.
    """
    @asynccontextmanager
    async def test_lifespan(application):
        api_module._embedder = mock_embedder
        api_module._store = test_store
        yield
        api_module._embedder = None
        api_module._store = None

    original_lifespan = app.router.lifespan_context
    app.router.lifespan_context = test_lifespan

    with TestClient(app) as test_client:
        yield test_client

    app.router.lifespan_context = original_lifespan


@pytest.fixture(scope="session")
def test_image_bytes() -> bytes:
    """Minimal 64×64 JPEG image generated in memory."""
    buf = BytesIO()
    Image.new("RGB", (64, 64), color=(200, 100, 50)).save(buf, format="JPEG")
    return buf.getvalue()


@pytest.fixture(scope="session")
def test_image_file(test_image_bytes) -> Path:
    """
    Writes the test image to tests/fixtures/test_image.jpg
    so it is available as a real file on disk.
    """
    fixtures_dir = Path(__file__).parent / "fixtures"
    fixtures_dir.mkdir(exist_ok=True)
    img_path = fixtures_dir / "test_image.jpg"
    img_path.write_bytes(test_image_bytes)
    return img_path
