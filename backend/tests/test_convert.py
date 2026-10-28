# backend/tests/test_convert.py
import pymupdf
import pypandoc
import pytest

from app.ingest.convert import (ConversionError, Page, _hyphenated_compounds, _restore_compounds,
                                _strip_repeated_lines, convert)
from scripts.build_test_corpus import render_pdf

LONG_PARAGRAPH = "<p>" + "Le cluster héberge les machines virtuelles du projet et assure leur disponibilité. " * 120 + "</p>"


def test_markdown_sans_commentaires_ni_gras(tmp_path):
    f = tmp_path / "doc.md"
    f.write_text("<!-- chemin/doc.md -->\n# Titre\n\nLe port **8090** est ouvert.\n", encoding="utf-8")
    pages = convert(f)
    assert pages == [Page("# Titre\n\nLe port 8090 est ouvert.", None)]


def test_latex_par_pandoc(tmp_path):
    f = tmp_path / "doc.tex"
    f.write_text("% commentaire\n\\documentclass{article}\n\\begin{document}\n\\section{Réseau}\n"
                 "Le pare-feu filtre l'entrée.\n\\begin{tabular}{|l|l|}\\hline Machine & Port \\\\ \\hline "
                 "VM150 & 8090 \\\\ \\hline\\end{tabular}\n\\end{document}\n", encoding="utf-8")
    text = convert(f)[0].text
    assert "# Réseau" in text and "commentaire" not in text
    assert "l'entrée" in text
    assert any("VM150" in line and "8090" in line for line in text.splitlines())


def test_word_par_pandoc(tmp_path):
    f = tmp_path / "doc.docx"
    pypandoc.convert_text("# Sauvegarde\n\nLa sauvegarde démarre à 01 h 30.\n\n| Élément | Heure |\n| --- | --- |\n"
                          "| VM | 01 h 30 |\n", "docx", format="md", outputfile=str(f))
    text = convert(f)[0].text
    assert "# Sauvegarde" in text
    assert any("VM" in line and "01 h 30" in line for line in text.splitlines() if line.startswith("|"))


def test_pdf_pages_titres_tableau_et_entetes_retires(tmp_path):
    f = tmp_path / "doc.pdf"
    html = ("<h1>Architecture</h1><h2>1. Machines</h2><table><tr><th>Machine</th><th>Rôle</th><th>Port</th></tr>"
            "<tr><td>VM150</td><td>GANDAL-AI</td><td>8090</td></tr></table><h2>2. Détails</h2>" + LONG_PARAGRAPH)
    count = render_pdf(html, "Projet GANDAL · en-tête répété", f)
    pages = convert(f)
    assert count >= 2 and [p.number for p in pages] == list(range(1, count + 1))
    text = "\n".join(p.text for p in pages)
    assert "en-tête répété" not in text and "Page 1 /" not in text
    assert "# Architecture" in text and "## 1. Machines" in text
    assert "|VM150|GANDAL-AI|8090|" in text


def test_pdf_petit_tableau_sans_bordure_garde_son_contenu(tmp_path, monkeypatch):
    # Limite connue, un petit tableau sans bordure devient du texte dans l'ordre de lecture
    import scripts.build_test_corpus as builder
    monkeypatch.setattr(builder, "CSS", builder.CSS.replace("border: 0.5pt solid #888;", ""))
    f = tmp_path / "doc.pdf"
    builder.render_pdf("<h1>T</h1><table><tr><th>Machine</th><th>Port</th></tr>"
                       "<tr><td>VM150</td><td>8090</td></tr></table>", "en-tête", f)
    text = convert(f)[0].text
    assert "VM150" in text and "8090" in text


def test_pdf_scanne_refuse(tmp_path):
    f = tmp_path / "scan.pdf"
    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_image(page.rect, pixmap=pymupdf.Pixmap(pymupdf.csRGB, pymupdf.IRect(0, 0, 50, 50), 0))
    doc.save(f)
    with pytest.raises(ConversionError, match="scanné"):
        convert(f)


def test_pdf_corrompu_et_format_inconnu(tmp_path):
    bad = tmp_path / "abime.pdf"
    bad.write_bytes(b"%PDF-1.7 pas vraiment un pdf")
    with pytest.raises(ConversionError):
        convert(bad)
    with pytest.raises(ConversionError, match="non pris en charge"):
        convert(tmp_path / "image.png")


def test_entetes_et_pieds_de_page_seulement_en_bord_de_page():
    body = "\n".join(f"Ligne {n} du contenu" for n in range(6))
    pages = [Page(f"Rapport GANDAL\n{body}\nOui\n{body}\nPage {i} / 3", i) for i in range(1, 4)]
    cleaned = _strip_repeated_lines(pages)
    assert all("Rapport GANDAL" not in p.text and "Page" not in p.text for p in cleaned)
    assert all("Oui" in p.text for p in cleaned)
    assert _strip_repeated_lines(pages[:1]) == pages[:1]


def test_trait_union_des_noms_composes_restaure():
    raw = "l'ordonnanceur gandal-\ngpu lance les jobs.\nVoir gandal-gpu status. Une infor-\nmation utile. VM-\n150"
    compounds = _hyphenated_compounds(raw)
    assert compounds == {"gandalgpu": "gandal-gpu", "VM150": "VM-150"}
    assert _restore_compounds("ordonnanceur gandalgpu, une information", compounds) == \
        "ordonnanceur gandal-gpu, une information"
