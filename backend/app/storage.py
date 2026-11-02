# backend/app/storage.py
# Fichiers des documents, un dossier par version (empreinte) pour garder l'ancienne jusqu'à l'indexation de la nouvelle
import hashlib
import re
import shutil
import unicodedata
from pathlib import Path
from typing import BinaryIO

CHUNK_BYTES = 1024 * 1024
_UNSAFE = re.compile(r"[^\w.\- ()]+")


class UploadTooLarge(ValueError):
    pass


def safe_filename(name: str) -> str:
    base = unicodedata.normalize("NFC", Path(name.replace("\\", "/")).name).strip()
    base = _UNSAFE.sub("_", base).lstrip(".").strip()
    stem, dot, ext = base.rpartition(".")
    if not dot:
        stem, ext = base, ""
    stem = stem[:150] or "document"
    return f"{stem}.{ext.lower()}" if ext else stem


def save_version(source: BinaryIO, document_dir: Path, filename: str, max_bytes: int) -> tuple[Path, str, int]:
    document_dir.mkdir(parents=True, exist_ok=True)
    temp = document_dir / ".envoi-en-cours"
    digest, size = hashlib.sha256(), 0
    try:
        with temp.open("wb") as out:
            while block := source.read(CHUNK_BYTES):
                size += len(block)
                if size > max_bytes:
                    raise UploadTooLarge(f"fichier plus grand que {max_bytes // (1024 * 1024)} Mo")
                digest.update(block)
                out.write(block)
        sha256 = digest.hexdigest()
        target = document_dir / sha256[:16] / filename
        target.parent.mkdir(parents=True, exist_ok=True)
        temp.replace(target)
        return target, sha256, size
    finally:
        temp.unlink(missing_ok=True)


def remove_other_versions(document_dir: Path, keep: Path) -> None:
    for version_dir in document_dir.iterdir():
        if version_dir.is_dir() and version_dir != keep.parent:
            shutil.rmtree(version_dir, ignore_errors=True)


def remove_document(document_dir: Path) -> None:
    shutil.rmtree(document_dir, ignore_errors=True)
