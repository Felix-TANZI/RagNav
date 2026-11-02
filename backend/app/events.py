# backend/app/events.py
# Journal d'événements consultable par les admins (OWASP), jamais de mot de passe, de jeton ni de clé dedans
import logging
import traceback
from contextvars import ContextVar
from dataclasses import dataclass
from datetime import timedelta

from sqlalchemy import delete
from sqlalchemy.orm import Session, sessionmaker

from app.models import Event, EventCategory, EventLevel, utcnow


@dataclass
class RequestContext:
    request_id: str
    ip: str | None = None
    method: str | None = None
    path: str | None = None
    actor: str | None = None


current_request: ContextVar[RequestContext | None] = ContextVar("current_request", default=None)
log = logging.getLogger("gandal")
_LOG_LEVELS = {EventLevel.INFO: logging.INFO, EventLevel.WARNING: logging.WARNING, EventLevel.ERROR: logging.ERROR}


def exception_detail(error: BaseException) -> str:
    return "".join(traceback.format_exception(error)).strip()


class EventLog:
    def __init__(self, sessions: sessionmaker[Session]):
        self.sessions = sessions

    def record(self, level: EventLevel, category: EventCategory, action: str, message: str, *,
               detail: str | None = None, document_id: str | None = None, actor: str | None = None,
               status_code: int | None = None) -> str:
        ctx = current_request.get()
        event = Event(level=level, category=category, action=action, message=message, detail=detail,
                      document_id=document_id, status_code=status_code,
                      actor=actor or (ctx.actor if ctx else "système"),
                      ip=ctx.ip if ctx else None, method=ctx.method if ctx else None, path=ctx.path if ctx else None,
                      request_id=ctx.request_id if ctx else None)
        try:
            with self.sessions() as session:
                session.add(event)
                session.commit()
        except Exception:
            log.exception("écriture du journal impossible")
        log.log(_LOG_LEVELS[level], "[%s] %s %s %s", event.request_id or "-", category.value, action, message)
        return event.id

    def info(self, category: EventCategory, action: str, message: str, **kwargs) -> str:
        return self.record(EventLevel.INFO, category, action, message, **kwargs)

    def warning(self, category: EventCategory, action: str, message: str, **kwargs) -> str:
        return self.record(EventLevel.WARNING, category, action, message, **kwargs)

    def error(self, category: EventCategory, action: str, message: str, **kwargs) -> str:
        return self.record(EventLevel.ERROR, category, action, message, **kwargs)

    def prune(self, retention_days: int) -> int:
        with self.sessions() as session:
            result = session.execute(delete(Event).where(Event.created_at < utcnow() - timedelta(days=retention_days)))
            session.commit()
            return result.rowcount
