from __future__ import annotations

import logging

from sqlalchemy.orm import Session

from memory_api.config import settings
from memory_api.db.models import Memory
from memory_api.services.extraction import Candidate
from memory_api.services.graph_triples import resolve_graph_triples
from memory_api.stores.protocols import GraphStore

logger = logging.getLogger(__name__)


def persist_graph_facts(
    *,
    graph: GraphStore,
    memory: Memory,
    candidate: Candidate,
    session: Session | None = None,
) -> None:
    if not settings.enable_graph:
        return
    try:
        triples = resolve_graph_triples(candidate)
    except Exception:
        logger.exception("graph fan-out failed")
        return
    for triple in triples:
        try:
            confidence = float(triple.get("confidence", 1.0))
            if confidence < settings.graph_min_confidence:
                continue
            if session is not None:
                with session.begin_nested():
                    graph.add_edge(
                        memory.org_id,
                        triple["subject"],
                        triple["relation"],
                        triple["object"],
                        memory_id=memory.id,
                        confidence=confidence,
                    )
            else:
                graph.add_edge(
                    memory.org_id,
                    triple["subject"],
                    triple["relation"],
                    triple["object"],
                    memory_id=memory.id,
                    confidence=confidence,
                )
        except Exception:
            logger.exception("graph fan-out failed")
