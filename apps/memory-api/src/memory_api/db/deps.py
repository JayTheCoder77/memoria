from collections.abc import Generator

from fastapi import Depends
from sqlalchemy.orm import Session

from memory_api.config import settings
from memory_api.db.events import EventStore, PostgresEventStore
from memory_api.db.identity import IdentityRepository, PostgresIdentityRepository
from memory_api.db.repository import MemoryRepository, PostgresMemoryRepository
from memory_api.db.session import get_db
from memory_api.services.api_keys import ApiKeyStore, PostgresApiKeyStore
from memory_api.services.extraction import Extractor, HeuristicExtractor
from memory_api.services.google_auth import get_google_verifier
from memory_api.services.rate_limit import SlidingWindowRateLimiter
from memory_api.stores.noop import NoOpGraphStore, NoOpKVStore
from memory_api.stores.protocols import GraphStore, KVStore

_limiter: SlidingWindowRateLimiter | None = None


def get_repository(db: Session = Depends(get_db)) -> Generator[MemoryRepository, None, None]:
    yield PostgresMemoryRepository(db)


def get_event_store(db: Session = Depends(get_db)) -> EventStore:
    return PostgresEventStore(db)


def get_extractor() -> Extractor:
    return HeuristicExtractor()


def get_api_key_store(db: Session = Depends(get_db)) -> ApiKeyStore:
    return PostgresApiKeyStore(db)


def get_kv_store(db: Session = Depends(get_db)) -> KVStore:
    if not settings.enable_kv:
        return NoOpKVStore()
    from memory_api.stores.kv import PostgresKVStore

    return PostgresKVStore(db)


def get_graph_store(db: Session = Depends(get_db)) -> GraphStore:
    if not settings.enable_graph:
        return NoOpGraphStore()
    from memory_api.stores.graph import PostgresGraphStore

    return PostgresGraphStore(db)


def get_identity_repository(db: Session = Depends(get_db)) -> IdentityRepository:
    return PostgresIdentityRepository(db)


def get_rate_limiter() -> SlidingWindowRateLimiter:
    global _limiter
    if _limiter is None:
        _limiter = SlidingWindowRateLimiter(limit=settings.rate_limit_per_minute)
    return _limiter


__all__ = [
    "get_api_key_store",
    "get_event_store",
    "get_extractor",
    "get_google_verifier",
    "get_graph_store",
    "get_identity_repository",
    "get_kv_store",
    "get_rate_limiter",
    "get_repository",
]
