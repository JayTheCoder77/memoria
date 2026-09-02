from __future__ import annotations

import argparse
import uuid
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from memory_api.db.models import ApiKey, Org, User
from memory_api.db.session import SessionLocal
from memory_api.services.api_keys import generate_api_key, hash_api_key, key_last4


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


def main() -> None:
    parser = argparse.ArgumentParser(description="Memoria Memory API CLI")
    sub = parser.add_subparsers(dest="command", required=True)
    issue = sub.add_parser("issue-key", help="Create an org and print a one-time API key")
    issue.add_argument("--org-name", default="local")
    args = parser.parse_args()
    if args.command == "issue-key":
        session = SessionLocal()
        try:
            org, raw = issue_api_key(session, org_name=args.org_name)
        finally:
            session.close()
        print(f"org_id={org.id}")
        print(raw)


if __name__ == "__main__":
    main()
