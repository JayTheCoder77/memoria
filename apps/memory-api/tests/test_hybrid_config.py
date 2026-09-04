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
