import os
from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from memory_api.config import settings
from memory_api.db.url import engine_kwargs, sqlalchemy_url

_raw_database_url = (
    os.environ.get("MEMORIA_DATABASE_URL")
    or os.environ.get("DATABASE_URL")
    or settings.database_url
)
DATABASE_URL = sqlalchemy_url(_raw_database_url)
engine = create_engine(DATABASE_URL, **engine_kwargs(DATABASE_URL))
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)


def get_db() -> Generator[Session, None, None]:
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
