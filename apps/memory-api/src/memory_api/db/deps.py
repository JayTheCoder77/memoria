from collections.abc import Generator

from fastapi import Depends
from sqlalchemy.orm import Session

from memory_api.db.repository import MemoryRepository, PostgresMemoryRepository
from memory_api.db.session import get_db


def get_repository(db: Session = Depends(get_db)) -> Generator[MemoryRepository, None, None]:
    yield PostgresMemoryRepository(db)
