# backend/app/ingest/pipeline.py
# Chaîne d'indexation (Chapitre 2, section 3.2), un document inchangé n'est pas recalculé
import hashlib
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from qdrant_client import models as qm

from app.config import Settings
from app.embeddings import Embedder
from app.ingest.base import ConversionError, ConvertOptions
from app.ingest.chunker import Chunk, chunk_document
from app.ingest.convert import convert
from app.store import DENSE, VectorStore

PIPELINE_VERSION = "2"


@dataclass(frozen=True)
class DocumentSource:
    id: str
    filename: str
    title: str
    source: str
    version: str
    date: date
    path: Path


@dataclass(frozen=True)
class IndexResult:
    chunks: int
    ocr_pages: int


def content_hash(doc: DocumentSource, settings: Settings) -> str:
    digest = hashlib.sha256(doc.path.read_bytes())
    digest.update("|".join([doc.filename, doc.title, doc.source, doc.version, doc.date.isoformat(),
                            settings.embed_model, str(settings.chunk_words), str(settings.chunk_overlap_words),
                            settings.ocr_language, PIPELINE_VERSION]).encode())
    return digest.hexdigest()


def embedding_text(doc: DocumentSource, chunk: Chunk) -> str:
    headings = list(chunk.headings)
    if headings and headings[0] == doc.title:
        headings = headings[1:]
    return f"{' > '.join([doc.title, *headings])}\n\n{chunk.text}"


def _point(doc: DocumentSource, chunk: Chunk, digest: str, vector: list[float], ocr: bool) -> qm.PointStruct:
    return qm.PointStruct(
        id=str(uuid.uuid5(uuid.NAMESPACE_URL, f"gandal://{doc.id}#{digest}#{chunk.index}")),
        vector={DENSE: vector},
        payload={
            "document_id": doc.id, "document": doc.filename, "title": doc.title, "source": doc.source,
            "version": doc.version, "date": doc.date.isoformat(), "section": chunk.section,
            "section_path": chunk.section_path, "page": chunk.page, "chunk_index": chunk.index,
            "text": chunk.text, "ocr": ocr, "content_hash": digest,
        },
    )


def index_document(doc: DocumentSource, corpus: str, settings: Settings, embedder: Embedder, store: VectorStore,
                   force: bool = False, on_stage: Callable[[str], None] = lambda _: None) -> IndexResult | None:
    on_stage("Vérification de l'index")
    digest = content_hash(doc, settings)
    if not force and store.has_version(corpus, doc.id, digest):
        return None
    on_stage("Lecture du document")
    pages = convert(doc.path, ConvertOptions.from_settings(settings))
    on_stage("Découpage en passages")
    chunks = chunk_document(doc.filename, pages, settings.chunk_words, settings.chunk_overlap_words, doc.title)
    if not chunks:
        raise ConversionError("aucun passage exploitable après découpage")
    on_stage("Calcul des embeddings")
    vectors = embedder.embed([embedding_text(doc, c) for c in chunks])
    on_stage("Écriture dans l'index")
    store.ensure_collection(corpus, len(vectors[0]), settings.embed_model)
    ocr_pages = {p.number for p in pages if p.ocr}
    store.replace_document(corpus, doc.id, digest, [_point(doc, c, digest, v, c.page in ocr_pages)
                                                    for c, v in zip(chunks, vectors, strict=True)])
    return IndexResult(len(chunks), len(ocr_pages))
