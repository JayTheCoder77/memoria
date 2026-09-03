from __future__ import annotations

import hashlib
import math
import time
from collections.abc import Callable
from typing import Protocol

import httpx

EMBEDDING_DIM = 384
_HF_ROUTER = "https://router.huggingface.co/hf-inference/models"


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


def _l2_normalize(values: list[float]) -> list[float]:
    norm = math.sqrt(sum(value * value for value in values)) or 1.0
    return [value / norm for value in values]


def _as_vector(payload: object) -> list[float]:
    if isinstance(payload, list) and payload and isinstance(payload[0], (int, float)):
        values = [float(item) for item in payload]
    elif isinstance(payload, list) and payload:
        rows = [_as_vector(row) for row in payload]
        dim = len(rows[0])
        values = [sum(row[i] for row in rows) / len(rows) for i in range(dim)]
    else:
        raise RuntimeError(f"unexpected embedding payload: {type(payload)}")
    if len(values) != EMBEDDING_DIM:
        raise RuntimeError(f"expected {EMBEDDING_DIM}d embedding, got {len(values)}")
    return _l2_normalize(values)


class HuggingFaceEmbedder:
    """Remote all-MiniLM-L6-v2 via Hugging Face Inference. MEMORIA_EMBEDDER=hf."""

    def __init__(
        self,
        *,
        token: str | None = None,
        model: str | None = None,
        http: httpx.Client | None = None,
        sleep: Callable[[float], None] = time.sleep,
        retries: int = 5,
    ) -> None:
        from memory_api.config import settings

        self._token = settings.hf_token if token is None else token
        self._model = model or settings.hf_model
        self._http = http or httpx.Client(timeout=60.0)
        self._sleep = sleep
        self._retries = retries

    def embed(self, text: str) -> list[float]:
        if not self._token:
            raise RuntimeError("MEMORIA_HF_TOKEN is required when MEMORIA_EMBEDDER=hf")
        url = f"{_HF_ROUTER}/{self._model}/pipeline/feature-extraction"
        headers = {
            "Authorization": f"Bearer {self._token}",
            "Content-Type": "application/json",
        }
        last_error: Exception | None = None
        for attempt in range(self._retries):
            response = self._http.post(url, headers=headers, json={"inputs": text})
            if response.status_code in {429, 503} and attempt + 1 < self._retries:
                self._sleep(2**attempt)
                continue
            try:
                response.raise_for_status()
            except httpx.HTTPStatusError as exc:
                last_error = exc
                if attempt + 1 < self._retries:
                    self._sleep(2**attempt)
                    continue
                raise RuntimeError(
                    f"Hugging Face embedding failed: {exc.response.status_code} {exc.response.text}"
                ) from exc
            return _as_vector(response.json())
        raise RuntimeError("Hugging Face embedding failed") from last_error


def get_embedder() -> Embedder:
    from memory_api.config import settings

    if settings.embedder in {"hf", "huggingface"}:
        return HuggingFaceEmbedder()
    if settings.embedder == "minilm":
        return MiniLMEmbedder()
    return HashEmbedder()


def embed_text(text: str, embedder: Embedder | None = None) -> list[float]:
    if embedder is None:
        embedder = get_embedder()
    return embedder.embed(text)
