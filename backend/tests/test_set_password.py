# backend/tests/test_set_password.py
# Mot de passe changé depuis le serveur, compte débloqué et sessions fermées
from scripts.set_password import set_password
from tests.conftest import login
from tests.fakes import ADMIN_EMAIL

NEW_PASSWORD = "nouveau-mot-de-passe-serveur"


def test_admin_bloque_retrouve_l_acces(client, admin):
    for _ in range(6):
        client.post("/auth/token", data={"username": ADMIN_EMAIL, "password": "mauvais-mot-de-passe"})
    assert client.post("/auth/token", data={"username": ADMIN_EMAIL, "password": NEW_PASSWORD}).status_code == 401

    sessions = client.app.state.sessions
    assert set_password(sessions, ADMIN_EMAIL.upper(), NEW_PASSWORD)
    assert client.post("/auth/refresh").status_code == 401
    headers = login(client, ADMIN_EMAIL, NEW_PASSWORD)
    events = client.get("/admin/events", headers=headers, params={"category": "comptes"}).json()
    assert any(e["action"] == "mot_de_passe_serveur" for e in events)


def test_compte_inconnu(client):
    assert not set_password(client.app.state.sessions, "personne@test.cm", NEW_PASSWORD)
