# backend/scripts/evaluate.py
# Évaluation de bout en bout (Chapitre 2, section 1.4), refus, citations, mots-clés, fidélité et latence
# La fidélité automatique vérifie que chaque nombre de la réponse (port, adresse, durée) figure dans les extraits
import argparse
import csv
import json
import re
import statistics
import sys
import time
from pathlib import Path

from app.config import get_settings
from app.embeddings import Embedder, EmbeddingError
from app.llm import ChatModel, LLMError
from app.prompt import location
from app.rag import Assistant
from app.store import StoreError, VectorStore
from scripts.eval_retrieval import expected_sources

NUMBER = re.compile(r"\d+(?:[.,/:]\d+)*")
CITATION = re.compile(r"\[\d{1,3}\]")


def rate(values: list[bool]) -> str:
    return f"{sum(values)}/{len(values)}  {100 * sum(values) / len(values):.0f} %" if values else "aucune"


def unsourced_numbers(answer: str, context: list) -> list[str]:
    source = " ".join(f"{location(h)} {h.payload.get('text', '')}" for h in context).replace("\u202f", " ")
    return [n for n in NUMBER.findall(CITATION.sub(" ", answer)) if n not in source]


def main() -> int:
    settings = get_settings()
    parser = argparse.ArgumentParser(description="Évaluation de bout en bout de l'assistant")
    parser.add_argument("--questions", type=Path, default=Path("../eval/questions.jsonl"))
    parser.add_argument("--out", type=Path, default=Path("../eval/resultats.csv"))
    parser.add_argument("--corpus", default=settings.default_corpus)
    parser.add_argument("--top-k", type=int, default=settings.top_k)
    parser.add_argument("--mode", choices=["hybride", "dense"], default=settings.retrieval_mode)
    parser.add_argument("--ids", help="questions à rejouer, par exemple Q19,Q20,H01")
    args = parser.parse_args()
    settings = settings.model_copy(update={"retrieval_mode": args.mode})

    questions = [json.loads(line) for line in args.questions.read_text(encoding="utf-8").splitlines() if line.strip()]
    if args.ids:
        wanted = {i.strip() for i in args.ids.split(",")}
        questions = [q for q in questions if q["id"] in wanted]
    assistant = Assistant(settings, Embedder(settings), VectorStore.from_settings(settings), ChatModel(settings))
    rows, refusals, false_refusals, keywords, citations, faithful, latencies = [], [], [], [], [], [], []
    print(f"{len(questions)} questions, recherche {args.mode}, {args.top_k} passages, seuil {settings.min_score}")
    for q in questions:
        started = time.monotonic()
        try:
            result = assistant.ask(q["question"], args.corpus, args.top_k)
        except (EmbeddingError, LLMError, StoreError) as e:
            print(f"Évaluation interrompue sur {q['id']}, {e}", file=sys.stderr)
            return 2
        latency = time.monotonic() - started
        latencies.append(latency)
        cited = [(h.payload.get("document"), h.payload.get("section")) for h in result.sources]
        invented = unsourced_numbers(result.answer, result.context) if result.found else []
        row = {"id": q["id"], "cas": q["cas"], "question": q["question"], "trouve": result.found,
               "latence_s": round(latency, 1), "reponse": result.answer, "nombres_hors_extraits": " ".join(invented),
               "sources": " | ".join(f"{d} / {s}" for d, s in cited), "fidele": ""}
        if result.found:
            faithful.append(not invented)
        if q["reponse"] is None:
            refusals.append(not result.found)
            verdict = "refus juste" if not result.found else "A RÉPONDU"
        else:
            false_refusals.append(not result.found)
            keyword_ok = result.found and all(k.lower() in result.answer.lower() for k in q["mots_cles"])
            citation_ok = result.found and bool(expected_sources(q) & set(cited))
            keywords.append(keyword_ok)
            citations.append(citation_ok)
            row.update(mots_cles=keyword_ok, citation_correcte=citation_ok)
            verdict = "FAUX REFUS" if not result.found else f"mots-clés {'ok' if keyword_ok else 'MANQUANTS'}, " \
                                                            f"citation {'ok' if citation_ok else 'AUTRE SOURCE'}"
        if invented:
            verdict += f", HORS EXTRAITS {' '.join(invented)}"
        rows.append(row)
        print(f"{q['id']} {latency:5.1f} s  {verdict:<40} {q['question'][:60]}", flush=True)

    print(f"\nRefus justifiés (hors corpus)     {rate(refusals)}")
    print(f"Faux refus (réponse existante)    {rate(false_refusals)}")
    print(f"Mots-clés attendus présents       {rate(keywords)}")
    print(f"Citation de la bonne section      {rate(citations)}")
    print(f"Réponses sans nombre inventé      {rate(faithful)}")
    print(f"Latence médiane {statistics.median(latencies):.1f} s, maximale {max(latencies):.1f} s")
    fields = ["id", "cas", "question", "trouve", "mots_cles", "citation_correcte", "nombres_hors_extraits", "fidele",
              "latence_s", "reponse", "sources"]
    with args.out.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fields, delimiter=";", extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    print(f"Détail dans {args.out}, colonne fidele à remplir à la main (oui ou non)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
