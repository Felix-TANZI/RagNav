# backend/app/routers/users.py
# Gestion des comptes par les admins, il reste toujours au moins un admin actif
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import Settings
from app.deps import app_settings, db_session, event_log, require_admin
from app.events import EventLog
from app.models import EventCategory, Role, User
from app.routers.auth import check_password_policy, revoke_user_sessions
from app.schemas import ErrorOut, UserCreateIn, UserOut, UserUpdateIn
from app.security import hash_password

router = APIRouter(prefix="/admin/users", tags=["Comptes"],
                   responses={401: {"model": ErrorOut}, 403: {"model": ErrorOut}})


def _get(session: Session, user_id: str) -> User:
    user = session.get(User, user_id)
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Compte introuvable")
    return user


def _other_active_admins(session: Session, user_id: str) -> int:
    return session.scalar(select(func.count()).select_from(User).where(
        User.role == Role.ADMIN, User.is_active.is_(True), User.id != user_id))


@router.get("", response_model=list[UserOut], summary="Lister les comptes")
def list_users(role: Role | None = None, session: Session = Depends(db_session),
               _: User = Depends(require_admin)) -> list[User]:
    query = select(User).order_by(User.created_at.desc())
    if role is not None:
        query = query.where(User.role == role)
    return list(session.scalars(query))


@router.post("", response_model=UserOut, status_code=status.HTTP_201_CREATED, summary="Créer un compte",
             description="Permet notamment de créer d'autres admins, l'inscription libre ne crée que des clients.",
             responses={409: {"model": ErrorOut}})
def create_user(body: UserCreateIn, session: Session = Depends(db_session), settings: Settings = Depends(app_settings),
                events: EventLog = Depends(event_log), _: User = Depends(require_admin)) -> User:
    check_password_policy(body.password, settings)
    email = body.email.lower()
    if session.scalar(select(User.id).where(User.email == email)):
        raise HTTPException(status.HTTP_409_CONFLICT, "Un compte existe déjà avec cette adresse")
    user = User(email=email, name=body.name.strip(), password_hash=hash_password(body.password), role=body.role)
    session.add(user)
    session.commit()
    events.info(EventCategory.COMPTES, "compte_cree", f"compte {body.role.value} {email} créé")
    return user


@router.patch("/{user_id}", response_model=UserOut, summary="Activer, désactiver ou changer le rôle",
              responses={400: {"model": ErrorOut}, 404: {"model": ErrorOut}})
def update_user(user_id: str, body: UserUpdateIn, session: Session = Depends(db_session),
                events: EventLog = Depends(event_log), admin: User = Depends(require_admin)) -> User:
    user = _get(session, user_id)
    loses_admin = (body.is_active is False) or (body.role is not None and body.role != Role.ADMIN)
    if user.role == Role.ADMIN and loses_admin:
        if user.id == admin.id:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Vous ne pouvez pas retirer vos propres droits")
        if _other_active_admins(session, user.id) == 0:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Il doit rester au moins un admin actif")
    if body.role is not None:
        user.role = body.role
    if body.is_active is not None:
        user.is_active = body.is_active
        if not body.is_active:
            revoke_user_sessions(session, user.id)
    session.commit()
    events.info(EventCategory.COMPTES, "compte_modifie", f"{user.email} est {user.role.value}, "
                f"{'actif' if user.is_active else 'désactivé'}")
    return user


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Supprimer un compte",
               responses={400: {"model": ErrorOut}, 404: {"model": ErrorOut}})
def delete_user(user_id: str, session: Session = Depends(db_session), events: EventLog = Depends(event_log),
                admin: User = Depends(require_admin)) -> None:
    user = _get(session, user_id)
    if user.id == admin.id:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Vous ne pouvez pas supprimer votre propre compte")
    if user.role == Role.ADMIN and _other_active_admins(session, user.id) == 0:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Il doit rester au moins un admin actif")
    session.delete(user)
    session.commit()
    events.info(EventCategory.COMPTES, "compte_supprime", f"compte {user.email} supprimé")
