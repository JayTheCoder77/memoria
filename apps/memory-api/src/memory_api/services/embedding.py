from __future__ import annotations

import hashlib
import math
from typing import Protocol

EMBEDDING_DIM = 384


class Embedder(Protocol):
    def embed(self, text: str) -> list[float]: ...


class HashEmbedder:
    """Deterministic 384-d embedder used until the MiniLM model is wired in Phase 2."""

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


def get_embedder() -> Embedder:
    return HashEmbedder()


def embed_text(text: str, embedder: Embedder | None = None) -> list[float]:
    if embedder is None:
        embedder = get_embedder()
    return embedder.embed(text)
