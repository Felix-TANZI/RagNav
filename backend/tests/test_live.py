# backend/tests/test_live.py
# Vérifie les vrais services de la machine (Ollama ou LiteLLM, Qdrant), lancer avec pytest -m live
import uuid
from datetime import date

import httpx2 as httpx
import pytest

from app.config import Settings
from app.embeddings import Embedder
from app.ingest.inventory import Entry
from app.ingest.pipeline import ingest_corpus
from app.store import VectorStore

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


def test_indexation_et_recherche_reelles(tmp_path):
    (tmp_path / "a.md").write_text("# Réseau\n\nLe VPN WireGuard écoute sur le port 51820 du pare-feu.\n",
                                   encoding="utf-8")
    (tmp_path / "b.md").write_text("# Sauvegarde\n\nLes machines virtuelles sont sauvegardées à 01 h 30.\n",
                                   encoding="utf-8")
    entries = [Entry(n, n, "test", "1", date(2026, 10, 29)) for n in ("a.md", "b.md")]
    corpus, store, embedder = f"test_{uuid.uuid4().hex[:8]}", VectorStore.from_settings(settings), Embedder(settings)
    try:
        report = ingest_corpus(tmp_path, entries, corpus, settings, embedder, store, log=lambda _: None)
        assert report.indexed == {"a.md": 1, "b.md": 1}
        hits = store.search(corpus, embedder.embed(["À quelle heure a lieu la sauvegarde ?"])[0], 2)
        assert hits[0].payload["document"] == "b.md"
    finally:
        store.drop(corpus)


def test_generation_en_francais():
    r = httpx.post(f"{base}/chat/completions", headers=headers, timeout=600, json={
        "model": settings.llm_model,
        "messages": [{"role": "user", "content": "Réponds en un mot, quelle est la capitale du Cameroun ?"}],
        "temperature": 0,
    })
    r.raise_for_status()
    assert "yaound" in r.json()["choices"][0]["message"]["content"].lower()
