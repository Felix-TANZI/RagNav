# backend/tests/test_keywords.py
# Recherche par mots-clés BM25 et fusion avec la recherche dense (architecture B du Chapitre 2)
from datetime import date

import pytest
from fastapi.testclient import TestClient
from qdrant_client import models as qm

from app.ingest.pipeline import DocumentSource, index_document
from app.keywords import K, passage_vector, query_vector, tokenize
from app.main import create_app
from app.rag import Assistant, fuse
from app.store import DENSE, Hit, StoreError
from tests.conftest import login
from tests.fakes import DIM, FakeEmbedder


def test_identifiants_techniques_gardes_entiers():
    assert tokenize("Quelle machine a l'adresse 10.10.40.30 ?") == ["machine", "adresse", "10.10.40.30"]
    assert tokenize("dcgm-exporter") == ["dcgm-exporter", "dcgm", "exporter"]
    assert tokenize("/mnt/projets") == ["mnt/projets", "mnt", "projet"]


def test_accents_mots_vides_et_pluriels():
    assert tokenize("Où sont les Sauvegardes du nœud ?") == ["sauvegarde", "noeud"]
    assert tokenize("écoute ECOUTE") == ["ecoute", "ecoute"]
    assert query_vector("le la de du ?") is None


def test_poids_bm25_sature_avec_la_frequence():
    once, twice = passage_vector("grafana port"), passage_vector("grafana grafana port")
    weight = dict(zip(once.indices, once.values))
    weight_twice = dict(zip(twice.indices, twice.values))
    grafana = query_vector("grafana").indices[0]
    assert weight[grafana] < weight_twice[grafana] < K + 1


def test_fusion_par_rang_reciproque():
    a, b, c = (Hit(i, 0.5, {}) for i in "abc")
    assert [h.id for h in fuse([[a, b], [b, c]], 3)] == ["b", "a", "c"]
    assert [h.id for h in fuse([[a], []], 5)] == ["a"]


@pytest.fixture
def indexed(tmp_path, settings, store):
    for doc_id, name, text in [
        ("doc-1", "rem.md", "# REM\n\n## Conteneurs\n\nJupyterLab tourne dans le conteneur CT310 sur le port 8888.\n"),
        ("doc-2", "vpn.md", "# VPN\n\n## Accès\n\nLe tunnel WireGuard écoute sur le port 51820.\n"),
    ]:
        path = tmp_path / name
        path.write_text(text, encoding="utf-8")
        index_document(DocumentSource(doc_id, name, name, "Cellule", "1.0", date(2026, 11, 8), path),
                       "navigation", settings, FakeEmbedder(), store)
    return store


def assistant(settings, store, **overrides) -> Assistant:
    return Assistant(settings.model_copy(update=overrides), FakeEmbedder(), store, None)


def test_nom_exact_retrouve_sous_le_seuil_en_mode_hybride(settings, indexed):
    _, kept, _ = assistant(settings, indexed, min_score=0.99).retrieve("À quoi sert CT310 ?", "navigation", 3)
    assert [h.payload["document"] for h in kept][:1] == ["rem.md"]
    assert 0 <= kept[0].score <= 1
    _, dense_kept, _ = assistant(settings, indexed, min_score=0.99, retrieval_mode="dense").retrieve(
        "À quoi sert CT310 ?", "navigation", 3)
    assert dense_kept == []


def test_aucun_mot_commun_aucun_passage(settings, indexed):
    _, kept, _ = assistant(settings, indexed, min_score=0.99).retrieve("Recette du ndolé", "navigation", 3)
    assert kept == []


def test_similarite_des_passages_par_mots_cles_egale_a_la_recherche_dense(indexed):
    vector = FakeEmbedder().embed(["conteneur CT310"])[0]
    by_words = {h.id: h.score for h in indexed.search_keywords("navigation", "conteneur CT310", vector, 5)}
    by_dense = {h.id: h.score for h in indexed.search("navigation", vector, 5)}
    assert by_words and all(by_words[i] == pytest.approx(by_dense[i], abs=1e-4) for i in by_words)


def old_collection(store, name: str) -> None:
    store.client.create_collection(name, vectors_config={DENSE: qm.VectorParams(size=DIM, distance=qm.Distance.COSINE)},
                                   metadata={"embed_model": "faux-modele", "dim": DIM})


def test_ancienne_collection_sans_mots_cles_signalee(store):
    old_collection(store, "ancienne")
    with pytest.raises(StoreError, match="mots-clés"):
        store.check_model("ancienne", "faux-modele")


def test_index_a_reconstruire_inscrit_au_journal_au_demarrage(settings, store):
    old_collection(store, "navigation")
    with TestClient(create_app(settings, store=store, embedder=FakeEmbedder())) as client:
        events = client.get("/admin/events", headers=login(client), params={"level": "error"}).json()
    assert any(e["action"] == "index_a_verifier" and "--reset" in e["message"] for e in events)
