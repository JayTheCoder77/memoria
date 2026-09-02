from memory_api.services.embedding import HashEmbedder, get_embedder


def test_default_embedder_is_hash() -> None:
    assert isinstance(get_embedder(), HashEmbedder)
