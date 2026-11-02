# backend/tests/conftest.py
# Application complète par test, base SQLite temporaire, Qdrant en mémoire et faux modèle d'embedding
import pytest
from fastapi.testclient import TestClient
from qdrant_client import QdrantClient

from app.main import create_app
from app.store import VectorStore
from tests.fakes import ADMIN_EMAIL, ADMIN_PASSWORD, FakeEmbedder, make_settings


@pytest.fixture
def settings(tmp_path):
    return make_settings(tmp_path / "data")


@pytest.fixture
def store():
    return VectorStore(QdrantClient(":memory:"), payload_indexes=False)


@pytest.fixture
def client(settings, store):
    app = create_app(settings, store=store, embedder=FakeEmbedder())
    with TestClient(app) as test_client:
        yield test_client


def login(client: TestClient, email: str = ADMIN_EMAIL, password: str = ADMIN_PASSWORD) -> dict:
    r = client.post("/auth/token", data={"username": email, "password": password})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


@pytest.fixture
def admin(client):
    return login(client)
