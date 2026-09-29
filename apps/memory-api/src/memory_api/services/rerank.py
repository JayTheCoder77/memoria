from __future__ import annotations

import importlib.util
import threading
from dataclasses import replace
from typing import TYPE_CHECKING

from fastapi import HTTPException, status

if TYPE_CHECKING:
    from memory_api.services.hybrid_search import RankedHit

RERANK_MODEL = "cross-encoder/ms-marco-MiniLM-L-6-v2"

_model: object | None = None
_model_lock = threading.Lock()


def _minilm_extra_installed() -> bool:
    return importlib.util.find_spec("sentence_transformers") is not None


def _configured() -> bool:
    from memory_api.config import settings

    return settings.reranker == "minilm" and _minilm_extra_installed()


def _cross_encoder() -> object:
    global _model
    if _model is not None:
        return _model
    with _model_lock:
        if _model is None:
            from sentence_transformers import CrossEncoder

            _model = CrossEncoder(RERANK_MODEL)
    return _model


def _scores(raw: object, count: int) -> list[float]:
    if count == 1:
        try:
            return [float(raw)]  # type: ignore[arg-type]
        except TypeError:
            pass
    return [float(score) for score in raw]  # type: ignore[arg-type]


def rerank(query: str, hits: list[RankedHit], *, limit: int) -> list[RankedHit]:
    if not _configured():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="reranker is not configured",
        )
    if not hits or limit <= 0:
        return []
    model = _cross_encoder()
    pairs = [(query, hit.memory.content) for hit in hits]
    raw = model.predict(pairs, show_progress_bar=False)  # type: ignore[attr-defined]
    values = _scores(raw, len(hits))
    ordered = sorted(zip(values, hits, strict=True), key=lambda pair: pair[0], reverse=True)
    return [replace(hit, score=score) for score, hit in ordered[:limit]]
