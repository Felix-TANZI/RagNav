# backend/tests/test_chunker.py
from app.ingest.chunker import chunk_document
from app.ingest.convert import Page


def sentences(n: int, word: str = "mot") -> str:
    return " ".join(f"Phrase {i} avec quelques {word} utiles." for i in range(n))


def test_chemin_des_titres():
    md = "# Doc\n\nIntro.\n\n## A\n\nTexte A.\n\n### A1\n\nTexte A1.\n\n## B\n\nTexte B.\n"
    chunks = chunk_document("doc.md", [Page(md)])
    assert [c.section_path for c in chunks] == ["Doc", "Doc > A", "Doc > A > A1", "Doc > B"]
    assert chunks[3].section == "B"


def test_taille_bornee_recouvrement_et_sections_separees():
    md = f"# S1\n\n{sentences(60)}\n\n# S2\n\n{sentences(5)}\n"
    chunks = chunk_document("doc.md", [Page(md)], max_words=80, overlap_words=15)
    s1 = [c for c in chunks if c.section == "S1"]
    assert len(s1) > 2 and all(c.words <= 80 for c in chunks)
    for previous, current in zip(s1, s1[1:]):
        last_sentence = previous.text.split(". ")[-1]
        assert last_sentence in current.text
    assert all("S1" not in c.text for c in chunks if c.section == "S2")


def test_tableau_jamais_coupe_dans_une_ligne_et_entete_repete():
    rows = "\n".join(f"| VM{i} | 10.10.20.{i} | port {8000 + i} |" for i in range(40))
    md = f"# Machines\n\n| Machine | Adresse | Port |\n| --- | --- | --- |\n{rows}\n"
    chunks = chunk_document("doc.md", [Page(md)], max_words=60, overlap_words=10)
    assert len(chunks) > 1
    for c in chunks:
        lines = c.text.splitlines()
        assert lines[0] == "| Machine | Adresse | Port |"
        assert all(line.startswith("|") and line.endswith("|") for line in lines)
    assert sum(c.text.count("| VM") for c in chunks) >= 40


def test_code_avec_diese_et_titres_soulignes():
    md = "Titre principal\n===============\n\n```\n# pas un titre\nssh -p 2222 bastion\n```\n\nSous titre\n---\n\nFin.\n"
    chunks = chunk_document("doc.md", [Page(md)])
    assert [c.section_path for c in chunks] == ["Titre principal", "Titre principal > Sous titre"]
    assert "# pas un titre" in chunks[0].text


def test_pages_paragraphe_recolle_et_page_du_passage():
    pages = [Page("# Stockage\n\nLes instantanés sont pris toutes les", 1), Page("six heures.\n\nAutre fait.", 2)]
    chunks = chunk_document("doc.pdf", pages)
    assert "toutes les six heures." in chunks[0].text and chunks[0].page == 1


def test_paragraphe_geant_sans_ponctuation_et_titre_par_defaut():
    md = " ".join(["donnée"] * 700)
    chunks = chunk_document("doc.txt", [Page(md)], max_words=300, overlap_words=0, title="Notes")
    assert len(chunks) == 3 and all(c.words <= 300 for c in chunks)
    assert all(c.section == "Notes" for c in chunks)


def test_identifiants_stables_et_uniques():
    md = f"# A\n\n{sentences(40)}"
    first = chunk_document("doc.md", [Page(md)], max_words=60)
    second = chunk_document("doc.md", [Page(md)], max_words=60)
    assert [c.id for c in first] == [c.id for c in second]
    assert len({c.id for c in first}) == len(first)
