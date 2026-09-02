from __future__ import annotations

import time

from memory_api.config import settings
from memory_api.db.events import PostgresEventStore
from memory_api.db.repository import PostgresMemoryRepository
from memory_api.db.session import SessionLocal
from memory_api.services.embedding import get_embedder
from memory_api.services.extraction import HeuristicExtractor
from memory_api.services.worker import run_once


def main() -> None:
    embedder = get_embedder()
    extractor = HeuristicExtractor()
    while True:
        session = SessionLocal()
        try:
            created = run_once(
                events=PostgresEventStore(session),
                repo=PostgresMemoryRepository(session),
                embedder=embedder,
                extractor=extractor,
                batch_size=settings.extract_batch_size,
                threshold=settings.dedup_threshold,
            )
            session.commit()
            if created:
                print(f"extracted {created} memories")
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()
        time.sleep(2)


if __name__ == "__main__":
    main()
