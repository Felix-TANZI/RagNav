# backend/tests/test_pipeline.py
from datetime import date

import pytest

from app.ingest.base import ConversionError
from app.ingest.chunker import Chunk
from app.ingest.pipeline import DocumentSource, embedding_text, index_document
from app.store import StoreError
from tests.fakes import FakeEmbedder


def source(path, title: str = "Titre", doc_id: str = "doc-1") -> DocumentSource:
    return DocumentSource(doc_id, path.name, title, "Cellule de test", "1.0", date(2026, 10, 29), path)


@pytest.fixture
def reseau(tmp_path):
    f = tmp_path / "reseau.md"
    f.write_text("# Réseau\n\n## Pare-feu\n\nLe pare-feu GARDIEN filtre le port 51820.\n", encoding="utf-8")
    return f


def test_indexation_puis_document_inchange_saute(reseau, settings, store):
    result = index_document(source(reseau), "navigation", settings, FakeEmbedder(), store)
    assert result.chunks == 1 and store.count("navigation") == 1
    embedder = FakeEmbedder()
    assert index_document(source(reseau), "navigation", settings, embedder, store) is None
    assert embedder.calls == 0


def test_document_modifie_remplace_sans_passage_perime(reseau, settings, store):
    index_document(source(reseau), "navigation", settings, FakeEmbedder(), store)
    reseau.write_text("# Réseau\n\n## VPN\n\nLe VPN WireGuard écoute sur le port 51820.\n", encoding="utf-8")
    index_document(source(reseau), "navigation", settings, FakeEmbedder(), store)
    hits = store.search("navigation", FakeEmbedder().embed(["VPN WireGuard"])[0], 10)
    assert [h.payload["section"] for h in hits] == ["VPN"]


def test_metadonnees_modifiees_provoquent_une_reindexation(reseau, settings, store):
    index_document(source(reseau, "Ancien titre"), "navigation", settings, FakeEmbedder(), store)
    assert index_document(source(reseau, "Nouveau titre"), "navigation", settings, FakeEmbedder(), store) is not None
    hits = store.search("navigation", FakeEmbedder().embed(["pare-feu"])[0], 10)
    assert [h.payload["title"] for h in hits] == ["Nouveau titre"]


def test_metadonnees_des_passages(reseau, settings, store):
    index_document(source(reseau, "Plan réseau"), "navigation", settings, FakeEmbedder(), store)
    payload = store.search("navigation", FakeEmbedder().embed(["GARDIEN"])[0], 1)[0].payload
    assert payload["document_id"] == "doc-1" and payload["document"] == "reseau.md"
    assert payload["title"] == "Plan réseau" and payload["section"] == "Pare-feu"
    assert payload["section_path"] == "Réseau > Pare-feu" and payload["page"] is None
    assert payload["version"] == "1.0" and payload["date"] == "2026-10-29" and "51820" in payload["text"]


def test_etapes_suivies_et_echec_de_lecture(tmp_path, settings, store):
    bad = tmp_path / "abime.pdf"
    bad.write_bytes(b"%PDF-1.7 abime")
    stages = []
    with pytest.raises(ConversionError):
        index_document(source(bad), "navigation", settings, FakeEmbedder(), store, on_stage=stages.append)
    assert stages == ["Vérification de l'index", "Lecture du document"]


def test_changement_de_modele_detecte(reseau, settings, store):
    index_document(source(reseau), "navigation", settings, FakeEmbedder(), store)
    with pytest.raises(StoreError, match="réindexer"):
        store.check_model("navigation", "autre-modele")


def test_suppression_et_comptage_par_document(reseau, tmp_path, settings, store):
    other = tmp_path / "gpu.md"
    other.write_text("# GPU\n\nLa commande gandal-gpu submit lance un job.\n", encoding="utf-8")
    index_document(source(reseau), "navigation", settings, FakeEmbedder(), store)
    index_document(source(other, doc_id="doc-2"), "navigation", settings, FakeEmbedder(), store)
    assert store.documents("navigation") == {"doc-1": 1, "doc-2": 1}
    store.delete_document("navigation", "doc-1")
    assert store.documents("navigation") == {"doc-2": 1}


def test_texte_vectorise_avec_contexte_sans_titre_en_double(tmp_path):
    chunk = Chunk("doc.md", ("Guide", "1. VPN"), None, "Installer WireGuard.", 0)
    assert embedding_text(source(tmp_path / "doc.md", "Guide"), chunk) == "Guide > 1. VPN\n\nInstaller WireGuard."
