# backend/app/routers/chat.py
# Question à l'assistant (EF1 à EF4, EF6), réponse complète ou en continu, pour un compte ou une clé de service
import json
import time
from collections.abc import Iterator
from dataclasses import replace

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import StreamingResponse

from app.config import Settings
from app.deps import Caller, app_settings, event_log, require_caller
from app.embeddings import EmbeddingError
from app.events import EventLog, current_request, exception_detail
from app.llm import LLMError
from app.models import EventCategory
from app.rag import Assistant, RagAnswer
from app.schemas import ChatIn, ChatOut, ErrorOut, SourceOut
from app.store import Hit, StoreError

router = APIRouter(tags=["Assistant"])
FAILURES = (EmbeddingError, LLMError, StoreError)
RESPONSES = {401: {"model": ErrorOut}, 404: {"model": ErrorOut}, 422: {"model": ErrorOut}, 429: {"model": ErrorOut},
             503: {"model": ErrorOut}}


def _source(hit: Hit) -> SourceOut:
    p = hit.payload
    return SourceOut(document_id=p.get("document_id", ""), document=p.get("document", ""), title=p.get("title", ""),
                     section=p.get("section", ""), page=p.get("page"), version=p.get("version", ""),
                     score=round(hit.score, 4))


def _out(result: RagAnswer) -> ChatOut:
    return ChatOut(answer=result.answer, found=result.found, sources=[_source(h) for h in result.sources])


def _prepare(body: ChatIn, request: Request, caller: Caller, settings: Settings) -> tuple[Assistant, str]:
    wait = request.app.state.limiters["chat"].retry_after(f"{caller.kind}:{caller.id}")
    if wait is not None:
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "Trop de questions, réessayer dans un instant",
                            headers={"Retry-After": str(wait)})
    question = body.message.strip()
    if not question or len(question) > settings.max_question_chars:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT,
                            f"La question doit compter entre 1 et {settings.max_question_chars} caractères")
    assistant: Assistant = request.app.state.assistant
    if not assistant.store.exists(body.corpus):
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Le corpus {body.corpus} n'est pas indexé")
    return assistant, question


def _record_failure(events: EventLog, question: str, error: Exception) -> str:
    events.error(EventCategory.CHAT, "chat_echec", f"assistant indisponible, {error}",
                 detail=f"Question {question[:300]}\n\n{exception_detail(error)}", status_code=503)
    ctx = current_request.get()
    return f"Assistant momentanément indisponible, référence {ctx.request_id if ctx else 'inconnue'}"


def _record_answer(events: EventLog, result: RagAnswer, started: float) -> None:
    events.info(EventCategory.CHAT, "question", f"{'réponse' if result.found else 'refus'}, "
                f"{len(result.sources)} source(s), {time.monotonic() - started:.1f} s")


@router.post("/chat", response_model=ChatOut, summary="Poser une question sur le projet GANDAL",
             description="Répond à partir des documents du corpus en citant ses sources. Si l'information est absente, "
                         "found vaut false et la réponse le dit. Accessible avec un compte (Authorize) ou une clé de "
                         "service dans l'en-tête X-API-Key.", responses=RESPONSES)
def chat(body: ChatIn, request: Request, caller: Caller = Depends(require_caller),
         settings: Settings = Depends(app_settings), events: EventLog = Depends(event_log)) -> ChatOut:
    assistant, question = _prepare(body, request, caller, settings)
    started = time.monotonic()
    try:
        result = assistant.ask(question, body.corpus, body.top_k)
    except FAILURES as e:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, _record_failure(events, question, e))
    _record_answer(events, result, started)
    return _out(result)


def _sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


@router.post("/chat/stream", summary="Poser une question, réponse en continu",
             description="Même question que /chat, réponse en Server-Sent Events. Événements statut (recherche puis "
                         "redaction), texte (morceau de réponse), fin (réponse finale au format de /chat, citations "
                         "vérifiées) ou erreur (message et référence).", responses=RESPONSES)
def chat_stream(body: ChatIn, request: Request, caller: Caller = Depends(require_caller),
                settings: Settings = Depends(app_settings), events: EventLog = Depends(event_log)) -> StreamingResponse:
    assistant, question = _prepare(body, request, caller, settings)
    ctx = current_request.get()
    snapshot = replace(ctx) if ctx else None

    def stream() -> Iterator[str]:
        # Chaque morceau du flux peut tourner dans un autre contexte, on replace celui de la requête avant le journal
        started = time.monotonic()
        try:
            for kind, data in assistant.ask_stream(question, body.corpus, body.top_k):
                if kind == "fin":
                    current_request.set(snapshot)
                    _record_answer(events, data, started)
                    yield _sse("fin", _out(data).model_dump())
                else:
                    yield _sse(kind, {"texte": data} if kind == "texte" else {"etape": data})
        except FAILURES as e:
            current_request.set(snapshot)
            yield _sse("erreur", {"detail": _record_failure(events, question, e),
                                  "request_id": snapshot.request_id if snapshot else None})

    return StreamingResponse(stream(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})
