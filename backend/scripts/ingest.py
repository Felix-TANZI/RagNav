# backend/scripts/ingest.py
# Indexation du corpus listé dans inventaire.csv (CU5), commande du gestionnaire du corpus
import argparse
import sys
import time
from pathlib import Path

from app.config import get_settings
from app.embeddings import Embedder, EmbeddingError
from app.ingest.inventory import InventoryError, check_corpus, load_inventory
from app.ingest.pipeline import ingest_corpus
from app.store import StoreError, VectorStore

INVENTORY = "inventaire.csv"


def main() -> int:
    settings = get_settings()
    parser = argparse.ArgumentParser(description="Indexation du corpus de navigation")
    parser.add_argument("--corpus-dir", type=Path, default=Path("../corpus"))
    parser.add_argument("--corpus", default=settings.default_corpus, help="nom de la collection Qdrant")
    parser.add_argument("--reset", action="store_true", help="supprime la collection avant d'indexer")
    parser.add_argument("--force", action="store_true", help="recalcule aussi les documents inchangés")
    args = parser.parse_args()

    try:
        entries = load_inventory(args.corpus_dir / INVENTORY)
    except (OSError, InventoryError) as e:
        print(f"Liste du corpus illisible, {e}", file=sys.stderr)
        return 1
    check = check_corpus(args.corpus_dir, entries, ignored={INVENTORY})
    for name in check.unlisted:
        print(f"  non listé {name}, ignoré")
    entries = [e for e in entries if e.file not in check.missing]

    store = VectorStore.from_settings(settings)
    started = time.time()
    try:
        if args.reset:
            store.drop(args.corpus)
            print(f"Collection {args.corpus} supprimée")
        print(f"Indexation de {len(entries)} document(s) dans {args.corpus}, embeddings {settings.embed_model}")
        report = ingest_corpus(args.corpus_dir, entries, args.corpus, settings, Embedder(settings), store,
                               force=args.force)
    except (EmbeddingError, StoreError) as e:
        print(f"Indexation interrompue, {e}", file=sys.stderr)
        return 2
    for name in check.missing:
        print(f"  ABSENT    {name}, listé mais introuvable")

    print(f"\n{len(report.indexed)} indexé(s), {len(report.unchanged)} inchangé(s), {len(report.failed)} en échec, "
          f"{len(report.removed)} retiré(s), {store.count(args.corpus)} passages dans l'index, "
          f"{time.time() - started:.1f} s")
    return 0 if not report.failed and not check.missing else 1


if __name__ == "__main__":
    sys.exit(main())
