# backend/app/ingest/pdf.py
# PDF et XPS page par page avec pymupdf4llm, OCR Tesseract des pages sans texte et des images
import os
import re
from functools import lru_cache
from pathlib import Path

import pymupdf
import pymupdf4llm

from app.ingest.base import ConversionError, ConvertOptions, Page

OCR_MIN_CHARACTERS = 30
WINDOWS_TESSDATA = Path(os.environ.get("PROGRAMFILES", "C:/Program Files")) / "Tesseract-OCR/tessdata"
_LINE_END_HYPHEN = re.compile(r"(\w+)-\n(\w+)")


def pdf_pages(path: Path, options: ConvertOptions) -> list[Page]:
    with pymupdf.open(path) as source:
        if source.needs_pass:
            raise ConversionError("document protégé par un mot de passe")
        if source.is_pdf:
            return _markdown_pages(source, options)
        with pymupdf.open("pdf", source.convert_to_pdf()) as doc:
            return _markdown_pages(doc, options)


def _markdown_pages(doc: pymupdf.Document, options: ConvertOptions) -> list[Page]:
    compounds = _hyphenated_compounds("\n".join(page.get_text() for page in doc))
    pages = []
    markdown = pymupdf4llm.to_markdown(doc, page_chunks=True, show_progress=False, use_ocr=False)
    for chunk in markdown:
        number = chunk["metadata"]["page_number"]
        text = _restore_compounds(chunk["text"], compounds)
        if len(re.sub(r"\W", "", text)) < OCR_MIN_CHARACTERS:
            pages.append(Page(ocr_page(doc[number - 1], options), number, ocr=True))
        else:
            pages.append(Page(text, number))
    return pages


def image_pages(path: Path, options: ConvertOptions) -> list[Page]:
    with pymupdf.open(path) as image, pymupdf.open("pdf", image.convert_to_pdf()) as doc:
        return [Page(ocr_page(page, options), None, ocr=True) for page in doc]


@lru_cache
def tessdata_dir(configured: str = "") -> str:
    if configured:
        return configured
    try:
        return pymupdf.get_tessdata()
    except RuntimeError:
        if WINDOWS_TESSDATA.exists():
            return str(WINDOWS_TESSDATA)
    raise ConversionError("Tesseract n'est pas installé, il est requis pour l'OCR")


def ocr_page(page: pymupdf.Page, options: ConvertOptions) -> str:
    try:
        textpage = page.get_textpage_ocr(language=options.ocr_language, dpi=options.ocr_dpi, full=True,
                                         tessdata=tessdata_dir(options.tessdata_path))
    except RuntimeError as e:
        raise ConversionError(f"OCR impossible, Tesseract et ses langues {options.ocr_language} sont requis ({e})") from e
    return page.get_text(textpage=textpage)


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
