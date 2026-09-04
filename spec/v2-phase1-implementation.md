# Phase 1 KV Store Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Persist exact facts in Postgres `kv_facts`, fan out from remember/extraction without failing the canonical write, and union KV hits into search so fact lookups work when vector ranking is weak.

**Architecture:** `memories` stays canonical. `PostgresKVStore` / `InMemoryKVStore` implement the existing `KVStore` protocol. After `persist_candidate`, `persist_kv_facts` upserts triples inside a savepoint (log and continue on error). Search derives `(fact_type, entity)` keys via LLM when the org has an OpenRouter key, else rules; `search_keys` results are unioned by `memory_id` with `relevance = max(vector_similarity, kv_match)`.

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy 2, Alembic, pgvector, pytest, httpx mocks, ruff (existing Memory API).

## Global Constraints

- Spec: `spec/v2-phase1-kv-store.md` (parent `spec/v2_extension_plan.md`).
- `enable_kv` defaults **true**; `enable_graph` stays **false**.
- Exact KV `kv_match` is `1.0`. No fuzzy keys, no graph, no `as_of`, no MCP schema changes.
- Remember must **not** fail because KV or candidate-LLM failed; search must **not** 500 for those either.
- Open `fact_type` strings; no DB allow-list. Seed extractors with preference / city / decision / language.
- `MEMORIA_KV_MAX_TRIPLES_PER_ADD` default `6`. Candidate-key lists capped at `12`.
- MCP tools unchanged. HTTP `POST /memories` may accept `kv_triples`.
- Every production change is preceded by a failing test (TDD).
- Work on a feature branch off current `main`; do not commit secrets.
- Run Memory API tests from `apps/memory-api` with `uv run pytest …`.

## File map

- Create: `apps/memory-api/alembic/versions/0005_kv_facts.py`
- Create: `apps/memory-api/src/memory_api/stores/kv.py`
- Create: `apps/memory-api/src/memory_api/services/kv_triples.py`
- Create: `apps/memory-api/src/memory_api/services/kv_fanout.py`
- Create: `apps/memory-api/src/memory_api/services/kv_candidates.py`
- Create: `apps/memory-api/tests/test_kv_triples.py`
- Create: `apps/memory-api/tests/test_kv_fanout.py`
- Create: `apps/memory-api/tests/test_kv_candidates.py`
- Modify: `apps/memory-api/src/memory_api/config.py`
- Modify: `apps/memory-api/tests/test_hybrid_config.py`
- Modify: `apps/memory-api/.env.example`
- Modify: `apps/memory-api/src/memory_api/db/models.py`
- Modify: `apps/memory-api/src/memory_api/stores/__init__.py`
- Modify: `apps/memory-api/tests/test_stores.py`
- Modify: `apps/memory-api/src/memory_api/services/extraction.py`
- Modify: `apps/memory-api/tests/test_extraction.py`
- Modify: `apps/memory-api/src/memory_api/schemas/memory.py`
- Modify: `apps/memory-api/src/memory_api/db/deps.py`
- Modify: `apps/memory-api/src/memory_api/routers/memories.py`
- Modify: `apps/memory-api/tests/test_memories_api.py`
- Modify: `apps/memory-api/src/memory_api/services/worker.py`
- Modify: `apps/memory-api/src/memory_api/worker.py`
- Modify: `apps/memory-api/tests/test_postgres_api.py`
- Modify: `spec/v2_extension_plan.md`
- Modify: `spec/03-architecture.md`

---

### Task 1: Default-on KV flag and triple cap

**Files:**
- Modify: `apps/memory-api/src/memory_api/config.py`
- Modify: `apps/memory-api/tests/test_hybrid_config.py`
- Modify: `apps/memory-api/.env.example`

**Interfaces:**
- Consumes: existing `Settings` (`env_prefix="MEMORIA_"`)
- Produces: `enable_kv: bool = True`, `kv_max_triples_per_add: int = 6`

- [ ] **Step 1: Write the failing test**

Replace `test_hybrid_flags_default_off` and add a cap assertion:

```python
from memory_api.config import Settings


def test_hybrid_flags_kv_on_graph_off() -> None:
    s = Settings()
    assert s.enable_kv is True
    assert s.enable_graph is False


def test_kv_max_triples_per_add_default() -> None:
    s = Settings()
    assert s.kv_max_triples_per_add == 6


def test_fusion_weights_match_current_scoring_defaults() -> None:
    s = Settings()
    assert s.fusion_weight_relevance == 0.6
    assert s.fusion_weight_importance == 0.2
    assert s.fusion_weight_recency == 0.2
    assert s.recency_halflife_days == 14.0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_hybrid_config.py::test_hybrid_flags_kv_on_graph_off tests/test_hybrid_config.py::test_kv_max_triples_per_add_default -v`

Expected: FAIL (`enable_kv is False` and/or attribute missing)

- [ ] **Step 3: Write minimal implementation**

In `config.py` set:

```python
enable_kv: bool = True
enable_graph: bool = False
kv_max_triples_per_add: int = 6
```

In `.env.example` replace the hybrid block with:

```
# Hybrid stores (v2). Graph stays off until Phase 2.
MEMORIA_ENABLE_KV=true
MEMORIA_ENABLE_GRAPH=false
MEMORIA_KV_MAX_TRIPLES_PER_ADD=6
MEMORIA_FUSION_WEIGHT_RELEVANCE=0.6
MEMORIA_FUSION_WEIGHT_IMPORTANCE=0.2
MEMORIA_FUSION_WEIGHT_RECENCY=0.2
MEMORIA_RECENCY_HALFLIFE_DAYS=14
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_hybrid_config.py -v`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add apps/memory-api/src/memory_api/config.py apps/memory-api/tests/test_hybrid_config.py apps/memory-api/.env.example
git commit -m "Default KV on and cap triples per remember."
```

---

### Task 2: `kv_facts` migration and ORM

**Files:**
- Create: `apps/memory-api/alembic/versions/0005_kv_facts.py`
- Modify: `apps/memory-api/src/memory_api/db/models.py` (add `KvFact` after `Memory`)

**Interfaces:**
- Consumes: Alembic `0004_openrouter_byok`, `orgs.id`, `memories.id`
- Produces: table `kv_facts`; class `KvFact` with fields matching the spec SQL

- [ ] **Step 1: Write the failing test**

Add to `tests/test_stores.py`:

```python
from memory_api.db.models import KvFact


def test_kv_fact_model_maps_kv_facts_table() -> None:
    assert KvFact.__tablename__ == "kv_facts"
    column_names = set(KvFact.__table__.columns.keys())
    assert column_names == {
        "id",
        "org_id",
        "memory_id",
        "user_key",
        "fact_type",
        "entity",
        "value",
        "importance",
        "created_at",
        "updated_at",
    }
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_stores.py::test_kv_fact_model_maps_kv_facts_table -v`

Expected: FAIL (`ImportError` / `KvFact` not defined)

- [ ] **Step 3: Write minimal implementation**

Add `UniqueConstraint` to sqlalchemy imports in `models.py`. After `class Memory`:

```python
class KvFact(Base):
    __tablename__ = "kv_facts"
    __table_args__ = (
        UniqueConstraint("org_id", "fact_type", "entity", name="uq_kv_facts_org_type_entity"),
        Index("idx_kv_facts_org_type", "org_id", "fact_type"),
        Index("idx_kv_facts_memory", "memory_id"),
        Index(
            "idx_kv_facts_org_user",
            "org_id",
            "user_key",
            postgresql_where=text("user_key IS NOT NULL"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("orgs.id"), nullable=False
    )
    memory_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("memories.id", ondelete="CASCADE"), nullable=False
    )
    user_key: Mapped[str | None] = mapped_column(Text, nullable=True)
    fact_type: Mapped[str] = mapped_column(Text, nullable=False)
    entity: Mapped[str] = mapped_column(Text, nullable=False)
    value: Mapped[str | None] = mapped_column(Text, nullable=True)
    importance: Mapped[float] = mapped_column(Float, nullable=False, default=0.5)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
```

Import `text` from `sqlalchemy` and `UniqueConstraint` from `sqlalchemy`. If `postgresql_where` makes SQLite-unfriendly metadata in unit tests, omit that partial index from the ORM and only create it in Alembic (preferred if the model test fails to construct the table).

Create `0005_kv_facts.py` mirroring `0004` style:

```python
"""add kv_facts for hybrid exact lookup

Revision ID: 0005_kv_facts
Revises: 0004_openrouter_byok
Create Date: 2026-09-04
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0005_kv_facts"
down_revision: str | None = "0004_openrouter_byok"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "kv_facts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "org_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("orgs.id"),
            nullable=False,
        ),
        sa.Column(
            "memory_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("memories.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("user_key", sa.Text(), nullable=True),
        sa.Column("fact_type", sa.Text(), nullable=False),
        sa.Column("entity", sa.Text(), nullable=False),
        sa.Column("value", sa.Text(), nullable=True),
        sa.Column("importance", sa.Float(), nullable=False, server_default="0.5"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("org_id", "fact_type", "entity", name="uq_kv_facts_org_type_entity"),
    )
    op.create_index("idx_kv_facts_org_type", "kv_facts", ["org_id", "fact_type"])
    op.create_index("idx_kv_facts_memory", "kv_facts", ["memory_id"])
    op.create_index(
        "idx_kv_facts_org_user",
        "kv_facts",
        ["org_id", "user_key"],
        postgresql_where=sa.text("user_key IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("idx_kv_facts_org_user", table_name="kv_facts")
    op.drop_index("idx_kv_facts_memory", table_name="kv_facts")
    op.drop_index("idx_kv_facts_org_type", table_name="kv_facts")
    op.drop_table("kv_facts")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_stores.py::test_kv_fact_model_maps_kv_facts_table -v`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add apps/memory-api/alembic/versions/0005_kv_facts.py apps/memory-api/src/memory_api/db/models.py apps/memory-api/tests/test_stores.py
git commit -m "Add kv_facts table and KvFact model."
```

---

### Task 3: In-memory and Postgres KV stores

**Files:**
- Create: `apps/memory-api/src/memory_api/stores/kv.py`
- Modify: `apps/memory-api/src/memory_api/stores/__init__.py`
- Modify: `apps/memory-api/tests/test_stores.py`
- Modify: `apps/memory-api/tests/test_postgres_api.py` (Postgres-only upsert/isolation; skipif already on file)

**Interfaces:**
- Consumes: `KVStore` protocol, `KVFact` dataclass, `KvFact` ORM, `Session`
- Produces: `normalize_kv_token(value: str) -> str`; `InMemoryKVStore`; `PostgresKVStore`

`normalize_kv_token` is `value.strip().lower()`. `put` skips when type or entity normalizes to `""`.

- [ ] **Step 1: Write the failing test**

Add to `tests/test_stores.py`:

```python
from memory_api.stores.kv import InMemoryKVStore, normalize_kv_token


def test_normalize_kv_token_strips_and_lowercases() -> None:
    assert normalize_kv_token("  TypeScript ") == "typescript"


def test_in_memory_kv_put_get_search_and_org_isolation() -> None:
    store = InMemoryKVStore()
    org_a = uuid.uuid4()
    org_b = uuid.uuid4()
    mem_a = uuid.uuid4()
    mem_b = uuid.uuid4()
    store.put(org_a, mem_a, "Preference", "TypeScript", value="ts", importance=0.8)
    store.put(org_b, mem_b, "preference", "typescript", value="other", importance=0.1)
    hit = store.get(org_a, "preference", "typescript")
    assert hit is not None
    assert hit.memory_id == mem_a
    assert hit.value == "ts"
    assert hit.importance == 0.8
    assert store.get(org_a, "preference", "python") is None
    keys = store.search_keys(org_a, [("preference", "typescript"), ("city", "lisbon")])
    assert [row.memory_id for row in keys] == [mem_a]
    assert all(row.org_id == org_a for row in store.by_org(org_a))
    assert store.get(org_b, "preference", "typescript") is not None


def test_in_memory_kv_upsert_replaces_memory_id() -> None:
    store = InMemoryKVStore()
    org_id = uuid.uuid4()
    first = uuid.uuid4()
    second = uuid.uuid4()
    store.put(org_id, first, "city", "lisbon", value=None, importance=0.4)
    store.put(org_id, second, "city", "lisbon", value="pt", importance=0.9)
    hit = store.get(org_id, "city", "lisbon")
    assert hit is not None
    assert hit.memory_id == second
    assert hit.value == "pt"
    assert hit.importance == 0.9
    assert len(store.by_org(org_id)) == 1
```

Add to `tests/test_postgres_api.py` (uses live DB; skip if Postgres down):

```python
from memory_api.db.models import Memory, MemoryType, Org
from memory_api.db.session import SessionLocal
from memory_api.stores.kv import PostgresKVStore
from memory_api.services.embedding import EMBEDDING_DIM


def test_postgres_kv_store_round_trip_and_tenant_isolation(
    pg_client: TestClient, org_and_key: tuple[str, str]
) -> None:
    org_id = uuid.UUID(org_and_key[0])
    other = Org(id=uuid.uuid4(), name="other", created_at=datetime.now(UTC))
    session = SessionLocal()
    try:
        session.add(other)
        memory = Memory(
            org_id=org_id,
            session_id="s1",
            memory_type=MemoryType.semantic,
            content="prefer typescript",
            embedding=[0.0] * EMBEDDING_DIM,
            importance=0.7,
            source_metadata={},
        )
        session.add(memory)
        session.flush()
        store = PostgresKVStore(session)
        store.put(org_id, memory.id, "preference", "typescript", value="ts", importance=0.7)
        store.put(other.id, memory.id, "preference", "typescript", value="no", importance=0.1)
        hit = store.get(org_id, "preference", "typescript")
        assert hit is not None
        assert hit.memory_id == memory.id
        assert store.get(other.id, "preference", "typescript") is None or (
            store.get(other.id, "preference", "typescript").org_id == other.id
        )
        # other org put should fail FK or require its own memory — insert a memory for other instead:
        session.rollback()
    finally:
        session.close()
```

Do **not** use the broken other-org `put` against `memory.id` of a different org. Correct Postgres test:

```python
def test_postgres_kv_store_round_trip_and_tenant_isolation() -> None:
    session = SessionLocal()
    try:
        org_a = Org(id=uuid.uuid4(), name="a", created_at=datetime.now(UTC))
        org_b = Org(id=uuid.uuid4(), name="b", created_at=datetime.now(UTC))
        session.add_all([org_a, org_b])
        session.flush()
        mem_a = Memory(
            org_id=org_a.id,
            session_id="s1",
            memory_type=MemoryType.semantic,
            content="a",
            embedding=[0.0] * EMBEDDING_DIM,
            importance=0.5,
            source_metadata={},
        )
        mem_b = Memory(
            org_id=org_b.id,
            session_id="s1",
            memory_type=MemoryType.semantic,
            content="b",
            embedding=[0.0] * EMBEDDING_DIM,
            importance=0.5,
            source_metadata={},
        )
        session.add_all([mem_a, mem_b])
        session.flush()
        store = PostgresKVStore(session)
        store.put(org_a.id, mem_a.id, "preference", "typescript", value="ts", importance=0.8)
        store.put(org_b.id, mem_b.id, "preference", "typescript", value="no", importance=0.1)
        hit = store.get(org_a.id, "preference", "typescript")
        assert hit is not None
        assert hit.memory_id == mem_a.id
        assert hit.value == "ts"
        keys = store.search_keys(org_a.id, [("preference", "typescript")])
        assert len(keys) == 1
        assert keys[0].memory_id == mem_a.id
        session.rollback()
    finally:
        session.close()
```

This test does not need `pg_client`. Keep `pytestmark` skipif.

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_stores.py::test_in_memory_kv_put_get_search_and_org_isolation -v`

Expected: FAIL (`ImportError` for `memory_api.stores.kv`)

- [ ] **Step 3: Write minimal implementation**

`stores/kv.py`:

```python
from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from memory_api.db.models import KvFact
from memory_api.stores.types import KVFact


def normalize_kv_token(value: str) -> str:
    return value.strip().lower()


def _as_dataclass(row: KvFact) -> KVFact:
    return KVFact(
        org_id=row.org_id,
        memory_id=row.memory_id,
        fact_type=row.fact_type,
        entity=row.entity,
        value=row.value,
        importance=row.importance,
        user_key=row.user_key,
        id=row.id,
    )


class InMemoryKVStore:
    def __init__(self) -> None:
        self._rows: dict[tuple[uuid.UUID, str, str], KVFact] = {}

    def put(
        self,
        org_id: uuid.UUID,
        memory_id: uuid.UUID,
        fact_type: str,
        entity: str,
        *,
        value: str | None,
        importance: float,
        user_key: str | None = None,
    ) -> None:
        fact_type_n = normalize_kv_token(fact_type)
        entity_n = normalize_kv_token(entity)
        if not fact_type_n or not entity_n:
            return
        key = (org_id, fact_type_n, entity_n)
        existing = self._rows.get(key)
        self._rows[key] = KVFact(
            org_id=org_id,
            memory_id=memory_id,
            fact_type=fact_type_n,
            entity=entity_n,
            value=value,
            importance=importance,
            user_key=user_key,
            id=existing.id if existing is not None else uuid.uuid4(),
        )

    def get(self, org_id: uuid.UUID, fact_type: str, entity: str) -> KVFact | None:
        return self._rows.get(
            (org_id, normalize_kv_token(fact_type), normalize_kv_token(entity))
        )

    def search_keys(
        self, org_id: uuid.UUID, candidates: list[tuple[str, str]]
    ) -> list[KVFact]:
        found: list[KVFact] = []
        seen: set[uuid.UUID] = set()
        for fact_type, entity in candidates:
            row = self.get(org_id, fact_type, entity)
            if row is None or row.id in seen:
                continue
            seen.add(row.id)  # type: ignore[arg-type]
            found.append(row)
        return found

    def by_org(self, org_id: uuid.UUID, *, user_key: str | None = None) -> list[KVFact]:
        rows = [row for row in self._rows.values() if row.org_id == org_id]
        if user_key is not None:
            rows = [row for row in rows if row.user_key == user_key]
        return rows


class PostgresKVStore:
    def __init__(self, session: Session) -> None:
        self._session = session

    def put(
        self,
        org_id: uuid.UUID,
        memory_id: uuid.UUID,
        fact_type: str,
        entity: str,
        *,
        value: str | None,
        importance: float,
        user_key: str | None = None,
    ) -> None:
        fact_type_n = normalize_kv_token(fact_type)
        entity_n = normalize_kv_token(entity)
        if not fact_type_n or not entity_n:
            return
        now = datetime.now(UTC)
        stmt = insert(KvFact).values(
            org_id=org_id,
            memory_id=memory_id,
            user_key=user_key,
            fact_type=fact_type_n,
            entity=entity_n,
            value=value,
            importance=importance,
            created_at=now,
            updated_at=now,
        )
        stmt = stmt.on_conflict_do_update(
            constraint="uq_kv_facts_org_type_entity",
            set_={
                "memory_id": memory_id,
                "value": value,
                "importance": importance,
                "user_key": user_key,
                "updated_at": now,
            },
        )
        self._session.execute(stmt)
        self._session.flush()

    def get(self, org_id: uuid.UUID, fact_type: str, entity: str) -> KVFact | None:
        row = self._session.scalar(
            select(KvFact).where(
                KvFact.org_id == org_id,
                KvFact.fact_type == normalize_kv_token(fact_type),
                KvFact.entity == normalize_kv_token(entity),
            )
        )
        return _as_dataclass(row) if row is not None else None

    def search_keys(
        self, org_id: uuid.UUID, candidates: list[tuple[str, str]]
    ) -> list[KVFact]:
        found: list[KVFact] = []
        seen: set[uuid.UUID] = set()
        for fact_type, entity in candidates:
            row = self.get(org_id, fact_type, entity)
            if row is None or row.id in seen:
                continue
            if row.id is not None:
                seen.add(row.id)
            found.append(row)
        return found

    def by_org(self, org_id: uuid.UUID, *, user_key: str | None = None) -> list[KVFact]:
        stmt = select(KvFact).where(KvFact.org_id == org_id)
        if user_key is not None:
            stmt = stmt.where(KvFact.user_key == user_key)
        return [_as_dataclass(row) for row in self._session.scalars(stmt)]
```

Export `InMemoryKVStore`, `PostgresKVStore`, `normalize_kv_token` from `stores/__init__.py`.

Fix `search_keys` duplicate-skip to use `(fact_type, entity)` if `id` is awkward.

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_stores.py tests/test_postgres_api.py::test_postgres_kv_store_round_trip_and_tenant_isolation -v`

Expected: in-memory PASS; Postgres test PASS if Docker Postgres is up, else skipped.

Apply migration on local Postgres before the Postgres test: `uv run alembic upgrade head` from `apps/memory-api`. If CI runs migrations in the workflow, follow that same path.

- [ ] **Step 5: Commit**

```bash
git add apps/memory-api/src/memory_api/stores/kv.py apps/memory-api/src/memory_api/stores/__init__.py apps/memory-api/tests/test_stores.py apps/memory-api/tests/test_postgres_api.py
git commit -m "Implement in-memory and Postgres KV stores."
```

---

### Task 4: Resolve triples (explicit, then heuristic)

**Files:**
- Create: `apps/memory-api/src/memory_api/services/kv_triples.py`
- Create: `apps/memory-api/tests/test_kv_triples.py`
- Modify: `apps/memory-api/src/memory_api/services/extraction.py` (`Candidate.kv_triples`)

**Interfaces:**
- Consumes: `Candidate`, `settings.kv_max_triples_per_add`
- Produces: `KvTriple` TypedDict or small dataclass `{fact_type, entity, value}`; `resolve_kv_triples(candidate: Candidate) -> list[KvTriple]`

Heuristic (conservative):

- `prefer|always|never|we use` + following token → `preference`
- `lives in|in <City>` (capitalized token after `in`) → `city`
- `decided|decision|going with` + token → `decision`
- `language` + token → `language`
- `"explain skeleton probe"` → `[]`

- [ ] **Step 1: Write the failing test**

```python
from memory_api.db.models import MemoryType
from memory_api.services.extraction import Candidate
from memory_api.services.kv_triples import resolve_kv_triples


def test_explicit_triples_win_over_heuristic() -> None:
    candidate = Candidate(
        content="We prefer pytest over unittest in this repo.",
        memory_type=MemoryType.semantic,
        kv_triples=[{"fact_type": "language", "entity": "python", "value": None}],
    )
    triples = resolve_kv_triples(candidate)
    assert triples == [{"fact_type": "language", "entity": "python", "value": None}]


def test_heuristic_preference_and_skips_probe() -> None:
    prefer = Candidate(
        content="We prefer pytest over unittest in this repo.",
        memory_type=MemoryType.semantic,
    )
    probe = Candidate(
        content="explain skeleton probe",
        memory_type=MemoryType.semantic,
    )
    triples = resolve_kv_triples(prefer)
    assert any(t["fact_type"] == "preference" and t["entity"] == "pytest" for t in triples)
    assert resolve_kv_triples(probe) == []


def test_empty_type_or_entity_dropped_and_cap_applied(monkeypatch) -> None:
    from memory_api.config import settings

    monkeypatch.setattr(settings, "kv_max_triples_per_add", 2)
    candidate = Candidate(
        content="x",
        memory_type=MemoryType.semantic,
        kv_triples=[
            {"fact_type": "", "entity": "x"},
            {"fact_type": "a", "entity": "1"},
            {"fact_type": "b", "entity": "2"},
            {"fact_type": "c", "entity": "3"},
        ],
    )
    triples = resolve_kv_triples(candidate)
    assert len(triples) == 2
    assert triples[0]["entity"] == "1"
```

Add `kv_triples: list[dict[str, Any]] = field(default_factory=list)` to `Candidate` **in the implementation step**, not before the test fails on `resolve_kv_triples` import. The first failure should be missing `resolve_kv_triples`. If `Candidate` has no `kv_triples`, the explicit test will fail next — add the field in Step 3.

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_kv_triples.py -v`

Expected: FAIL (module not found)

- [ ] **Step 3: Write minimal implementation**

`Candidate`:

```python
kv_triples: list[dict[str, Any]] = field(default_factory=list)
```

`kv_triples.py`: normalize with `normalize_kv_token`; drop empties; if any explicit remain, return `[:cap]`; else heuristic regexes; cap.

Use `value` key default `None`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_kv_triples.py -v`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add apps/memory-api/src/memory_api/services/kv_triples.py apps/memory-api/src/memory_api/services/extraction.py apps/memory-api/tests/test_kv_triples.py
git commit -m "Resolve KV triples from payload or conservative heuristics."
```

---

### Task 5: Fan-out that cannot fail remember

**Files:**
- Create: `apps/memory-api/src/memory_api/services/kv_fanout.py`
- Create: `apps/memory-api/tests/test_kv_fanout.py`

**Interfaces:**
- Consumes: `KVStore.put`, `resolve_kv_triples`, `settings.enable_kv`, optional SQLAlchemy `Session`
- Produces: `persist_kv_facts(*, kv, memory, candidate, session=None) -> None`

When `session` is not `None`, wrap each `put` in `session.begin_nested()`. Catch `Exception`, `logger.exception("kv fan-out failed")`, continue. When `enable_kv` is false, no-op.

- [ ] **Step 1: Write the failing test**

```python
import uuid
from unittest.mock import MagicMock

from memory_api.db.models import Memory, MemoryType
from memory_api.db.repository import InMemoryMemoryRepository
from memory_api.services.embedding import HashEmbedder
from memory_api.services.extraction import Candidate
from memory_api.services.dedup import persist_candidate
from memory_api.services.kv_fanout import persist_kv_facts
from memory_api.stores.kv import InMemoryKVStore


def _memory() -> Memory:
    repo = InMemoryMemoryRepository()
    memory, _ = persist_candidate(
        repo=repo,
        embedder=HashEmbedder(),
        org_id=uuid.uuid4(),
        session_id="s1",
        candidate=Candidate(
            content="We prefer pytest over unittest in this repo.",
            memory_type=MemoryType.semantic,
        ),
    )
    return memory


def test_persist_kv_facts_writes_heuristic_triple() -> None:
    kv = InMemoryKVStore()
    memory = _memory()
    persist_kv_facts(
        kv=kv,
        memory=memory,
        candidate=Candidate(
            content=memory.content,
            memory_type=MemoryType.semantic,
        ),
    )
    assert kv.get(memory.org_id, "preference", "pytest") is not None


def test_persist_kv_facts_survives_put_error() -> None:
    memory = _memory()
    kv = MagicMock()
    kv.put.side_effect = RuntimeError("db down")
    persist_kv_facts(
        kv=kv,
        memory=memory,
        candidate=Candidate(
            content=memory.content,
            memory_type=MemoryType.semantic,
            kv_triples=[{"fact_type": "preference", "entity": "pytest"}],
        ),
    )
    kv.put.assert_called()


def test_persist_kv_facts_noop_when_flag_off(monkeypatch) -> None:
    from memory_api.config import settings

    monkeypatch.setattr(settings, "enable_kv", False)
    kv = InMemoryKVStore()
    memory = _memory()
    persist_kv_facts(
        kv=kv,
        memory=memory,
        candidate=Candidate(
            content=memory.content,
            memory_type=MemoryType.semantic,
            kv_triples=[{"fact_type": "preference", "entity": "pytest"}],
        ),
    )
    assert kv.get(memory.org_id, "preference", "pytest") is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_kv_fanout.py -v`

Expected: FAIL (import)

- [ ] **Step 3: Write minimal implementation**

```python
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
    for triple in resolve_kv_triples(candidate):
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_kv_fanout.py -v`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add apps/memory-api/src/memory_api/services/kv_fanout.py apps/memory-api/tests/test_kv_fanout.py
git commit -m "Fan out KV facts without failing remember."
```

---

### Task 6: Wire writes (API, extractor, worker)

**Files:**
- Modify: `apps/memory-api/src/memory_api/schemas/memory.py`
- Modify: `apps/memory-api/src/memory_api/db/deps.py`
- Modify: `apps/memory-api/src/memory_api/routers/memories.py`
- Modify: `apps/memory-api/tests/test_memories_api.py`
- Modify: `apps/memory-api/src/memory_api/services/extraction.py` (`LlmExtractor` parse `kv_triples`)
- Modify: `apps/memory-api/tests/test_extraction.py`
- Modify: `apps/memory-api/src/memory_api/services/worker.py`
- Modify: `apps/memory-api/src/memory_api/worker.py`

**Interfaces:**
- Consumes: `persist_kv_facts`, `get_kv_store`, `InMemoryKVStore`
- Produces: `MemoryCreate.kv_triples` optional list; `GET`/`POST` share one KV instance in tests via override

- [ ] **Step 1: Write the failing tests**

In `test_memories_api.py`, share an `InMemoryKVStore` on the client fixture:

```python
from memory_api.db.deps import get_api_key_store, get_kv_store, get_repository
from memory_api.stores.kv import InMemoryKVStore


@pytest.fixture
def kv() -> InMemoryKVStore:
    return InMemoryKVStore()


@pytest.fixture
def client(
    repo: InMemoryMemoryRepository, keys: InMemoryApiKeyStore, kv: InMemoryKVStore
) -> TestClient:
    app.dependency_overrides[get_repository] = lambda: repo
    app.dependency_overrides[get_embedder] = lambda: HashEmbedder()
    app.dependency_overrides[get_api_key_store] = lambda: keys
    app.dependency_overrides[get_kv_store] = lambda: kv
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
```

Add:

```python
def test_remember_writes_explicit_kv_triples(
    client: TestClient, raw_key: str, org_id: uuid.UUID, kv: InMemoryKVStore
) -> None:
    created = client.post(
        "/memories",
        headers=_auth(raw_key),
        json={
            "session_id": "s1",
            "memory_type": "semantic",
            "content": "zzz-unrelated-content-for-hash",
            "kv_triples": [{"fact_type": "preference", "entity": "typescript"}],
        },
    )
    assert created.status_code == 201
    fact = kv.get(org_id, "preference", "typescript")
    assert fact is not None
    assert str(fact.memory_id) == created.json()["id"]


def test_remember_still_201_when_kv_put_raises(
    client: TestClient, raw_key: str, monkeypatch
) -> None:
    from memory_api.services import kv_fanout

    def boom(*args, **kwargs):
        raise RuntimeError("should be caught inside persist_kv_facts")

    # Override store.put via a wrapper store injected in fixture instead:
    ...
```

Prefer a dedicated failing-store fixture rather than patching after persist:

```python
def test_remember_still_201_when_kv_put_raises(
    repo, keys, raw_key
) -> None:
    class BoomStore(InMemoryKVStore):
        def put(self, *args, **kwargs) -> None:
            raise RuntimeError("db down")

    app.dependency_overrides[get_repository] = lambda: repo
    app.dependency_overrides[get_embedder] = lambda: HashEmbedder()
    app.dependency_overrides[get_api_key_store] = lambda: keys
    app.dependency_overrides[get_kv_store] = lambda: BoomStore()
    with TestClient(app) as client:
        created = client.post(
            "/memories",
            headers=_auth(raw_key),
            json={"session_id": "s1", "content": "We prefer pytest over unittest."},
        )
        assert created.status_code == 201
    app.dependency_overrides.clear()
```

LLM extractor test: completion JSON includes `kv_triples`; assert `candidates[0].kv_triples[0]["entity"] == "pytest"`. Update `_LLM_SYSTEM` to mention optional `kv_triples`.

Worker: after `persist_candidate`, call `persist_kv_facts`. Add optional `kv: KVStore | None = None` to `run_once` / `_process`. In `worker.tick`, `kv=PostgresKVStore(session)` when `settings.enable_kv` else `NoOpKVStore()`.

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_memories_api.py::test_remember_writes_explicit_kv_triples tests/test_extraction.py -v`

Expected: FAIL (`get_kv_store` missing and/or `kv_triples` rejected by schema)

- [ ] **Step 3: Write minimal implementation**

`MemoryCreate`:

```python
kv_triples: list[dict[str, Any]] = Field(default_factory=list)
```

`deps.py`:

```python
def get_kv_store(db: Session = Depends(get_db)) -> KVStore:
    if not settings.enable_kv:
        return NoOpKVStore()
    from memory_api.stores.kv import PostgresKVStore

    return PostgresKVStore(db)
```

`create_memory`: map `body.kv_triples` onto `Candidate`; after `persist_candidate`, `persist_kv_facts(kv=kv, memory=memory, candidate=candidate, session=getattr(repo, "_session", None))`. Inject `kv: KVStore = Depends(get_kv_store)`.

`PostgresMemoryRepository` has `_session`; `InMemoryMemoryRepository` does not — pass `session=None` for tests.

`LlmExtractor`: for each memory item, parse `kv_triples` list of dicts with `fact_type`/`entity`/`value`.

`_process`: call `persist_kv_facts` for every candidate (inserted or not).

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_memories_api.py tests/test_extraction.py tests/test_worker.py tests/test_kv_fanout.py -v`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add apps/memory-api/src/memory_api/schemas/memory.py apps/memory-api/src/memory_api/db/deps.py apps/memory-api/src/memory_api/routers/memories.py apps/memory-api/tests/test_memories_api.py apps/memory-api/src/memory_api/services/extraction.py apps/memory-api/tests/test_extraction.py apps/memory-api/src/memory_api/services/worker.py apps/memory-api/src/memory_api/worker.py
git commit -m "Write KV facts from remember, extraction, and the worker."
```

---

### Task 7: Derive search candidates (LLM then rules)

**Files:**
- Create: `apps/memory-api/src/memory_api/services/kv_candidates.py`
- Create: `apps/memory-api/tests/test_kv_candidates.py`

**Interfaces:**
- Consumes: org OpenRouter `api_key` + `model` (optional), `httpx.Client`
- Produces: `derive_kv_candidates(query: str, *, api_key: str | None = None, model: str | None = None, http: httpx.Client | None = None) -> list[tuple[str, str]]`

LLM JSON: `{"keys":[{"fact_type":string,"entity":string}, ...]}`. Cap 12 after normalize/dedupe. On any error, log and use rules. No key → rules only.

Rules: tokens `[a-z0-9]{3,}`; for each of `preference,city,decision,language` emit `(type, token)`; plus phrase `prefer X` → `("preference", x)` etc.

- [ ] **Step 1: Write the failing test**

```python
import httpx

from memory_api.services.kv_candidates import derive_kv_candidates


def test_rules_prefer_phrase_without_api_key() -> None:
    keys = derive_kv_candidates("What language do they prefer typescript")
    assert ("preference", "typescript") in keys


def test_llm_parses_keys_from_completion() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "content": '{"keys":[{"fact_type":"city","entity":"Lisbon"}]}'
                        }
                    }
                ]
            },
        )

    http = httpx.Client(transport=httpx.MockTransport(handler))
    keys = derive_kv_candidates("where do they live", api_key="sk-or-test", http=http)
    assert keys == [("city", "lisbon")]


def test_llm_error_falls_back_to_rules() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, json={"error": "nope"})

    http = httpx.Client(transport=httpx.MockTransport(handler))
    keys = derive_kv_candidates(
        "prefer typescript",
        api_key="sk-or-test",
        http=http,
    )
    assert ("preference", "typescript") in keys
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_kv_candidates.py -v`

Expected: FAIL (import)

- [ ] **Step 3: Write minimal implementation**

Mirror `LlmExtractor` HTTP call (same headers, `settings.llm_base_url`, `temperature=0`, `response_format=json_object`). System prompt: extract lookup keys only, return `{"keys":[...]}`. Catch `Exception`, log, fall back to `_rules_candidates(query)`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_kv_candidates.py -v`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add apps/memory-api/src/memory_api/services/kv_candidates.py apps/memory-api/tests/test_kv_candidates.py
git commit -m "Derive KV search keys with LLM and rules fallback."
```

---

### Task 8: Union search and explain

**Files:**
- Modify: `apps/memory-api/src/memory_api/routers/memories.py`
- Modify: `apps/memory-api/tests/test_memories_api.py`
- Modify: `apps/memory-api/src/memory_api/db/deps.py` (optional `get_org_openrouter_key`)

**Interfaces:**
- Consumes: `derive_kv_candidates`, `kv.search_keys`, `repo.get`, existing `retrieval_score`
- Produces: unioned hits; `relevance = max(vector_similarity, kv_match or 0)`; explain `sources` / `kv_match` per spec

When `enable_kv` is false, keep Phase 0 search (no `search_keys`). In-memory API tests have no org OpenRouter key → rules path.

Search `search_keys` errors: log, treat as no KV hits.

- [ ] **Step 1: Write the failing test**

```python
def test_search_unions_kv_hit_when_vector_is_weak(
    client: TestClient, raw_key: str
) -> None:
    decoy = client.post(
        "/memories",
        headers=_auth(raw_key),
        json={
            "session_id": "s1",
            "content": "What language do they prefer typescript",
        },
    )
    target = client.post(
        "/memories",
        headers=_auth(raw_key),
        json={
            "session_id": "s1",
            "content": "zzz-kv-only-payload-not-the-query",
            "kv_triples": [{"fact_type": "preference", "entity": "typescript"}],
        },
    )
    assert decoy.status_code == 201
    assert target.status_code == 201
    search = client.get(
        "/memories/search",
        headers=_auth(raw_key),
        params={
            "q": "What language do they prefer typescript",
            "session_id": "s1",
            "explain": True,
            "limit": 10,
        },
    )
    assert search.status_code == 200
    hits = search.json()["memories"]
    ids = [row["id"] for row in hits]
    assert target.json()["id"] in ids
    kv_hit = next(row for row in hits if row["id"] == target.json()["id"])
    assert kv_hit["score_details"]["kv_match"] == 1.0
    assert "kv" in kv_hit["score_details"]["sources"]


def test_search_explain_vector_only_still_null_kv(
    client: TestClient, raw_key: str
) -> None:
    client.post(
        "/memories",
        headers=_auth(raw_key),
        json={"session_id": "s1", "content": "explain skeleton probe"},
    )
    search = client.get(
        "/memories/search",
        headers=_auth(raw_key),
        params={"q": "explain skeleton probe", "session_id": "s1", "explain": True},
    )
    details = search.json()["memories"][0]["score_details"]
    assert details["kv_match"] is None
    assert details["sources"] == ["vector"]
```

Existing `test_search_explain_returns_full_score_details_keys` must still pass (probe content writes no triples).

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_memories_api.py::test_search_unions_kv_hit_when_vector_is_weak -v`

Expected: FAIL (target id not in hits, or `kv_match` null)

- [ ] **Step 3: Write minimal implementation**

In `search`:

1. Run vector `repo.search` as today; keep a dict `memory_id -> (memory, similarity)`.
2. If `settings.enable_kv`: `keys = derive_kv_candidates(q, api_key=..., model=...)` (load org key from DB when using Postgres; tests pass `api_key=None`). Wrap `search_keys` in try/except.
3. For each fact, `repo.get`; skip missing.
4. Merge: set `kv_match=1.0` for those ids; vector-only keep similarity; KV-only similarity `0.0`.
5. Score with `retrieval_score(similarity=max(sim, kv_match or 0), ...)`.
6. Explain per spec.

Load OpenRouter key like `worker.tick`: `session.get(Org, principal.org_id)` then `decrypt_secret` if ciphertext present. `InMemory` tests: `get_repository` is not Postgres — do not call `session.get`. Helper:

```python
def _org_llm_key(repo: MemoryRepository, org_id: uuid.UUID) -> tuple[str | None, str | None]:
    session = getattr(repo, "_session", None)
    if session is None:
        return None, None
    org = session.get(Org, org_id)
    if org is None or not org.openrouter_key_ciphertext:
        return None, None
    return decrypt_secret(org.openrouter_key_ciphertext), org.openrouter_model
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_memories_api.py -v`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add apps/memory-api/src/memory_api/routers/memories.py apps/memory-api/tests/test_memories_api.py apps/memory-api/src/memory_api/db/deps.py
git commit -m "Union KV exact matches into memory search scoring."
```

---

### Task 9: Postgres round-trip, truncate, docs, full suite

**Files:**
- Modify: `apps/memory-api/tests/test_postgres_api.py` (`TRUNCATE` include `kv_facts`; HTTP test for KV union if cheap)
- Modify: `spec/v2_extension_plan.md` (tick Phase 1 boxes; for allow-list, mark done as “open set, hard allow-list deferred” in the checkbox text)
- Modify: `spec/03-architecture.md` hybrid section

**Interfaces:**
- Consumes: all previous tasks
- Produces: green full Memory API suite; docs match behaviour

- [ ] **Step 1: Write the failing test**

Update truncate:

```python
connection.execute(text("TRUNCATE kv_facts, memories, api_keys, users, event_buffer, orgs CASCADE"))
```

Add `test_postgres_kv_union_search` posting explicit `kv_triples` and searching with `prefer typescript` / explain. Fails until migration applied and router uses PostgresKVStore (already wired).

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_postgres_api.py::test_postgres_kv_union_search -v`

Expected: FAIL or skip if Postgres down; if up, fail until truncate/search works.

- [ ] **Step 3: Write minimal implementation**

Fix truncate and any leftover wiring. Architecture note:

```
## Hybrid stores (v2 Phase 1)

KV is on by default (`MEMORIA_ENABLE_KV=true`). `kv_facts` is a secondary index.
Search unions exact KV hits with vector hits. Graph remains a no-op.
See `spec/v2-phase1-kv-store.md`.
```

Tick Phase 1 items in `v2_extension_plan.md`. Change the allow-list bullet to: `- [x] Guardrail: open fact_type set in Phase 1 (hard allow-list deferred)`.

- [ ] **Step 4: Run the full Memory API suite**

Run: `uv run pytest -v`

Expected: PASS (Postgres tests skipped if DB down)

- [ ] **Step 5: Commit**

```bash
git add apps/memory-api/tests/test_postgres_api.py spec/v2_extension_plan.md spec/03-architecture.md spec/v2-phase1-kv-store.md spec/v2-phase1-implementation.md
git commit -m "Document Phase 1 KV store and cover Postgres union search."
```

Include the design spec in this commit if it is still untracked.

---

## Self-review

1. **Spec coverage:** Table, `PostgresKVStore`, extraction `kv_triples`, write fan-out + cap, search union + LLM candidates, fusion `max`, tests, remember/search error logging, default-on flag, open fact types — each has a task. Hard allow-list explicitly deferred in Task 9. PATCH/MCP out of scope.
2. **Placeholders:** None intended; Task 6 worker wiring is specified (`persist_kv_facts` in `_process`, `PostgresKVStore(session)` in `tick`).
3. **Types:** `KVFact` dataclass vs ORM `KvFact`; protocol methods unchanged; `Candidate.kv_triples` is `list[dict]`.
