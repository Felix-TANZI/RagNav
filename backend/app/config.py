# backend/app/config.py
from functools import lru_cache

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Les secrets n'ont pas de valeur par défaut, ils viennent de backend/.env ou de l'environnement
    llm_api_key: SecretStr = Field(min_length=1)
    llm_base_url: str = "http://localhost:11434/v1"
    llm_model: str = "qwen3:4b-instruct-2507-q4_K_M"
    embed_model: str = "bge-m3"
    qdrant_url: str = "http://localhost:6333"
    cors_origins: list[str] = ["http://localhost:5173"]
    health_timeout: float = 5.0


@lru_cache
def get_settings() -> Settings:
    return Settings()
