# backend/app/routers/documents.py
# Documents du corpus gérés par les admins (CU5), l'indexation se fait en arrière-plan par la file d'indexation
from datetime import date
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import storage
from app.config import Settings
from app.deps import app_settings, db_session, event_log, require_admin
from app.events import EventLog
from app.ingest.convert import SUPPORTED_FORMATS
from app.models import Document, DocumentStatus, EventCategory, User, new_id
from app.schemas import DocumentOut, DocumentUpdateIn, ErrorOut, FormatsOut

DOCS = EventCategory.DOCUMENTS
router = APIRouter(prefix="/admin/documents", tags=["Documents"],
                   responses={401: {"model": ErrorOut}, 403: {"model": ErrorOut}})


def _get(session: Session, document_id: str) -> Document:
    doc = session.get(Document, document_id)
    if doc is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Document introuvable")
    if doc.status == DocumentStatus.DELETING:
        raise HTTPException(status.HTTP_409_CONFLICT, "Document en cours de suppression")
    return doc


def _store_upload(upload: UploadFile, document_id: str, settings: Settings) -> tuple[str, Path, str, int]:
    filename = storage.safe_filename(upload.filename or "")
    if Path(filename).suffix.lower() not in SUPPORTED_FORMATS:
        raise HTTPException(status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
                            f"Format {Path(filename).suffix or 'sans extension'} non pris en charge")
    try:
        path, sha256, size = storage.save_version(upload.file, settings.documents_dir / document_id, filename,
                                                  settings.max_upload_mb * 1024 * 1024)
    except storage.UploadTooLarge as e:
        raise HTTPException(status.HTTP_413_CONTENT_TOO_LARGE, str(e))
    return filename, path, sha256, size


def _check_duplicate(session: Session, sha256: str, document_id: str) -> None:
    other = session.scalar(select(Document).where(Document.sha256 == sha256, Document.id != document_id))
    if other is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, f"Ce fichier est déjà dans le corpus ({other.title})")


@router.get("/formats", response_model=FormatsOut, summary="Formats acceptés et taille maximale")
def formats(settings: Settings = Depends(app_settings), _: User = Depends(require_admin)) -> FormatsOut:
    return FormatsOut(extensions=sorted(SUPPORTED_FORMATS), max_upload_mb=settings.max_upload_mb)


@router.get("", response_model=list[DocumentOut], summary="Lister les documents du corpus")
def list_documents(session: Session = Depends(db_session), _: User = Depends(require_admin)) -> list[Document]:
    return list(session.scalars(select(Document).order_by(Document.created_at.desc())))


@router.post("", response_model=DocumentOut, status_code=status.HTTP_202_ACCEPTED, summary="Ajouter un document",
             description="Le document est enregistré puis indexé en arrière-plan, suivre son statut avec GET.",
             responses={409: {"model": ErrorOut}, 413: {"model": ErrorOut}, 415: {"model": ErrorOut}})
def upload_document(request: Request, file: UploadFile = File(...), title: str = Form(min_length=1, max_length=255),
                    source: str = Form(min_length=1, max_length=255), version: str = Form(min_length=1, max_length=50),
                    document_date: date = Form(), session: Session = Depends(db_session),
                    settings: Settings = Depends(app_settings), events: EventLog = Depends(event_log),
                    admin: User = Depends(require_admin)) -> Document:
    document_id = new_id()
    try:
        filename, path, sha256, size = _store_upload(file, document_id, settings)
        _check_duplicate(session, sha256, document_id)
    except HTTPException:
        storage.remove_document(settings.documents_dir / document_id)
        raise
    doc = Document(id=document_id, filename=filename, title=title.strip(), source=source.strip(),
                   version=version.strip(), document_date=document_date, sha256=sha256, size=size,
                   storage_path=str(path), uploaded_by=admin.id)
    session.add(doc)
    session.commit()
    events.info(DOCS, "document_ajoute", f"{doc.filename} ajouté ({doc.size} octets), indexation en attente",
                document_id=doc.id)
    request.app.state.worker.submit_index(doc.id)
    return doc


@router.get("/{document_id}", response_model=DocumentOut, summary="Consulter un document",
            responses={404: {"model": ErrorOut}})
def get_document(document_id: str, session: Session = Depends(db_session), _: User = Depends(require_admin)) -> Document:
    return _get(session, document_id)


@router.patch("/{document_id}", response_model=DocumentOut, status_code=status.HTTP_202_ACCEPTED,
              summary="Modifier les métadonnées", description="Le document est réindexé avec ses nouvelles métadonnées.",
              responses={404: {"model": ErrorOut}, 409: {"model": ErrorOut}})
def update_document(document_id: str, body: DocumentUpdateIn, request: Request, session: Session = Depends(db_session),
                    events: EventLog = Depends(event_log), _: User = Depends(require_admin)) -> Document:
    doc = _get(session, document_id)
    for field, value in body.model_dump(exclude_none=True).items():
        setattr(doc, field, value.strip() if isinstance(value, str) else value)
    doc.status, doc.error = DocumentStatus.PENDING, None
    session.commit()
    events.info(DOCS, "document_modifie", f"{doc.filename}, métadonnées modifiées "
                f"({', '.join(body.model_dump(exclude_none=True))})", document_id=doc.id)
    request.app.state.worker.submit_index(doc.id)
    return doc


@router.put("/{document_id}/file", response_model=DocumentOut, status_code=status.HTTP_202_ACCEPTED,
            summary="Remplacer le fichier", description="La version précédente reste interrogeable jusqu'à "
                                                        "l'indexation de la nouvelle.",
            responses={404: {"model": ErrorOut}, 409: {"model": ErrorOut}, 413: {"model": ErrorOut},
                       415: {"model": ErrorOut}})
def replace_file(document_id: str, request: Request, file: UploadFile = File(...),
                 version: str | None = Form(default=None, max_length=50), session: Session = Depends(db_session),
                 settings: Settings = Depends(app_settings), events: EventLog = Depends(event_log),
                 _: User = Depends(require_admin)) -> Document:
    doc = _get(session, document_id)
    filename, path, sha256, size = _store_upload(file, doc.id, settings)
    if sha256 == doc.sha256:
        raise HTTPException(status.HTTP_409_CONFLICT, "Ce fichier est identique à la version actuelle")
    try:
        _check_duplicate(session, sha256, doc.id)
    except HTTPException:
        storage.remove_other_versions(settings.documents_dir / doc.id, Path(doc.storage_path))
        raise
    doc.filename, doc.sha256, doc.size, doc.storage_path = filename, sha256, size, str(path)
    if version and version.strip():
        doc.version = version.strip()
    doc.status, doc.error = DocumentStatus.PENDING, None
    session.commit()
    events.info(DOCS, "fichier_remplace", f"{doc.title}, nouveau fichier {filename} ({size} octets)",
                document_id=doc.id)
    request.app.state.worker.submit_index(doc.id)
    return doc


@router.get("/{document_id}/file", response_class=FileResponse, summary="Télécharger le fichier d'origine",
            responses={404: {"model": ErrorOut}})
def download_file(document_id: str, session: Session = Depends(db_session),
                  _: User = Depends(require_admin)) -> FileResponse:
    doc = _get(session, document_id)
    return FileResponse(doc.storage_path, filename=doc.filename)


@router.post("/{document_id}/reindex", response_model=DocumentOut, status_code=status.HTTP_202_ACCEPTED,
             summary="Forcer la réindexation", responses={404: {"model": ErrorOut}, 409: {"model": ErrorOut}})
def reindex_document(document_id: str, request: Request, session: Session = Depends(db_session),
                     events: EventLog = Depends(event_log), _: User = Depends(require_admin)) -> Document:
    doc = _get(session, document_id)
    doc.status, doc.error = DocumentStatus.PENDING, None
    session.commit()
    events.info(DOCS, "reindexation_demandee", f"{doc.filename}, réindexation forcée", document_id=doc.id)
    request.app.state.worker.submit_index(doc.id, force=True)
    return doc


@router.delete("/{document_id}", status_code=status.HTTP_202_ACCEPTED, summary="Supprimer un document",
               description="Le document est retiré de l'index puis du disque en arrière-plan.",
               responses={404: {"model": ErrorOut}, 409: {"model": ErrorOut}})
def delete_document(document_id: str, request: Request, session: Session = Depends(db_session),
                    events: EventLog = Depends(event_log), _: User = Depends(require_admin)) -> None:
    doc = _get(session, document_id)
    doc.status = DocumentStatus.DELETING
    session.commit()
    events.info(DOCS, "suppression_demandee", f"{doc.filename}, suppression demandée", document_id=doc.id)
    request.app.state.worker.submit_delete(doc.id)
