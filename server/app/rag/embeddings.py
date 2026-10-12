import hashlib
import logging
from typing import Any

import httpx

from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


class EmbeddingService:
    def __init__(self) -> None:
        self.openai_api_key = settings.OPENAI_API_KEY
        self.openai_model = settings.OPENAI_EMBEDDING_MODEL
        self.api_key = settings.GEMINI_API_KEY
        self.model_name = settings.EMBEDDING_MODEL
        self.dimension = settings.EMBEDDING_DIMENSION

    async def get_embedding(self, text: str) -> list[float]:
        """Generate dense vector embedding for clinical text (OpenAI primary, Gemini fallback)."""
        clean_text = text.strip()
        if not clean_text:
            return [0.0] * self.dimension

        # 1. Primary: OpenAI text-embedding-3-small
        if self.openai_api_key:
            try:
                async with httpx.AsyncClient(timeout=30.0) as client:
                    resp = await client.post(
                        "https://api.openai.com/v1/embeddings",
                        headers={
                            "Authorization": f"Bearer {self.openai_api_key}",
                            "Content-Type": "application/json",
                        },
                        json={
                            "model": self.openai_model,
                            "input": clean_text,
                            "dimensions": self.dimension,
                        },
                    )
                    if resp.status_code == 200:
                        data = resp.json().get("data", [])
                        if data and "embedding" in data[0]:
                            values = data[0]["embedding"]
                            if len(values) == self.dimension:
                                return list(values)
                    logger.warning(
                        "OpenAI embedding API returned status %s: %s",
                        resp.status_code,
                        resp.text[:200],
                    )
            except Exception as exc:
                logger.warning("OpenAI embedding generation failed, falling back: %s", exc)

        # 2. Fallback: Google Gemini embedding
        if self.api_key:
            try:
                from google import genai
                from google.genai import types

                client = genai.Client(api_key=self.api_key)
                response = await client.aio.models.embed_content(
                    model=self.model_name,
                    contents=clean_text,
                    config=types.EmbedContentConfig(output_dimensionality=self.dimension),
                )
                if response.embeddings:
                    values = response.embeddings[0].values
                    if values and len(values) == self.dimension:
                        return list(values)
                raise ValueError("Embedding response has an unexpected dimension or no values")
            except Exception as e:
                raise RuntimeError("Unable to generate semantic embeddings") from e

        if not self.openai_api_key and not self.api_key:
            raise RuntimeError("API key is required for semantic embeddings (OpenAI or Gemini)")
        raise RuntimeError("Unable to generate semantic embeddings from configured providers")

    async def get_embeddings_batch(self, texts: list[str]) -> list[list[float]]:
        """Batch embedding generation with native OpenAI API batching and fallback."""
        if not texts:
            return []

        cleaned_texts = [t.strip() if t.strip() else " " for t in texts]

        # 1. Primary: OpenAI batch embeddings (up to 64 per HTTP request)
        if self.openai_api_key:
            try:
                results: list[list[float]] = []
                async with httpx.AsyncClient(timeout=45.0) as client:
                    for i in range(0, len(cleaned_texts), 64):
                        batch = cleaned_texts[i : i + 64]
                        resp = await client.post(
                            "https://api.openai.com/v1/embeddings",
                            headers={
                                "Authorization": f"Bearer {self.openai_api_key}",
                                "Content-Type": "application/json",
                            },
                            json={
                                "model": self.openai_model,
                                "input": batch,
                                "dimensions": self.dimension,
                            },
                        )
                        if resp.status_code == 200:
                            data = resp.json().get("data", [])
                            data.sort(key=lambda x: x.get("index", 0))
                            for item in data:
                                results.append(item["embedding"])
                        else:
                            for t in batch:
                                results.append(await self.get_embedding(t))
                if len(results) == len(texts):
                    return results
            except Exception as e:
                logger.warning("OpenAI batch embedding failed, falling back: %s", e)

        import asyncio

        fallback_results: list[list[float]] = []
        for t in texts:
            await asyncio.sleep(0.15)
            fallback_results.append(await self.get_embedding(t))
        return fallback_results

    def compute_sparse_vector(self, text: str) -> dict[str, Any]:
        """Compute term frequency sparse representation for hybrid retrieval."""
        words = [w.lower() for w in text.split() if len(w) > 2]
        tf: dict[int, float] = {}
        for w in words:
            # Map word hash into integer index
            idx = int(hashlib.md5(w.encode("utf-8")).hexdigest()[:6], 16) % 100000
            tf[idx] = tf.get(idx, 0.0) + 1.0

        indices = list(tf.keys())
        values = list(tf.values())
        return {"indices": indices, "values": values}


embedding_service = EmbeddingService()
