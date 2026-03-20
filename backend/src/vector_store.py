import logging
import uuid

from qdrant_client import QdrantClient, models
from qdrant_client.models import (
    Distance,
    FieldCondition,
    Filter,
    MatchValue,
    PointStruct,
    Range,
    VectorParams,
)

logger = logging.getLogger(__name__)

COLLECTION_NAME = "products"
VECTOR_SIZE = 3072
DISTANCE = Distance.COSINE


class ProductVectorStore:
    def __init__(self, host: str = "localhost", port: int = 6333):
        self.client = QdrantClient(host=host, port=port)
        self._ensure_collection()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _ensure_collection(self) -> None:
        """Creates the collection if it does not exist (idempotent)."""
        existing = {c.name for c in self.client.get_collections().collections}
        if COLLECTION_NAME in existing:
            logger.debug("Collection '%s' already exists — skipping creation.", COLLECTION_NAME)
            return

        self.client.create_collection(
            collection_name=COLLECTION_NAME,
            vectors_config=VectorParams(size=VECTOR_SIZE, distance=DISTANCE),
        )
        logger.info("Collection '%s' created (%d dims, %s).", COLLECTION_NAME, VECTOR_SIZE, DISTANCE)

    # ------------------------------------------------------------------
    # Write
    # ------------------------------------------------------------------

    def upsert_product(
        self,
        product_id: str,
        embedding: list[float],
        payload: dict,
    ) -> None:
        """
        Insert or update a product.

        The payload must include: name, description, category, price, image_url.
        product_id (string) is converted to UUID v5 to satisfy Qdrant's point ID
        format; the original string ID is stored in the payload.
        """
        required = {"name", "description", "category", "price", "image_url"}
        missing = required - payload.keys()
        if missing:
            raise ValueError(f"Payload missing required fields: {missing}")

        # Qdrant accepts integers or UUIDs as point IDs.
        # We convert the string to a deterministic UUID v5 so that upserts
        # with the same product_id always target the same point.
        point_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, product_id))

        self.client.upsert(
            collection_name=COLLECTION_NAME,
            points=[
                PointStruct(
                    id=point_id,
                    vector=embedding,
                    payload={**payload, "product_id": product_id},
                )
            ],
        )
        logger.debug("Upserted product '%s' as point %s.", product_id, point_id)

    # ------------------------------------------------------------------
    # Read
    # ------------------------------------------------------------------

    def search(
        self,
        query_vector: list[float],
        k: int = 10,
        category: str | None = None,
        max_price: float | None = None,
    ) -> list[dict]:
        """
        Returns the k products nearest to query_vector.

        Optional filters:
        - category: exact match on the 'category' field.
        - max_price: numeric range on the 'price' field (≤ max_price).
        """
        must_conditions: list[FieldCondition] = []

        if category is not None:
            must_conditions.append(
                FieldCondition(key="category", match=MatchValue(value=category))
            )

        if max_price is not None:
            must_conditions.append(
                FieldCondition(key="price", range=Range(lte=max_price))
            )

        query_filter = Filter(must=must_conditions) if must_conditions else None

        results = self.client.query_points(
            collection_name=COLLECTION_NAME,
            query=query_vector,
            query_filter=query_filter,
            limit=k,
            with_payload=True,
        )

        return [
            {
                "id": point.payload.get("product_id", str(point.id)),
                "score": point.score,
                "name": point.payload.get("name"),
                "description": point.payload.get("description"),
                "category": point.payload.get("category"),
                "price": point.payload.get("price"),
                "image_url": point.payload.get("image_url"),
            }
            for point in results.points
        ]

    def get_collection_info(self) -> dict:
        """Returns vectors_count and status for the collection."""
        info = self.client.get_collection(COLLECTION_NAME)
        return {
            "vectors_count": info.points_count,
            "status": info.status.value,
        }


if __name__ == "__main__":
    import random

    logging.basicConfig(level=logging.DEBUG)

    store = ProductVectorStore()

    # --- upsert dummy products ---
    dummy_products = [
        {
            "id": "prod_test_001",
            "payload": {
                "name": "Blue Denim Jacket",
                "description": "Classic washed denim jacket with button front.",
                "category": "outerwear",
                "price": 129.99,
                "image_url": "https://picsum.photos/seed/denim/400/400",
            },
        },
        {
            "id": "prod_test_002",
            "payload": {
                "name": "White Canvas Sneakers",
                "description": "Minimalist leather sneakers for everyday use.",
                "category": "footwear",
                "price": 89.99,
                "image_url": "https://picsum.photos/seed/sneakers/400/400",
            },
        },
        {
            "id": "prod_test_003",
            "payload": {
                "name": "Leather Crossbody Bag",
                "description": "Compact genuine leather bag with gold hardware.",
                "category": "bags",
                "price": 175.00,
                "image_url": "https://picsum.photos/seed/leatherbag/400/400",
            },
        },
    ]

    rng = random.Random(42)
    dummy_vector = [rng.uniform(-1, 1) for _ in range(VECTOR_SIZE)]

    for product in dummy_products:
        store.upsert_product(
            product_id=product["id"],
            embedding=dummy_vector,
            payload=product["payload"],
        )
    print(f"Upserted {len(dummy_products)} products.")

    # --- search without filters ---
    results = store.search(query_vector=dummy_vector, k=3)
    assert len(results) == 3
    print(f"\nSearch (no filter) → {len(results)} results:")
    for r in results:
        print(f"  [{r['score']:.4f}] {r['id']} — {r['name']} (${r['price']})")

    # --- search with category filter ---
    results = store.search(query_vector=dummy_vector, k=10, category="footwear")
    assert all(r["category"] == "footwear" for r in results)
    print(f"\nSearch (category=footwear) → {len(results)} results:")
    for r in results:
        print(f"  [{r['score']:.4f}] {r['name']}")

    # --- search with price filter ---
    results = store.search(query_vector=dummy_vector, k=10, max_price=130.00)
    assert all(r["price"] <= 130.00 for r in results)
    print(f"\nSearch (max_price=130) → {len(results)} results:")
    for r in results:
        print(f"  [{r['score']:.4f}] {r['name']} (${r['price']})")

    # --- collection info ---
    info = store.get_collection_info()
    print(f"\nCollection info: {info}")

    print("\n✅ VectorStore OK")
