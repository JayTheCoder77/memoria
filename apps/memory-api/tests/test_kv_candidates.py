import inspect

from memory_api.services.kv_candidates import derive_kv_candidates


def test_rules_prefer_phrase_without_api_key() -> None:
    keys = derive_kv_candidates("What language do they prefer typescript")
    assert ("preference", "typescript") in keys


def test_language_preference_query_rejects_api_key() -> None:
    keys = derive_kv_candidates("what language does the user prefer")
    assert any(fact_type in {"language", "preference"} for fact_type, _entity in keys)
    assert list(inspect.signature(derive_kv_candidates).parameters) == ["query"]
