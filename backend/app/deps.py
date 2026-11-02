# backend/app/deps.py
# Dépendances partagées par les routes, session de base, utilisateur connecté, clé de service et limite de débit
from collections.abc import Callable, Iterator
from dataclasses import dataclass

import jwt
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import APIKeyHeader, OAuth2PasswordBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import Settings
from app.events import EventLog, current_request
from app.models import Role, ServiceKey, User, utcnow
from app.security import decode_access_token, digest

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/token", auto_error=False,
                                     description="Connexion par e-mail (champ username) et mot de passe")
api_key_scheme = APIKeyHeader(name="X-API-Key", auto_error=False,
                              description="Clé de service d'une application appelante, créée par un admin")


@dataclass(frozen=True)
class Caller:
    kind: str
    id: str
    label: str


def app_settings(request: Request) -> Settings:
    return request.app.state.settings


def db_session(request: Request) -> Iterator[Session]:
    with request.app.state.sessions() as session:
        yield session


def event_log(request: Request) -> EventLog:
    return request.app.state.events


def client_ip(request: Request) -> str:
    return request.client.host if request.client else "inconnu"


def _set_actor(actor: str) -> None:
    ctx = current_request.get()
    if ctx is not None:
        ctx.actor = actor


def unauthorized(detail: str = "Authentification requise") -> HTTPException:
    return HTTPException(status.HTTP_401_UNAUTHORIZED, detail, headers={"WWW-Authenticate": "Bearer"})


def current_user(token: str | None = Depends(oauth2_scheme), session: Session = Depends(db_session),
                 settings: Settings = Depends(app_settings)) -> User:
    if not token:
        raise unauthorized()
    try:
        claims = decode_access_token(token, settings.jwt_secret.get_secret_value())
    except jwt.InvalidTokenError:
        raise unauthorized("Jeton invalide ou expiré")
    user = session.get(User, claims["sub"])
    if user is None or not user.is_active:
        raise unauthorized("Compte introuvable ou désactivé")
    _set_actor(user.email)
    return user


def require_admin(user: User = Depends(current_user)) -> User:
    if user.role != Role.ADMIN:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Réservé aux administrateurs")
    return user


def require_caller(token: str | None = Depends(oauth2_scheme), api_key: str | None = Depends(api_key_scheme),
                   session: Session = Depends(db_session), settings: Settings = Depends(app_settings)) -> Caller:
    if api_key:
        key = session.scalar(select(ServiceKey).where(ServiceKey.key_hash == digest(api_key),
                                                      ServiceKey.revoked_at.is_(None)))
        if key is None:
            raise unauthorized("Clé de service invalide ou révoquée")
        key.last_used_at = utcnow()
        session.commit()
        _set_actor(f"clé {key.name}")
        return Caller("service", key.id, key.name)
    user = current_user(token, session, settings)
    return Caller("user", user.id, user.email)


def rate_limited(name: str) -> Callable[[Request], None]:
    def check(request: Request) -> None:
        wait = request.app.state.limiters[name].retry_after(client_ip(request))
        if wait is not None:
            raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "Trop de tentatives, réessayer plus tard",
                                headers={"Retry-After": str(wait)})
    return check
