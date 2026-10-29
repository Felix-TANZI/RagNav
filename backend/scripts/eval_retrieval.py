# backend/scripts/eval_retrieval.py
# Rappel@k de l'index sur le jeu d'évaluation (Chapitre 2, section 1.4), sans LLM
import argparse
import json
import statistics
import sys
from pathlib import Path

from app.config import get_settings
from app.embeddings import Embedder, EmbeddingError
from app.store import StoreError, VectorStore


def rank_of(question: dict, hits: list) -> int | None:
    for rank, hit in enumerate(hits, start=1):
        if hit.payload.get("document") == question["document"] and hit.payload.get("section") == question["section"]:
            return rank
    return None


def main() -> int:
    settings = get_settings()
    parser = argparse.ArgumentParser(description="Rappel@k de l'index")
    parser.add_argument("--questions", type=Path, default=Path("../eval/questions.jsonl"))
    parser.add_argument("--corpus", default=settings.default_corpus)
    parser.add_argument("--k", type=int, default=5)
    args = parser.parse_args()

    questions = [json.loads(line) for line in args.questions.read_text(encoding="utf-8").splitlines() if line.strip()]
    store, embedder = VectorStore.from_settings(settings), Embedder(settings)
    try:
        store.check_model(args.corpus, settings.embed_model)
        vectors = embedder.embed([q["question"] for q in questions])
        results = [store.search(args.corpus, v, args.k) for v in vectors]
    except (EmbeddingError, StoreError) as e:
        print(f"Évaluation impossible, {e}", file=sys.stderr)
        return 2

    ranks, answered_scores, refused_scores = [], [], []
    for q, hits in zip(questions, results):
        best = hits[0].score if hits else 0.0
        if q["reponse"] is None:
            refused_scores.append(best)
            print(f"{q['id']} hors corpus  meilleur score {best:.3f}  {q['question']}")
            continue
        rank = rank_of(q, hits)
        ranks.append(rank)
        answered_scores.append(best)
        found = f"rang {rank}" if rank else "ABSENT"
        print(f"{q['id']} {found:<8} meilleur score {best:.3f}  {q['question']}")

    total = len(ranks)
    print(f"\nQuestions avec réponse {total}, hors corpus {len(refused_scores)}")
    for k in sorted({1, 3, args.k}):
        hit = sum(1 for r in ranks if r and r <= k)
        print(f"Rappel@{k}  {hit}/{total}  {100 * hit / total:.0f} %")
    print(f"MRR       {sum(1 / r for r in ranks if r) / total:.3f}")
    if answered_scores and refused_scores:
        print(f"Score du premier passage, avec réponse min {min(answered_scores):.3f} "
              f"médiane {statistics.median(answered_scores):.3f}, hors corpus max {max(refused_scores):.3f} "
              f"médiane {statistics.median(refused_scores):.3f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
