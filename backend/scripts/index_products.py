"""
Index products from data/sample_products.json into Qdrant.

Usage:
    python scripts/index_products.py [--force]

Flags:
    --force   Re-embed and overwrite products that already exist in Qdrant.
              Without this flag, already-indexed products are skipped.
"""

import logging
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

# Allow imports from src/ without installing the package
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from embeddings import GeminiEmbedder
from indexer import ProductIndexer
from vector_store import ProductVectorStore

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


def main() -> None:
    load_dotenv()

    force = "--force" in sys.argv

    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        logger.error("GEMINI_API_KEY not set. Add it to backend/.env")
        sys.exit(1)

    qdrant_host = os.environ.get("QDRANT_HOST", "localhost")
    qdrant_port = int(os.environ.get("QDRANT_PORT", 6333))

    json_path = Path(__file__).parent.parent / "data" / "sample_products.json"

    logger.info("Connecting to Qdrant at %s:%d", qdrant_host, qdrant_port)
    logger.info("Product file: %s", json_path)
    logger.info("Force re-index: %s", force)

    embedder = GeminiEmbedder(api_key=api_key)
    store = ProductVectorStore(host=qdrant_host, port=qdrant_port)
    indexer = ProductIndexer(embedder=embedder, store=store, force=force)

    result = indexer.index_from_json(str(json_path))

    print()
    print("=" * 40)
    print("  Indexing summary")
    print("=" * 40)
    print(f"  Total products : {result.total}")
    print(f"  Indexed        : {result.indexed}")
    print(f"  Skipped        : {result.skipped}  (already in Qdrant)")
    print(f"  Failed         : {result.failed}")
    print(f"  Chars processed: {result.total_chars:,}")
    print(f"  Estimated cost : ${result.estimated_cost_usd:.6f}")
    print("=" * 40)

    info = store.get_collection_info()
    print(f"  Collection status : {info['status']}")
    print(f"  Vectors in store  : {info['vectors_count']}")
    print("=" * 40)

    if result.failed > 0:
        logger.warning("%d product(s) failed to index.", result.failed)
        sys.exit(1)

    print("\n✅ Indexing complete")


if __name__ == "__main__":
    main()
