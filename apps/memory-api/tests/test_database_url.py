from memory_api.db.url import engine_kwargs, sqlalchemy_url


def test_rewrites_postgres_scheme_to_psycopg() -> None:
    url = sqlalchemy_url("postgres://memoria:secret@localhost:5432/memoria")
    assert url.startswith("postgresql+psycopg://")
    assert "localhost:5432/memoria" in url


def test_rewrites_postgresql_scheme_to_psycopg() -> None:
    url = sqlalchemy_url("postgresql://memoria:secret@localhost/memoria")
    assert url.startswith("postgresql+psycopg://")


def test_leaves_psycopg_url_intact() -> None:
    raw = "postgresql+psycopg://memoria:secret@localhost/memoria"
    assert sqlalchemy_url(raw) == raw


def test_neon_pooler_uses_ssl_and_disables_prepared_statements() -> None:
    url = (
        "postgresql+psycopg://u:p@ep-example-pooler.us-east-1.aws.neon.tech/neondb"
    )
    kwargs = engine_kwargs(url)
    assert kwargs["pool_pre_ping"] is True
    assert kwargs["connect_args"]["sslmode"] == "require"
    assert kwargs["connect_args"]["prepare_threshold"] is None


def test_local_url_skips_ssl_and_pgbouncer_flags() -> None:
    kwargs = engine_kwargs("postgresql+psycopg://memoria:memoria@localhost:5432/memoria")
    assert kwargs["pool_pre_ping"] is True
    assert "connect_args" not in kwargs
