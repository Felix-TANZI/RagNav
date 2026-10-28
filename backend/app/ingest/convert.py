# backend/app/ingest/convert.py
# Ramène chaque format à du Markdown, page par page pour les PDF afin de pouvoir citer la page
import math
import re
from collections import Counter
from pathlib import Path

import pypandoc

from app.ingest import office
from app.ingest.base import ConversionError, ConvertOptions, Page
from app.ingest.pdf import image_pages, pdf_pages

PDF_FORMATS = {".pdf", ".xps", ".oxps"}
IMAGE_FORMATS = {".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp", ".gif"}
PANDOC_FORMATS = {
    ".tex": "latex", ".docx": "docx", ".odt": "odt", ".html": "html", ".htm": "html", ".rst": "rst",
    ".pptx": "pptx", ".xlsx": "xlsx", ".csv": "csv", ".tsv": "tsv", ".rtf": "rtf", ".epub": "epub",
    ".ipynb": "ipynb", ".adoc": "asciidoc", ".asciidoc": "asciidoc", ".org": "org", ".typ": "typst",
    ".dbk": "docbook", ".wiki": "mediawiki", ".textile": "textile",
}
LIBREOFFICE_FORMATS = {".doc": "docx", ".dot": "docx", ".xls": "xlsx", ".ods": "xlsx", ".ppt": "pptx",
                       ".pps": "pptx", ".odp": "pptx"}
MARKDOWN_FORMATS = {".md", ".markdown", ".txt"}
CODE_FORMATS = {".yaml", ".yml", ".json", ".xml", ".toml", ".ini", ".conf", ".cfg", ".sh", ".ps1", ".py",
                ".sql", ".log"}
SUPPORTED_FORMATS = (PDF_FORMATS | IMAGE_FORMATS | set(PANDOC_FORMATS) | set(LIBREOFFICE_FORMATS)
                     | MARKDOWN_FORMATS | CODE_FORMATS)
MIN_CHARACTERS = 20
EDGE_LINES = 3

_HTML_COMMENT = re.compile(r"<!--.*?-->", re.DOTALL)
_IMAGE = re.compile(r"!\[[^\]]*\]\([^)]*\)")
_BOLD = re.compile(r"\*\*(.+?)\*\*")
_HYPHEN_BR = re.compile(r"(?<=\w)-<br\s*/?>(?=\w)", re.IGNORECASE)
_BR = re.compile(r"<br\s*/?>", re.IGNORECASE)
_URL_BREAK = re.compile(r"(?<=://)\s+")
_DIGITS = re.compile(r"\d+")


def convert(path: Path, options: ConvertOptions = ConvertOptions()) -> list[Page]:
    ext = path.suffix.lower()
    if ext not in SUPPORTED_FORMATS:
        raise ConversionError(f"format {ext or 'sans extension'} non pris en charge")
    try:
        pages = _dispatch(path, ext, options)
    except ConversionError:
        raise
    except Exception as e:
        raise ConversionError(f"lecture impossible ({type(e).__name__}, {e})") from e
    pages = [Page(_clean(p.text), p.number, p.ocr) for p in pages]
    if sum(len(p.text.strip()) for p in pages) < MIN_CHARACTERS:
        raise ConversionError("aucun texte exploitable, même après OCR")
    return pages


def _dispatch(path: Path, ext: str, options: ConvertOptions) -> list[Page]:
    if ext in PDF_FORMATS:
        return _strip_repeated_lines(pdf_pages(path, options))
    if ext in IMAGE_FORMATS:
        return image_pages(path, options)
    if ext in PANDOC_FORMATS:
        return [Page(_pandoc(path, PANDOC_FORMATS[ext]))]
    if ext in LIBREOFFICE_FORMATS:
        target = LIBREOFFICE_FORMATS[ext]
        with office.converted(path, target, options) as converted:
            return [Page(_pandoc(converted, target))]
    text = _read_text(path)
    if ext in CODE_FORMATS:
        return [Page(f"# {path.name}\n\n```\n{text}\n```")]
    return [Page(text)]


def _read_text(path: Path) -> str:
    data = path.read_bytes()
    try:
        text = data.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = data.decode("cp1252", errors="replace")
    return text.replace("\r\n", "\n").replace("\r", "\n")


def _pandoc(path: Path, source_format: str) -> str:
    try:
        return pypandoc.convert_file(str(path), "gfm", format=source_format, extra_args=["--wrap=none"])
    except RuntimeError as e:
        raise ConversionError(f"conversion Pandoc impossible ({e})") from e


def _clean(text: str) -> str:
    text = _HTML_COMMENT.sub("", text)
    text = _IMAGE.sub("", text)
    text = _HYPHEN_BR.sub("-", text)
    text = _BR.sub(" ", text)
    text = _URL_BREAK.sub("", text)
    text = _BOLD.sub(r"\1", text)
    return text.replace(" ", " ").replace("’", "'").strip()


def _line_key(line: str) -> str:
    return _DIGITS.sub("#", line.strip().strip("*_ ").lower())


def _edge_indexes(lines: list[str]) -> set[int]:
    filled = [i for i, line in enumerate(lines) if line.strip()]
    return set(filled[:EDGE_LINES] + filled[-EDGE_LINES:])


def _strip_repeated_lines(pages: list[Page]) -> list[Page]:
    # En-têtes et pieds de page, lignes du haut ou du bas de page répétées sur la majorité des pages
    if len(pages) < 2:
        return pages
    split = [p.text.splitlines() for p in pages]
    counts = Counter(key for lines in split for key in {_line_key(lines[i]) for i in _edge_indexes(lines)})
    threshold = max(2, math.ceil(len(pages) / 2))
    repeated = {k for k, n in counts.items() if n >= threshold and k and len(k) <= 150 and not k.startswith("|")}
    cleaned = []
    for page, lines in zip(pages, split):
        edges = _edge_indexes(lines)
        kept = [line for i, line in enumerate(lines) if not (i in edges and _line_key(line) in repeated)]
        cleaned.append(Page("\n".join(kept), page.number, page.ocr))
    return cleaned
