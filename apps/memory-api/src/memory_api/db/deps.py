from collections.abc import Generator

from fastapi import Depends
from sqlalchemy.orm import Session

from memory_api.db.repository import MemoryRepository, PostgresMemoryRepository
from memory_api.db.session import get_db
from memory_api.services.api_keys import ApiKeyStore, PostgresApiKeyStore


def get_repository(db: Session = Depends(get_db)) -> Generator[MemoryRepository, None, None]:
    yield PostgresMemoryRepository(db)


def get_api_key_store(db: Session = Depends(get_db)) -> ApiKeyStore:
    return PostgresApiKeyStore(db)
