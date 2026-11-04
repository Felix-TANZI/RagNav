# backend/app/config.py
from functools import lru_cache
from pathlib import Path

from pydantic import EmailStr, Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Les secrets n'ont pas de valeur par défaut, ils viennent de backend/.env ou de l'environnement
    llm_api_key: SecretStr = Field(min_length=1)
    jwt_secret: SecretStr = Field(min_length=32)
    admin_email: EmailStr | None = None
    admin_password: SecretStr | None = None

    llm_base_url: str = "http://127.0.0.1:11434/v1"
    llm_model: str = "qwen3:4b-instruct-2507-q4_K_M"
    embed_model: str = "bge-m3"
    embed_batch_size: int = Field(default=16, ge=1)
    embed_timeout: float = Field(default=300.0, gt=0)
    qdrant_url: str = "http://127.0.0.1:6333"
    qdrant_timeout: float = Field(default=30.0, gt=0)
    default_corpus: str = "navigation"
    top_k: int = Field(default=5, ge=1, le=20)
    min_score: float = Field(default=0.40, ge=0, le=1)
    temperature: float = Field(default=0.0, ge=0, le=2)
    max_tokens: int = Field(default=512, ge=32)
    llm_timeout: float = Field(default=300.0, gt=0)
    max_question_chars: int = Field(default=1000, ge=10)
    chat_per_minute: int = Field(default=20, ge=1)
    cors_origins: list[str] = ["http://localhost:5173"]
    health_timeout: float = 5.0

    data_dir: Path = Path("data")
    max_upload_mb: int = Field(default=50, ge=1)
    access_token_minutes: int = Field(default=15, ge=1, le=60)
    session_hours: int = Field(default=8, ge=1, le=24)
    cookie_secure: bool = True
    password_min_length: int = Field(default=12, ge=8)
    login_max_failures: int = Field(default=5, ge=1)
    lockout_minutes: int = Field(default=15, ge=1)
    login_per_minute: int = Field(default=10, ge=1)
    register_per_hour: int = Field(default=10, ge=1)
    events_retention_days: int = Field(default=90, ge=1)

    chunk_words: int = Field(default=300, ge=50)
    chunk_overlap_words: int = Field(default=45, ge=0)
    ocr_language: str = "fra+eng"
    tessdata_path: str = ""
    ocr_dpi: int = Field(default=300, ge=72)
    libreoffice_path: str = ""
    conversion_timeout: float = Field(default=180.0, gt=0)

    @property
    def database_url(self) -> str:
        return f"sqlite:///{(self.data_dir / 'gandal.db').resolve().as_posix()}"

    @property
    def documents_dir(self) -> Path:
        return self.data_dir / "documents"

    def document_path(self, storage_path: str) -> Path:
        return self.documents_dir / storage_path


@lru_cache
def get_settings() -> Settings:
    return Settings()
