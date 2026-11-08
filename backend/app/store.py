# backend/app/store.py
# Index Qdrant, une collection par corpus (ENF6), vecteur dense et vecteur creux BM25 par passage
import math
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass

from qdrant_client import QdrantClient
from qdrant_client import models as qm
from qdrant_client.http.exceptions import ApiException

from app import keywords
from app.config import Settings

DENSE = "dense"
KEYWORDS = "mots"
KEYWORD_FIELDS = ("document_id", "content_hash")


class StoreError(RuntimeError):
    pass


@dataclass
class Hit:
    id: str
    score: float
    payload: dict


def _match(field: str, value: str) -> qm.FieldCondition:
    return qm.FieldCondition(key=field, match=qm.MatchValue(value=value))


def _cosine(a: list[float], b: list[float]) -> float:
    norm = math.sqrt(sum(x * x for x in a)) * math.sqrt(sum(y * y for y in b))
    return sum(x * y for x, y in zip(a, b, strict=True)) / norm if norm else 0.0


@contextmanager
def _qdrant(action: str) -> Iterator[None]:
    try:
        yield
    except ApiException as e:
        raise StoreError(f"Qdrant injoignable ou en erreur pendant {action}, {e}") from e


class VectorStore:
    def __init__(self, client: QdrantClient, payload_indexes: bool = True):
        self.client = client
        self.payload_indexes = payload_indexes

    @classmethod
    def from_settings(cls, settings: Settings) -> "VectorStore":
        return cls(QdrantClient(url=settings.qdrant_url, timeout=int(settings.qdrant_timeout)))

    def exists(self, corpus: str) -> bool:
        with _qdrant("la lecture des collections"):
            return self.client.collection_exists(corpus)

    def ensure_collection(self, corpus: str, dim: int, embed_model: str) -> None:
        if self.exists(corpus):
            self.check_model(corpus, embed_model, dim)
        else:
            self.client.create_collection(
                corpus,
                vectors_config={DENSE: qm.VectorParams(size=dim, distance=qm.Distance.COSINE)},
                sparse_vectors_config={KEYWORDS: qm.SparseVectorParams(modifier=qm.Modifier.IDF)},
                metadata={"embed_model": embed_model, "dim": dim, "keywords": keywords.VERSION},
            )
        if self.payload_indexes:
            for field in KEYWORD_FIELDS:
                self.client.create_payload_index(corpus, field, qm.PayloadSchemaType.KEYWORD)

    def check_model(self, corpus: str, embed_model: str, dim: int | None = None) -> None:
        with _qdrant(f"la lecture de la collection {corpus}"):
            metadata = self.client.get_collection(corpus).config.metadata or {}
        if metadata.get("embed_model") != embed_model or (dim is not None and metadata.get("dim") != dim):
            raise StoreError(f"la collection {corpus} a été indexée avec {metadata.get('embed_model')} "
                             f"({metadata.get('dim')} dimensions), réindexer avec --reset pour passer à {embed_model}")
        if metadata.get("keywords") != keywords.VERSION:
            raise StoreError(f"la collection {corpus} n'a pas l'index par mots-clés version {keywords.VERSION}, "
                             "réindexer avec scripts.ingest --reset")

    def drop(self, corpus: str) -> None:
        if self.exists(corpus):
            self.client.delete_collection(corpus)

    def has_version(self, corpus: str, document_id: str, content_hash: str) -> bool:
        if not self.exists(corpus):
            return False
        flt = qm.Filter(must=[_match("document_id", document_id), _match("content_hash", content_hash)])
        return self.client.count(corpus, count_filter=flt, exact=True).count > 0

    def replace_document(self, corpus: str, document_id: str, content_hash: str, points: list[qm.PointStruct]) -> None:
        # Nouvelle version écrite avant de retirer l'ancienne, le document n'est jamais absent de l'index
        self.client.upsert(corpus, points=points, wait=True)
        stale = qm.Filter(must=[_match("document_id", document_id)], must_not=[_match("content_hash", content_hash)])
        self.client.delete(corpus, points_selector=qm.FilterSelector(filter=stale), wait=True)

    def delete_document(self, corpus: str, document_id: str) -> None:
        if self.exists(corpus):
            flt = qm.Filter(must=[_match("document_id", document_id)])
            self.client.delete(corpus, points_selector=qm.FilterSelector(filter=flt), wait=True)

    def documents(self, corpus: str) -> dict[str, int]:
        if not self.exists(corpus):
            return {}
        hits = self.client.facet(corpus, key="document_id", exact=True, limit=100_000).hits
        return {str(h.value): h.count for h in hits}

    def count(self, corpus: str) -> int:
        return self.client.count(corpus, exact=True).count if self.exists(corpus) else 0

    def search(self, corpus: str, vector: list[float], limit: int) -> list[Hit]:
        if not self.exists(corpus):
            raise StoreError(f"le corpus {corpus} n'est pas indexé")
        with _qdrant("la recherche"):
            result = self.client.query_points(corpus, query=vector, using=DENSE, limit=limit, with_payload=True)
        return [Hit(str(p.id), p.score, p.payload or {}) for p in result.points]

    def search_keywords(self, corpus: str, question: str, vector: list[float], limit: int) -> list[Hit]:
        sparse = keywords.query_vector(question)
        if sparse is None or not self.exists(corpus):
            return []
        with _qdrant("la recherche par mots-clés"):
            result = self.client.query_points(corpus, query=sparse, using=KEYWORDS, limit=limit, with_payload=True,
                                              with_vectors=[DENSE])
        return [Hit(str(p.id), _cosine(vector, p.vector[DENSE]), p.payload or {}) for p in result.points]
