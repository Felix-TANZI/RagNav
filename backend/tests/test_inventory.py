# backend/tests/test_inventory.py
from datetime import date

import pytest

from app.ingest.inventory import InventoryError, check_corpus, load_inventory

HEADER = "fichier;titre;source;version;date\n"


def write(tmp_path, body: str):
    f = tmp_path / "inventaire.csv"
    f.write_text(HEADER + body, encoding="utf-8")
    return f


def test_lecture(tmp_path):
    entries = load_inventory(write(tmp_path, "a.pdf;Architecture;Cellule I1;1.2;2026-10-20\n"))
    assert entries[0].title == "Architecture" and entries[0].date == date(2026, 10, 20)


@pytest.mark.parametrize("body, message", [
    ("a.pdf;Architecture;;1.2;2026-10-20\n", "obligatoires"),
    ("a.pdf;A;I1;1;2026-10-20\na.pdf;A;I1;2;2026-10-21\n", "déjà listé"),
    ("a.pdf;A;I1;1;20/10/2026\n", "AAAA-MM-JJ"),
])
def test_erreurs(tmp_path, body, message):
    with pytest.raises(InventoryError, match=message):
        load_inventory(write(tmp_path, body))


def test_colonnes_attendues(tmp_path):
    f = tmp_path / "inventaire.csv"
    f.write_text("fichier;titre\na.pdf;A\n", encoding="utf-8")
    with pytest.raises(InventoryError, match="colonnes"):
        load_inventory(f)


def test_documents_absents_et_non_listes(tmp_path):
    (tmp_path / "test").mkdir()
    (tmp_path / "test" / "a.md").write_text("# A", encoding="utf-8")
    (tmp_path / "b.md").write_text("# B", encoding="utf-8")
    inventory = write(tmp_path, "test/a.md;A;I1;1;2026-10-20\nc.md;C;I1;1;2026-10-20\n")
    check = check_corpus(tmp_path, load_inventory(inventory), ignored={inventory.name})
    assert check.missing == ["c.md"] and check.unlisted == ["b.md"] and not check.ok
