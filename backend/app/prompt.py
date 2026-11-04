# backend/app/prompt.py
# Consigne du modèle, extraits numérotés, contrôle des citations et détection du refus
import re
import unicodedata

from app.store import Hit

REFUSAL = "Je ne trouve pas cette information dans la documentation GANDAL."

SYSTEM_PROMPT = f"""Tu es GANDAL-AI, l'assistant de navigation du projet GANDAL, un mini data center.
Tu aides les membres du projet à retrouver une information dans la documentation, machines, services, ports,
adresses, procédures et architecture.

Règles à respecter strictement.
1. Réponds uniquement à partir des extraits numérotés fournis, jamais avec des connaissances extérieures.
2. Après chaque information, cite l'extrait utilisé par son numéro entre crochets, par exemple [1] ou [2][3].
3. Si les extraits ne contiennent pas la réponse, réponds exactement « {REFUSAL} » et rien d'autre.
4. Réponds en français, de façon courte et précise. Pour une procédure, donne les étapes dans l'ordre.
5. Recopie à l'identique les noms de machines, ports, adresses, chemins et commandes.
6. Si on te demande où se trouve une information, nomme le document et la section indiqués en tête de l'extrait,
sans parler d'extrait."""

_CITATION = re.compile(r"\[(\d{1,3})\]")
_SPACES_BEFORE_PUNCT = re.compile(r"\s+([.,;:!?])")


def _location(hit: Hit) -> str:
    p = hit.payload
    parts = [p.get("title") or p.get("document", ""), p.get("section_path") or p.get("section", "")]
    if p.get("page"):
        parts.append(f"page {p['page']}")
    return ", ".join(part for part in parts if part)


def build_messages(question: str, hits: list[Hit]) -> list[dict]:
    extracts = "\n\n".join(f"[{i}] {_location(h)}\n{h.payload.get('text', '')}" for i, h in enumerate(hits, 1))
    user = f"Extraits de la documentation\n\n{extracts}\n\nQuestion\n{question}"
    return [{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": user}]


def cited_numbers(answer: str, available: int) -> list[int]:
    seen: list[int] = []
    for match in _CITATION.finditer(answer):
        number = int(match.group(1))
        if 1 <= number <= available and number not in seen:
            seen.append(number)
    return seen


def renumber(answer: str, mapping: dict[int, int]) -> str:
    # Les numéros cités deviennent la position de la source renvoyée, une citation inventée est retirée
    def replace(match: re.Match) -> str:
        number = mapping.get(int(match.group(1)))
        return f"[{number}]" if number else ""
    return _SPACES_BEFORE_PUNCT.sub(r"\1", _CITATION.sub(replace, answer)).strip()


def _normalize(text: str) -> str:
    text = unicodedata.normalize("NFKD", text.lower())
    return re.sub(r"[^a-z ]", "", "".join(c for c in text if not unicodedata.combining(c))).strip()


def is_refusal(answer: str) -> bool:
    return _normalize(REFUSAL)[:40] in _normalize(answer) or _normalize(answer).startswith("je ne trouve pas")
