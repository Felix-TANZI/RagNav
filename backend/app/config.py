# backend/app/config.py
from functools import lru_cache

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Les secrets n'ont pas de valeur par défaut, ils viennent de backend/.env ou de l'environnement
    llm_api_key: SecretStr = Field(min_length=1)
    llm_base_url: str = "http://127.0.0.1:11434/v1"
    llm_model: str = "qwen3:4b-instruct-2507-q4_K_M"
    embed_model: str = "bge-m3"
    embed_batch_size: int = Field(default=16, ge=1)
    embed_timeout: float = Field(default=300.0, gt=0)
    qdrant_url: str = "http://127.0.0.1:6333"
    qdrant_timeout: float = Field(default=30.0, gt=0)
    default_corpus: str = "navigation"
    cors_origins: list[str] = ["http://localhost:5173"]
    health_timeout: float = 5.0
    chunk_words: int = Field(default=300, ge=50)
    chunk_overlap_words: int = Field(default=45, ge=0)
    ocr_language: str = "fra+eng"
    tessdata_path: str = ""
    ocr_dpi: int = Field(default=300, ge=72)
    libreoffice_path: str = ""
    conversion_timeout: float = Field(default=180.0, gt=0)


@lru_cache
def get_settings() -> Settings:
    return Settings()
