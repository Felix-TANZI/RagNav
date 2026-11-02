# backend/app/routers/service_keys.py
# Clés des applications qui appellent /chat, seule leur empreinte est gardée, la clé n'est montrée qu'une fois
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.deps import db_session, event_log, require_admin
from app.events import EventLog
from app.models import EventCategory, ServiceKey, User, utcnow
from app.schemas import ErrorOut, ServiceKeyCreated, ServiceKeyCreateIn, ServiceKeyOut
from app.security import digest, new_service_key

router = APIRouter(prefix="/admin/service-keys", tags=["Clés de service"],
                   responses={401: {"model": ErrorOut}, 403: {"model": ErrorOut}})


@router.get("", response_model=list[ServiceKeyOut], summary="Lister les clés de service")
def list_keys(session: Session = Depends(db_session), _: User = Depends(require_admin)) -> list[ServiceKey]:
    return list(session.scalars(select(ServiceKey).order_by(ServiceKey.created_at.desc())))


@router.post("", response_model=ServiceKeyCreated, status_code=status.HTTP_201_CREATED,
             summary="Créer une clé de service", responses={409: {"model": ErrorOut}})
def create_key(body: ServiceKeyCreateIn, session: Session = Depends(db_session), events: EventLog = Depends(event_log),
               admin: User = Depends(require_admin)) -> ServiceKeyCreated:
    name = body.name.strip()
    if session.scalar(select(ServiceKey.id).where(ServiceKey.name == name)):
        raise HTTPException(status.HTTP_409_CONFLICT, "Une clé porte déjà ce nom")
    raw = new_service_key()
    key = ServiceKey(name=name, prefix=raw[:12], key_hash=digest(raw), created_by=admin.id)
    session.add(key)
    session.commit()
    events.info(EventCategory.CLES, "cle_creee", f"clé de service {name} créée ({key.prefix})")
    return ServiceKeyCreated(**ServiceKeyOut.model_validate(key).model_dump(), key=raw)


@router.delete("/{key_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Révoquer une clé de service",
               responses={404: {"model": ErrorOut}})
def revoke_key(key_id: str, session: Session = Depends(db_session), events: EventLog = Depends(event_log),
               _: User = Depends(require_admin)) -> None:
    key = session.get(ServiceKey, key_id)
    if key is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Clé introuvable")
    if key.revoked_at is None:
        key.revoked_at = utcnow()
        session.commit()
        events.info(EventCategory.CLES, "cle_revoquee", f"clé de service {key.name} révoquée")
