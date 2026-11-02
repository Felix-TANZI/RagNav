# backend/app/routers/events.py
# Journal consultable par les admins, une erreur se retrouve par sa référence de requête ou par document
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.deps import db_session, require_admin
from app.models import Event, EventCategory, EventLevel, User
from app.schemas import ErrorOut, EventDetailOut, EventOut

router = APIRouter(prefix="/admin/events", tags=["Journal"],
                   responses={401: {"model": ErrorOut}, 403: {"model": ErrorOut}})


@router.get("", response_model=list[EventOut], summary="Lister les événements, du plus récent au plus ancien")
def list_events(level: EventLevel | None = None, category: EventCategory | None = None,
                document_id: str | None = None, request_id: str | None = None,
                limit: int = Query(default=100, ge=1, le=500), offset: int = Query(default=0, ge=0),
                session: Session = Depends(db_session), _: User = Depends(require_admin)) -> list[Event]:
    query = select(Event).order_by(Event.created_at.desc())
    for column, value in ((Event.level, level), (Event.category, category), (Event.document_id, document_id),
                          (Event.request_id, request_id)):
        if value is not None:
            query = query.where(column == value)
    return list(session.scalars(query.limit(limit).offset(offset)))


@router.get("/{event_id}", response_model=EventDetailOut, summary="Consulter un événement et son détail technique",
            responses={404: {"model": ErrorOut}})
def get_event(event_id: str, session: Session = Depends(db_session), _: User = Depends(require_admin)) -> Event:
    event = session.get(Event, event_id)
    if event is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Événement introuvable")
    return event
