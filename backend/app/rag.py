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


@dataclass
class RagAnswer:
    answer: str
    found: bool
    sources: list[Hit]
    retrieved: list[Hit]
    timings: dict[str, float] = field(default_factory=dict)


class Assistant:
    def __init__(self, settings: Settings, embedder: Embedder, store: VectorStore, model: ChatModel):
        self.settings, self.embedder, self.store, self.model = settings, embedder, store, model

    def _retrieve(self, question: str, corpus: str, top_k: int | None) -> tuple[list[Hit], list[Hit], dict]:
        started = time.monotonic()
        vector = self.embedder.embed([question])[0]
        hits = self.store.search(corpus, vector, top_k or self.settings.top_k)
        kept = [h for h in hits if h.score >= self.settings.min_score]
        return hits, kept, {"recherche": time.monotonic() - started}

    @staticmethod
    def _finalize(answer: str, kept: list[Hit], hits: list[Hit], timings: dict) -> RagAnswer:
        cited = cited_numbers(answer, len(kept))
        if is_refusal(answer) and not cited:
            return RagAnswer(REFUSAL, False, [], hits, timings)
        if not cited:
            return RagAnswer(answer, True, kept, hits, timings)
        mapping = {number: position for position, number in enumerate(cited, 1)}
        return RagAnswer(renumber(answer, mapping), True, [kept[n - 1] for n in cited], hits, timings)

    def ask(self, question: str, corpus: str, top_k: int | None = None) -> RagAnswer:
        hits, kept, timings = self._retrieve(question, corpus, top_k)
        if not kept:
            return RagAnswer(REFUSAL, False, [], hits, timings)
        started = time.monotonic()
        answer = self.model.complete(build_messages(question, kept))
        timings["generation"] = time.monotonic() - started
        return self._finalize(answer, kept, hits, timings)

    def ask_stream(self, question: str, corpus: str, top_k: int | None = None) -> Iterator[tuple[str, object]]:
        yield "statut", "recherche"
        hits, kept, timings = self._retrieve(question, corpus, top_k)
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
