# backend/scripts/set_password.py
# Nouveau mot de passe pour un compte, depuis le serveur, par exemple quand le seul admin a perdu le sien
# Le compte est réactivé et débloqué, ses sessions sont fermées, le mot de passe n'est jamais affiché
import argparse
import getpass
import sys

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.config import get_settings
from app.db import make_engine, make_session_factory
from app.events import EventLog
from app.migrate import run_migrations
from app.models import EventCategory, User
from app.routers.auth import revoke_user_sessions
from app.security import hash_password


def set_password(sessions: sessionmaker[Session], email: str, password: str) -> bool:
    with sessions() as session:
        user = session.scalar(select(User).where(User.email == email.lower()))
        if user is None:
            return False
        user.password_hash, user.is_active, user.failed_logins, user.locked_until = hash_password(password), True, 0, None
        revoke_user_sessions(session, user.id)
        session.commit()
    EventLog(sessions).warning(EventCategory.COMPTES, "mot_de_passe_serveur",
                               f"mot de passe de {email.lower()} changé depuis le serveur")
    return True


def main() -> int:
    settings = get_settings()
    parser = argparse.ArgumentParser(description="Changer le mot de passe d'un compte depuis le serveur")
    parser.add_argument("email")
    args = parser.parse_args()
    password = getpass.getpass("Nouveau mot de passe ")
    if len(password) < settings.password_min_length:
        print(f"Le mot de passe doit compter au moins {settings.password_min_length} caractères", file=sys.stderr)
        return 2
    if getpass.getpass("Confirmer le mot de passe ") != password:
        print("Les deux saisies diffèrent", file=sys.stderr)
        return 2
    run_migrations(settings.database_url)
    if not set_password(make_session_factory(make_engine(settings.database_url)), args.email, password):
        print(f"Aucun compte {args.email}", file=sys.stderr)
        return 1
    print(f"Mot de passe de {args.email} changé, compte actif et débloqué, sessions fermées")
    return 0


if __name__ == "__main__":
    sys.exit(main())
