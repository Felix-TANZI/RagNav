# backend/app/main.py
# Fabrique d'application, lancée par uvicorn app.main:create_app --factory
from collections.abc import Iterator

import httpx2 as httpx
from fastapi import Depends, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from app import __version__
from app.config import Settings, get_settings
from app.health import check_models, check_qdrant


def app_settings(request: Request) -> Settings:
    return request.app.state.settings


def get_http(settings: Settings = Depends(app_settings)) -> Iterator[httpx.Client]:
    with httpx.Client(timeout=settings.health_timeout) as client:
        yield client


def health(settings: Settings = Depends(app_settings), http: httpx.Client = Depends(get_http)) -> dict:
    services = {"models": check_models(settings, http), "qdrant": check_qdrant(settings, http)}
    status = "ok" if all(s["ok"] for s in services.values()) else "degraded"
    return {"status": status, "version": __version__, "services": services}


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    app = FastAPI(title="GANDAL-AI", version=__version__, description="Assistant de navigation du projet GANDAL")
    app.state.settings = settings
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_api_route("/health", health, methods=["GET"])
    return app
