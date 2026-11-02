# backend/app/schemas.py
# Schémas d'entrée et de sortie de l'API, ils produisent aussi la documentation Swagger
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.models import DocumentStatus, EventCategory, EventLevel, Role


class ErrorOut(BaseModel):
    detail: str = Field(examples=["Authentification requise"])
    request_id: str | None = Field(default=None, description="Référence pour retrouver l'erreur dans le journal")


class RegisterIn(BaseModel):
    email: EmailStr = Field(examples=["prenom.nom@exemple.cm"])
    password: str = Field(max_length=128, description="Au moins 12 caractères")


class PasswordChangeIn(BaseModel):
    current_password: str = Field(max_length=128)
    new_password: str = Field(max_length=128, description="Au moins 12 caractères")


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int = Field(description="Durée de validité du jeton d'accès, en secondes")
    role: Role


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    email: EmailStr
    role: Role
    is_active: bool
    created_at: datetime
    last_login_at: datetime | None


class UserCreateIn(RegisterIn):
    role: Role = Role.CLIENT


class UserUpdateIn(BaseModel):
    is_active: bool | None = None
    role: Role | None = None


class ServiceKeyCreateIn(BaseModel):
    name: str = Field(min_length=1, max_length=100, examples=["frontend-gandal-ai"])


class ServiceKeyOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    prefix: str = Field(description="Début de la clé, pour la reconnaître sans la révéler")
    created_at: datetime
    last_used_at: datetime | None
    revoked_at: datetime | None


class ServiceKeyCreated(ServiceKeyOut):
    key: str = Field(description="Clé complète, affichée une seule fois, à envoyer dans l'en-tête X-API-Key")


class DocumentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    filename: str
    title: str
    source: str
    version: str
    document_date: date
    size: int = Field(description="Taille du fichier en octets")
    status: DocumentStatus
    error: str | None = Field(description="Raison de l'échec d'indexation")
    chunks: int | None = Field(description="Nombre de passages indexés")
    ocr_pages: int | None = Field(description="Nombre de pages lues par OCR")
    created_at: datetime
    updated_at: datetime
    indexed_at: datetime | None


class DocumentUpdateIn(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=255)
    source: str | None = Field(default=None, min_length=1, max_length=255)
    version: str | None = Field(default=None, min_length=1, max_length=50)
    document_date: date | None = None


class FormatsOut(BaseModel):
    extensions: list[str]
    max_upload_mb: int


class EventOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    created_at: datetime
    level: EventLevel
    category: EventCategory
    action: str
    message: str
    actor: str | None
    ip: str | None
    method: str | None
    path: str | None
    status_code: int | None
    request_id: str | None = Field(description="Référence affichée à l'utilisateur avec le message d'erreur")
    document_id: str | None


class EventDetailOut(EventOut):
    detail: str | None = Field(description="Détail technique, trace de la pile d'appels")
