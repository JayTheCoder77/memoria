import inspect

from memory_api.services.graph_seeds import derive_graph_seeds


def test_rules_prefer_phrase_without_api_key() -> None:
    seeds = derive_graph_seeds("What language do they prefer typescript")
    assert "typescript" in seeds


def test_graph_seeds_query_rejects_api_key() -> None:
    seeds = derive_graph_seeds("what language does the user prefer")
    assert "language" in seeds or "prefer" in seeds
    assert list(inspect.signature(derive_graph_seeds).parameters) == ["query"]
