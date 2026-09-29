from __future__ import annotations

import argparse
import uuid
from datetime import UTC, datetime

from sqlalchemy import Select, select
from sqlalchemy.orm import Session

from memory_api.db.models import ApiKey, Memory, Org, User
from memory_api.db.session import SessionLocal
from memory_api.services.api_keys import generate_api_key, hash_api_key, key_last4
from memory_api.services.embedding import (
    Embedder,
    HashEmbedder,
    HuggingFaceEmbedder,
    MiniLMEmbedder,
)


def issue_api_key(session: Session, *, org_name: str) -> tuple[Org, str]:
    org = Org(name=org_name, created_at=datetime.now(UTC))
    user = User(
        org=org,
        google_id=f"local-{uuid.uuid4()}",
        email=f"local-{uuid.uuid4()}@memoria.local",
        name="local",
        created_at=datetime.now(UTC),
    )
    raw = generate_api_key()
    session.add(
        ApiKey(
            org=org,
            created_by=user,
            key_hash=hash_api_key(raw),
            key_last4=key_last4(raw),
            created_at=datetime.now(UTC),
        )
    )
    session.commit()
    session.refresh(org)
    return org, raw


def embedder_for_target(name: str) -> Embedder:
    from memory_api.config import settings

    if name == "hash":
        if settings.env != "test":
            raise RuntimeError(
                "MEMORIA_EMBEDDER=hash is only allowed when MEMORIA_ENV=test; "
                "set MEMORIA_EMBEDDER to minilm or hf"
            )
        return HashEmbedder()
    if name == "minilm":
        return MiniLMEmbedder()
    if name in {"hf", "huggingface"}:
        return HuggingFaceEmbedder()
    return HuggingFaceEmbedder(model=name)


def rewrite_memory_embedding(memory: Memory, embedder: Embedder) -> None:
    memory.embedding = embedder.embed(memory.content)
    memory.embedding_model = embedder.model_name
    memory.embedding_version += 1


def reembed_statement(*, org_id: uuid.UUID, from_model: str) -> Select[tuple[Memory]]:
    return select(Memory).where(
        Memory.org_id == org_id,
        Memory.embedding_model == from_model,
    )


def reembed_memories(session: Session, *, from_model: str, embedder: Embedder) -> int:
    org_ids = list(session.scalars(select(Org.id)))
    updated = 0
    for org_id in org_ids:
        rows = session.scalars(reembed_statement(org_id=org_id, from_model=from_model)).all()
        for memory in rows:
            rewrite_memory_embedding(memory, embedder)
            updated += 1
    session.commit()
    return updated


def main() -> None:
    parser = argparse.ArgumentParser(description="Memoria Memory API CLI")
    sub = parser.add_subparsers(dest="command", required=True)
    issue = sub.add_parser("issue-key", help="Create an org and print a one-time API key")
    issue.add_argument("--org-name", default="local")
    reembed = sub.add_parser("reembed", help="Re-embed memories from one model to another")
    reembed.add_argument("--from", dest="from_model", required=True)
    reembed.add_argument("--to", dest="to_model", required=True)
    args = parser.parse_args()
    if args.command == "issue-key":
        session = SessionLocal()
        try:
            org, raw = issue_api_key(session, org_name=args.org_name)
        finally:
            session.close()
        print(f"org_id={org.id}")
        print(raw)
    elif args.command == "reembed":
        embedder = embedder_for_target(args.to_model)
        session = SessionLocal()
        try:
            updated = reembed_memories(
                session, from_model=args.from_model, embedder=embedder
            )
        finally:
            session.close()
        print(f"reembedded={updated}")


if __name__ == "__main__":
    main()
