# backend/app/ingest/inventory.py
# Liste du corpus (Chapitre 2, section 1.3), un document de référence par ligne avec source, version et date
import csv
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

COLUMNS = ["fichier", "titre", "source", "version", "date"]


class InventoryError(ValueError):
    pass


@dataclass(frozen=True)
class Entry:
    file: str
    title: str
    source: str
    version: str
    date: date


@dataclass
class InventoryCheck:
    missing: list[str] = field(default_factory=list)
    unlisted: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.missing and not self.unlisted


def load_inventory(path: Path) -> list[Entry]:
    with path.open(encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f, delimiter=";")
        if reader.fieldnames != COLUMNS:
            raise InventoryError(f"{path.name} doit avoir les colonnes {';'.join(COLUMNS)}")
        entries, seen = [], set()
        for n, row in enumerate(reader, start=2):
            values = {k: (v or "").strip() for k, v in row.items()}
            if not all(values.values()):
                raise InventoryError(f"{path.name} ligne {n}, toutes les colonnes sont obligatoires")
            if values["fichier"] in seen:
                raise InventoryError(f"{path.name} ligne {n}, {values['fichier']} est déjà listé")
            try:
                day = date.fromisoformat(values["date"])
            except ValueError as e:
                raise InventoryError(f"{path.name} ligne {n}, date attendue au format AAAA-MM-JJ") from e
            seen.add(values["fichier"])
            entries.append(Entry(values["fichier"], values["titre"], values["source"], values["version"], day))
    return entries


def check_corpus(root: Path, entries: list[Entry], ignored: set[str]) -> InventoryCheck:
    listed = {e.file for e in entries}
    present = {p.relative_to(root).as_posix() for p in root.rglob("*") if p.is_file()} - ignored
    return InventoryCheck(missing=sorted(listed - present), unlisted=sorted(present - listed))
