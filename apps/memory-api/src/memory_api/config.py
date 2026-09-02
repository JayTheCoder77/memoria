from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="MEMORIA_",
        env_file=".env",
        extra="ignore",
    )

    database_url: str = "postgresql+psycopg://memoria:memoria@localhost:5432/memoria"
    embedder: str = "hash"
    jwt_secret: str = "dev-secret-change-me-please-use-32b+"
    jwt_ttl_minutes: int = 60 * 24
    google_client_id: str = ""
    rate_limit_per_minute: int = 120
    session_cookie_name: str = "memoria_session"


settings = Settings()
