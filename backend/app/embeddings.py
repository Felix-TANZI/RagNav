# backend/app/embeddings.py
# Embeddings par l'API compatible OpenAI, la même pour Ollama sur le PC et LiteLLM sur GANDAL
import httpx2 as httpx

from app.config import Settings


class EmbeddingError(RuntimeError):
    pass


class Embedder:
    def __init__(self, settings: Settings, http: httpx.Client | None = None):
        self.model = settings.embed_model
        self.batch_size = settings.embed_batch_size
        self._url = f"{settings.llm_base_url.rstrip('/')}/embeddings"
        self._headers = {"Authorization": f"Bearer {settings.llm_api_key.get_secret_value()}"}
        self._http = http or httpx.Client(timeout=settings.embed_timeout)

    def embed(self, texts: list[str]) -> list[list[float]]:
        vectors: list[list[float]] = []
        for start in range(0, len(texts), self.batch_size):
            batch = texts[start:start + self.batch_size]
            vectors.extend(self._embed_batch(batch))
        if len({len(v) for v in vectors}) > 1:
            raise EmbeddingError("le modèle a renvoyé des vecteurs de tailles différentes")
        return vectors

    def _embed_batch(self, batch: list[str]) -> list[list[float]]:
        try:
            r = self._http.post(self._url, headers=self._headers, json={"model": self.model, "input": batch})
            r.raise_for_status()
            data = sorted(r.json()["data"], key=lambda item: item["index"])
        except httpx.HTTPStatusError as e:
            raise EmbeddingError(f"{self._url} a répondu {e.response.status_code}, {e.response.text[:200]}") from e
        except httpx.HTTPError as e:
            raise EmbeddingError(f"serveur de modèles injoignable ({self._url}, {e})") from e
        except (KeyError, TypeError, ValueError) as e:
            raise EmbeddingError(f"réponse d'embeddings inattendue ({e})") from e
        if len(data) != len(batch):
            raise EmbeddingError(f"{len(data)} vecteurs reçus pour {len(batch)} textes")
        return [item["embedding"] for item in data]
