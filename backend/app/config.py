"""Zentrale Konfiguration, liest aus Umgebungsvariablen (.env)."""
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Postgres. In lokaler Dev-Umgebung passt der docker-compose Default.
    database_url: str = "postgresql+psycopg2://landtag:landtag@localhost:5432/landtag_sim"

    # CORS für das lokale Vite-Frontend
    frontend_origin: str = "http://localhost:5173"

    app_env: str = "development"


@lru_cache
def get_settings() -> Settings:
    return Settings()
