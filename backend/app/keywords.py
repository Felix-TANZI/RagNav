# backend/app/keywords.py
# Vecteur creux BM25 d'un passage ou d'une question, Qdrant applique l'IDF (Modifier.IDF)
# Les identifiants techniques restent entiers (10.10.40.30, dcgm-exporter, /mnt/projets) et leurs parties sont ajoutées
import re
import unicodedata
import zlib
from collections import Counter

from qdrant_client import models as qm

VERSION = "1"
K, B, AVERAGE_LENGTH = 1.2, 0.75, 200
_TOKEN = re.compile(r"[a-z0-9]+(?:[._/:-][a-z0-9]+)*")
_SEPARATORS = re.compile(r"[._/:-]")
STOPWORDS = frozenset("""
a au aux avec ce ces cet cette comment dans de des du elle en est et etre il ils je la le les leur lui ma mais me
meme mes moi mon ne nos notre nous on ou par pas pour qu que quel quelle quelles quels qui sa se ses son sont sur
ta te tes toi ton tu un une vos votre vous y ai as avons avez ont ete fait faut peut peuvent doit combien quand
quoi dont ceci cela ca tout tous toute toutes plus moins tres aussi alors donc ainsi entre sous vers chez
the an and or of to in on at by for with from is are was were be been it its this that these those what which who
whom how when where why do does did can could should would will my your our their as if not no yes into about
""".split())


def fold(text: str) -> str:
    decomposed = unicodedata.normalize("NFKD", text.lower().replace("œ", "oe").replace("æ", "ae"))
    return "".join(c for c in decomposed if not unicodedata.combining(c))


def _stem(token: str) -> str:
    return token[:-1] if token.isalpha() and len(token) > 3 and token.endswith("s") else token


def tokenize(text: str) -> list[str]:
    tokens = []
    for token in _TOKEN.findall(fold(text)):
        parts = _SEPARATORS.split(token)
        candidates = [token, *parts] if len(parts) > 1 and any(c.isalpha() for c in token) else [token]
        tokens.extend(_stem(t) for t in candidates if len(t) > 1 and t not in STOPWORDS)
    return tokens


def _vector(weights: dict[str, float]) -> qm.SparseVector:
    merged: dict[int, float] = {}
    for token, weight in weights.items():
        index = zlib.crc32(token.encode())
        merged[index] = merged.get(index, 0.0) + weight
    indices = sorted(merged)
    return qm.SparseVector(indices=indices, values=[merged[i] for i in indices])


def passage_vector(text: str) -> qm.SparseVector:
    counts = Counter(tokenize(text))
    norm = K * (1 - B + B * sum(counts.values()) / AVERAGE_LENGTH)
    return _vector({t: n * (K + 1) / (n + norm) for t, n in counts.items()})


def query_vector(text: str) -> qm.SparseVector | None:
    tokens = set(tokenize(text))
    return _vector(dict.fromkeys(tokens, 1.0)) if tokens else None
