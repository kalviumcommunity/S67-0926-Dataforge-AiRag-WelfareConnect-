"""
Embedding Service.
Generates text embeddings using OpenAI API with fallback deterministic vectors for testing and local development.
Enforces the configured embedding model and dimension.
"""

import hashlib
import logging
import math
from typing import List
from backend.app.config import settings

logger = logging.getLogger(__name__)


class EmbeddingService:
    @classmethod
    def _generate_fallback_vector(cls, text: str, dimension: int) -> List[float]:
        """
        Generate a deterministic, unit-normalized float vector of length `dimension`
        based on token hashes from the input text.
        Ensures consistent cosine similarity behavior during local testing without API keys.
        """
        if not text:
            return [0.0] * dimension

        # Tokenize and hash
        tokens = text.lower().split()
        vector = [0.0] * dimension

        for t_idx, token in enumerate(tokens):
            h = hashlib.sha256(token.encode("utf-8")).hexdigest()
            # Distribute hash entropy across vector dimensions
            for i in range(0, min(len(h), 16), 2):
                pos = (int(h[i : i + 2], 16) * 31 + t_idx * 7) % dimension
                weight = (int(h[i], 16) - 7.5) / 10.0
                vector[pos] += weight

        # Normalize to unit length (L2 norm)
        norm = math.sqrt(sum(v * v for v in vector))
        if norm > 0.0:
            vector = [round(v / norm, 6) for v in vector]
        else:
            vector[0] = 1.0

        return vector

    @classmethod
    def create_embedding(cls, text: str) -> List[float]:
        """
        Generate embedding vector for text using the configured model.
        Returns a float list matching settings.EMBEDDING_DIMENSION.
        """
        clean_text = text.strip() if text else ""
        dimension = settings.EMBEDDING_DIMENSION

        # Attempt OpenAI API if real key is configured
        if settings.OPENAI_API_KEY and "placeholder" not in settings.OPENAI_API_KEY:
            try:
                from openai import OpenAI
                client = OpenAI(api_key=settings.OPENAI_API_KEY)
                response = client.embeddings.create(
                    input=clean_text,
                    model=settings.EMBEDDING_MODEL,
                )
                vec = response.data[0].embedding
                if len(vec) == dimension:
                    return vec
                logger.warning(
                    f"OpenAI embedding returned dimension {len(vec)}, expected {dimension}. Falling back."
                )
            except Exception as e:
                logger.warning(f"OpenAI embedding API call skipped/failed: {e}. Using deterministic fallback.")

        # Deterministic fallback vector
        return cls._generate_fallback_vector(clean_text, dimension)

    @staticmethod
    def cosine_similarity(v1: List[float], v2: List[float]) -> float:
        """Calculate cosine similarity between two float vectors."""
        if not v1 or not v2 or len(v1) != len(v2):
            return 0.0
        dot = sum(a * b for a, b in zip(v1, v2))
        norm1 = math.sqrt(sum(a * a for a in v1))
        norm2 = math.sqrt(sum(b * b for b in v2))
        if norm1 <= 0.0 or norm2 <= 0.0:
            return 0.0
        return max(0.0, min(1.0, dot / (norm1 * norm2)))


embedding_service = EmbeddingService()
