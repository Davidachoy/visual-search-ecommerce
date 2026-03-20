import logging
import time
from io import BytesIO

from google import genai
from google.genai import types
from PIL import Image

logger = logging.getLogger(__name__)

# gemini-embedding-2-preview: Google's first natively multimodal embedding model.
# Supports text, image, video, audio, and PDF in a single unified vector space.
# Reference: https://qdrant.tech/documentation/embeddings/gemini/
EMBEDDING_MODEL = "gemini-embedding-2-preview"
EMBEDDING_DIMS = 3072
_RATE_LIMIT_SLEEP = 0.1


class GeminiEmbedder:
    def __init__(self, api_key: str):
        self.client = genai.Client(api_key=api_key)

    def _embed(self, contents, task_type: str) -> list[float]:
        response = self.client.models.embed_content(
            model=EMBEDDING_MODEL,
            contents=contents,
            config=types.EmbedContentConfig(
                task_type=task_type,
                output_dimensionality=EMBEDDING_DIMS,
            ),
        )
        time.sleep(_RATE_LIMIT_SLEEP)

        # Log token usage if available (Vertex AI only; no-op on Gemini API)
        if response.metadata and hasattr(response.metadata, "usage"):
            logger.debug("Tokens used: %s", response.metadata.usage)

        return response.embeddings[0].values

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """
        Embed multiple texts in a single API call (RETRIEVAL_DOCUMENT).
        Up to ~100 texts per call. Much faster than calling embed_text() in a loop.
        """
        response = self.client.models.embed_content(
            model=EMBEDDING_MODEL,
            contents=texts,
            config=types.EmbedContentConfig(
                task_type="RETRIEVAL_DOCUMENT",
                output_dimensionality=EMBEDDING_DIMS,
            ),
        )
        time.sleep(_RATE_LIMIT_SLEEP)
        return [e.values for e in response.embeddings]

    def embed_text(self, text: str) -> list[float]:
        """Embed a text string for document indexing."""
        return self._embed(text, task_type="RETRIEVAL_DOCUMENT")

    def embed_image(self, image_bytes: bytes, mime_type: str = "image/jpeg") -> list[float]:
        """Embed raw image bytes (JPEG/PNG)."""
        part = types.Part.from_bytes(data=image_bytes, mime_type=mime_type)
        return self._embed([part], task_type="RETRIEVAL_DOCUMENT")

    def embed_product(
        self, name: str, description: str, image_bytes: bytes | None, mime_type: str = "image/jpeg"
    ) -> list[float]:
        """
        Embed a product for indexing.
        - With image: single multimodal call (text + image → 1 vector).
        - Without image: text-only call.
        """
        text = f"{name}: {description}"

        if image_bytes is None:
            return self._embed(text, task_type="RETRIEVAL_DOCUMENT")

        # A single types.Content with multiple Parts → one aggregated embedding
        contents = types.Content(
            parts=[
                types.Part(text=text),
                types.Part.from_bytes(data=image_bytes, mime_type=mime_type),
            ]
        )
        return self._embed([contents], task_type="RETRIEVAL_DOCUMENT")

    def embed_query(self, text: str) -> list[float]:
        """Embed a search query (different task_type from document indexing)."""
        return self._embed(text, task_type="RETRIEVAL_QUERY")


if __name__ == "__main__":
    import os
    from dotenv import load_dotenv

    logging.basicConfig(level=logging.DEBUG)
    load_dotenv()

    api_key = os.environ["GEMINI_API_KEY"]
    embedder = GeminiEmbedder(api_key=api_key)

    # 1. embed_text
    vec = embedder.embed_text("A red leather wallet")
    assert len(vec) == EMBEDDING_DIMS, f"Expected {EMBEDDING_DIMS} dims, got {len(vec)}"
    print(f"embed_text      → {len(vec)} dims  first value: {vec[0]:.6f}")

    # 2. embed_image — solid-color JPEG generated in memory
    buf = BytesIO()
    Image.new("RGB", (64, 64), color=(120, 80, 200)).save(buf, format="JPEG")
    dummy_image_bytes = buf.getvalue()

    vec = embedder.embed_image(dummy_image_bytes)
    assert len(vec) == EMBEDDING_DIMS
    print(f"embed_image     → {len(vec)} dims  first value: {vec[0]:.6f}")

    # 3. embed_product with image (multimodal)
    vec = embedder.embed_product(
        name="Purple Tote Bag",
        description="A spacious canvas tote in violet.",
        image_bytes=dummy_image_bytes,
    )
    assert len(vec) == EMBEDDING_DIMS
    print(f"embed_product   → {len(vec)} dims (multimodal)  first value: {vec[0]:.6f}")

    # 4. embed_product without image (text-only)
    vec = embedder.embed_product(
        name="Purple Tote Bag",
        description="A spacious canvas tote in violet.",
        image_bytes=None,
    )
    assert len(vec) == EMBEDDING_DIMS
    print(f"embed_product   → {len(vec)} dims (text-only)   first value: {vec[0]:.6f}")

    # 5. embed_query
    vec = embedder.embed_query("purple bag for shopping")
    assert len(vec) == EMBEDDING_DIMS
    print(f"embed_query     → {len(vec)} dims  first value: {vec[0]:.6f}")

    print("\n✅ Embeddings OK")
