"""
Fast multimodal batch indexer.

Speeds up indexing by:
  1. Downloading images concurrently (ThreadPoolExecutor) with local cache.
  2. Sending products to Gemini in multimodal batches (N per API call).

Usage:
    python scripts/index_fast.py [--force] [--workers 8] [--batch-size 5]
"""

import json
import logging
import os
import sys
import time
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import httpx
from dotenv import load_dotenv
from google.genai import types
from tqdm import tqdm

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from embeddings import EMBEDDING_DIMS, EMBEDDING_MODEL, GeminiEmbedder
from vector_store import COLLECTION_NAME, ProductVectorStore

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

IMAGE_CACHE_DIR = Path(__file__).parent.parent / "data" / "image_cache"
IMAGE_CACHE_DIR.mkdir(exist_ok=True)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    )
}

# ---------------------------------------------------------------------------
# Image downloader (with local cache)
# ---------------------------------------------------------------------------

def download_image(product_id: str, url: str) -> bytes | None:
    """Download image with local cache. Returns None on failure."""
    if not url:
        return None

    cache_path = IMAGE_CACHE_DIR / f"{product_id}.jpg"
    if cache_path.exists():
        return cache_path.read_bytes()

    for attempt in range(3):
        try:
            r = httpx.get(url, headers=HEADERS, timeout=10, follow_redirects=True)
            if r.status_code == 429:
                wait = 2 ** attempt
                time.sleep(wait)
                continue
            r.raise_for_status()
            cache_path.write_bytes(r.content)
            return r.content
        except Exception as exc:
            if attempt == 2:
                logger.debug("Image failed for %s: %s", product_id, exc)
    return None


def prefetch_images(products: list[dict], max_workers: int) -> dict[str, bytes | None]:
    """Download all images concurrently. Returns {product_id: bytes|None}."""
    results: dict[str, bytes | None] = {}

    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        futures = {
            pool.submit(download_image, p["id"], p.get("image_url", "")): p["id"]
            for p in products
        }
        with tqdm(total=len(futures), desc="Downloading images", unit="img") as bar:
            for future in as_completed(futures):
                pid = futures[future]
                results[pid] = future.result()
                bar.update(1)

    ok = sum(1 for v in results.values() if v)
    logger.info("Images: %d downloaded, %d failed/missing.", ok, len(results) - ok)
    return results


# ---------------------------------------------------------------------------
# Batch multimodal embedding
# ---------------------------------------------------------------------------

def build_content(product: dict, image_bytes: bytes | None):
    """Build a Gemini Content object for one product."""
    text = f"{product['name']}: {product['description']}"
    if image_bytes:
        return types.Content(
            parts=[
                types.Part(text=text),
                types.Part.from_bytes(data=image_bytes, mime_type="image/jpeg"),
            ]
        )
    return text


def embed_batch_multimodal(embedder: GeminiEmbedder, contents: list) -> list[list[float]]:
    """Embed a batch of Content objects or strings in one API call."""
    from google.genai import types as gtypes
    response = embedder.client.models.embed_content(
        model=EMBEDDING_MODEL,
        contents=contents,
        config=gtypes.EmbedContentConfig(
            task_type="RETRIEVAL_DOCUMENT",
            output_dimensionality=EMBEDDING_DIMS,
        ),
    )
    time.sleep(0.1)
    return [e.values for e in response.embeddings]


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    load_dotenv()

    force = "--force" in sys.argv
    max_workers = 8
    batch_size = 5

    for arg in sys.argv[1:]:
        if arg.startswith("--workers="):
            max_workers = int(arg.split("=")[1])
        if arg.startswith("--batch-size="):
            batch_size = int(arg.split("=")[1])

    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        logger.error("GEMINI_API_KEY not set.")
        sys.exit(1)

    json_path = Path(__file__).parent.parent / "data" / "sample_products.json"
    all_products: list[dict] = json.loads(json_path.read_text())

    embedder = GeminiEmbedder(api_key=api_key)
    store = ProductVectorStore()

    # Filter out already-indexed products unless --force
    if not force:
        to_index = []
        for p in all_products:
            point_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, p["id"]))
            existing = store.client.retrieve(
                collection_name=COLLECTION_NAME,
                ids=[point_id],
                with_payload=False,
                with_vectors=False,
            )
            if not existing:
                to_index.append(p)
        skipped = len(all_products) - len(to_index)
        if skipped:
            logger.info("Skipping %d already-indexed products.", skipped)
    else:
        to_index = all_products
        skipped = 0

    if not to_index:
        print("All products already indexed. Use --force to re-index.")
        return

    logger.info(
        "Indexing %d products | %d image-download workers | batch size %d",
        len(to_index), max_workers, batch_size,
    )

    # Step 1: download all images concurrently
    image_map = prefetch_images(to_index, max_workers=max_workers)

    # Step 2: batch multimodal embedding + upsert
    indexed = failed = 0

    with tqdm(total=len(to_index), desc="Embedding & indexing", unit="product") as bar:
        for i in range(0, len(to_index), batch_size):
            batch = to_index[i : i + batch_size]
            contents = [
                build_content(p, image_map.get(p["id"])) for p in batch
            ]

            try:
                embeddings = embed_batch_multimodal(embedder, contents)
            except Exception as exc:
                logger.warning("Embedding batch %d failed: %s", i // batch_size, exc)
                failed += len(batch)
                bar.update(len(batch))
                continue

            for product, embedding in zip(batch, embeddings):
                try:
                    store.upsert_product(
                        product_id=product["id"],
                        embedding=embedding,
                        payload={k: v for k, v in product.items() if k != "id"},
                    )
                    indexed += 1
                except Exception as exc:
                    logger.warning("Upsert failed for '%s': %s", product["id"], exc)
                    failed += 1

            bar.update(len(batch))
            bar.set_postfix(ok=indexed, fail=failed)

    print()
    print("=" * 40)
    print("  Indexing summary")
    print("=" * 40)
    print(f"  Indexed  : {indexed}")
    print(f"  Skipped  : {skipped}  (already in Qdrant)")
    print(f"  Failed   : {failed}")
    print("=" * 40)
    info = store.get_collection_info()
    print(f"  Vectors  : {info['vectors_count']}")
    print(f"  Status   : {info['status']}")
    print("=" * 40)
    print(f"\n  Image cache: {IMAGE_CACHE_DIR}")
    print("\n✅ Done")


if __name__ == "__main__":
    main()
