"""
Delete and recreate the Qdrant 'products' collection.
Run this before re-indexing with a new dataset.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams
from vector_store import COLLECTION_NAME, VECTOR_SIZE

HOST = "localhost"
PORT = 6333

client = QdrantClient(host=HOST, port=PORT)

existing = {c.name for c in client.get_collections().collections}

if COLLECTION_NAME in existing:
    client.delete_collection(COLLECTION_NAME)
    print(f"Deleted collection '{COLLECTION_NAME}'")
else:
    print(f"Collection '{COLLECTION_NAME}' did not exist")

client.create_collection(
    collection_name=COLLECTION_NAME,
    vectors_config=VectorParams(size=VECTOR_SIZE, distance=Distance.COSINE),
)
print(f"Created collection '{COLLECTION_NAME}' ({VECTOR_SIZE} dims, Cosine)")
print("\n✅ Ready to index")
