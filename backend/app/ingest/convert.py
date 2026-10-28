# backend/app/ingest/convert.py
# Ramène chaque format à du Markdown, page par page pour les PDF afin de pouvoir citer la page
import math
import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

import pymupdf
import pymupdf4llm
import pypandoc

PANDOC_FORMATS = {".tex": "latex", ".docx": "docx", ".odt": "odt", ".html": "html", ".htm": "html", ".rst": "rst"}
MARKDOWN_FORMATS = {".md", ".markdown", ".txt"}
SUPPORTED_FORMATS = {".pdf"} | set(PANDOC_FORMATS) | MARKDOWN_FORMATS
MIN_CHARACTERS = 20
EDGE_LINES = 3

_HTML_COMMENT = re.compile(r"<!--.*?-->", re.DOTALL)
_IMAGE = re.compile(r"!\[[^\]]*\]\([^)]*\)")
_BOLD = re.compile(r"\*\*(.+?)\*\*")
_BR = re.compile(r"<br\s*/?>", re.IGNORECASE)
_HYPHEN_BR = re.compile(r"(?<=\w)-<br\s*/?>(?=\w)", re.IGNORECASE)
_URL_BREAK = re.compile(r"(?<=://)\s+")
_LINE_END_HYPHEN = re.compile(r"(\w+)-\n(\w+)")
_DIGITS = re.compile(r"\d+")


class ConversionError(ValueError):
    pass


@dataclass
class Page:
    text: str
    number: int | None = None


def convert(path: Path) -> list[Page]:
    ext = path.suffix.lower()
    if ext not in SUPPORTED_FORMATS:
        raise ConversionError(f"format {ext or 'sans extension'} non pris en charge")
    if ext == ".pdf":
        pages = _strip_repeated_lines(_pdf_pages(path))
    elif ext in PANDOC_FORMATS:
        pages = [Page(_pandoc(path, PANDOC_FORMATS[ext]))]
    else:
        pages = [Page(path.read_text(encoding="utf-8", errors="replace"))]
    pages = [Page(_clean(p.text), p.number) for p in pages]
    if sum(len(p.text.strip()) for p in pages) < MIN_CHARACTERS:
        raise ConversionError("aucun texte exploitable, le document est peut-être scanné")
    return pages


def _pdf_pages(path: Path) -> list[Page]:
    try:
        with pymupdf.open(path) as doc:
            if doc.needs_pass:
                raise ConversionError("PDF protégé par un mot de passe")
            raw = [page.get_text() for page in doc]
            chunks = pymupdf4llm.to_markdown(doc, page_chunks=True, show_progress=False, ignore_images=True)
    except (pymupdf.FileDataError, RuntimeError) as e:
        raise ConversionError(f"PDF illisible ({e})") from e
    compounds = _hyphenated_compounds("\n".join(raw))
    return [Page(_restore_compounds(c["text"], compounds), c["metadata"]["page_number"]) for c in chunks]


def _hyphenated_compounds(raw: str) -> dict[str, str]:
    # pymupdf4llm recolle tout mot coupé en fin de ligne, on remet le trait d'union des noms composés
    compounds = {}
    for left, right in _LINE_END_HYPHEN.findall(raw):
        compound = f"{left}-{right}"
        seen_whole = re.search(rf"(?<![\w-]){re.escape(compound)}(?![\w-])", raw, re.IGNORECASE)
        if seen_whole or any(ch.isdigit() for ch in compound):
            compounds[left + right] = compound
    return compounds


def _restore_compounds(text: str, compounds: dict[str, str]) -> str:
    for joined, compound in compounds.items():
        text = re.sub(rf"(?<![\w-]){re.escape(joined)}(?![\w-])", compound, text)
    return text


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
        cleaned.append(Page("\n".join(kept), page.number))
    return cleaned
