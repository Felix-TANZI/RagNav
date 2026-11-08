# backend/tests/test_eval_set.py
# Le jeu d'évaluation reste juste, chaque réponse attendue figure dans la section qu'il indique
import json
from pathlib import Path

import pytest

from app.ingest.chunker import chunk_document
from app.ingest.convert import convert
from app.ingest.inventory import load_inventory

ROOT = Path(__file__).resolve().parents[2]
QUESTIONS = [json.loads(line) for line in (ROOT / "eval" / "questions.jsonl").read_text(encoding="utf-8").splitlines()
             if line.strip()]
ENTRIES = {Path(e.file).name: e for e in load_inventory(ROOT / "corpus" / "inventaire.csv")}


@pytest.fixture(scope="module")
def sections():
    found: dict[tuple[str, str], str] = {}
    for name, entry in ENTRIES.items():
        for c in chunk_document(name, convert(ROOT / "corpus" / entry.file), title=entry.title):
            found[(name, c.section)] = found.get((name, c.section), "") + "\n" + c.text
    return found


def test_identifiants_uniques_et_cas_connus():
    assert len({q["id"] for q in QUESTIONS}) == len(QUESTIONS)
    assert {q["cas"] for q in QUESTIONS} == {"CU1", "CU2", "CU3", "CU4"}


@pytest.mark.parametrize("q", [q for q in QUESTIONS if q["reponse"]], ids=lambda q: q["id"])
def test_reponse_presente_dans_la_section_indiquee(q, sections):
    text = sections.get((q["document"], q["section"]))
    assert text is not None, f"section introuvable {q['document']} / {q['section']}"
    if q["cas"] == "CU3":
        text = ENTRIES[q["document"]].title
    assert all(k in text for k in q["mots_cles"]), q["mots_cles"]


@pytest.mark.parametrize("q", [q for q in QUESTIONS if q.get("autres_sources")], ids=lambda q: q["id"])
def test_autres_sources_contiennent_la_reponse(q, sections):
    for document, section in q["autres_sources"]:
        assert (document, section) in sections, f"section introuvable {document} / {section}"
        text = sections[(document, section)].lower()
        assert all(k.lower() in text for k in q["mots_cles"]), f"{document} / {section} sans {q['mots_cles']}"
