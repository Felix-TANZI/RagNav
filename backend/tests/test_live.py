# backend/tests/test_live.py
# Vérifie les vrais services de la machine (Ollama ou LiteLLM, Qdrant), lancer avec pytest -m live
import httpx2 as httpx
import pytest

from app.config import Settings

pytestmark = pytest.mark.live
settings = Settings()
headers = {"Authorization": f"Bearer {settings.llm_api_key.get_secret_value()}"}
base = settings.llm_base_url.rstrip("/")


def test_qdrant_repond():
    r = httpx.get(f"{settings.qdrant_url.rstrip('/')}/", timeout=10)
    assert r.status_code == 200 and "version" in r.json()


def test_embedding_bge_m3_en_1024_dimensions():
    r = httpx.post(f"{base}/embeddings", headers=headers, timeout=120,
                   json={"model": settings.embed_model, "input": ["Sur quel port écoute LiteLLM ?"]})
    r.raise_for_status()
    assert len(r.json()["data"][0]["embedding"]) == 1024


def test_generation_en_francais():
    r = httpx.post(f"{base}/chat/completions", headers=headers, timeout=600, json={
        "model": settings.llm_model,
        "messages": [{"role": "user", "content": "Réponds en un mot, quelle est la capitale du Cameroun ?"}],
        "temperature": 0,
    })
    r.raise_for_status()
    assert "yaound" in r.json()["choices"][0]["message"]["content"].lower()
