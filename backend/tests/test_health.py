# backend/tests/test_health.py
import httpx2 as httpx
import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app, get_http

SETTINGS = Settings(_env_file=None, llm_api_key="cle-de-test",
                    llm_model="qwen3:4b-instruct-2507-q4_K_M", embed_model="bge-m3")


def fake_services(models: list[str], qdrant_up: bool = True):
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/v1/models":
            return httpx.Response(200, json={"object": "list", "data": [{"id": m} for m in models]})
        if request.url.port == 6333 and qdrant_up:
            return httpx.Response(200, json={"title": "qdrant", "version": "1.19.2"})
        raise httpx.ConnectError("injoignable", request=request)
    return handler


@pytest.fixture
def client_for():
    def build(handler) -> TestClient:
        app = create_app(SETTINGS)
        app.dependency_overrides[get_http] = lambda: httpx.Client(transport=httpx.MockTransport(handler))
        return TestClient(app)
    return build


def test_health_ok_quand_tout_repond(client_for):
    body = client_for(fake_services(["qwen3:4b-instruct-2507-q4_K_M", "bge-m3:latest"])).get("/health").json()
    assert body["status"] == "ok"
    assert body["services"]["models"]["missing"] == []
    assert body["services"]["qdrant"]["version"] == "1.19.2"


def test_health_signale_un_modele_manquant(client_for):
    body = client_for(fake_services(["qwen3:4b-instruct-2507-q4_K_M"])).get("/health").json()
    assert body["status"] == "degraded"
    assert body["services"]["models"]["missing"] == ["bge-m3"]


def test_health_signale_qdrant_injoignable(client_for):
    body = client_for(fake_services(["qwen3:4b-instruct-2507-q4_K_M", "bge-m3"], qdrant_up=False)).get("/health").json()
    assert body["status"] == "degraded"
    assert body["services"]["qdrant"]["ok"] is False
    assert body["services"]["models"]["ok"] is True
