# backend/app/main.py
# Fabrique d'application, lancée par uvicorn app.main:create_app --factory
import logging
import re
import uuid
from collections.abc import Iterator
from contextlib import asynccontextmanager

import httpx2 as httpx
from fastapi import Depends, FastAPI, Request
from fastapi.exception_handlers import request_validation_exception_handler
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app import __version__
from app.bootstrap import ensure_first_admin
from app.config import Settings, get_settings
from app.db import make_engine, make_session_factory
from app.deps import app_settings, client_ip
from app.embeddings import Embedder
from app.events import EventLog, RequestContext, current_request, exception_detail
from app.health import check_models, check_qdrant
from app.llm import ChatModel
from app.migrate import run_migrations
from app.models import EventCategory
from app.rag import Assistant
from app.ratelimit import RateLimiter
from app.routers import auth, chat, documents, events, service_keys, users
from app.store import VectorStore
from app.worker import IndexWorker

TAGS = [
    {"name": "Assistant", "description": "Questions sur le projet GANDAL, réponses citant leurs sources"},
    {"name": "Supervision", "description": "État du service et de ses dépendances"},
    {"name": "Authentification", "description": "Inscription des clients, connexion, session et mot de passe"},
    {"name": "Comptes", "description": "Gestion des comptes par les admins"},
    {"name": "Clés de service", "description": "Clés des applications qui appellent /chat (en-tête X-API-Key)"},
    {"name": "Documents", "description": "Corpus de navigation, ajout, remplacement, suppression et indexation"},
    {"name": "Journal", "description": "Événements, erreurs et actions sensibles, retrouvables par référence"},
]
_REQUEST_ID = re.compile(r"[A-Za-z0-9-]{8,64}")
_UPLOAD_PATHS = ("/admin/documents",)


def get_http(settings: Settings = Depends(app_settings)) -> Iterator[httpx.Client]:
    with httpx.Client(timeout=settings.health_timeout) as client:
        yield client


def health(settings: Settings = Depends(app_settings), http: httpx.Client = Depends(get_http)) -> dict:
    services = {"models": check_models(settings, http), "qdrant": check_qdrant(settings, http)}
    status = "ok" if all(s["ok"] for s in services.values()) else "degraded"
    return {"status": status, "version": __version__, "services": services}


def _with_request_id(response: JSONResponse) -> JSONResponse:
    ctx = current_request.get()
    if ctx is not None:
        response.headers["X-Request-ID"] = ctx.request_id
    return response


def create_app(settings: Settings | None = None, *, store: VectorStore | None = None,
               embedder: Embedder | None = None, model: ChatModel | None = None) -> FastAPI:
    settings = settings or get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
        logging.getLogger("httpx").setLevel(logging.WARNING)
        run_migrations(settings.database_url)
        engine = make_engine(settings.database_url)
        app.state.sessions = sessions = make_session_factory(engine)
        app.state.events = event_log = EventLog(sessions)
        with sessions() as session:
            if ensure_first_admin(session, settings):
                event_log.info(EventCategory.COMPTES, "premier_admin", f"premier admin {settings.admin_email} créé")
        event_log.prune(settings.events_retention_days)
        app.state.store = store or VectorStore.from_settings(settings)
        app.state.embedder = embedder or Embedder(settings)
        app.state.assistant = Assistant(settings, app.state.embedder, app.state.store, model or ChatModel(settings))
        app.state.worker = worker = IndexWorker(sessions, settings, app.state.embedder, app.state.store, event_log)
        worker.start()
        event_log.info(EventCategory.SYSTEME, "demarrage", f"GANDAL-AI {__version__} démarré")
        worker.recover()
        yield
        worker.stop()
        event_log.info(EventCategory.SYSTEME, "arret", f"GANDAL-AI {__version__} arrêté")
        engine.dispose()

    app = FastAPI(title="GANDAL-AI", version=__version__, lifespan=lifespan, openapi_tags=TAGS,
                  description="Assistant de navigation du projet GANDAL. Chaque réponse porte l'en-tête X-Request-ID, "
                              "à communiquer en cas d'erreur pour la retrouver dans le journal.")
    app.state.settings = settings
    app.state.limiters = {"login": RateLimiter(settings.login_per_minute, 60),
                          "register": RateLimiter(settings.register_per_hour, 3600),
                          "chat": RateLimiter(settings.chat_per_minute, 60)}

    @app.middleware("http")
    async def request_context(request: Request, call_next):
        incoming = request.headers.get("x-request-id", "")
        request_id = incoming if _REQUEST_ID.fullmatch(incoming) else uuid.uuid4().hex
        token = current_request.set(RequestContext(request_id, client_ip(request), request.method, request.url.path))
        try:
            length = int(request.headers.get("content-length") or 0)
            if request.method in ("POST", "PUT") and request.url.path.startswith(_UPLOAD_PATHS) \
                    and length > (settings.max_upload_mb + 1) * 1024 * 1024:
                response = JSONResponse({"detail": f"Fichier plus grand que {settings.max_upload_mb} Mo",
                                         "request_id": request_id}, status_code=413)
            else:
                response = await call_next(request)
        except Exception as e:
            request.app.state.events.error(EventCategory.API, "erreur_interne", f"{type(e).__name__}, {e}",
                                           detail=exception_detail(e), status_code=500)
            response = JSONResponse({"detail": f"Erreur interne, référence {request_id}", "request_id": request_id},
                                    status_code=500)
        finally:
            current_request.reset(token)
        response.headers["X-Request-ID"] = request_id
        return response

    @app.exception_handler(StarletteHTTPException)
    async def http_error(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        ctx = current_request.get()
        if exc.status_code in (403, 429):
            action = "acces_refuse" if exc.status_code == 403 else "limite_atteinte"
            request.app.state.events.warning(EventCategory.API, action, str(exc.detail), status_code=exc.status_code)
        return _with_request_id(JSONResponse({"detail": exc.detail, "request_id": ctx.request_id if ctx else None},
                                             status_code=exc.status_code, headers=exc.headers))

    @app.exception_handler(RequestValidationError)
    async def validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
        return _with_request_id(await request_validation_exception_handler(request, exc))

    app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origins, allow_credentials=True,
                       allow_methods=["*"], allow_headers=["*"], expose_headers=["X-Request-ID"])
    app.add_api_route("/health", health, methods=["GET"], tags=["Supervision"], summary="État du service")
    for router in (chat.router, auth.router, users.router, service_keys.router, documents.router, events.router):
        app.include_router(router)
    return app
