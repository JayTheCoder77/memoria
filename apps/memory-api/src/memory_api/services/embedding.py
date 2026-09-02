from __future__ import annotations

import hashlib
import math
from typing import Protocol

EMBEDDING_DIM = 384


class Embedder(Protocol):
    def embed(self, text: str) -> list[float]: ...


class HashEmbedder:
    """Deterministic 384-d embedder used in tests and as the default local fallback."""

    def embed(self, text: str) -> list[float]:
        seed = text.encode("utf-8")
        values: list[float] = []
        while len(values) < EMBEDDING_DIM:
            seed = hashlib.sha256(seed).digest()
            for offset in range(0, len(seed), 4):
                raw = int.from_bytes(seed[offset : offset + 4], "big")
                values.append((raw / 2**32) * 2 - 1)
                if len(values) == EMBEDDING_DIM:
                    break
        norm = math.sqrt(sum(value * value for value in values)) or 1.0
        return [value / norm for value in values]


class MiniLMEmbedder:
    """In-process all-MiniLM-L6-v2 embedder. Enable with MEMORIA_EMBEDDER=minilm."""

    _model = None

    def embed(self, text: str) -> list[float]:
        from sentence_transformers import SentenceTransformer

        if MiniLMEmbedder._model is None:
            MiniLMEmbedder._model = SentenceTransformer(
                "sentence-transformers/all-MiniLM-L6-v2"
            )
        vector = MiniLMEmbedder._model.encode(text, normalize_embeddings=True)
        return vector.tolist()


def get_embedder() -> Embedder:
    from memory_api.config import settings

    if settings.embedder == "minilm":
        return MiniLMEmbedder()
    return HashEmbedder()


def embed_text(text: str, embedder: Embedder | None = None) -> list[float]:
    if embedder is None:
        embedder = get_embedder()
    return embedder.embed(text)
