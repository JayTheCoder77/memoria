from __future__ import annotations

import logging

from sqlalchemy.orm import Session

from memory_api.config import settings
from memory_api.db.models import Memory
from memory_api.services.extraction import Candidate
from memory_api.services.kv_triples import resolve_kv_triples
from memory_api.stores.protocols import KVStore

logger = logging.getLogger(__name__)


def persist_kv_facts(
    *,
    kv: KVStore,
    memory: Memory,
    candidate: Candidate,
    session: Session | None = None,
) -> None:
    if not settings.enable_kv:
        return
    try:
        triples = resolve_kv_triples(candidate)
    except Exception:
        logger.exception("kv fan-out failed")
        return
    for triple in triples:
        try:
            if session is not None:
                with session.begin_nested():
                    kv.put(
                        memory.org_id,
                        memory.id,
                        triple["fact_type"],
                        triple["entity"],
                        value=triple.get("value"),
                        importance=memory.importance,
                    )
            else:
                kv.put(
                    memory.org_id,
                    memory.id,
                    triple["fact_type"],
                    triple["entity"],
                    value=triple.get("value"),
                    importance=memory.importance,
                )
        except Exception:
            logger.exception("kv fan-out failed")
