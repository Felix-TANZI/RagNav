# backend/app/rag.py
# Chaîne de réponse (Chapitre 2, section 3.3), question, passages au-dessus du seuil, modèle, citations vérifiées
import time
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

    def ask(self, question: str, corpus: str, top_k: int | None = None) -> RagAnswer:
        timings: dict[str, float] = {}
        started = time.monotonic()
        vector = self.embedder.embed([question])[0]
        hits = self.store.search(corpus, vector, top_k or self.settings.top_k)
        timings["recherche"] = time.monotonic() - started
        kept = [h for h in hits if h.score >= self.settings.min_score]
        if not kept:
            return RagAnswer(REFUSAL, False, [], hits, timings)

        started = time.monotonic()
        answer = self.model.complete(build_messages(question, kept))
        timings["generation"] = time.monotonic() - started
        cited = cited_numbers(answer, len(kept))
        if is_refusal(answer) and not cited:
            return RagAnswer(REFUSAL, False, [], hits, timings)
        if not cited:
            return RagAnswer(answer, True, kept, hits, timings)
        mapping = {number: position for position, number in enumerate(cited, 1)}
        return RagAnswer(renumber(answer, mapping), True, [kept[n - 1] for n in cited], hits, timings)
