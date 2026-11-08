# backend/app/rag.py
# Chaîne de réponse (Chapitre 2, section 3.3), question, passages au-dessus du seuil, modèle, citations vérifiées
import time
from collections.abc import Iterator
from dataclasses import dataclass, field

from app.config import Settings
from app.embeddings import Embedder
from app.llm import ChatModel
from app.prompt import REFUSAL, build_messages, cited_numbers, is_refusal, renumber
from app.store import Hit, VectorStore

RRF_K, RRF_CANDIDATES = 60, 20


def fuse(rankings: list[list[Hit]], limit: int) -> list[Hit]:
    # Fusion par rang réciproque, un passage trouvé par mots-clés passe même sous le seuil de similarité
    scores: dict[str, float] = {}
    hits: dict[str, Hit] = {}
    for ranking in rankings:
        for rank, hit in enumerate(ranking, 1):
            scores[hit.id] = scores.get(hit.id, 0.0) + 1 / (RRF_K + rank)
            hits.setdefault(hit.id, hit)
    return [hits[i] for i in sorted(scores, key=scores.__getitem__, reverse=True)[:limit]]


@dataclass
class RagAnswer:
    answer: str
    found: bool
    sources: list[Hit]
    retrieved: list[Hit]
    timings: dict[str, float] = field(default_factory=dict)
    context: list[Hit] = field(default_factory=list)


class Assistant:
    def __init__(self, settings: Settings, embedder: Embedder, store: VectorStore, model: ChatModel):
        self.settings, self.embedder, self.store, self.model = settings, embedder, store, model

    def retrieve(self, question: str, corpus: str, top_k: int | None) -> tuple[list[Hit], list[Hit], dict]:
        started, limit = time.monotonic(), top_k or self.settings.top_k
        vector = self.embedder.embed([question])[0]
        if self.settings.retrieval_mode == "dense":
            hits = self.store.search(corpus, vector, limit)
            kept = [h for h in hits if h.score >= self.settings.min_score]
            return hits, kept, {"recherche": time.monotonic() - started}
        candidates = max(4 * limit, RRF_CANDIDATES)
        dense = self.store.search(corpus, vector, candidates)
        words = self.store.search_keywords(corpus, question, vector, candidates)
        hits = fuse([dense, words], limit)
        kept = fuse([[h for h in dense if h.score >= self.settings.min_score], words], limit)
        return hits, kept, {"recherche": time.monotonic() - started}

    @staticmethod
    def _finalize(answer: str, kept: list[Hit], hits: list[Hit], timings: dict) -> RagAnswer:
        cited = cited_numbers(answer, len(kept))
        if is_refusal(answer) and not cited:
            return RagAnswer(REFUSAL, False, [], hits, timings, kept)
        if not cited:
            return RagAnswer(answer, True, kept, hits, timings, kept)
        mapping = {number: position for position, number in enumerate(cited, 1)}
        return RagAnswer(renumber(answer, mapping), True, [kept[n - 1] for n in cited], hits, timings, kept)

    def ask(self, question: str, corpus: str, top_k: int | None = None) -> RagAnswer:
        hits, kept, timings = self.retrieve(question, corpus, top_k)
        if not kept:
            return RagAnswer(REFUSAL, False, [], hits, timings)
        started = time.monotonic()
        answer = self.model.complete(build_messages(question, kept))
        timings["generation"] = time.monotonic() - started
        return self._finalize(answer, kept, hits, timings)

    def ask_stream(self, question: str, corpus: str, top_k: int | None = None) -> Iterator[tuple[str, object]]:
        yield "statut", "recherche"
        hits, kept, timings = self.retrieve(question, corpus, top_k)
        if not kept:
            yield "fin", RagAnswer(REFUSAL, False, [], hits, timings)
            return
        yield "statut", "redaction"
        started, parts = time.monotonic(), []
        for piece in self.model.stream(build_messages(question, kept)):
            parts.append(piece)
            yield "texte", piece
        timings["generation"] = time.monotonic() - started
        yield "fin", self._finalize("".join(parts).strip(), kept, hits, timings)
