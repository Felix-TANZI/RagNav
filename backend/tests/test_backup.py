# backend/tests/test_backup.py
# Sauvegarde puis restauration de la base et des documents, rotation des archives
import sqlite3
from contextlib import closing

from scripts.backup import backup
from scripts.restore import restore


def execute(db, *statements: str) -> list:
    with closing(sqlite3.connect(db)) as connection, connection:
        return [connection.execute(s).fetchall() for s in statements]


def test_sauvegarde_puis_restauration(settings, tmp_path):
    settings.documents_dir.mkdir(parents=True)
    db = settings.data_dir / "gandal.db"
    execute(db, "create table essai (valeur text)", "insert into essai values ('avant')")
    (settings.documents_dir / "guide.md").write_text("version sauvegardée", encoding="utf-8")

    archive = backup(settings, tmp_path / "sauvegardes", keep=3)
    execute(db, "update essai set valeur = 'apres'")
    (settings.documents_dir / "guide.md").write_text("version modifiée", encoding="utf-8")
    (settings.documents_dir / "nouveau.md").write_text("ajouté après", encoding="utf-8")

    restore(settings, archive)
    assert execute(db, "select valeur from essai") == [[("avant",)]]
    assert (settings.documents_dir / "guide.md").read_text(encoding="utf-8") == "version sauvegardée"
    assert not (settings.documents_dir / "nouveau.md").exists()


def test_seules_les_dernieres_archives_sont_gardees(settings, tmp_path):
    settings.data_dir.mkdir(parents=True)
    sqlite3.connect(settings.data_dir / "gandal.db").close()
    target = tmp_path / "sauvegardes"
    target.mkdir()
    for day in ("20260101", "20260102", "20260103"):
        (target / f"gandal-{day}-000000.tar.gz").write_bytes(b"")
    latest = backup(settings, target, keep=2)
    assert sorted(p.name for p in target.iterdir()) == ["gandal-20260103-000000.tar.gz", latest.name]
