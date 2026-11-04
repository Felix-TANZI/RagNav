# backend/app/routers/chat.py
# Question à l'assistant (EF1 à EF4, EF6), pour un compte connecté ou une application munie d'une clé de service
import time

from fastapi import APIRouter, Depends, HTTPException, Request, status

from app.config import Settings
from app.deps import Caller, app_settings, event_log, require_caller
from app.embeddings import EmbeddingError
from app.events import EventLog, current_request, exception_detail
from app.llm import LLMError
from app.models import EventCategory
from app.rag import Assistant
from app.schemas import ChatIn, ChatOut, ErrorOut, SourceOut
from app.store import StoreError

router = APIRouter(tags=["Assistant"])


def _check_rate(request: Request, caller: Caller) -> None:
    wait = request.app.state.limiters["chat"].retry_after(f"{caller.kind}:{caller.id}")
    if wait is not None:
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "Trop de questions, réessayer dans un instant",
                            headers={"Retry-After": str(wait)})


@router.post("/chat", response_model=ChatOut, summary="Poser une question sur le projet GANDAL",
             description="Répond à partir des documents du corpus en citant ses sources. Si l'information est absente, "
                         "found vaut false et la réponse le dit. Accessible avec un compte (Authorize) ou une clé de "
                         "service dans l'en-tête X-API-Key.",
             responses={401: {"model": ErrorOut}, 404: {"model": ErrorOut}, 422: {"model": ErrorOut},
                        429: {"model": ErrorOut}, 503: {"model": ErrorOut}})
def chat(body: ChatIn, request: Request, caller: Caller = Depends(require_caller),
         settings: Settings = Depends(app_settings), events: EventLog = Depends(event_log)) -> ChatOut:
    _check_rate(request, caller)
    question = body.message.strip()
    if not question or len(question) > settings.max_question_chars:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT,
                            f"La question doit compter entre 1 et {settings.max_question_chars} caractères")
    assistant: Assistant = request.app.state.assistant
    if not assistant.store.exists(body.corpus):
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Le corpus {body.corpus} n'est pas indexé")

    started = time.monotonic()
    try:
        result = assistant.ask(question, body.corpus, body.top_k)
    except (EmbeddingError, LLMError, StoreError) as e:
        events.error(EventCategory.CHAT, "chat_echec", f"assistant indisponible, {e}",
                     detail=f"Question {question[:300]}\n\n{exception_detail(e)}", status_code=503)
        ctx = current_request.get()
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Assistant momentanément indisponible, "
                            f"référence {ctx.request_id if ctx else 'inconnue'}")
    events.info(EventCategory.CHAT, "question", f"{'réponse' if result.found else 'refus'}, "
                f"{len(result.sources)} source(s), {time.monotonic() - started:.1f} s")
    return ChatOut(answer=result.answer, found=result.found, sources=[
        SourceOut(document=h.payload.get("document", ""), title=h.payload.get("title", ""),
                  section=h.payload.get("section", ""), page=h.payload.get("page"),
                  version=h.payload.get("version", ""), score=round(h.score, 4)) for h in result.sources])
