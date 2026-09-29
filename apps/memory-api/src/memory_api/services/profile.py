from __future__ import annotations

import uuid
from dataclasses import dataclass

from memory_api.db.repository import MemoryRepository
from memory_api.services.scoring import truncate_to_token_budget
from memory_api.services.scope import stored_scope_id
from memory_api.stores.protocols import KVStore

_DYNAMIC_IMPORTANCE_MIN = 0.6
_DYNAMIC_LIMIT = 5


@dataclass(frozen=True)
class ProfileFact:
    fact_type: str
    entity: str
    value: str | None


@dataclass(frozen=True)
class Profile:
    static: list[ProfileFact]
    dynamic: list[str]
    text: str


def _static_line(fact: ProfileFact) -> str:
    if fact.value is not None and fact.value != "":
        return f"{fact.fact_type}: {fact.entity} = {fact.value}"
    return f"{fact.fact_type}: {fact.entity}"


def _static_values(static: list[ProfileFact]) -> set[str]:
    values: set[str] = set()
    for fact in static:
        if fact.value is None:
            continue
        normalized = fact.value.strip().lower()
        if normalized:
            values.add(normalized)
    return values


def _memory_duplicates_static(content: str, static_values: set[str]) -> bool:
    lowered = content.lower()
    return any(value in lowered for value in static_values)


def build_profile(
    *,
    org_id: uuid.UUID,
    user_id: str,
    token_budget: int = 800,
    kv: KVStore,
    repo: MemoryRepository,
) -> Profile:
    scoped_user = stored_scope_id(user_id)
    kv_rows = sorted(
        kv.by_org(org_id, user_id=scoped_user),
        key=lambda row: row.importance,
        reverse=True,
    )
    static = [
        ProfileFact(fact_type=row.fact_type, entity=row.entity, value=row.value)
        for row in kv_rows
    ]
    static_values = _static_values(static)

    memories = repo.list(org_id=org_id, user_id=scoped_user)
    dynamic: list[str] = []
    for memory in memories:
        if memory.importance < _DYNAMIC_IMPORTANCE_MIN:
            continue
        if _memory_duplicates_static(memory.content, static_values):
            continue
        dynamic.append(memory.content)
        if len(dynamic) >= _DYNAMIC_LIMIT:
            break

    lines = [_static_line(fact) for fact in static] + dynamic
    kept = truncate_to_token_budget(lines, token_budget, text_of=lambda line: line)
    text = "\n".join(kept)

    return Profile(static=static, dynamic=dynamic, text=text)
