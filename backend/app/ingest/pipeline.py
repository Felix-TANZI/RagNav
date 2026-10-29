# backend/app/ingest/pipeline.py
# Chaîne d'indexation (Chapitre 2, section 3.2), seuls les documents nouveaux ou modifiés sont recalculés
import hashlib
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from qdrant_client import models as qm

from app.config import Settings
from app.embeddings import Embedder
from app.ingest.base import ConversionError, ConvertOptions
from app.ingest.chunker import Chunk, chunk_document
from app.ingest.convert import convert
from app.ingest.inventory import Entry
from app.store import DENSE, VectorStore

PIPELINE_VERSION = "1"


@dataclass
class IngestReport:
    indexed: dict[str, int] = field(default_factory=dict)
    unchanged: list[str] = field(default_factory=list)
    failed: dict[str, str] = field(default_factory=dict)
    removed: list[str] = field(default_factory=list)


def content_hash(path: Path, settings: Settings) -> str:
    digest = hashlib.sha256(path.read_bytes())
    digest.update(f"|{settings.embed_model}|{settings.chunk_words}|{settings.chunk_overlap_words}|"
                  f"{settings.ocr_language}|{PIPELINE_VERSION}".encode())
    return digest.hexdigest()


def embedding_text(entry: Entry, chunk: Chunk) -> str:
    headings = list(chunk.headings)
    if headings and headings[0] == entry.title:
        headings = headings[1:]
    context = " > ".join([entry.title, *headings])
    return f"{context}\n\n{chunk.text}"


def _point(entry: Entry, chunk: Chunk, digest: str, vector: list[float], ocr_pages: set[int]) -> qm.PointStruct:
    return qm.PointStruct(
        id=str(uuid.uuid5(uuid.NAMESPACE_URL, f"gandal://{entry.file}#{digest}#{chunk.index}")),
        vector={DENSE: vector},
        payload={
            "document": entry.file, "title": entry.title, "source": entry.source, "version": entry.version,
            "date": entry.date.isoformat(), "section": chunk.section, "section_path": chunk.section_path,
            "page": chunk.page, "chunk_index": chunk.index, "text": chunk.text, "ocr": chunk.page in ocr_pages,
            "content_hash": digest,
        },
    )


def index_document(entry: Entry, path: Path, corpus: str, settings: Settings, embedder: Embedder,
                   store: VectorStore, force: bool = False) -> int | None:
    digest = content_hash(path, settings)
    if not force and store.has_version(corpus, entry.file, digest):
        return None
    pages = convert(path, ConvertOptions.from_settings(settings))
    chunks = chunk_document(entry.file, pages, settings.chunk_words, settings.chunk_overlap_words, entry.title)
    if not chunks:
        raise ConversionError("aucun passage exploitable après découpage")
    vectors = embedder.embed([embedding_text(entry, c) for c in chunks])
    store.ensure_collection(corpus, len(vectors[0]), settings.embed_model)
    ocr_pages = {p.number for p in pages if p.ocr}
    store.replace_document(corpus, entry.file, digest, [_point(entry, c, digest, v, ocr_pages)
                                                        for c, v in zip(chunks, vectors, strict=True)])
    return len(chunks)


def ingest_corpus(root: Path, entries: list[Entry], corpus: str, settings: Settings, embedder: Embedder,
                  store: VectorStore, force: bool = False, prune: bool = True,
                  log: Callable[[str], None] = print) -> IngestReport:
    report = IngestReport()
    for entry in entries:
        try:
            count = index_document(entry, root / entry.file, corpus, settings, embedder, store, force)
        except (ConversionError, OSError) as e:
            report.failed[entry.file] = str(e)
            log(f"  ÉCHEC     {entry.file}, {e}")
            continue
        if count is None:
            report.unchanged.append(entry.file)
            log(f"  inchangé  {entry.file}")
        else:
            report.indexed[entry.file] = count
            log(f"  indexé    {entry.file}, {count} passages")
    if prune:
        listed = {e.file for e in entries}
        for document in store.documents(corpus):
            if document not in listed:
                store.delete_document(corpus, document)
                report.removed.append(document)
                log(f"  retiré    {document}")
    return report
