# backend/app/routers/library.py
# Documents consultables par tout appelant connecté, pour vérifier une source citée (EF3)
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import Settings
from app.deps import Caller, app_settings, db_session, require_caller
from app.models import Document, DocumentStatus
from app.schemas import ErrorOut, LibraryDocumentOut

router = APIRouter(prefix="/documents", tags=["Documentation"], responses={401: {"model": ErrorOut}})


@router.get("", response_model=list[LibraryDocumentOut], summary="Lister les documents consultables")
def list_library(session: Session = Depends(db_session), _: Caller = Depends(require_caller)) -> list[Document]:
    query = select(Document).where(Document.status == DocumentStatus.INDEXED).order_by(Document.title)
    return list(session.scalars(query))


@router.get("/{document_id}/file", response_class=FileResponse, summary="Ouvrir un document",
            responses={404: {"model": ErrorOut}})
def open_document(document_id: str, session: Session = Depends(db_session), settings: Settings = Depends(app_settings),
                  _: Caller = Depends(require_caller)) -> FileResponse:
    doc = session.get(Document, document_id)
    if doc is None or doc.status != DocumentStatus.INDEXED:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Document introuvable ou pas encore consultable")
    return FileResponse(settings.document_path(doc.storage_path), filename=doc.filename,
                        content_disposition_type="inline")
