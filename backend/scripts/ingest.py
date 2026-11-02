# backend/scripts/ingest.py
# Réindexe les documents de la base avec la même logique que la file de l'API, et retire de l'index les orphelins
import argparse
import sys
import time

from sqlalchemy import select

from app.config import get_settings
from app.db import make_engine, make_session_factory
from app.embeddings import Embedder
from app.events import EventLog
from app.migrate import run_migrations
from app.models import Document, DocumentStatus
from app.store import StoreError, VectorStore
from app.worker import IndexWorker


def main() -> int:
    settings = get_settings()
    parser = argparse.ArgumentParser(description="Indexation des documents de la base")
    parser.add_argument("--reset", action="store_true", help="supprime la collection puis réindexe tout")
    parser.add_argument("--force", action="store_true", help="recalcule aussi les documents inchangés")
    args = parser.parse_args()

    run_migrations(settings.database_url)
    sessions = make_session_factory(make_engine(settings.database_url))
    store = VectorStore.from_settings(settings)
    worker = IndexWorker(sessions, settings, Embedder(settings), store, EventLog(sessions))
    corpus, started = settings.default_corpus, time.time()
    try:
        if args.reset:
            store.drop(corpus)
            print(f"Collection {corpus} supprimée")
        with sessions() as session:
            documents = session.scalars(select(Document).where(Document.status != DocumentStatus.DELETING)).all()
        print(f"Indexation de {len(documents)} document(s) dans {corpus}, embeddings {settings.embed_model}")
        failed = 0
        for doc in documents:
            worker.index_now(doc.id, force=args.force or args.reset)
            with sessions() as session:
                current = session.get(Document, doc.id)
            failed += current.status == DocumentStatus.FAILED
            print(f"  {current.status.value:<9} {current.filename}" + (f", {current.error}" if current.error else ""))
        known = {doc.id for doc in documents}
        orphans = [d for d in store.documents(corpus) if d not in known]
        for document_id in orphans:
            store.delete_document(corpus, document_id)
    except StoreError as e:
        print(f"Indexation interrompue, {e}", file=sys.stderr)
        return 2
    print(f"\n{len(documents) - failed} indexé(s), {failed} en échec, {len(orphans)} orphelin(s) retiré(s), "
          f"{store.count(corpus)} passages dans l'index, {time.time() - started:.1f} s")
    return 0 if not failed else 1


if __name__ == "__main__":
    sys.exit(main())
