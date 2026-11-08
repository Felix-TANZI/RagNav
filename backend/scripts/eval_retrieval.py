# backend/scripts/eval_retrieval.py
# Rappel@k de la recherche sur le jeu d'évaluation (Chapitre 2, section 1.4), sans appel au modèle de langue
# Un passage « filtré » est retrouvé mais écarté par le seuil, le modèle ne le verra pas
import argparse
import json
import statistics
import sys
from pathlib import Path

from app.config import get_settings
from app.embeddings import Embedder, EmbeddingError
from app.llm import ChatModel
from app.rag import Assistant
from app.store import StoreError, VectorStore


def expected_sources(question: dict) -> set[tuple[str, str]]:
    others = {(d, s) for d, s in question.get("autres_sources", [])}
    return {(question["document"], question["section"])} | others


def rank_of(question: dict, hits: list) -> int | None:
    expected = expected_sources(question)
    for rank, hit in enumerate(hits, start=1):
        if (hit.payload.get("document"), hit.payload.get("section")) in expected:
            return rank
    return None


def main() -> int:
    settings = get_settings()
    parser = argparse.ArgumentParser(description="Rappel@k de la recherche")
    parser.add_argument("--questions", type=Path, default=Path("../eval/questions.jsonl"))
    parser.add_argument("--corpus", default=settings.default_corpus)
    parser.add_argument("--k", type=int, default=5)
    parser.add_argument("--mode", choices=["hybride", "dense"], default=settings.retrieval_mode)
    args = parser.parse_args()

    settings = settings.model_copy(update={"retrieval_mode": args.mode})
    questions = [json.loads(line) for line in args.questions.read_text(encoding="utf-8").splitlines() if line.strip()]
    store = VectorStore.from_settings(settings)
    assistant = Assistant(settings, Embedder(settings), store, ChatModel(settings))
    try:
        store.check_model(args.corpus, settings.embed_model)
        results = [assistant.retrieve(q["question"], args.corpus, args.k)[:2] for q in questions]
    except (EmbeddingError, StoreError) as e:
        print(f"Évaluation impossible, {e}", file=sys.stderr)
        return 2

    print(f"Recherche {args.mode}, {args.k} passages, seuil {settings.min_score}")
    ranks, kept_ranks, early_refusals, answered_scores, refused_scores = [], [], [], [], []
    for q, (hits, kept) in zip(questions, results):
        best = max((h.score for h in hits), default=0.0)
        if q["reponse"] is None:
            refused_scores.append(best)
            early_refusals.append(not kept)
            verdict = "refus sans modèle" if not kept else f"{len(kept)} passage(s) au modèle"
            print(f"{q['id']} hors corpus  {verdict:<24} meilleur score {best:.3f}  {q['question']}")
            continue
        rank, kept_rank = rank_of(q, hits), rank_of(q, kept)
        ranks.append(rank)
        kept_ranks.append(kept_rank)
        answered_scores.append(best)
        found = f"rang {kept_rank}" if kept_rank else ("FILTRÉ" if rank else "ABSENT")
        print(f"{q['id']} {found:<8} meilleur score {best:.3f}  {q['question']}")

    total = len(ranks)
    print(f"\nQuestions avec réponse {total}, hors corpus {len(refused_scores)}")
    for k in sorted({1, 3, args.k}):
        hit = sum(1 for r in kept_ranks if r and r <= k)
        print(f"Rappel@{k}  {hit}/{total}  {100 * hit / total:.0f} %")
    print(f"MRR       {sum(1 / r for r in kept_ranks if r) / total:.3f}")
    print(f"Hors corpus refusées sans appel au modèle  {sum(early_refusals)}/{len(early_refusals)}")
    if answered_scores and refused_scores:
        print(f"Meilleure similarité, avec réponse min {min(answered_scores):.3f} "
              f"médiane {statistics.median(answered_scores):.3f}, hors corpus max {max(refused_scores):.3f} "
              f"médiane {statistics.median(refused_scores):.3f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
