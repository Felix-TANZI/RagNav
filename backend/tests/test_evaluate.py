# backend/tests/test_evaluate.py
# Mesures automatiques de l'évaluation, sources acceptées et nombres absents des extraits
from app.store import Hit
from scripts.eval_retrieval import expected_sources, rank_of
from scripts.evaluate import unsourced_numbers


def hit(document: str, section: str, text: str = "") -> Hit:
    return Hit("1", 0.8, {"document": document, "title": "Titre", "section": section, "text": text})


def test_nombres_presents_dans_les_extraits():
    context = [hit("a.md", "3. Noms DNS", "Le BASTION a l'adresse 10.10.20.110 et écoute sur le port 2222.")]
    assert unsourced_numbers("Le BASTION est en 10.10.20.110, port 2222 [1].", context) == []


def test_nombre_invente_signale():
    context = [hit("a.md", "Outils", "Grafana tourne sur le port 3000.")]
    assert unsourced_numbers("Grafana tourne sur le port 3001 [1].", context) == ["3001"]


def test_numero_de_section_et_espace_fine_reconnus():
    context = [hit("a.md", "6. Restaurer un fichier", "Démarre à 01 h 30.")]
    assert unsourced_numbers("Voir la section 6, départ à 01 h 30 [1].", context) == []


def test_autres_sources_acceptees_pour_le_rappel():
    q = {"document": "a.md", "section": "3. Noms DNS", "autres_sources": [["b.pdf", "3. Machines"]]}
    assert expected_sources(q) == {("a.md", "3. Noms DNS"), ("b.pdf", "3. Machines")}
    assert rank_of(q, [hit("c.md", "1. Autre"), hit("b.pdf", "3. Machines")]) == 2
