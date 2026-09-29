from __future__ import annotations

import uuid

from memory_api.db.models import MemoryType
from memory_api.db.repository import InMemoryMemoryRepository
from memory_api.services.profile import ProfileFact, build_profile
from memory_api.stores.kv import InMemoryKVStore


def test_profile_static_kv_and_dynamic_omits_redundant_memory() -> None:
    org_id = uuid.uuid4()
    user_id = "ava"
    kv = InMemoryKVStore()
    kv.put(
        org_id,
        uuid.uuid4(),
        "city",
        "ava",
        value="lisbon",
        importance=0.9,
        user_id=user_id,
    )

    repo = InMemoryMemoryRepository()
    repo.insert(
        org_id=org_id,
        session_id="s1",
        memory_type=MemoryType.semantic,
        content="Ava moved to Lisbon",
        embedding=[0.0],
        importance=0.8,
        source_metadata={},
        user_id=user_id,
    )
    repo.insert(
        org_id=org_id,
        session_id="s1",
        memory_type=MemoryType.semantic,
        content="Prefers morning standups",
        embedding=[0.0],
        importance=0.7,
        source_metadata={},
        user_id=user_id,
    )

    profile = build_profile(
        org_id=org_id,
        user_id=user_id,
        kv=kv,
        repo=repo,
    )

    assert profile.static == [
        ProfileFact(fact_type="city", entity="ava", value="lisbon"),
    ]
    assert profile.dynamic == ["Prefers morning standups"]
    assert "lisbon" in profile.text.lower()
    assert "Prefers morning standups" in profile.text
