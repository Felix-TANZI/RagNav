# backend/tests/test_config.py
import pytest
from pydantic import ValidationError

from app.config import Settings

JWT = "j" * 40


@pytest.fixture(autouse=True)
def secrets_env(monkeypatch):
    monkeypatch.setenv("LLM_API_KEY", "cle-de-test")
    monkeypatch.setenv("JWT_SECRET", JWT)
    monkeypatch.delenv("ADMIN_PASSWORD", raising=False)


@pytest.mark.parametrize("name, value", [("LLM_API_KEY", None), ("LLM_API_KEY", ""), ("JWT_SECRET", None),
                                         ("JWT_SECRET", "trop-court")])
def test_secret_absent_vide_ou_trop_court_refuse(monkeypatch, name, value):
    if value is None:
        monkeypatch.delenv(name)
    else:
        monkeypatch.setenv(name, value)
    with pytest.raises(ValidationError, match=name.lower()):
        Settings(_env_file=None)


def test_secrets_masques_dans_les_affichages(monkeypatch):
    monkeypatch.setenv("LLM_API_KEY", "sk-secret-litellm")
    monkeypatch.setenv("ADMIN_PASSWORD", "mot-de-passe-admin")
    settings = Settings(_env_file=None)
    shown = repr(settings) + str(settings.model_dump())
    assert all(secret not in shown for secret in ("sk-secret-litellm", JWT, "mot-de-passe-admin"))
    assert settings.llm_api_key.get_secret_value() == "sk-secret-litellm"


def test_securite_par_defaut():
    settings = Settings(_env_file=None)
    assert settings.cookie_secure is True and settings.access_token_minutes == 15 and settings.session_hours == 8
    assert settings.password_min_length >= 12
