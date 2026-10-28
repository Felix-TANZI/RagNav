# backend/scripts/inspect_corpus.py
# Contrôle du corpus avant indexation, lecture et découpage de chaque document sans modèle ni index
import argparse
import sys
from pathlib import Path

from app.config import get_settings
from app.ingest.base import ConversionError, ConvertOptions
from app.ingest.chunker import chunk_document
from app.ingest.convert import convert
from app.ingest.inventory import InventoryError, check_corpus, load_inventory

INVENTORY = "inventaire.csv"


def main() -> int:
    parser = argparse.ArgumentParser(description="Contrôle du corpus de navigation")
    parser.add_argument("--corpus", type=Path, default=Path("../corpus"))
    parser.add_argument("--detail", type=Path, help="fichier Markdown où écrire tous les passages")
    args = parser.parse_args()
    settings = get_settings()

    try:
        entries = load_inventory(args.corpus / INVENTORY)
    except (OSError, InventoryError) as e:
        print(f"Liste du corpus illisible, {e}", file=sys.stderr)
        return 1
    check = check_corpus(args.corpus, entries, ignored={INVENTORY})
    for name in check.missing:
        print(f"ABSENT     {name} est listé mais introuvable")
    for name in check.unlisted:
        print(f"NON LISTÉ  {name} est présent mais absent de {INVENTORY}, il ne sera pas indexé")

    print(f"\n{'Document':<40} {'Version':>7} {'Pages':>5} {'Sections':>8} {'Passages':>8} {'Mots moy.':>9} {'max':>5}")
    detail, failures, total = ["# Aperçu des passages"], 0, 0
    for entry in entries:
        if entry.file in check.missing:
            continue
        try:
            pages = convert(args.corpus / entry.file, ConvertOptions.from_settings(settings))
        except ConversionError as e:
            print(f"{entry.file:<40} ERREUR {e}")
            failures += 1
            continue
        chunks = chunk_document(entry.file, pages, settings.chunk_words, settings.chunk_overlap_words, entry.title)
        words = [c.words for c in chunks] or [0]
        page_count = len({p.number for p in pages if p.number}) or "-"
        sections = len({c.section_path for c in chunks})
        print(f"{entry.file:<40} {entry.version:>7} {page_count:>5} {sections:>8} {len(chunks):>8}"
              f" {sum(words) // len(words):>9} {max(words):>5}")
        total += len(chunks)
        detail.append(f"\n## {entry.file}, {entry.title}, version {entry.version}")
        for c in chunks:
            where = f", page {c.page}" if c.page else ""
            detail.append(f"\n### Passage {c.index}, {c.section_path or 'sans titre'}{where}, {c.words} mots\n\n{c.text}")

    print(f"\n{len(entries) - len(check.missing) - failures} document(s) lisible(s), {total} passages")
    if args.detail:
        args.detail.write_text("\n".join(detail) + "\n", encoding="utf-8")
        print(f"Détail écrit dans {args.detail}")
    return 0 if check.ok and not failures else 1


if __name__ == "__main__":
    sys.exit(main())
