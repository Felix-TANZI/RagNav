# backend/tests/test_events.py
# Toute erreur se retrouve dans le journal par sa référence, avec sa cause et sa trace technique
from datetime import timedelta

from app.embeddings import EmbeddingError
from app.models import Event, EventCategory, EventLevel, utcnow
from tests.fakes import ADMIN_EMAIL, ADMIN_PASSWORD
from tests.test_documents import settle, upload


def events(client, admin, **filters):
    r = client.get("/admin/events", headers=admin, params=filters)
    assert r.status_code == 200, r.text
    return r.json()


def test_chaque_reponse_porte_une_reference(client):
    r = client.get("/health")
    assert len(r.headers["x-request-id"]) == 32
    kept = client.get("/auth/me", headers={"X-Request-ID": "ref-du-frontend-1234"})
    assert kept.headers["x-request-id"] == "ref-du-frontend-1234" and kept.json()["request_id"] == "ref-du-frontend-1234"


def test_erreur_interne_retrouvee_par_sa_reference(client, admin):
    def boom():
        raise RuntimeError("panne simulée du service")

    client.app.add_api_route("/test/panne", boom)
    r = client.get("/test/panne")
    assert r.status_code == 500 and r.json()["request_id"] in r.json()["detail"]
    found = events(client, admin, request_id=r.json()["request_id"])
    assert found[0]["level"] == "error" and "panne simulée" in found[0]["message"] and found[0]["path"] == "/test/panne"
    detail = client.get(f"/admin/events/{found[0]['id']}", headers=admin).json()["detail"]
    assert "Traceback" in detail and "RuntimeError: panne simulée du service" in detail


def test_echec_d_indexation_visible_avec_etape_et_cause(client, admin):
    r = upload(client, admin, content="%PDF-1.7 fichier abîmé", filename="abime.pdf")
    settle(client)
    doc = client.get(f"/admin/documents/{r.json()['id']}", headers=admin).json()
    assert doc["status"] == "failed" and doc["error"].startswith("Lecture du document,")
    failure = events(client, admin, document_id=doc["id"], level="error")[0]
    assert failure["action"] == "indexation_echec" and "Lecture du document" in failure["message"]
    assert failure["actor"] == ADMIN_EMAIL and failure["request_id"] == r.headers["x-request-id"]
    assert "Traceback" in client.get(f"/admin/events/{failure['id']}", headers=admin).json()["detail"]
    history = [e["action"] for e in events(client, admin, document_id=doc["id"])]
    assert history == ["indexation_echec", "document_ajoute"]


def test_service_de_modeles_en_panne_signale(client, admin):
    def down(texts):
        raise EmbeddingError("serveur de modèles injoignable")

    client.app.state.worker.embedder.embed = down
    doc_id = upload(client, admin).json()["id"]
    settle(client)
    doc = client.get(f"/admin/documents/{doc_id}", headers=admin).json()
    assert doc["error"] == "Calcul des embeddings, service indisponible, serveur de modèles injoignable"


def test_actions_de_securite_tracees_sans_mot_de_passe(client, admin):
    client.post("/auth/token", data={"username": ADMIN_EMAIL, "password": "mauvais-mot-de-passe"})
    key = client.post("/admin/service-keys", headers=admin, json={"name": "frontend"}).json()["key"]
    actions = {e["action"]: e for e in events(client, admin)}
    assert {"premier_admin", "demarrage", "connexion", "connexion_echec", "cle_creee"} <= set(actions)
    assert actions["connexion_echec"]["level"] == "warning" and "mot de passe incorrect" in \
        actions["connexion_echec"]["message"]
    every_text = str(events(client, admin, limit=500))
    assert key[:12] in every_text
    for secret in (ADMIN_PASSWORD, "mauvais-mot-de-passe", key):
        assert secret not in every_text


def test_filtres_et_purge_des_vieux_evenements(client, admin):
    assert all(e["category"] == "authentification" for e in events(client, admin, category="authentification"))
    log = client.app.state.events
    with client.app.state.sessions() as session:
        session.add(Event(level=EventLevel.INFO, category=EventCategory.SYSTEME, action="ancien", message="vieux",
                          created_at=utcnow() - timedelta(days=200)))
        session.commit()
    assert log.prune(90) == 1
    assert "ancien" not in {e["action"] for e in events(client, admin, limit=500)}
