# backend/scripts/build_test_corpus.py
# Génère les PDF du corpus de test à partir des sources HTML de scripts/corpus_test
import argparse
from pathlib import Path

import pymupdf

SOURCES = Path(__file__).parent / "corpus_test"
CSS = """
body { font-family: sans-serif; font-size: 10pt; line-height: 1.4; }
h1 { font-size: 18pt; } h2 { font-size: 14pt; } h3 { font-size: 11.5pt; }
table { border-collapse: collapse; } th, td { border: 0.5pt solid #888; padding: 3pt; }
"""


def render_pdf(html: str, header: str, out: Path) -> int:
    page_rect = pymupdf.paper_rect("a4")
    body = page_rect + (60, 70, -60, -70)
    story = pymupdf.Story(html=html, user_css=CSS)
    writer = pymupdf.DocumentWriter(str(out))
    more = True
    while more:
        device = writer.begin_page(page_rect)
        more, _ = story.place(body)
        story.draw(device)
        writer.end_page()
    writer.close()

    with pymupdf.open(out) as doc:
        for number, page in enumerate(doc, start=1):
            page.insert_text((60, 45), header, fontsize=8, color=(0.4, 0.4, 0.4))
            page.insert_text((page_rect.width - 110, page_rect.height - 35), f"Page {number} / {doc.page_count}",
                             fontsize=8, color=(0.4, 0.4, 0.4))
        doc.saveIncr()
        return doc.page_count


def main() -> None:
    parser = argparse.ArgumentParser(description="Génère les PDF du corpus de test")
    parser.add_argument("--out", type=Path, default=Path("../corpus/test"))
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    for source in sorted(SOURCES.glob("*.html")):
        out = args.out / f"{source.stem}.pdf"
        pages = render_pdf(source.read_text(encoding="utf-8"), "GANDAL GI27 · Document de test fictif", out)
        print(f"{out} ({pages} pages)")


if __name__ == "__main__":
    main()
