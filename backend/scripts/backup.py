# backend/scripts/backup.py
# Sauvegarde de la base (copie cohérente même API en marche) et des documents dans une archive datée
# L'index Qdrant n'est pas sauvegardé, il se reconstruit depuis les documents avec scripts.ingest --reset
import argparse
import sqlite3
import sys
import tarfile
import tempfile
from datetime import datetime
from pathlib import Path

from app.config import Settings, get_settings

PREFIX = "gandal-"


def backup(settings: Settings, target: Path, keep: int) -> Path:
    target.mkdir(parents=True, exist_ok=True)
    archive = target / f"{PREFIX}{datetime.now():%Y%m%d-%H%M%S}.tar.gz"
    with tempfile.TemporaryDirectory() as tmp:
        copy = Path(tmp) / "gandal.db"
        source, destination = sqlite3.connect(settings.data_dir / "gandal.db"), sqlite3.connect(copy)
        with destination:
            source.backup(destination)
        source.close()
        destination.close()
        with tarfile.open(archive, "w:gz") as tar:
            tar.add(copy, arcname="gandal.db")
            if settings.documents_dir.is_dir():
                tar.add(settings.documents_dir, arcname="documents")
    for old in sorted(target.glob(f"{PREFIX}*.tar.gz"))[:-keep]:
        old.unlink()
    return archive


def main() -> int:
    settings = get_settings()
    parser = argparse.ArgumentParser(description="Sauvegarde de la base et des documents")
    parser.add_argument("--dossier", type=Path, default=settings.data_dir / "sauvegardes")
    parser.add_argument("--garder", type=int, default=7, help="nombre d'archives conservées")
    args = parser.parse_args()
    if not (settings.data_dir / "gandal.db").is_file():
        print(f"Aucune base dans {settings.data_dir}", file=sys.stderr)
        return 2
    archive = backup(settings, args.dossier, max(args.garder, 1))
    print(f"Sauvegarde écrite {archive} ({archive.stat().st_size / 1e6:.1f} Mo)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
