# backend/tests/test_corpus_test.py
# Lit et découpe le vrai corpus de test du dépôt, sans modèle ni index
from pathlib import Path

import pytest

from app.ingest.chunker import chunk_document
from app.ingest.convert import convert
from app.ingest.inventory import check_corpus, load_inventory

CORPUS = Path(__file__).resolve().parents[2] / "corpus"
ENTRIES = load_inventory(CORPUS / "inventaire.csv")


@pytest.fixture(scope="module")
def chunks():
    return {e.file: chunk_document(e.file, convert(CORPUS / e.file), 300, 45, e.title) for e in ENTRIES}


def test_liste_et_dossier_coherents():
    assert check_corpus(CORPUS, ENTRIES, ignored={"inventaire.csv"}).ok


def test_chaque_document_donne_des_passages_bornes(chunks):
    for name, doc_chunks in chunks.items():
        assert len(doc_chunks) >= 5, name
        assert all(0 < c.words <= 300 and c.section for c in doc_chunks), name


def test_faits_exacts_conserves(chunks):
    texts = [c.text for doc_chunks in chunks.values() for c in doc_chunks]
    assert any("VM150" in t and "10.10.20.150" in t and "8090" in t for t in texts)
    assert any("gandal-gpu submit" in t for t in texts)
    assert not any("gandalgpu" in t or "Page 1 /" in t or "GANDAL GI27 ·" in t for t in texts)


def test_pages_des_pdf(chunks):
    pdf_pages = {c.page for c in chunks["test/architecture_generale.pdf"]}
    assert pdf_pages == {1, 2, 3}
    assert all(c.page is None for c in chunks["test/plan_adressage_reseau.md"])
