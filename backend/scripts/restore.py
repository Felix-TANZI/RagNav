# backend/scripts/restore.py
# Restauration d'une archive de scripts.backup, API arrêtée, puis reconstruire l'index avec scripts.ingest --reset
import argparse
import shutil
import sys
import tarfile
import tempfile
from pathlib import Path

from app.config import Settings, get_settings


def restore(settings: Settings, archive: Path) -> None:
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=settings.data_dir) as tmp:
        with tarfile.open(archive, "r:gz") as tar:
            tar.extractall(tmp, filter="data")
        extracted = Path(tmp)
        if not (extracted / "gandal.db").is_file():
            raise ValueError(f"{archive.name} ne contient pas gandal.db")
        for suffix in ("", "-wal", "-shm"):
            (settings.data_dir / f"gandal.db{suffix}").unlink(missing_ok=True)
        shutil.move(extracted / "gandal.db", settings.data_dir / "gandal.db")
        shutil.rmtree(settings.documents_dir, ignore_errors=True)
        if (extracted / "documents").is_dir():
            shutil.move(extracted / "documents", settings.documents_dir)


def main() -> int:
    parser = argparse.ArgumentParser(description="Restauration de la base et des documents")
    parser.add_argument("archive", type=Path)
    args = parser.parse_args()
    try:
        restore(get_settings(), args.archive)
    except (OSError, tarfile.TarError, ValueError) as e:
        print(f"Restauration impossible, {e}", file=sys.stderr)
        return 2
    print(f"{args.archive.name} restaurée, lancer python -m scripts.ingest --reset puis démarrer l'API")
    return 0


if __name__ == "__main__":
    sys.exit(main())
