import httpx
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams

HOST = "localhost"
PORT = 6333
TEST_COLLECTION = "health_check_test"

client = QdrantClient(host=HOST, port=PORT)

resp = httpx.get(f"http://{HOST}:{PORT}/")
version = resp.json().get("version", "unknown")
print(f"Qdrant version: {version}")

client.create_collection(
    collection_name=TEST_COLLECTION,
    vectors_config=VectorParams(size=4, distance=Distance.COSINE),
)
print(f"Collection '{TEST_COLLECTION}' created")

client.delete_collection(collection_name=TEST_COLLECTION)
print(f"Collection '{TEST_COLLECTION}' deleted")

print("✅ Qdrant OK")
