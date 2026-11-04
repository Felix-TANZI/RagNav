# backend/app/worker.py
# File d'indexation à un seul fil, chaque étape est suivie pour que l'admin voie où et pourquoi un échec survient
import contextvars
import time
from concurrent.futures import Future, ThreadPoolExecutor

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app import storage
from app.config import Settings
from app.embeddings import Embedder, EmbeddingError
from app.events import EventLog, exception_detail
from app.ingest.base import ConversionError
from app.ingest.pipeline import DocumentSource, index_document
from app.models import Document, DocumentStatus, EventCategory, utcnow
from app.store import StoreError, VectorStore

INDEXATION = EventCategory.INDEXATION


def document_source(doc: Document, settings: Settings) -> DocumentSource:
    return DocumentSource(doc.id, doc.filename, doc.title, doc.source, doc.version, doc.document_date,
                          settings.document_path(doc.storage_path))


def _cause(error: Exception) -> str:
    if isinstance(error, (EmbeddingError, StoreError)):
        return f"service indisponible, {error}"
    if isinstance(error, (ConversionError, OSError)):
        return str(error)
    return f"erreur inattendue ({type(error).__name__}, {error})"


class IndexWorker:
    def __init__(self, sessions: sessionmaker[Session], settings: Settings, embedder: Embedder, store: VectorStore,
                 events: EventLog):
        self.sessions, self.settings, self.embedder, self.store, self.events = (sessions, settings, embedder, store,
                                                                                events)
        self.corpus = settings.default_corpus
        self._executor: ThreadPoolExecutor | None = None

    def start(self) -> None:
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="indexation")

    def stop(self) -> None:
        if self._executor:
            self._executor.shutdown(wait=True, cancel_futures=True)
            self._executor = None

    def _submit(self, fn, *args) -> Future:
        return self._executor.submit(contextvars.copy_context().run, fn, *args)

    def wait_idle(self, timeout: float | None = None) -> None:
        self._executor.submit(lambda: None).result(timeout)

    def submit_index(self, document_id: str, force: bool = False) -> Future:
        return self._submit(self.index_now, document_id, force)

    def submit_delete(self, document_id: str) -> Future:
        return self._submit(self.delete_now, document_id)

    def recover(self) -> int:
        with self.sessions() as session:
            docs = session.scalars(select(Document).where(Document.status.in_(
                [DocumentStatus.PENDING, DocumentStatus.INDEXING, DocumentStatus.DELETING]))).all()
        for doc in docs:
            if doc.status == DocumentStatus.DELETING:
                self.submit_delete(doc.id)
            else:
                self.submit_index(doc.id)
        if docs:
            self.events.info(EventCategory.SYSTEME, "reprise_file", f"{len(docs)} tâche(s) reprise(s) au démarrage")
        return len(docs)

    def index_now(self, document_id: str, force: bool = False) -> None:
        with self.sessions() as session:
            doc = session.get(Document, document_id)
            if doc is None or doc.status == DocumentStatus.DELETING:
                return
            doc.status, doc.error = DocumentStatus.INDEXING, None
            session.commit()
            started = (doc.storage_path, doc.title, doc.source, doc.version, doc.document_date)
            stage, began = "Préparation", time.monotonic()

            def on_stage(name: str) -> None:
                nonlocal stage
                stage = name

            try:
                result = index_document(document_source(doc, self.settings), self.corpus, self.settings, self.embedder, self.store,
                                        force, on_stage)
            except Exception as e:
                doc.status, doc.error = DocumentStatus.FAILED, f"{stage}, {_cause(e)}"
                session.commit()
                self.events.error(INDEXATION, "indexation_echec", f"{doc.filename}, échec à l'étape {stage}, "
                                  f"{_cause(e)}", detail=exception_detail(e), document_id=doc.id)
                return
            session.refresh(doc)
            if (doc.storage_path, doc.title, doc.source, doc.version, doc.document_date) != started \
                    or doc.status == DocumentStatus.DELETING:
                return
            if result is not None:
                doc.chunks, doc.ocr_pages = result.chunks, result.ocr_pages
            doc.status, doc.indexed_at = DocumentStatus.INDEXED, utcnow()
            session.commit()
            storage.remove_other_versions(self.settings.documents_dir / doc.id,
                                          self.settings.document_path(doc.storage_path))
            if result is None:
                self.events.info(INDEXATION, "indexation_inchangee", f"{doc.filename}, déjà à jour dans l'index",
                                 document_id=doc.id)
            else:
                self.events.info(INDEXATION, "indexation_ok", f"{doc.filename}, {result.chunks} passages, "
                                 f"{result.ocr_pages} page(s) OCR, {time.monotonic() - began:.1f} s", document_id=doc.id)

    def delete_now(self, document_id: str) -> None:
        with self.sessions() as session:
            doc = session.get(Document, document_id)
            if doc is None:
                return
            try:
                self.store.delete_document(self.corpus, doc.id)
            except Exception as e:
                doc.status, doc.error = DocumentStatus.FAILED, f"Suppression, {_cause(e)}"
                session.commit()
                self.events.error(INDEXATION, "suppression_echec", f"{doc.filename}, retrait de l'index impossible, "
                                  f"{_cause(e)}", detail=exception_detail(e), document_id=doc.id)
                return
            storage.remove_document(self.settings.documents_dir / doc.id)
            session.delete(doc)
            session.commit()
            self.events.info(EventCategory.DOCUMENTS, "document_supprime", f"{doc.filename} supprimé du corpus",
                             document_id=document_id)
