# Phase 0 Foundations Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add hybrid-memory store protocols, default-off KV/Graph flags, configurable fusion weights, a pgvector `VectorStore` adapter, and an opt-in search `explain` skeleton without changing default recall ranking.

**Architecture:** `MemoryRepository` stays canonical CRUD + cosine search. New `VectorStore` / `KVStore` / `GraphStore` protocols live under `memory_api.stores`. `PostgresVectorStore` delegates to the repository. KV/Graph are no-ops. Search still scores in the router; `explain=true` attaches a full `score_details` object with null KV/Graph fields.

**Tech Stack:** Python 3.12, FastAPI, Pydantic Settings, pytest, ruff (existing Memory API).

## Global Constraints

- Do not add Alembic migrations or new tables.
- `MEMORIA_ENABLE_KV` and `MEMORIA_ENABLE_GRAPH` default to `false`.
- Fusion defaults remain relevance `0.6`, importance `0.2`, recency `0.2`, half-life `14.0` days.
- MCP tools are unchanged in this phase.
- Existing `GET /memories/search` tests must pass without sending `explain`.
- Work on a feature branch off current `main`; do not commit secrets.
- Every production change is preceded by a failing test (TDD).

## File map

- Create: `apps/memory-api/src/memory_api/stores/__init__.py`
- Create: `apps/memory-api/src/memory_api/stores/types.py`
- Create: `apps/memory-api/src/memory_api/stores/protocols.py`
- Create: `apps/memory-api/src/memory_api/stores/vector.py`
- Create: `apps/memory-api/src/memory_api/stores/noop.py`
- Create: `apps/memory-api/tests/test_hybrid_config.py`
- Create: `apps/memory-api/tests/test_stores.py`
- Modify: `apps/memory-api/src/memory_api/config.py`
- Modify: `apps/memory-api/src/memory_api/services/scoring.py`
- Modify: `apps/memory-api/tests/test_scoring.py`
- Modify: `apps/memory-api/src/memory_api/schemas/memory.py`
- Modify: `apps/memory-api/src/memory_api/routers/memories.py`
- Modify: `apps/memory-api/tests/test_memories_api.py`
- Modify: `apps/memory-api/.env.example`
- Modify: `spec/v2_extension_plan.md`
- Modify: `spec/03-architecture.md`

---

### Task 1: Hybrid feature flags and fusion weight settings

**Files:**
- Modify: `apps/memory-api/src/memory_api/config.py`
- Create: `apps/memory-api/tests/test_hybrid_config.py`
- Modify: `apps/memory-api/.env.example`

**Interfaces:**
- Consumes: existing `Settings` (`env_prefix="MEMORIA_"`)
- Produces: `Settings.enable_kv: bool`, `enable_graph: bool`, `fusion_weight_relevance: float`, `fusion_weight_importance: float`, `fusion_weight_recency: float`, `recency_halflife_days: float`

- [ ] **Step 1: Write the failing test**

Create `apps/memory-api/tests/test_hybrid_config.py`:

```python
from memory_api.config import Settings


def test_hybrid_flags_default_off() -> None:
    s = Settings()
    assert s.enable_kv is False
    assert s.enable_graph is False


def test_fusion_weights_match_current_scoring_defaults() -> None:
    s = Settings()
    assert s.fusion_weight_relevance == 0.6
    assert s.fusion_weight_importance == 0.2
    assert s.fusion_weight_recency == 0.2
    assert s.recency_halflife_days == 14.0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd apps/memory-api && uv run pytest tests/test_hybrid_config.py -v`

Expected: FAIL with `AttributeError: enable_kv` (or similar missing attribute).

- [ ] **Step 3: Write minimal implementation**

Add to `Settings` in `apps/memory-api/src/memory_api/config.py` (after `consolidate_threshold`):

```python
    enable_kv: bool = False
    enable_graph: bool = False
    fusion_weight_relevance: float = 0.6
    fusion_weight_importance: float = 0.2
    fusion_weight_recency: float = 0.2
    recency_halflife_days: float = 14.0
```

Append to `apps/memory-api/.env.example`:

```
# Hybrid stores (v2). Keep off until KV/Graph implementations exist.
MEMORIA_ENABLE_KV=false
MEMORIA_ENABLE_GRAPH=false
MEMORIA_FUSION_WEIGHT_RELEVANCE=0.6
MEMORIA_FUSION_WEIGHT_IMPORTANCE=0.2
MEMORIA_FUSION_WEIGHT_RECENCY=0.2
MEMORIA_RECENCY_HALFLIFE_DAYS=14
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd apps/memory-api && uv run pytest tests/test_hybrid_config.py -v`

Expected: PASS (2 tests).

- [ ] **Step 5: Commit**

```bash
git add apps/memory-api/src/memory_api/config.py apps/memory-api/tests/test_hybrid_config.py apps/memory-api/.env.example
git commit -m "Add hybrid store flags and configurable fusion weights."
```

---

### Task 2: Scoring functions honor configured weights

**Files:**
- Modify: `apps/memory-api/src/memory_api/services/scoring.py`
- Modify: `apps/memory-api/tests/test_scoring.py`

**Interfaces:**
- Consumes: Task 1 defaults (same numbers as current module constants)
- Produces: `recency_weight(..., half_life_days=...)` already exists; `retrieval_score(..., semantic_weight=..., importance_weight=..., recency_weight_value=...)` with defaults equal to current constants

- [ ] **Step 1: Write the failing test**

Add to `apps/memory-api/tests/test_scoring.py`:

```python
def test_retrieval_score_uses_override_weights() -> None:
    similarity_led = retrieval_score(
        similarity=0.9,
        importance=0.1,
        recency=0.1,
        semantic_weight=1.0,
        importance_weight=0.0,
        recency_weight_value=0.0,
    )
    importance_led = retrieval_score(
        similarity=0.9,
        importance=0.1,
        recency=0.1,
        semantic_weight=0.0,
        importance_weight=1.0,
        recency_weight_value=0.0,
    )
    assert similarity_led == 0.9
    assert importance_led == 0.1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd apps/memory-api && uv run pytest tests/test_scoring.py::test_retrieval_score_uses_override_weights -v`

Expected: FAIL with `TypeError: retrieval_score() got an unexpected keyword argument 'semantic_weight'`.

- [ ] **Step 3: Write minimal implementation**

Replace `retrieval_score` in `apps/memory-api/src/memory_api/services/scoring.py` with:

```python
def retrieval_score(
    *,
    similarity: float,
    importance: float,
    recency: float,
    semantic_weight: float = SEMANTIC_WEIGHT,
    importance_weight: float = IMPORTANCE_WEIGHT,
    recency_weight_value: float = RECENCY_WEIGHT,
) -> float:
    return (
        semantic_weight * similarity
        + importance_weight * importance
        + recency_weight_value * recency
    )
```

Do not rename the existing `recency_weight` function. The extra scoring kwarg is `recency_weight_value` to avoid a clash.

Existing tests that call `retrieval_score(similarity=..., importance=..., recency=...)` must still pass unchanged.

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd apps/memory-api && uv run pytest tests/test_scoring.py -v`

Expected: PASS (all tests in file).

- [ ] **Step 5: Commit**

```bash
git add apps/memory-api/src/memory_api/services/scoring.py apps/memory-api/tests/test_scoring.py
git commit -m "Allow retrieval_score weights to be overridden."
```

---

### Task 3: Store types, protocols, and no-op KV/Graph

**Files:**
- Create: `apps/memory-api/src/memory_api/stores/types.py`
- Create: `apps/memory-api/src/memory_api/stores/protocols.py`
- Create: `apps/memory-api/src/memory_api/stores/noop.py`
- Create: `apps/memory-api/src/memory_api/stores/__init__.py`
- Create: `apps/memory-api/tests/test_stores.py`

**Interfaces:**
- Consumes: `memory_api.db.models.Memory`
- Produces: `ScoredMemory`, `KVFact`, `GraphEdge`; `VectorStore`, `KVStore`, `GraphStore` protocols; `NoOpKVStore`, `NoOpGraphStore`

- [ ] **Step 1: Write the failing test**

Create `apps/memory-api/tests/test_stores.py`:

```python
from __future__ import annotations

import uuid

from memory_api.stores.noop import NoOpGraphStore, NoOpKVStore


def test_noop_kv_returns_empty() -> None:
    store = NoOpKVStore()
    org_id = uuid.uuid4()
    store.put(
        org_id,
        uuid.uuid4(),
        "preference",
        "typescript",
        value="ts",
        importance=0.8,
    )
    assert store.get(org_id, "preference", "typescript") is None
    assert store.search_keys(org_id, [("preference", "typescript")]) == []
    assert store.by_org(org_id) == []


def test_noop_graph_returns_empty_neighbors() -> None:
    store = NoOpGraphStore()
    org_id = uuid.uuid4()
    node_id = store.upsert_node(org_id, "ava", "person")
    edge_id = store.add_edge(
        org_id, "ava", "lives_in", "lisbon", memory_id=uuid.uuid4()
    )
    assert isinstance(node_id, uuid.UUID)
    assert isinstance(edge_id, uuid.UUID)
    assert store.neighbors(org_id, "ava") == []
    assert store.memories_for_subgraph(org_id, ["ava"]) == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd apps/memory-api && uv run pytest tests/test_stores.py -v`

Expected: FAIL with `ModuleNotFoundError: No module named 'memory_api.stores'`.

- [ ] **Step 3: Write minimal implementation**

`apps/memory-api/src/memory_api/stores/types.py`:

```python
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime

from memory_api.db.models import Memory


@dataclass(frozen=True)
class ScoredMemory:
    memory: Memory
    similarity: float


@dataclass(frozen=True)
class KVFact:
    org_id: uuid.UUID
    memory_id: uuid.UUID
    fact_type: str
    entity: str
    value: str | None
    importance: float
    user_key: str | None = None
    id: uuid.UUID | None = None


@dataclass(frozen=True)
class GraphEdge:
    org_id: uuid.UUID
    subject_key: str
    relation: str
    object_key: str
    memory_id: uuid.UUID | None = None
    valid: bool = True
    valid_from: datetime | None = None
    valid_to: datetime | None = None
    confidence: float = 1.0
    properties: dict = field(default_factory=dict)
    id: uuid.UUID | None = None
```

`apps/memory-api/src/memory_api/stores/protocols.py`:

```python
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Protocol

from memory_api.stores.types import GraphEdge, KVFact, ScoredMemory


class VectorStore(Protocol):
    def upsert(self, memory_id: uuid.UUID, embedding: list[float], metadata: dict) -> None: ...

    def search(
        self,
        org_id: uuid.UUID,
        query_embedding: list[float],
        *,
        session_id: str | None,
        limit: int,
    ) -> list[ScoredMemory]: ...


class KVStore(Protocol):
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
    ) -> None: ...

    def get(self, org_id: uuid.UUID, fact_type: str, entity: str) -> KVFact | None: ...

    def search_keys(
        self, org_id: uuid.UUID, candidates: list[tuple[str, str]]
    ) -> list[KVFact]: ...

    def by_org(self, org_id: uuid.UUID, *, user_key: str | None = None) -> list[KVFact]: ...


class GraphStore(Protocol):
    def upsert_node(
        self,
        org_id: uuid.UUID,
        entity_key: str,
        label: str,
        properties: dict | None = None,
    ) -> uuid.UUID: ...

    def add_edge(
        self,
        org_id: uuid.UUID,
        subject_key: str,
        relation: str,
        object_key: str,
        *,
        memory_id: uuid.UUID | None,
        confidence: float = 1.0,
    ) -> uuid.UUID: ...

    def neighbors(
        self,
        org_id: uuid.UUID,
        entity_key: str,
        *,
        hops: int = 1,
        valid_only: bool = True,
        as_of: datetime | None = None,
    ) -> list[GraphEdge]: ...

    def memories_for_subgraph(
        self, org_id: uuid.UUID, entity_keys: list[str], *, hops: int = 1
    ) -> list[uuid.UUID]: ...
```

`apps/memory-api/src/memory_api/stores/noop.py`:

```python
from __future__ import annotations

import uuid
from datetime import datetime

from memory_api.stores.types import GraphEdge, KVFact


class NoOpKVStore:
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
        return None

    def get(self, org_id: uuid.UUID, fact_type: str, entity: str) -> KVFact | None:
        return None

    def search_keys(
        self, org_id: uuid.UUID, candidates: list[tuple[str, str]]
    ) -> list[KVFact]:
        return []

    def by_org(self, org_id: uuid.UUID, *, user_key: str | None = None) -> list[KVFact]:
        return []


class NoOpGraphStore:
    def upsert_node(
        self,
        org_id: uuid.UUID,
        entity_key: str,
        label: str,
        properties: dict | None = None,
    ) -> uuid.UUID:
        return uuid.uuid4()

    def add_edge(
        self,
        org_id: uuid.UUID,
        subject_key: str,
        relation: str,
        object_key: str,
        *,
        memory_id: uuid.UUID | None,
        confidence: float = 1.0,
    ) -> uuid.UUID:
        return uuid.uuid4()

    def neighbors(
        self,
        org_id: uuid.UUID,
        entity_key: str,
        *,
        hops: int = 1,
        valid_only: bool = True,
        as_of: datetime | None = None,
    ) -> list[GraphEdge]:
        return []

    def memories_for_subgraph(
        self, org_id: uuid.UUID, entity_keys: list[str], *, hops: int = 1
    ) -> list[uuid.UUID]:
        return []
```

`apps/memory-api/src/memory_api/stores/__init__.py`:

```python
from memory_api.stores.noop import NoOpGraphStore, NoOpKVStore
from memory_api.stores.protocols import GraphStore, KVStore, VectorStore
from memory_api.stores.types import GraphEdge, KVFact, ScoredMemory

__all__ = [
    "GraphEdge",
    "GraphStore",
    "KVFact",
    "KVStore",
    "NoOpGraphStore",
    "NoOpKVStore",
    "ScoredMemory",
    "VectorStore",
]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd apps/memory-api && uv run pytest tests/test_stores.py -v && uv run ruff check src/memory_api/stores tests/test_stores.py`

Expected: PASS, ruff clean.

- [ ] **Step 5: Commit**

```bash
git add apps/memory-api/src/memory_api/stores apps/memory-api/tests/test_stores.py
git commit -m "Add hybrid store protocols and no-op KV/Graph implementations."
```

---

### Task 4: PostgresVectorStore adapter

**Files:**
- Create: `apps/memory-api/src/memory_api/stores/vector.py`
- Modify: `apps/memory-api/src/memory_api/stores/__init__.py`
- Modify: `apps/memory-api/tests/test_stores.py`

**Interfaces:**
- Consumes: `MemoryRepository.search`, `ScoredMemory`
- Produces: `PostgresVectorStore.upsert` (no-op), `PostgresVectorStore.search` → `list[ScoredMemory]`

- [ ] **Step 1: Write the failing test**

Add to `apps/memory-api/tests/test_stores.py` (imports: `MemoryType`, `InMemoryMemoryRepository`, `PostgresVectorStore`):

```python
from memory_api.db.models import MemoryType
from memory_api.db.repository import InMemoryMemoryRepository
from memory_api.stores.vector import PostgresVectorStore


def test_vector_store_search_delegates_to_repository() -> None:
    repo = InMemoryMemoryRepository()
    org_id = uuid.uuid4()
    memory = repo.insert(
        org_id=org_id,
        session_id="s1",
        memory_type=MemoryType.semantic,
        content="preferred language is typescript",
        embedding=[1.0, 0.0, 0.0],
        importance=0.7,
        source_metadata={},
    )
    store = PostgresVectorStore(repo)
    store.upsert(memory.id, memory.embedding, {})
    hits = store.search(org_id, [1.0, 0.0, 0.0], session_id="s1", limit=5)
    assert len(hits) == 1
    assert hits[0].memory.id == memory.id
    assert hits[0].similarity == 1.0
```

Use an embedding length that `InMemoryMemoryRepository` will accept as-is (the hash embedder dimension is not required here because insert is called directly). If `Memory.embedding` / pgvector dimension asserts at construction, pad the vector to `memory_api.services.embedding.EMBEDDING_DIM` with the first component `1.0` and the rest `0.0`.

If the test errors on vector length, switch both `embedding` and `query_embedding` to:

```python
from memory_api.services.embedding import EMBEDDING_DIM

embedding = [1.0] + [0.0] * (EMBEDDING_DIM - 1)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd apps/memory-api && uv run pytest tests/test_stores.py::test_vector_store_search_delegates_to_repository -v`

Expected: FAIL with `ModuleNotFoundError: No module named 'memory_api.stores.vector'` (or `ImportError` for `PostgresVectorStore`).

- [ ] **Step 3: Write minimal implementation**

`apps/memory-api/src/memory_api/stores/vector.py`:

```python
from __future__ import annotations

import uuid

from memory_api.db.repository import MemoryRepository
from memory_api.stores.types import ScoredMemory


class PostgresVectorStore:
    def __init__(self, repo: MemoryRepository) -> None:
        self._repo = repo

    def upsert(self, memory_id: uuid.UUID, embedding: list[float], metadata: dict) -> None:
        return None

    def search(
        self,
        org_id: uuid.UUID,
        query_embedding: list[float],
        *,
        session_id: str | None,
        limit: int,
    ) -> list[ScoredMemory]:
        rows = self._repo.search(
            org_id=org_id,
            query_embedding=query_embedding,
            session_id=session_id,
            limit=limit,
        )
        return [ScoredMemory(memory=memory, similarity=similarity) for memory, similarity in rows]
```

Export `PostgresVectorStore` from `stores/__init__.py`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd apps/memory-api && uv run pytest tests/test_stores.py -v`

Expected: PASS (all store tests).

- [ ] **Step 5: Commit**

```bash
git add apps/memory-api/src/memory_api/stores/vector.py apps/memory-api/src/memory_api/stores/__init__.py apps/memory-api/tests/test_stores.py
git commit -m "Wrap pgvector search behind a VectorStore adapter."
```

---

### Task 5: Explain skeleton on search responses

**Files:**
- Modify: `apps/memory-api/src/memory_api/schemas/memory.py`
- Modify: `apps/memory-api/src/memory_api/routers/memories.py`
- Modify: `apps/memory-api/tests/test_memories_api.py`

**Interfaces:**
- Consumes: `retrieval_score` kwargs from Task 2; `settings` fusion fields from Task 1
- Produces: `ScoreDetails` on `MemoryOut.score_details`; `GET /memories/search?explain=true`

- [ ] **Step 1: Write the failing test**

Add to `apps/memory-api/tests/test_memories_api.py`:

```python
def test_search_omits_score_details_by_default(
    client: TestClient, raw_key: str
) -> None:
    created = client.post(
        "/memories",
        headers=_auth(raw_key),
        json={
            "session_id": "s1",
            "memory_type": "semantic",
            "content": "explain skeleton probe",
            "importance": 0.7,
        },
    )
    assert created.status_code == 201
    search = client.get(
        "/memories/search",
        headers=_auth(raw_key),
        params={"q": "explain skeleton probe", "session_id": "s1"},
    )
    assert search.status_code == 200
    hit = search.json()["memories"][0]
    assert hit.get("score_details") is None


def test_search_explain_returns_full_score_details_keys(
    client: TestClient, raw_key: str
) -> None:
    created = client.post(
        "/memories",
        headers=_auth(raw_key),
        json={
            "session_id": "s1",
            "memory_type": "semantic",
            "content": "explain skeleton probe",
            "importance": 0.7,
        },
    )
    assert created.status_code == 201
    search = client.get(
        "/memories/search",
        headers=_auth(raw_key),
        params={"q": "explain skeleton probe", "session_id": "s1", "explain": True},
    )
    assert search.status_code == 200
    details = search.json()["memories"][0]["score_details"]
    assert details["sources"] == ["vector"]
    assert details["kv_match"] is None
    assert details["graph_hops"] is None
    assert details["vector_similarity"] == details["relevance"]
    assert details["importance"] == 0.7
    assert set(details["weights"]) == {"relevance", "importance", "recency"}
    assert details["weights"]["relevance"] == 0.6
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd apps/memory-api && uv run pytest tests/test_memories_api.py::test_search_explain_returns_full_score_details_keys tests/test_memories_api.py::test_search_omits_score_details_by_default -v`

Expected: FAIL — `explain` ignored and/or `score_details` missing.

- [ ] **Step 3: Write minimal implementation**

In `apps/memory-api/src/memory_api/schemas/memory.py` add:

```python
class ScoreDetails(BaseModel):
    relevance: float
    importance: float
    recency: float
    sources: list[str]
    vector_similarity: float
    kv_match: float | None = None
    graph_hops: int | None = None
    weights: dict[str, float]


class MemoryOut(BaseModel):
    # existing fields...
    score: float | None = None
    score_details: ScoreDetails | None = None
```

In `apps/memory-api/src/memory_api/routers/memories.py`, extend `_to_out` and `search`:

```python
from memory_api.schemas.memory import MemoryCreate, MemoryOut, MemorySearchResponse, MemoryUpdate, ScoreDetails
from memory_api.config import settings


def _to_out(
    memory: Memory,
    score: float | None = None,
    score_details: ScoreDetails | None = None,
) -> MemoryOut:
    payload = MemoryOut.model_validate(memory)
    payload.score = score
    payload.score_details = score_details
    return payload


@router.get("/memories/search", response_model=MemorySearchResponse)
def search(
    q: str,
    session_id: str | None = None,
    limit: int = Query(default=10, ge=1, le=100),
    token_budget: int = Query(default=2048, ge=1, le=32_000),
    explain: bool = False,
    principal: Principal = Depends(get_principal),
    repo: MemoryRepository = Depends(get_repository),
    embedder: Embedder = Depends(get_embedder),
) -> MemorySearchResponse:
    query_embedding = embed_text(q, embedder=embedder)
    rows = repo.search(
        org_id=principal.org_id,
        query_embedding=query_embedding,
        session_id=session_id,
        limit=max(limit * 5, 20),
    )
    ranked: list[tuple[Memory, float, float, float, float]] = []
    for memory, similarity in rows:
        recency = recency_weight(
            memory.created_at, half_life_days=settings.recency_halflife_days
        )
        score = retrieval_score(
            similarity=similarity,
            importance=memory.importance,
            recency=recency,
            semantic_weight=settings.fusion_weight_relevance,
            importance_weight=settings.fusion_weight_importance,
            recency_weight_value=settings.fusion_weight_recency,
        )
        ranked.append((memory, score, similarity, recency, memory.importance))
    ranked.sort(key=lambda item: item[1], reverse=True)
    ranked = ranked[:limit]

    def _hit(memory: Memory, score: float, similarity: float, recency: float, importance: float) -> MemoryOut:
        details = None
        if explain:
            details = ScoreDetails(
                relevance=similarity,
                importance=importance,
                recency=recency,
                sources=["vector"],
                vector_similarity=similarity,
                kv_match=None,
                graph_hops=None,
                weights={
                    "relevance": settings.fusion_weight_relevance,
                    "importance": settings.fusion_weight_importance,
                    "recency": settings.fusion_weight_recency,
                },
            )
        return _to_out(memory, score, details)

    memories = truncate_to_token_budget(
        [
            _hit(memory, score, similarity, recency, importance)
            for memory, score, similarity, recency, importance in ranked
        ],
        token_budget,
        text_of=lambda item: item.content,
    )
    return MemorySearchResponse(memories=memories)
```

Response model must not exclude `score_details` when null; FastAPI/Pydantic default is fine (`null` in JSON).

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd apps/memory-api && uv run pytest tests/test_memories_api.py tests/test_retrieval.py -v && uv run ruff check src tests`

Expected: PASS, ruff clean.

- [ ] **Step 5: Commit**

```bash
git add apps/memory-api/src/memory_api/schemas/memory.py apps/memory-api/src/memory_api/routers/memories.py apps/memory-api/tests/test_memories_api.py
git commit -m "Add opt-in search explain skeleton with full score_details keys."
```

---

### Task 6: Spec ticks, architecture note, full suite

**Files:**
- Modify: `spec/v2_extension_plan.md` (Phase 0 checklist)
- Modify: `spec/03-architecture.md`

**Interfaces:**
- Consumes: completed Tasks 1–5
- Produces: docs that match shipped behaviour

- [ ] **Step 1: Update Phase 0 checkboxes**

In `spec/v2_extension_plan.md` Phase 0, mark these items `[x]`:

- Define `VectorStore`, `KVStore`, `GraphStore` protocols / abstract classes
- Wrap existing pgvector logic behind `VectorStore`
- Add feature flags and config for fusion weights
- Add `explain` support skeleton on search responses
- Document hybrid mental model in `spec/`
- Ensure all existing tests still pass with flags off

Leave Phases 1–5 unchecked.

- [ ] **Step 2: Add architecture note**

After the components list in `spec/03-architecture.md`, add:

```markdown
## Hybrid stores (v2 Phase 0)

Search is still vector-only. `memory_api.stores` defines `VectorStore`, `KVStore`,
and `GraphStore`. KV and Graph are no-ops behind `MEMORIA_ENABLE_KV` /
`MEMORIA_ENABLE_GRAPH` (default false). `GET /memories/search?explain=true`
returns per-hit `score_details` with `sources: ["vector"]` and null KV/Graph
fields. See `spec/v2_extension_plan.md` and `spec/v2-phase0-foundations.md`.
```

- [ ] **Step 3: Run the full Memory API suite**

Run: `cd apps/memory-api && uv run pytest && uv run ruff check src tests`

Expected: all tests pass, ruff clean.

- [ ] **Step 4: Commit**

```bash
git add spec/v2_extension_plan.md spec/03-architecture.md spec/v2-phase0-foundations.md spec/v2-phase0-implementation.md
git commit -m "Document Phase 0 hybrid store foundations."
```

Include the Phase 0 design spec in this commit if it is still untracked.

---

## Self-review

1. **Spec coverage:** Flags, protocols, vector adapter, no-op KV/Graph, configurable weights, explain skeleton, docs, existing tests green — each has a task.
2. **Placeholders:** None. `recency_weight_value` is the explicit name for the weight kwarg.
3. **Types:** `ScoredMemory.similarity`, `ScoreDetails` field names, and `PostgresVectorStore.search` signatures match `spec/v2-phase0-foundations.md`.
