# backend/tests/test_chat.py
import json

import pytest
from fastapi.testclient import TestClient

from app.llm import LLMError
from app.main import create_app
from app.prompt import REFUSAL
from tests.conftest import login
from tests.fakes import FakeEmbedder
from tests.test_documents import settle, upload

ARCHI = ("# Architecture\n\n## Passerelle\n\nLa passerelle LiteLLM écoute sur le port 4000 du serveur EMILIA.\n\n"
         "## Calcul\n\nOllama tourne sur REM, port 11434.\n")


class FakeModel:
    def __init__(self, answer: str = "LiteLLM écoute sur le port 4000 [2]. Voir aussi [9]."):
        self.answer, self.calls = answer, []

    def complete(self, messages):
        self.calls.append(messages)
        if isinstance(self.answer, Exception):
            raise self.answer
        return self.answer

    def stream(self, messages):
        answer = self.complete(messages)
        for i in range(0, len(answer), 10):
            yield answer[i:i + 10]


@pytest.fixture
def model():
    return FakeModel()


@pytest.fixture
def client(settings, store, model):
    with TestClient(create_app(settings, store=store, embedder=FakeEmbedder(), model=model)) as test_client:
        admin = login(test_client)
        upload(test_client, admin, content=ARCHI, filename="architecture.md", title="Architecture GANDAL")
        settle(test_client)
        yield test_client


def ask(client, headers, message="Sur quel port écoute la passerelle LiteLLM ?", **extra):
    return client.post("/chat", headers=headers, json={"message": message, **extra})


def test_reponse_citee_et_sources_renumerotees(client, model, settings):
    settings.min_score = 0.0
    r = ask(client, login(client))
    body = r.json()
    assert r.status_code == 200 and body["found"] is True
    assert body["answer"] == "LiteLLM écoute sur le port 4000 [1]. Voir aussi."
    assert len(body["sources"]) == 1
    source = body["sources"][0]
    assert source["document"] == "architecture.md" and source["title"] == "Architecture GANDAL"
    assert source["version"] == "1.0" and 0 < source["score"] <= 1
    assert "Question\nSur quel port écoute la passerelle LiteLLM ?" in model.calls[0][1]["content"]


def test_refus_sans_appel_au_modele_sous_le_seuil(client, model, settings):
    settings.min_score = 0.99
    body = ask(client, login(client), message="Quelle est la recette du ndolé ?").json()
    assert body == {"answer": REFUSAL, "found": False, "sources": []} and model.calls == []


def test_refus_du_modele(client, model, settings):
    settings.min_score = 0.0
    model.answer = REFUSAL
    assert ask(client, login(client), message="Quel est le mot de passe du pare-feu ?").json()["found"] is False


def test_acces_client_cle_de_service_ou_refuse(client):
    client.post("/auth/register", json={"name": "Alice", "email": "client@test.cm",
                                        "password": "mot-de-passe-client"})
    assert ask(client, login(client, "client@test.cm", "mot-de-passe-client")).status_code == 200
    key = client.post("/admin/service-keys", headers=login(client), json={"name": "frontend"}).json()["key"]
    assert ask(client, {"X-API-Key": key}).status_code == 200
    assert ask(client, {}).status_code == 401
    assert ask(client, {"X-API-Key": "gai_fausse"}).status_code == 401


def test_validation_de_la_question_et_du_corpus(client):
    admin = login(client)
    assert ask(client, admin, message="   ").status_code == 422
    assert ask(client, admin, message="x" * 1001).status_code == 422
    assert ask(client, admin, corpus="tuteur").status_code == 404
    assert ask(client, admin, corpus="../etc").status_code == 422


def test_modele_en_panne_signale_avec_reference(client, model):
    model.answer = LLMError("serveur de modèles injoignable")
    admin = login(client)
    r = ask(client, admin)
    assert r.status_code == 503 and r.json()["request_id"] in r.json()["detail"]
    event = client.get("/admin/events", headers=admin, params={"request_id": r.json()["request_id"]}).json()[0]
    assert event["category"] == "chat" and "injoignable" in event["message"]
    detail = client.get(f"/admin/events/{event['id']}", headers=admin).json()["detail"]
    assert "Sur quel port écoute la passerelle LiteLLM" in detail and "LLMError" in detail


def test_question_journalisee_sans_son_texte(client):
    admin = login(client)
    ask(client, admin, message="Question confidentielle sur le port de LiteLLM")
    events = client.get("/admin/events", headers=admin, params={"category": "chat"}).json()
    assert events and "confidentielle" not in str(events)


def test_limite_de_debit_par_appelant(client, settings):
    client.app.state.limiters["chat"].limit = 2
    admin = login(client)
    assert [ask(client, admin).status_code for _ in range(3)] == [200, 200, 429]


def events_of(response) -> list[tuple[str, dict]]:
    parsed = []
    for block in response.text.strip().split("\n\n"):
        lines = dict(line.split(": ", 1) for line in block.splitlines())
        parsed.append((lines["event"], json.loads(lines["data"])))
    return parsed


def test_reponse_en_continu(client, settings):
    settings.min_score = 0.0
    r = client.post("/chat/stream", headers=login(client), json={"message": "Port de LiteLLM ?"})
    assert r.status_code == 200 and r.headers["content-type"].startswith("text/event-stream")
    stream = events_of(r)
    assert [kind for kind, _ in stream[:2]] == ["statut", "statut"] and stream[1][1] == {"etape": "redaction"}
    assert "".join(d["texte"] for k, d in stream if k == "texte") == "LiteLLM écoute sur le port 4000 [2]. Voir aussi [9]."
    kind, final = stream[-1]
    assert kind == "fin" and final["answer"] == "LiteLLM écoute sur le port 4000 [1]. Voir aussi."
    assert final["sources"][0]["document_id"] and final["found"] is True


def test_refus_en_continu_sans_modele(client, model, settings):
    settings.min_score = 0.99
    stream = events_of(client.post("/chat/stream", headers=login(client), json={"message": "Recette du ndolé ?"}))
    assert [k for k, _ in stream] == ["statut", "fin"] and stream[-1][1]["found"] is False and model.calls == []


def test_panne_en_continu_signalee(client, model, settings):
    settings.min_score = 0.0
    model.answer = LLMError("serveur de modèles injoignable")
    r = client.post("/chat/stream", headers=login(client), json={"message": "Port de LiteLLM ?"})
    kind, data = events_of(r)[-1]
    assert kind == "erreur" and data["request_id"] == r.headers["x-request-id"] and data["request_id"] in data["detail"]


def test_documentation_consultable_et_source_ouvrable(client, settings):
    settings.min_score = 0.0
    client.post("/auth/register", json={"name": "Alice", "email": "lectrice@test.cm", "password": "mot-de-passe-client"})
    reader = login(client, "lectrice@test.cm", "mot-de-passe-client")
    documents = client.get("/documents", headers=reader).json()
    assert [d["title"] for d in documents] == ["Architecture GANDAL"] and documents[0]["chunks"] == 2
    source = ask(client, reader).json()["sources"][0]
    opened = client.get(f"/documents/{source['document_id']}/file", headers=reader)
    assert opened.status_code == 200 and "inline" in opened.headers["content-disposition"]
    assert "LiteLLM" in opened.text
    assert client.get("/documents").status_code == 401
    assert client.get("/documents/inconnu/file", headers=reader).status_code == 404
