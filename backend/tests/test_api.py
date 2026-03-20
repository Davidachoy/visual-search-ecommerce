"""
Integration tests for the visual search API.

Uses TestClient with a mocked embedder and real Qdrant (collection 'products_test').
The 10 test products are indexed once per session in conftest.py.
"""

from pathlib import Path

import pytest

# Required fields in every search result
REQUIRED_RESULT_FIELDS = {
    "id",
    "name",
    "description",
    "category",
    "price",
    "image_url",
    "similarity_score",
}


# ---------------------------------------------------------------------------
# /health
# ---------------------------------------------------------------------------

class TestHealth:
    def test_returns_200(self, client):
        response = client.get("/health")
        assert response.status_code == 200

    def test_status_is_ok(self, client):
        data = client.get("/health").json()
        assert data["status"] == "ok"

    def test_qdrant_is_connected(self, client):
        data = client.get("/health").json()
        assert data["qdrant"] is True

    def test_vectors_count_is_positive(self, client):
        data = client.get("/health").json()
        assert data["vectors_count"] >= 10


# ---------------------------------------------------------------------------
# /search/text
# ---------------------------------------------------------------------------

class TestTextSearch:
    def test_basic_search_returns_200(self, client):
        response = client.post("/search/text", json={"query": "white sneakers"})
        assert response.status_code == 200

    def test_basic_search_has_results(self, client):
        data = client.post("/search/text", json={"query": "white sneakers"}).json()
        assert len(data["results"]) > 0

    def test_basic_search_response_shape(self, client):
        data = client.post("/search/text", json={"query": "white sneakers"}).json()
        assert "results" in data
        assert "query_time_ms" in data
        assert "total_found" in data
        assert isinstance(data["query_time_ms"], float)
        assert data["total_found"] == len(data["results"])

    def test_each_result_has_required_fields(self, client):
        data = client.post("/search/text", json={"query": "white sneakers"}).json()
        for result in data["results"]:
            assert REQUIRED_RESULT_FIELDS <= result.keys(), (
                f"Missing fields: {REQUIRED_RESULT_FIELDS - result.keys()}"
            )

    def test_similarity_score_is_between_minus1_and_1(self, client):
        data = client.post("/search/text", json={"query": "leather bag"}).json()
        for result in data["results"]:
            assert -1.0 <= result["similarity_score"] <= 1.0

    def test_limit_is_respected(self, client):
        data = client.post(
            "/search/text", json={"query": "clothing", "limit": 3}
        ).json()
        assert len(data["results"]) <= 3

    def test_empty_query_returns_422(self, client):
        response = client.post("/search/text", json={"query": ""})
        assert response.status_code == 422

    def test_missing_query_returns_422(self, client):
        response = client.post("/search/text", json={})
        assert response.status_code == 422


# ---------------------------------------------------------------------------
# /search/text — category filter
# ---------------------------------------------------------------------------

class TestTextSearchCategoryFilter:
    def test_category_filter_returns_200(self, client):
        response = client.post(
            "/search/text", json={"query": "bag", "category": "bags"}
        )
        assert response.status_code == 200

    def test_all_results_match_category(self, client):
        data = client.post(
            "/search/text",
            json={"query": "nice bag", "category": "bags", "limit": 10},
        ).json()
        assert len(data["results"]) > 0, "Expected results for category=bags"
        for result in data["results"]:
            assert result["category"] == "bags", (
                f"Expected category 'bags', got '{result['category']}'"
            )

    def test_category_filter_reduces_results(self, client):
        all_results = client.post(
            "/search/text", json={"query": "item", "limit": 10}
        ).json()
        filtered = client.post(
            "/search/text",
            json={"query": "item", "category": "footwear", "limit": 10},
        ).json()
        assert filtered["total_found"] < all_results["total_found"]

    def test_nonexistent_category_returns_empty(self, client):
        data = client.post(
            "/search/text",
            json={"query": "item", "category": "nonexistent_xyz"},
        ).json()
        assert data["results"] == []


# ---------------------------------------------------------------------------
# /search/text — price filter
# ---------------------------------------------------------------------------

class TestTextSearchPriceFilter:
    # max_price=100 includes: prod_t001(89.99), prod_t004(64.99), prod_t006(59.99),
    #                          prod_t007(49.99), prod_t008(79.99), prod_t009(34.99)
    # Excludes: prod_t002(129.99), prod_t003(175), prod_t005(299), prod_t010(199.99)

    def test_price_filter_returns_200(self, client):
        response = client.post(
            "/search/text", json={"query": "clothing", "max_price": 100.0}
        )
        assert response.status_code == 200

    def test_all_results_within_price(self, client):
        data = client.post(
            "/search/text",
            json={"query": "fashion", "max_price": 100.0, "limit": 10},
        ).json()
        assert len(data["results"]) > 0, "Expected results for max_price=100"
        for result in data["results"]:
            assert result["price"] <= 100.0, (
                f"Price {result['price']} exceeds max_price=100"
            )

    def test_strict_price_filter(self, client):
        # max_price=50: only prod_t007(49.99) and prod_t009(34.99)
        data = client.post(
            "/search/text",
            json={"query": "cheap accessory", "max_price": 50.0, "limit": 10},
        ).json()
        for result in data["results"]:
            assert result["price"] <= 50.0

    def test_price_filter_reduces_results(self, client):
        all_data = client.post(
            "/search/text", json={"query": "product", "limit": 10}
        ).json()
        cheap_data = client.post(
            "/search/text",
            json={"query": "product", "max_price": 100.0, "limit": 10},
        ).json()
        assert cheap_data["total_found"] < all_data["total_found"]

    def test_combined_category_and_price_filter(self, client):
        # bags with max_price=50: only prod_t009(34.99)
        data = client.post(
            "/search/text",
            json={
                "query": "bag",
                "category": "bags",
                "max_price": 50.0,
                "limit": 10,
            },
        ).json()
        for result in data["results"]:
            assert result["category"] == "bags"
            assert result["price"] <= 50.0


# ---------------------------------------------------------------------------
# /search/image
# ---------------------------------------------------------------------------

class TestImageSearch:
    def test_image_search_returns_200(self, client, test_image_bytes):
        response = client.post(
            "/search/image",
            files={"file": ("test.jpg", test_image_bytes, "image/jpeg")},
        )
        assert response.status_code == 200

    def test_image_search_has_results(self, client, test_image_bytes):
        data = client.post(
            "/search/image",
            files={"file": ("test.jpg", test_image_bytes, "image/jpeg")},
        ).json()
        assert len(data["results"]) > 0

    def test_image_search_response_fields(self, client, test_image_bytes):
        data = client.post(
            "/search/image",
            files={"file": ("test.jpg", test_image_bytes, "image/jpeg")},
        ).json()
        assert "results" in data
        assert "query_time_ms" in data
        assert "total_found" in data
        for result in data["results"]:
            assert REQUIRED_RESULT_FIELDS <= result.keys()

    def test_image_from_file(self, client, test_image_file):
        with open(test_image_file, "rb") as f:
            response = client.post(
                "/search/image",
                files={"file": ("test_image.jpg", f, "image/jpeg")},
            )
        assert response.status_code == 200

    def test_non_image_file_returns_422(self, client):
        response = client.post(
            "/search/image",
            files={"file": ("document.txt", b"not an image", "text/plain")},
        )
        assert response.status_code == 422

    def test_empty_file_returns_422(self, client):
        response = client.post(
            "/search/image",
            files={"file": ("empty.jpg", b"", "image/jpeg")},
        )
        assert response.status_code == 422


# ---------------------------------------------------------------------------
# /search/multimodal
# ---------------------------------------------------------------------------

class TestMultimodalSearch:
    def test_text_only_returns_200(self, client):
        response = client.post(
            "/search/multimodal",
            data={"query": "running shoes"},
        )
        assert response.status_code == 200

    def test_image_only_returns_200(self, client, test_image_bytes):
        response = client.post(
            "/search/multimodal",
            files={"file": ("img.jpg", test_image_bytes, "image/jpeg")},
        )
        assert response.status_code == 200

    def test_text_and_image_returns_200(self, client, test_image_bytes):
        response = client.post(
            "/search/multimodal",
            data={"query": "brown leather bag"},
            files={"file": ("img.jpg", test_image_bytes, "image/jpeg")},
        )
        assert response.status_code == 200

    def test_text_and_image_calls_embed_product(self, client, mock_embedder, test_image_bytes):
        mock_embedder.reset_mock()
        client.post(
            "/search/multimodal",
            data={"query": "bag"},
            files={"file": ("img.jpg", test_image_bytes, "image/jpeg")},
        )
        mock_embedder.embed_product.assert_called_once()

    def test_text_only_calls_embed_query(self, client, mock_embedder):
        mock_embedder.reset_mock()
        client.post("/search/multimodal", data={"query": "blue t-shirt"})
        mock_embedder.embed_query.assert_called_once_with("blue t-shirt")

    def test_image_only_calls_embed_image(self, client, mock_embedder, test_image_bytes):
        mock_embedder.reset_mock()
        client.post(
            "/search/multimodal",
            files={"file": ("img.jpg", test_image_bytes, "image/jpeg")},
        )
        mock_embedder.embed_image.assert_called_once()

    def test_no_input_returns_422(self, client):
        response = client.post("/search/multimodal", data={})
        assert response.status_code == 422


# ---------------------------------------------------------------------------
# /categories
# ---------------------------------------------------------------------------

class TestCategories:
    def test_returns_200(self, client):
        assert client.get("/categories").status_code == 200

    def test_returns_list(self, client):
        data = client.get("/categories").json()
        assert "categories" in data
        assert isinstance(data["categories"], list)

    def test_contains_expected_categories(self, client):
        categories = set(client.get("/categories").json()["categories"])
        expected = {"footwear", "bags", "outerwear", "accessories"}
        assert expected <= categories

    def test_categories_are_sorted(self, client):
        categories = client.get("/categories").json()["categories"]
        assert categories == sorted(categories)

    def test_no_duplicates(self, client):
        categories = client.get("/categories").json()["categories"]
        assert len(categories) == len(set(categories))
