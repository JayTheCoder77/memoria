from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="MEMORIA_", extra="ignore")

    database_url: str = "postgresql+psycopg://memoria:memoria@localhost:5432/memoria"


settings = Settings()
