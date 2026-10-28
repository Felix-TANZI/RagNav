# backend/tests/test_config.py
import pytest
from pydantic import ValidationError

from app.config import Settings


def test_cle_absente_refusee(monkeypatch):
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    with pytest.raises(ValidationError, match="llm_api_key"):
        Settings(_env_file=None)


def test_cle_vide_refusee(monkeypatch):
    monkeypatch.setenv("LLM_API_KEY", "")
    with pytest.raises(ValidationError, match="llm_api_key"):
        Settings(_env_file=None)


def test_cle_masquee_dans_les_affichages(monkeypatch):
    monkeypatch.setenv("LLM_API_KEY", "sk-secret-litellm")
    settings = Settings(_env_file=None)
    assert "sk-secret-litellm" not in repr(settings)
    assert "sk-secret-litellm" not in str(settings.model_dump())
    assert settings.llm_api_key.get_secret_value() == "sk-secret-litellm"
