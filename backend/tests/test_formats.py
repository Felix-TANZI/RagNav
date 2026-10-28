# backend/tests/test_formats.py
# Formats au-delà de PDF, Markdown et LaTeX, chaque fichier de test est fabriqué par le test lui-même
import subprocess

import pymupdf
import pypandoc
import pytest

from app.ingest import convert as convert_module
from app.ingest.base import ConversionError, ConvertOptions
from app.ingest.convert import convert
from app.ingest.office import libreoffice_binary
from app.ingest.pdf import tessdata_dir

OPTIONS = ConvertOptions(timeout=240)
SENTENCE = "Le serveur EMILIA ecoute sur le port 4000"


def available(check) -> bool:
    try:
        check()
        return True
    except ConversionError:
        return False


needs_tesseract = pytest.mark.skipif(not available(tessdata_dir), reason="Tesseract absent")
needs_libreoffice = pytest.mark.skipif(not available(libreoffice_binary), reason="LibreOffice absent")


def text_image(path, text: str = SENTENCE) -> None:
    doc = pymupdf.open()
    page = doc.new_page(width=900, height=200)
    page.insert_text((30, 110), text, fontsize=30)
    page.get_pixmap(dpi=150).save(path)


def libreoffice(source, target: str, outdir) -> None:
    subprocess.run([libreoffice_binary(), "--headless", "--convert-to", target, "--outdir", str(outdir), str(source)],
                   check=True, capture_output=True, timeout=240)


def test_powerpoint(tmp_path):
    f = tmp_path / "slides.pptx"
    pypandoc.convert_text("# Accès VPN\n\nLe VPN écoute sur le port 51820.\n", "pptx", format="md", outputfile=str(f))
    text = convert(f, OPTIONS)[0].text
    assert "Accès VPN" in text and "51820" in text


def test_csv_en_tableau(tmp_path):
    f = tmp_path / "machines.csv"
    f.write_text("Machine,Port\nVM150,8090\nEMILIA,4000\n", encoding="utf-8")
    lines = convert(f, OPTIONS)[0].text.splitlines()
    assert any("VM150" in line and "8090" in line and line.startswith("|") for line in lines)


def test_fichier_de_configuration_en_code(tmp_path):
    f = tmp_path / "docker-compose.yml"
    f.write_text("services:\n  qdrant:\n    image: qdrant/qdrant:v1.19.2\n", encoding="utf-8")
    text = convert(f, OPTIONS)[0].text
    assert text.startswith("# docker-compose.yml") and "```\nservices:" in text


def test_texte_windows_1252(tmp_path):
    f = tmp_path / "notes.txt"
    f.write_bytes("Procédure de mise à jour du pare-feu".encode("cp1252"))
    assert "Procédure de mise à jour" in convert(f, OPTIONS)[0].text


def test_erreur_imprevue_transformee_en_message(tmp_path, monkeypatch):
    f = tmp_path / "doc.docx"
    f.write_bytes(b"pas un docx")
    monkeypatch.setattr(convert_module, "_pandoc", lambda *_: (_ for _ in ()).throw(KeyError("zip")))
    with pytest.raises(ConversionError, match="lecture impossible"):
        convert(f, OPTIONS)


@needs_tesseract
def test_image_par_ocr(tmp_path):
    f = tmp_path / "schema.png"
    text_image(f)
    pages = convert(f, OPTIONS)
    assert pages[0].ocr and "EMILIA" in pages[0].text and "4000" in pages[0].text


@needs_tesseract
def test_pdf_mixte_seule_la_page_scannee_passe_par_ocr(tmp_path):
    image = tmp_path / "scan.png"
    text_image(image)
    doc = pymupdf.open()
    doc.new_page().insert_text((72, 72), "Page texte normale avec assez de contenu pour ne pas passer par OCR.")
    scanned = doc.new_page()
    scanned.insert_image(scanned.rect, filename=str(image), keep_proportion=True)
    f = tmp_path / "mixte.pdf"
    doc.save(f)
    pages = convert(f, OPTIONS)
    assert [p.ocr for p in pages] == [False, True]
    assert "EMILIA" in pages[1].text


@needs_libreoffice
@pytest.mark.parametrize("modern, legacy", [("docx", "doc"), ("pptx", "ppt")])
def test_anciens_formats_office(tmp_path, modern, legacy):
    source = tmp_path / f"source.{modern}"
    pypandoc.convert_text("# Sauvegarde\n\nLa sauvegarde démarre à 01 h 30.\n", modern, format="md",
                          outputfile=str(source))
    libreoffice(source, legacy, tmp_path / "out")
    text = convert(tmp_path / "out" / f"source.{legacy}", OPTIONS)[0].text
    assert "Sauvegarde" in text and "01 h 30" in text


@needs_libreoffice
def test_tableur_xls_et_xlsx(tmp_path):
    source = tmp_path / "machines.csv"
    source.write_text("Machine,Port\nVM150,8090\n", encoding="utf-8")
    for target in ("xlsx", "xls"):
        libreoffice(source, target, tmp_path / target)
        lines = convert(tmp_path / target / f"machines.{target}", OPTIONS)[0].text.splitlines()
        assert any("VM150" in line and "8090" in line for line in lines), target
