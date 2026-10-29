# backend/tests/test_pipeline.py
from datetime import date

import pytest
from qdrant_client import QdrantClient

from app.config import Settings
from app.ingest.inventory import Entry
from app.ingest.pipeline import embedding_text, ingest_corpus
from app.ingest.chunker import Chunk
from app.store import StoreError, VectorStore
from tests.fakes import FakeEmbedder

SETTINGS = Settings(_env_file=None, llm_api_key="cle-de-test", embed_model="faux-modele", chunk_words=60,
                    chunk_overlap_words=10)


def entry(name: str, title: str = "Titre") -> Entry:
    return Entry(name, title, "Cellule de test", "1.0", date(2026, 10, 29))


@pytest.fixture
def corpus(tmp_path):
    (tmp_path / "reseau.md").write_text("# Réseau\n\n## Pare-feu\n\nLe pare-feu GARDIEN filtre le port 51820.\n",
                                        encoding="utf-8")
    (tmp_path / "gpu.md").write_text("# GPU\n\n## Jobs\n\nLa commande gandal-gpu submit lance un job.\n",
                                     encoding="utf-8")
    return tmp_path


@pytest.fixture
def store():
    return VectorStore(QdrantClient(":memory:"), payload_indexes=False)


def run(corpus, entries, store, embedder=None, **kwargs):
    return ingest_corpus(corpus, entries, "navigation", SETTINGS, embedder or FakeEmbedder(), store,
                         log=lambda _: None, **kwargs)


def test_indexation_puis_documents_inchanges_sautes(corpus, store):
    entries = [entry("reseau.md", "Réseau"), entry("gpu.md", "GPU")]
    report = run(corpus, entries, store)
    assert set(report.indexed) == {"reseau.md", "gpu.md"} and store.count("navigation") == 2
    embedder = FakeEmbedder()
    report = run(corpus, entries, store, embedder)
    assert report.unchanged == ["reseau.md", "gpu.md"] and embedder.calls == 0


def test_document_modifie_remplace_sans_passage_perime(corpus, store):
    entries = [entry("reseau.md", "Réseau")]
    run(corpus, entries, store)
    (corpus / "reseau.md").write_text("# Réseau\n\n## VPN\n\nLe VPN WireGuard écoute sur le port 51820.\n",
                                      encoding="utf-8")
    report = run(corpus, entries, store)
    assert report.indexed == {"reseau.md": 1}
    hits = store.search("navigation", FakeEmbedder().embed(["VPN WireGuard"])[0], 10)
    assert [h.payload["section"] for h in hits] == ["VPN"]


def test_document_retire_de_la_liste_supprime_de_l_index(corpus, store):
    run(corpus, [entry("reseau.md"), entry("gpu.md")], store)
    report = run(corpus, [entry("gpu.md")], store)
    assert report.removed == ["reseau.md"] and store.documents("navigation") == {"gpu.md": 1}


def test_document_illisible_signale_sans_bloquer_les_autres(corpus, store):
    (corpus / "abime.pdf").write_bytes(b"%PDF-1.7 abime")
    report = run(corpus, [entry("abime.pdf"), entry("gpu.md")], store)
    assert "abime.pdf" in report.failed and report.indexed == {"gpu.md": 1}


def test_metadonnees_des_passages(corpus, store):
    run(corpus, [entry("gpu.md", "Procédure GPU")], store)
    payload = store.search("navigation", FakeEmbedder().embed(["gandal-gpu"])[0], 1)[0].payload
    assert payload["document"] == "gpu.md" and payload["title"] == "Procédure GPU"
    assert payload["section"] == "Jobs" and payload["section_path"] == "GPU > Jobs"
    assert payload["version"] == "1.0" and payload["date"] == "2026-10-29" and payload["page"] is None
    assert "gandal-gpu submit" in payload["text"]


def test_changement_de_modele_detecte(corpus, store):
    run(corpus, [entry("gpu.md")], store)
    with pytest.raises(StoreError, match="réindexer"):
        store.check_model("navigation", "autre-modele")


def test_texte_vectorise_avec_contexte_sans_titre_en_double():
    chunk = Chunk("doc.md", ("Guide", "1. VPN"), None, "Installer WireGuard.", 0)
    assert embedding_text(entry("doc.md", "Guide"), chunk) == "Guide > 1. VPN\n\nInstaller WireGuard."
