# backend/app/security.py
# Mots de passe Argon2, jetons d'accès JWT courts, jetons de renouvellement et clés de service gardés en empreinte
import hashlib
import secrets
import uuid
from datetime import datetime, timedelta, timezone

import jwt
from pwdlib import PasswordHash

ALGORITHM = "HS256"
SERVICE_KEY_PREFIX = "gai_"

_hasher = PasswordHash.recommended()
_DUMMY_HASH = _hasher.hash(secrets.token_urlsafe(16))


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password: str, password_hash: str | None) -> bool:
    # Hachage factice si le compte n'existe pas, même durée de réponse dans les deux cas
    if password_hash is None:
        _hasher.verify(password, _DUMMY_HASH)
        return False
    return _hasher.verify(password, password_hash)


def create_access_token(user_id: str, role: str, secret: str, minutes: int) -> str:
    now = datetime.now(timezone.utc)
    claims = {"sub": user_id, "role": role, "type": "access", "iat": now, "exp": now + timedelta(minutes=minutes),
              "jti": str(uuid.uuid4())}
    return jwt.encode(claims, secret, algorithm=ALGORITHM)


def decode_access_token(token: str, secret: str) -> dict:
    claims = jwt.decode(token, secret, algorithms=[ALGORITHM], options={"require": ["exp", "sub", "type"]})
    if claims["type"] != "access":
        raise jwt.InvalidTokenError("type de jeton inattendu")
    return claims


def new_opaque_token() -> str:
    return secrets.token_urlsafe(32)


def digest(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def new_service_key() -> str:
    return SERVICE_KEY_PREFIX + secrets.token_urlsafe(32)
