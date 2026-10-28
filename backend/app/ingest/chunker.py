# backend/app/ingest/chunker.py
# Découpe le Markdown par section en passages de taille bornée, avec recouvrement par phrases
import re
import uuid
from dataclasses import dataclass, field

from app.ingest.base import Page

_ATX = re.compile(r"^ {0,3}(#{1,6})\s+(.+?)\s*#*\s*$")
_SETEXT = re.compile(r"^ {0,3}(=+|-+)\s*$")
_FENCE = re.compile(r"^ {0,3}(```|~~~)")
_SENTENCE_END = re.compile(r"(?<=[.!?;])\s+(?=\S)")
_MARKUP = re.compile(r"[*_`]+")
_PARAGRAPH_END = (".", "!", "?", ":", ";", "»", ")", "|")


@dataclass
class Chunk:
    document: str
    headings: tuple[str, ...]
    page: int | None
    text: str
    index: int

    @property
    def section(self) -> str:
        return self.headings[-1] if self.headings else ""

    @property
    def section_path(self) -> str:
        return " > ".join(self.headings)

    @property
    def id(self) -> str:
        return str(uuid.uuid5(uuid.NAMESPACE_URL, f"gandal://{self.document}#{self.index}"))

    @property
    def words(self) -> int:
        return len(self.text.split())


@dataclass
class _Block:
    kind: str
    text: str
    page: int | None
    level: int = 0


@dataclass
class _Unit:
    text: str
    page: int | None
    joiner: str
    words: int = field(init=False)

    def __post_init__(self) -> None:
        self.words = len(self.text.split())


def _heading_text(raw: str) -> str:
    return _MARKUP.sub("", raw).strip()


def _blocks(pages: list[Page]) -> list[_Block]:
    blocks: list[_Block] = []
    for page in pages:
        lines = page.text.splitlines()
        current: list[str] = []
        kind = "text"
        page_start = len(blocks)

        def flush() -> None:
            nonlocal current, kind
            filled = [l for l in current if l.strip()]
            if filled:
                if kind == "text" and all(l.startswith(("    ", "\t")) for l in filled):
                    kind = "code"
                text = "\n".join(current).strip("\n")
                previous = blocks[-1] if blocks else None
                if (len(blocks) == page_start and previous and previous.kind == kind == "text"
                        and not previous.text.rstrip().endswith(_PARAGRAPH_END) and text.lstrip()[:1].islower()):
                    previous.text = f"{previous.text.rstrip()} {text.lstrip()}"
                else:
                    blocks.append(_Block(kind, text, page.number))
            current, kind = [], "text"

        i = 0
        while i < len(lines):
            line = lines[i]
            if _FENCE.match(line):
                flush()
                fence = [line]
                i += 1
                while i < len(lines) and not _FENCE.match(lines[i]):
                    fence.append(lines[i])
                    i += 1
                if i < len(lines):
                    fence.append(lines[i])
                blocks.append(_Block("code", "\n".join(fence), page.number))
            elif m := _ATX.match(line):
                flush()
                blocks.append(_Block("heading", _heading_text(m.group(2)), page.number, len(m.group(1))))
            elif current and kind == "text" and len(current) == 1 and _SETEXT.match(line) and current[0].strip():
                blocks.append(_Block("heading", _heading_text(current[0]), page.number, 1 if "=" in line else 2))
                current = []
            elif not line.strip():
                flush()
            else:
                is_table = line.lstrip().startswith("|")
                if current and (kind == "table") != is_table:
                    flush()
                kind = "table" if is_table else kind
                current.append(line)
            i += 1
        flush()
    return blocks


def _sections(blocks: list[_Block]) -> list[tuple[tuple[str, ...], list[_Block]]]:
    stack: list[tuple[int, str]] = []
    sections: list[tuple[tuple[str, ...], list[_Block]]] = []
    for block in blocks:
        if block.kind == "heading":
            stack = [(lvl, title) for lvl, title in stack if lvl < block.level] + [(block.level, block.text)]
            continue
        path = tuple(title for _, title in stack)
        if sections and sections[-1][0] == path:
            sections[-1][1].append(block)
        else:
            sections.append((path, [block]))
    return sections


def _split_words(text: str, max_words: int) -> list[str]:
    words = text.split()
    return [" ".join(words[i:i + max_words]) for i in range(0, len(words), max_words)]


def _units(block: _Block, max_words: int) -> list[_Unit]:
    if block.kind == "table":
        rows = block.text.splitlines()
        if len(block.text.split()) <= max_words or len(rows) <= 3:
            return [_Unit(block.text, block.page, "\n\n")]
        header, body = rows[:2], rows[2:]
        groups, current = [], []
        for row in body:
            if current and len(" ".join(header + current + [row]).split()) > max_words:
                groups.append(current)
                current = []
            current.append(row)
        groups.append(current)
        return [_Unit("\n".join(header + g), block.page, "\n\n") for g in groups]
    if block.kind == "code":
        if len(block.text.split()) <= max_words:
            return [_Unit(block.text, block.page, "\n\n")]
        return [_Unit(part, block.page, "\n\n") for part in _split_words(block.text, max_words)]
    units: list[_Unit] = []
    for line in (l.strip() for l in block.text.splitlines() if l.strip()):
        pieces = [p for s in _SENTENCE_END.split(line) for p in _split_words(s, max_words)]
        for i, piece in enumerate(pieces):
            joiner = " " if i else ("\n" if units else "\n\n")
            units.append(_Unit(piece, block.page, joiner))
    return units


def _join(units: list[_Unit]) -> str:
    return "".join(u.text if i == 0 else u.joiner + u.text for i, u in enumerate(units))


def chunk_document(document: str, pages: list[Page], max_words: int = 300, overlap_words: int = 45,
                   title: str = "") -> list[Chunk]:
    chunks: list[Chunk] = []
    for headings, blocks in _sections(_blocks(pages)):
        headings = headings or ((title,) if title else ())
        units = [u for b in blocks for u in _units(b, max_words)]
        current: list[_Unit] = []
        carried = 0

        def emit() -> None:
            fresh = current[carried:]
            chunks.append(Chunk(document, headings, fresh[0].page, _join(current), len(chunks)))

        for unit in units:
            if current and sum(u.words for u in current) + unit.words > max_words:
                if len(current) > carried:
                    emit()
                    tail: list[_Unit] = []
                    for u in reversed(current):
                        if sum(t.words for t in tail) + u.words > overlap_words:
                            break
                        tail.insert(0, u)
                    current = tail if len(tail) < len(current) else []
                if sum(u.words for u in current) + unit.words > max_words:
                    current = []
                carried = len(current)
            current.append(unit)
        if len(current) > carried:
            emit()
    return chunks
