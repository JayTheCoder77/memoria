import uuid

import pytest

from memory_api.services.api_keys import (
    AuthError,
    InMemoryApiKeyStore,
    authenticate_bearer,
    generate_api_key,
    hash_api_key,
    key_last4,
)


def test_generate_api_key_uses_mem_prefix() -> None:
    raw = generate_api_key()
    assert raw.startswith("mem_")
    assert len(raw) > 12


def test_hash_api_key_is_deterministic_and_not_plaintext() -> None:
    raw = generate_api_key()
    first = hash_api_key(raw)
    second = hash_api_key(raw)
    assert first == second
    assert first != raw
    assert "mem_" not in first


def test_key_last4_is_the_raw_suffix() -> None:
    raw = "mem_abcdefghijkl"
    assert key_last4(raw) == "ijkl"


def test_authenticate_bearer_resolves_org_from_active_key() -> None:
    store = InMemoryApiKeyStore()
    org_id = uuid.uuid4()
    raw = generate_api_key()
    store.add(org_id=org_id, raw_key=raw)

    principal = authenticate_bearer(f"Bearer {raw}", store)

    assert principal.org_id == org_id
    assert store.last_used_at(principal.api_key_id) is not None


def test_authenticate_bearer_rejects_missing_invalid_and_revoked() -> None:
    store = InMemoryApiKeyStore()
    org_id = uuid.uuid4()
    raw = generate_api_key()
    record = store.add(org_id=org_id, raw_key=raw)
    store.revoke(record.id)

    with pytest.raises(AuthError):
        authenticate_bearer(None, store)
    with pytest.raises(AuthError):
        authenticate_bearer("Bearer not-a-real-key", store)
    with pytest.raises(AuthError):
        authenticate_bearer(f"Bearer {raw}", store)
    with pytest.raises(AuthError):
        authenticate_bearer("Basic nope", store)
