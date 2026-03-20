import json
import logging
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path

import httpx
from tqdm import tqdm

from embeddings import GeminiEmbedder
from vector_store import COLLECTION_NAME, ProductVectorStore

logger = logging.getLogger(__name__)

# Pricing reference (March 2026): gemini-embedding-2-preview
# https://ai.google.dev/gemini-api/docs/pricing
_COST_PER_1K_CHARS = 0.000_002  # $0.000002 per 1K input characters (text)

_MAX_RETRIES = 3
_BACKOFF_BASE = 2.0  # seconds: 2, 4, 8


@dataclass
class IndexResult:
    indexed: int = 0
    failed: int = 0
    skipped: int = 0
    total_chars: int = 0  # proxy for token count (API doesn't return tokens)

    @property
    def total(self) -> int:
        return self.indexed + self.failed + self.skipped

    @property
    def estimated_cost_usd(self) -> float:
        return (self.total_chars / 1000) * _COST_PER_1K_CHARS

    def as_dict(self) -> dict:
        return {
            "indexed": self.indexed,
            "failed": self.failed,
            "skipped": self.skipped,
            "total": self.total,
            "total_chars": self.total_chars,
            "estimated_cost_usd": round(self.estimated_cost_usd, 6),
        }


class ProductIndexer:
    def __init__(
        self,
        embedder: GeminiEmbedder,
        store: ProductVectorStore,
        force: bool = False,
    ):
        self.embedder = embedder
        self.store = store
        self.force = force  # if True, re-embeds even if the product already exists

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def index_from_json(self, filepath: str) -> IndexResult:
        """Reads a JSON file with a list of products and indexes each one."""
        path = Path(filepath)
        if not path.exists():
            raise FileNotFoundError(f"Product file not found: {filepath}")

        with open(path) as f:
            products: list[dict] = json.load(f)

        result = IndexResult()

        with tqdm(products, desc="Indexing products", unit="product") as bar:
            for product in bar:
                bar.set_postfix(
                    id=product.get("id", "?"),
                    ok=result.indexed,
                    fail=result.failed,
                    skip=result.skipped,
                )
                success, chars, skipped = self._index_with_retry(product)
                if skipped:
                    result.skipped += 1
                elif success:
                    result.indexed += 1
                    result.total_chars += chars
                else:
                    result.failed += 1

        return result

    def index_product(self, product: dict) -> bool:
        """Indexes a single product. Returns True if successful."""
        success, _, skipped = self._index_with_retry(product)
        return success or skipped

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _already_indexed(self, product_id: str) -> bool:
        """Checks whether the product already exists in Qdrant."""
        point_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, product_id))
        records = self.store.client.retrieve(
            collection_name=COLLECTION_NAME,
            ids=[point_id],
            with_payload=False,
            with_vectors=False,
        )
        return len(records) > 0

    def _download_image(self, url: str, timeout: float = 10.0) -> bytes | None:
        """Downloads an image by URL. Returns None on failure."""
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            )
        }
        try:
            response = httpx.get(
                url, timeout=timeout, follow_redirects=True, headers=headers
            )
            if response.status_code == 429:
                time.sleep(2.0)
                response = httpx.get(
                    url, timeout=timeout, follow_redirects=True, headers=headers
                )
            response.raise_for_status()
            return response.content
        except Exception as exc:
            logger.warning("Image download failed for %s: %s", url, exc)
            return None

    def _index_with_retry(self, product: dict) -> tuple[bool, int, bool]:
        """
        Attempts to index a product up to _MAX_RETRIES times.

        Returns (success, chars_used, was_skipped).
        """
        product_id = product.get("id", "")

        # Check existence — skip if already indexed and --force is not set
        if not self.force and self._already_indexed(product_id):
            logger.debug("Product '%s' already indexed — skipping.", product_id)
            return False, 0, True

        last_exc: Exception | None = None
        for attempt in range(1, _MAX_RETRIES + 1):
            try:
                success, chars = self._do_index(product)
                return success, chars, False
            except Exception as exc:
                last_exc = exc
                if attempt < _MAX_RETRIES:
                    wait = _BACKOFF_BASE ** attempt
                    logger.warning(
                        "Attempt %d/%d failed for '%s': %s — retrying in %.0fs",
                        attempt, _MAX_RETRIES, product_id, exc, wait,
                    )
                    time.sleep(wait)

        logger.error(
            "All %d attempts failed for '%s': %s",
            _MAX_RETRIES, product_id, last_exc,
        )
        return False, 0, False

    def _do_index(self, product: dict) -> tuple[bool, int]:
        """
        Core indexing logic for a single product.

        1. Download image (optional; silent failure → text-only fallback).
        2. Generate multimodal or text-only embedding.
        3. Upsert into Qdrant.

        Returns (True, chars_used).
        """
        product_id = product["id"]
        name = product["name"]
        description = product["description"]
        image_url = product.get("image_url", "")

        # Step 1: download image (silent failure → text-only fallback)
        image_bytes: bytes | None = None
        if image_url:
            image_bytes = self._download_image(image_url)
            if image_bytes is None:
                logger.info(
                    "Product '%s': image unavailable, falling back to text-only.",
                    product_id,
                )

        # Step 2: generate embedding
        embedding = self.embedder.embed_product(
            name=name,
            description=description,
            image_bytes=image_bytes,
        )

        # Step 3: upsert into Qdrant
        payload = {
            "name": name,
            "description": description,
            "category": product.get("category", ""),
            "price": product.get("price", 0.0),
            "image_url": image_url,
        }
        self.store.upsert_product(
            product_id=product_id,
            embedding=embedding,
            payload=payload,
        )

        chars = len(name) + len(description)
        mode = "multimodal" if image_bytes else "text-only"
        logger.info("Indexed '%s' (%s, %d chars).", product_id, mode, chars)

        return True, chars
