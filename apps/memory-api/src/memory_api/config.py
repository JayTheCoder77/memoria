from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="MEMORIA_",
        env_file=".env",
        extra="ignore",
    )

    database_url: str = "postgresql+psycopg://memoria:memoria@localhost:5432/memoria"
    embedder: str = "hash"
    hf_token: str = ""
    hf_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    run_worker: bool = False
    cors_origins: str = ""
    jwt_secret: str = "dev-secret-change-me-please-use-32b+"
    jwt_ttl_minutes: int = 60 * 24
    google_client_id: str = ""
    rate_limit_per_minute: int = 120
    session_cookie_name: str = "memoria_session"
    llm_model: str = "openai/gpt-4o-mini"
    llm_base_url: str = "https://openrouter.ai/api/v1"
    openrouter_http_referer: str = "http://localhost:3000"
    openrouter_app_title: str = "Memoria"
    extract_batch_size: int = 10
    dedup_threshold: float = 0.92
    consolidate_threshold: float = 0.85
    enable_kv: bool = True
    enable_graph: bool = True
    kv_max_triples_per_add: int = 6
    graph_max_edges_per_add: int = 8
    fusion_weight_relevance: float = 0.6
    fusion_weight_importance: float = 0.2
    fusion_weight_recency: float = 0.2
    recency_halflife_days: float = 14.0


settings = Settings()
