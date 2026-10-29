# backend/tests/test_embeddings.py
import json

import httpx2 as httpx
import pytest

from app.config import Settings
from app.embeddings import Embedder, EmbeddingError

SETTINGS = Settings(_env_file=None, llm_api_key="cle-de-test", embed_batch_size=2)


def embedder(handler) -> Embedder:
    return Embedder(SETTINGS, http=httpx.Client(transport=httpx.MockTransport(handler)))


def test_lots_ordre_et_cle():
    seen = []

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        seen.append((request.url.path, request.headers["authorization"], body["input"]))
        data = [{"index": i, "embedding": [float(len(t)), 1.0]} for i, t in enumerate(body["input"])]
        return httpx.Response(200, json={"data": list(reversed(data))})

    vectors = embedder(handler).embed(["a", "bb", "ccc"])
    assert vectors == [[1.0, 1.0], [2.0, 1.0], [3.0, 1.0]]
    assert [s[2] for s in seen] == [["a", "bb"], ["ccc"]]
    assert seen[0][:2] == ("/v1/embeddings", "Bearer cle-de-test")


@pytest.mark.parametrize("response, message", [
    (httpx.Response(500, text="panne"), "500"),
    (httpx.Response(200, json={"data": [{"index": 0, "embedding": [1.0]}]}), "1 vecteurs reçus pour 2"),
    (httpx.Response(200, json={"oups": []}), "inattendue"),
])
def test_erreurs(response, message):
    with pytest.raises(EmbeddingError, match=message):
        embedder(lambda request: response).embed(["a", "b"])


def test_serveur_injoignable():
    def handler(request):
        raise httpx.ConnectError("refus", request=request)
    with pytest.raises(EmbeddingError, match="injoignable"):
        embedder(handler).embed(["a"])
