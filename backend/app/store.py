# backend/app/store.py
# Index Qdrant, une collection par corpus (ENF6), vecteur dense nommé pour ajouter BM25 sans tout reconstruire
from dataclasses import dataclass

from qdrant_client import QdrantClient
from qdrant_client import models as qm

from app.config import Settings

DENSE = "dense"
KEYWORD_FIELDS = ("document", "content_hash")


class StoreError(RuntimeError):
    pass


@dataclass
class Hit:
    id: str
    score: float
    payload: dict


def _match(field: str, value: str) -> qm.FieldCondition:
    return qm.FieldCondition(key=field, match=qm.MatchValue(value=value))


class VectorStore:
    def __init__(self, client: QdrantClient, payload_indexes: bool = True):
        self.client = client
        self.payload_indexes = payload_indexes

    @classmethod
    def from_settings(cls, settings: Settings) -> "VectorStore":
        return cls(QdrantClient(url=settings.qdrant_url, timeout=int(settings.qdrant_timeout)))

    def exists(self, corpus: str) -> bool:
        return self.client.collection_exists(corpus)

    def ensure_collection(self, corpus: str, dim: int, embed_model: str) -> None:
        if self.exists(corpus):
            self.check_model(corpus, embed_model, dim)
            return
        self.client.create_collection(
            corpus,
            vectors_config={DENSE: qm.VectorParams(size=dim, distance=qm.Distance.COSINE)},
            metadata={"embed_model": embed_model, "dim": dim},
        )
        if self.payload_indexes:
            for field in KEYWORD_FIELDS:
                self.client.create_payload_index(corpus, field, qm.PayloadSchemaType.KEYWORD)

    def check_model(self, corpus: str, embed_model: str, dim: int | None = None) -> None:
        metadata = self.client.get_collection(corpus).config.metadata or {}
        if metadata.get("embed_model") != embed_model or (dim is not None and metadata.get("dim") != dim):
            raise StoreError(f"la collection {corpus} a été indexée avec {metadata.get('embed_model')} "
                             f"({metadata.get('dim')} dimensions), réindexer avec --reset pour passer à {embed_model}")

    def drop(self, corpus: str) -> None:
        if self.exists(corpus):
            self.client.delete_collection(corpus)

    def has_version(self, corpus: str, document: str, content_hash: str) -> bool:
        if not self.exists(corpus):
            return False
        flt = qm.Filter(must=[_match("document", document), _match("content_hash", content_hash)])
        return self.client.count(corpus, count_filter=flt, exact=True).count > 0

    def replace_document(self, corpus: str, document: str, content_hash: str, points: list[qm.PointStruct]) -> None:
        # Nouvelle version écrite avant de retirer l'ancienne, le document n'est jamais absent de l'index
        self.client.upsert(corpus, points=points, wait=True)
        stale = qm.Filter(must=[_match("document", document)], must_not=[_match("content_hash", content_hash)])
        self.client.delete(corpus, points_selector=qm.FilterSelector(filter=stale), wait=True)

    def delete_document(self, corpus: str, document: str) -> None:
        if self.exists(corpus):
            flt = qm.Filter(must=[_match("document", document)])
            self.client.delete(corpus, points_selector=qm.FilterSelector(filter=flt), wait=True)

    def documents(self, corpus: str) -> dict[str, int]:
        if not self.exists(corpus):
            return {}
        hits = self.client.facet(corpus, key="document", exact=True, limit=100_000).hits
        return {str(h.value): h.count for h in hits}

    def count(self, corpus: str) -> int:
        return self.client.count(corpus, exact=True).count if self.exists(corpus) else 0

    def search(self, corpus: str, vector: list[float], limit: int) -> list[Hit]:
        if not self.exists(corpus):
            raise StoreError(f"le corpus {corpus} n'est pas indexé")
        result = self.client.query_points(corpus, query=vector, using=DENSE, limit=limit, with_payload=True)
        return [Hit(str(p.id), p.score, p.payload or {}) for p in result.points]
