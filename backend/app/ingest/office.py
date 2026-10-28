# backend/app/ingest/office.py
# Anciens formats Office convertis par LibreOffice sans interface, un profil temporaire par conversion
import os
import shutil
import subprocess
import tempfile
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from app.ingest.base import ConversionError, ConvertOptions

WINDOWS_DEFAULT = Path(os.environ.get("PROGRAMFILES", "C:/Program Files")) / "LibreOffice/program/soffice.exe"


def libreoffice_binary(configured: str = "") -> str:
    for candidate in (configured, shutil.which("soffice"), shutil.which("libreoffice")):
        if candidate:
            return candidate
    if WINDOWS_DEFAULT.exists():
        return str(WINDOWS_DEFAULT)
    raise ConversionError("LibreOffice n'est pas installé, il est requis pour ce format")


@contextmanager
def converted(path: Path, target: str, options: ConvertOptions) -> Iterator[Path]:
    binary = libreoffice_binary(options.libreoffice_path)
    with tempfile.TemporaryDirectory(prefix="gandal-lo-", ignore_cleanup_errors=True) as tmp:
        command = [binary, f"-env:UserInstallation={Path(tmp, 'profil').as_uri()}", "--headless", "--norestore",
                   "--nolockcheck", "--convert-to", target, "--outdir", tmp, str(path.resolve())]
        try:
            result = subprocess.run(command, capture_output=True, text=True, timeout=options.timeout, check=False)
        except subprocess.TimeoutExpired as e:
            raise ConversionError(f"LibreOffice n'a pas terminé en {options.timeout:.0f} s") from e
        output = Path(tmp) / f"{path.stem}.{target}"
        if not output.exists():
            raise ConversionError(f"LibreOffice n'a pas pu convertir le fichier ({result.stderr.strip()[:200]})")
        yield output
