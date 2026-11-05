# backend/app/bootstrap.py
# Premier admin créé au démarrage depuis ADMIN_EMAIL et ADMIN_PASSWORD si aucun admin n'existe encore
import logging

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import Settings
from app.models import Role, User
from app.security import hash_password

log = logging.getLogger("gandal.amorcage")


def ensure_first_admin(session: Session, settings: Settings) -> bool:
    if session.scalar(select(User.id).where(User.role == Role.ADMIN).limit(1)):
        return False
    if not settings.admin_email or not settings.admin_password:
        log.warning("aucun admin, renseigner ADMIN_EMAIL et ADMIN_PASSWORD dans .env")
        return False
    email = settings.admin_email.lower()
    password = settings.admin_password.get_secret_value()
    if len(password) < settings.password_min_length:
        log.warning("ADMIN_PASSWORD fait moins de %s caractères, le changer après la première connexion",
                    settings.password_min_length)
    if session.scalar(select(User.id).where(User.email == email)):
        log.error("%s existe déjà comme compte client, il n'est pas promu admin automatiquement", email)
        return False
    session.add(User(email=email, name=settings.admin_name, password_hash=hash_password(password), role=Role.ADMIN))
    session.commit()
    log.info("premier admin %s créé", email)
    return True
