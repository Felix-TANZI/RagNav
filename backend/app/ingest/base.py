# backend/app/ingest/base.py
from dataclasses import dataclass

from app.config import Settings


class ConversionError(ValueError):
    pass


@dataclass
class Page:
    text: str
    number: int | None = None
    ocr: bool = False


@dataclass(frozen=True)
class ConvertOptions:
    ocr_language: str = "fra+eng"
    ocr_dpi: int = 300
    tessdata_path: str = ""
    libreoffice_path: str = ""
    timeout: float = 180.0

    @classmethod
    def from_settings(cls, settings: Settings) -> "ConvertOptions":
        return cls(settings.ocr_language, settings.ocr_dpi, settings.tessdata_path, settings.libreoffice_path,
                   settings.conversion_timeout)
