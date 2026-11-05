# backend/app/routers/auth.py
# Inscription, connexion, renouvellement par cookie HttpOnly avec rotation, déconnexion et changement de mot de passe
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.responses import JSONResponse
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.config import Settings
from app.deps import app_settings, current_user, db_session, event_log, rate_limited, unauthorized
from app.events import EventLog
from app.models import EventCategory, RefreshToken, Role, User, new_id, utcnow
from app.schemas import ErrorOut, PasswordChangeIn, ProfileUpdateIn, RegisterIn, TokenOut, UserOut
from app.security import create_access_token, digest, hash_password, new_opaque_token, verify_password

router = APIRouter(prefix="/auth", tags=["Authentification"])

REFRESH_COOKIE = "gandal_refresh"
INVALID_LOGIN = "E-mail ou mot de passe incorrect, ou compte temporairement bloqué"
AUTH = EventCategory.AUTHENTIFICATION


def check_password_policy(password: str, settings: Settings) -> None:
    if len(password) < settings.password_min_length:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT,
                            f"Le mot de passe doit compter au moins {settings.password_min_length} caractères")


def _set_cookie(response: Response, raw: str, expires_at: datetime, settings: Settings) -> None:
    max_age = max(0, int((expires_at - utcnow()).total_seconds()))
    response.set_cookie(REFRESH_COOKIE, raw, max_age=max_age, httponly=True, secure=settings.cookie_secure,
                        samesite="strict", path=settings.refresh_cookie_path)


def _clear_cookie(response: Response, settings: Settings) -> None:
    response.delete_cookie(REFRESH_COOKIE, path=settings.refresh_cookie_path, httponly=True,
                           secure=settings.cookie_secure, samesite="strict")


def _reject(detail: str, settings: Settings) -> JSONResponse:
    response = JSONResponse({"detail": detail}, status.HTTP_401_UNAUTHORIZED, headers={"WWW-Authenticate": "Bearer"})
    _clear_cookie(response, settings)
    return response


def _issue(session: Session, user: User, response: Response, settings: Settings, family_id: str | None = None,
           session_expires_at: datetime | None = None) -> TokenOut:
    raw = new_opaque_token()
    expires_at = session_expires_at or utcnow() + timedelta(hours=settings.session_hours)
    session.add(RefreshToken(user_id=user.id, family_id=family_id or new_id(), token_hash=digest(raw),
                             session_expires_at=expires_at))
    _set_cookie(response, raw, expires_at, settings)
    access = create_access_token(user.id, user.role.value, settings.jwt_secret.get_secret_value(),
                                 settings.access_token_minutes)
    return TokenOut(access_token=access, expires_in=settings.access_token_minutes * 60, role=user.role)


def _revoke_family(session: Session, family_id: str) -> None:
    session.execute(update(RefreshToken).where(RefreshToken.family_id == family_id, RefreshToken.revoked_at.is_(None))
                    .values(revoked_at=utcnow()))


def revoke_user_sessions(session: Session, user_id: str) -> None:
    session.execute(update(RefreshToken).where(RefreshToken.user_id == user_id, RefreshToken.revoked_at.is_(None))
                    .values(revoked_at=utcnow()))


@router.post("/register", status_code=status.HTTP_201_CREATED, response_model=UserOut,
             dependencies=[Depends(rate_limited("register"))],
             summary="Créer un compte client",
             responses={409: {"model": ErrorOut, "description": "Adresse déjà utilisée"},
                        429: {"model": ErrorOut, "description": "Trop d'inscriptions depuis cette adresse IP"}})
def register(body: RegisterIn, session: Session = Depends(db_session), settings: Settings = Depends(app_settings),
             events: EventLog = Depends(event_log)) -> User:
    check_password_policy(body.password, settings)
    email = body.email.lower()
    if session.scalar(select(User.id).where(User.email == email)):
        raise HTTPException(status.HTTP_409_CONFLICT, "Un compte existe déjà avec cette adresse")
    user = User(email=email, name=body.name.strip(), password_hash=hash_password(body.password), role=Role.CLIENT)
    session.add(user)
    session.commit()
    events.info(AUTH, "inscription", f"compte client {email} créé", actor=email)
    return user


@router.post("/token", response_model=TokenOut, dependencies=[Depends(rate_limited("login"))],
             summary="Se connecter",
             description="Renvoie un jeton d'accès et place le jeton de renouvellement dans un cookie HttpOnly. "
                         "Le champ username reçoit l'adresse e-mail.",
             responses={401: {"model": ErrorOut}, 429: {"model": ErrorOut}})
def login(response: Response, form: OAuth2PasswordRequestForm = Depends(), session: Session = Depends(db_session),
          settings: Settings = Depends(app_settings), events: EventLog = Depends(event_log)) -> TokenOut:
    now, email = utcnow(), form.username.strip().lower()
    user = session.scalar(select(User).where(User.email == email))
    if user is not None and user.locked_until and user.locked_until > now:
        verify_password(form.password, None)
        events.warning(AUTH, "connexion_bloquee", f"tentative sur le compte bloqué {email}", actor=email)
        raise unauthorized(INVALID_LOGIN)
    if not verify_password(form.password, user.password_hash if user else None) or not user.is_active:
        reason = "compte inconnu" if user is None else ("compte désactivé" if user.is_active is False else
                                                          "mot de passe incorrect")
        events.warning(AUTH, "connexion_echec", f"échec de connexion pour {email}, {reason}", actor=email)
        if user is not None:
            user.failed_logins += 1
            if user.failed_logins >= settings.login_max_failures:
                user.locked_until, user.failed_logins = now + timedelta(minutes=settings.lockout_minutes), 0
                events.warning(AUTH, "compte_bloque", f"{email} bloqué {settings.lockout_minutes} min après "
                               f"{settings.login_max_failures} échecs", actor=email)
            session.commit()
        raise unauthorized(INVALID_LOGIN)
    user.failed_logins, user.locked_until, user.last_login_at = 0, None, now
    token = _issue(session, user, response, settings)
    session.commit()
    events.info(AUTH, "connexion", f"{email} connecté ({user.role.value})", actor=email)
    return token


@router.post("/refresh", response_model=TokenOut, summary="Renouveler le jeton d'accès",
             description="Utilise le cookie de renouvellement, le remplace par un nouveau et renvoie un jeton d'accès.",
             responses={401: {"model": ErrorOut}})
def refresh(request: Request, response: Response, session: Session = Depends(db_session),
            settings: Settings = Depends(app_settings), events: EventLog = Depends(event_log)):
    raw = request.cookies.get(REFRESH_COOKIE)
    stored = session.scalar(select(RefreshToken).where(RefreshToken.token_hash == digest(raw))) if raw else None
    if stored is None:
        return _reject("Session absente ou expirée", settings)
    if stored.revoked_at is not None:
        _revoke_family(session, stored.family_id)
        session.commit()
        owner = session.get(User, stored.user_id)
        events.error(AUTH, "reutilisation_jeton", "jeton de renouvellement déjà utilisé présenté, session révoquée "
                     "par précaution (vol possible)", actor=owner.email if owner else None)
        return _reject("Session révoquée, se reconnecter", settings)
    user = session.get(User, stored.user_id)
    if stored.session_expires_at <= utcnow() or user is None or not user.is_active:
        _revoke_family(session, stored.family_id)
        session.commit()
        return _reject("Session expirée, se reconnecter", settings)
    stored.revoked_at = utcnow()
    token = _issue(session, user, response, settings, stored.family_id, stored.session_expires_at)
    session.commit()
    return token


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT, summary="Se déconnecter")
def logout(request: Request, response: Response, session: Session = Depends(db_session),
           settings: Settings = Depends(app_settings), events: EventLog = Depends(event_log)) -> None:
    raw = request.cookies.get(REFRESH_COOKIE)
    stored = session.scalar(select(RefreshToken).where(RefreshToken.token_hash == digest(raw))) if raw else None
    if stored is not None:
        _revoke_family(session, stored.family_id)
        session.commit()
        owner = session.get(User, stored.user_id)
        events.info(AUTH, "deconnexion", "session fermée", actor=owner.email if owner else None)
    _clear_cookie(response, settings)


@router.get("/me", response_model=UserOut, summary="Compte connecté", responses={401: {"model": ErrorOut}})
def me(user: User = Depends(current_user)) -> User:
    return user


@router.patch("/me", response_model=UserOut, summary="Modifier son prénom", responses={401: {"model": ErrorOut}})
def update_me(body: ProfileUpdateIn, user: User = Depends(current_user), session: Session = Depends(db_session)) -> User:
    user.name = body.name.strip()
    session.commit()
    return user


@router.post("/password", status_code=status.HTTP_204_NO_CONTENT, summary="Changer son mot de passe",
             description="Toutes les sessions du compte sont fermées, il faut se reconnecter.",
             responses={400: {"model": ErrorOut}, 401: {"model": ErrorOut}})
def change_password(body: PasswordChangeIn, response: Response, user: User = Depends(current_user),
                    session: Session = Depends(db_session), settings: Settings = Depends(app_settings),
                    events: EventLog = Depends(event_log)) -> None:
    if not verify_password(body.current_password, user.password_hash):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Mot de passe actuel incorrect")
    check_password_policy(body.new_password, settings)
    user.password_hash = hash_password(body.new_password)
    revoke_user_sessions(session, user.id)
    session.commit()
    events.info(AUTH, "mot_de_passe_change", "mot de passe changé, toutes les sessions fermées")
    _clear_cookie(response, settings)
