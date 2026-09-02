from memory_api.services.embedding import EMBEDDING_DIM, HashEmbedder, embed_text


def test_embed_text_returns_fixed_dimension_vector() -> None:
    vector = embed_text("the user prefers pytest over unittest", embedder=HashEmbedder())

    assert len(vector) == EMBEDDING_DIM
    assert all(isinstance(value, float) for value in vector)


def test_embed_text_is_deterministic_for_the_same_input() -> None:
    embedder = HashEmbedder()

    first = embed_text("session ended after a failed migration", embedder=embedder)
    second = embed_text("session ended after a failed migration", embedder=embedder)

    assert first == second


def test_embed_text_differs_for_different_inputs() -> None:
    embedder = HashEmbedder()

    first = embed_text("prefer dark mode", embedder=embedder)
    second = embed_text("always use type hints", embedder=embedder)

    assert first != second
