from __future__ import annotations

import time

from memory_api.config import settings
from memory_api.db.events import PostgresEventStore
from memory_api.db.models import Org
from memory_api.db.repository import PostgresMemoryRepository
from memory_api.db.session import SessionLocal
from memory_api.observability.tracing import start_span
from memory_api.services.embedding import Embedder, get_embedder
from memory_api.services.extraction import HeuristicExtractor, LlmExtractor
from memory_api.services.org_llm import org_chat_providers
from memory_api.services.worker import run_once
from memory_api.stores.graph import PostgresGraphStore
from memory_api.stores.kv import PostgresKVStore
from memory_api.stores.noop import NoOpGraphStore, NoOpKVStore


def tick(*, embedder: Embedder | None = None) -> int:
    embedder = embedder or get_embedder()
    with start_span("worker_tick", embedder=type(embedder).__name__):
        session = SessionLocal()
        try:

            def extractor_for_org(org_id):
                org = session.get(Org, org_id)
                providers = org_chat_providers(org, timeout=30.0)
                if not providers or org is None:
                    return HeuristicExtractor()
                raw_categories = org.categories if isinstance(org.categories, list) else []
                categories = [item for item in raw_categories if isinstance(item, str)]
                return LlmExtractor(
                    providers=providers,
                    org_id=org_id,
                    instructions=org.extraction_instructions,
                    categories=categories,
                )

            kv = PostgresKVStore(session) if settings.enable_kv else NoOpKVStore()
            graph = PostgresGraphStore(session) if settings.enable_graph else NoOpGraphStore()
            created = run_once(
                events=PostgresEventStore(session),
                repo=PostgresMemoryRepository(session),
                embedder=embedder,
                extractor=HeuristicExtractor(),
                extractor_for_org=extractor_for_org,
                batch_size=settings.extract_batch_size,
                threshold=settings.dedup_threshold,
                kv=kv,
                graph=graph,
            )
            session.commit()
            return created
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()


def main() -> None:
    embedder = get_embedder()
    while True:
        created = tick(embedder=embedder)
        if created:
            print(f"extracted {created} memories")
        time.sleep(2)


if __name__ == "__main__":
    main()
