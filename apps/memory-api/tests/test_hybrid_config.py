from memory_api.config import Settings


def test_hybrid_flags_kv_on_graph_on() -> None:
    s = Settings()
    assert s.enable_kv is True
    assert s.enable_graph is True


def test_graph_max_edges_per_add_default() -> None:
    s = Settings()
    assert s.graph_max_edges_per_add == 8


def test_kv_max_triples_per_add_default() -> None:
    s = Settings()
    assert s.kv_max_triples_per_add == 6


def test_fusion_weights_match_current_scoring_defaults() -> None:
    s = Settings()
    assert s.fusion_weight_relevance == 0.6
    assert s.fusion_weight_importance == 0.2
    assert s.fusion_weight_recency == 0.2
    assert s.recency_halflife_days == 14.0
