# backend/scripts/import_corpus.py
# Importe dans la base les documents d'un inventaire.csv (corpus de test), un fichier déjà présent est ignoré
import argparse
import hashlib
import sys
from pathlib import Path

from sqlalchemy import select

from app import storage
from app.config import get_settings
from app.db import make_engine, make_session_factory
from app.events import EventLog
from app.ingest.inventory import InventoryError, check_corpus, load_inventory
from app.migrate import run_migrations
from app.models import Document, EventCategory, new_id

INVENTORY = "inventaire.csv"


def main() -> int:
    parser = argparse.ArgumentParser(description="Import d'un corpus listé dans inventaire.csv")
    parser.add_argument("--corpus-dir", type=Path, default=Path("../corpus"))
    args = parser.parse_args()
    settings = get_settings()

    try:
        entries = load_inventory(args.corpus_dir / INVENTORY)
    except (OSError, InventoryError) as e:
        print(f"Liste du corpus illisible, {e}", file=sys.stderr)
        return 1
    check = check_corpus(args.corpus_dir, entries, ignored={INVENTORY})
    run_migrations(settings.database_url)
    sessions = make_session_factory(make_engine(settings.database_url))
    events = EventLog(sessions)

    imported = 0
    with sessions() as session:
        for entry in entries:
            if entry.file in check.missing:
                print(f"  ABSENT    {entry.file}")
                continue
            source = args.corpus_dir / entry.file
            sha256 = hashlib.sha256(source.read_bytes()).hexdigest()
            if session.scalar(select(Document.id).where(Document.sha256 == sha256)):
                print(f"  présent   {entry.file}")
                continue
            document_id, filename = new_id(), storage.safe_filename(Path(entry.file).name)
            with source.open("rb") as f:
                path, sha256, size = storage.save_version(f, settings.documents_dir / document_id, filename,
                                                          settings.max_upload_mb * 1024 * 1024)
            session.add(Document(id=document_id, filename=filename, title=entry.title, source=entry.source,
                                 version=entry.version, document_date=entry.date, sha256=sha256, size=size,
                                 storage_path=storage.relative_to_documents(path, settings.documents_dir)))
            session.commit()
            events.info(EventCategory.DOCUMENTS, "document_importe", f"{filename} importé depuis {INVENTORY}",
                        document_id=document_id)
            imported += 1
            print(f"  importé   {entry.file}")
    print(f"\n{imported} document(s) importé(s), l'indexation se fait au démarrage de l'API ou par scripts.ingest")
    return 0 if not check.missing else 1


if __name__ == "__main__":
    sys.exit(main())
