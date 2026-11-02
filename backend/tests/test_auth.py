# backend/tests/test_auth.py
import sqlite3
from datetime import timedelta

import jwt
from fastapi.testclient import TestClient

from app.main import create_app
from app.models import utcnow
from app.routers.auth import REFRESH_COOKIE
from tests.conftest import login
from tests.fakes import ADMIN_EMAIL, ADMIN_PASSWORD, FakeEmbedder

CLIENT_PASSWORD = "mot-de-passe-client-solide"


def register(client, email="client@test.cm", password=CLIENT_PASSWORD):
    return client.post("/auth/register", json={"email": email, "password": password})


def test_premier_admin_cree_une_seule_fois(settings, store, client):
    assert client.get("/auth/me", headers=login(client)).json()["role"] == "admin"
    with TestClient(create_app(settings, store=store, embedder=FakeEmbedder())) as second:
        users = second.get("/admin/users", headers=login(second)).json()
    assert [u["email"] for u in users] == [ADMIN_EMAIL]


def test_inscription_client_et_connexion(client):
    r = register(client, email="Client@Test.cm")
    assert r.status_code == 201 and r.json()["role"] == "client" and r.json()["email"] == "client@test.cm"
    headers = login(client, "client@test.cm", CLIENT_PASSWORD)
    assert client.get("/auth/me", headers=headers).json()["email"] == "client@test.cm"
    assert client.get("/admin/users", headers=headers).status_code == 403


def test_inscription_refusee_mot_de_passe_court_ou_adresse_prise(client):
    assert register(client, password="court").status_code == 422
    assert register(client, email="pas-une-adresse").status_code == 422
    assert register(client).status_code == 201
    assert register(client).status_code == 409


def test_mots_de_passe_jamais_stockes_en_clair(client, settings):
    register(client)
    with sqlite3.connect(settings.data_dir / "gandal.db") as db:
        hashes = [row[0] for row in db.execute("select password_hash from users")]
    assert all(h.startswith("$argon2") for h in hashes)
    assert not any(CLIENT_PASSWORD in h or ADMIN_PASSWORD in h for h in hashes)


def test_meme_message_compte_inconnu_ou_mauvais_mot_de_passe(client):
    unknown = client.post("/auth/token", data={"username": "inconnu@test.cm", "password": "x" * 12})
    wrong = client.post("/auth/token", data={"username": ADMIN_EMAIL, "password": "x" * 12})
    assert unknown.status_code == wrong.status_code == 401
    assert unknown.json()["detail"] == wrong.json()["detail"]


def test_blocage_apres_echecs_repetes(client, settings):
    for _ in range(settings.login_max_failures):
        client.post("/auth/token", data={"username": ADMIN_EMAIL, "password": "mauvais-mot-de-passe"})
    blocked = client.post("/auth/token", data={"username": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
    assert blocked.status_code == 401


def test_cookie_de_renouvellement_httponly_strict(client):
    r = client.post("/auth/token", data={"username": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
    cookie = r.headers["set-cookie"].lower()
    assert REFRESH_COOKIE in cookie and "httponly" in cookie and "samesite=strict" in cookie and "path=/auth" in cookie
    assert r.json()["expires_in"] == 15 * 60


def test_rotation_et_detection_de_reutilisation(client):
    login(client)
    first = client.cookies.get(REFRESH_COOKIE)
    renewed = client.post("/auth/refresh")
    second = client.cookies.get(REFRESH_COOKIE)
    assert renewed.status_code == 200 and second != first
    client.cookies.clear()
    client.cookies.set(REFRESH_COOKIE, first, path="/auth")
    assert client.post("/auth/refresh").status_code == 401
    client.cookies.clear()
    client.cookies.set(REFRESH_COOKIE, second, path="/auth")
    assert client.post("/auth/refresh").status_code == 401


def test_deconnexion_revoque_la_session(client):
    login(client)
    cookie = client.cookies.get(REFRESH_COOKIE)
    assert client.post("/auth/logout").status_code == 204
    client.cookies.clear()
    client.cookies.set(REFRESH_COOKIE, cookie, path="/auth")
    assert client.post("/auth/refresh").status_code == 401


def test_changement_de_mot_de_passe(client):
    register(client)
    headers = login(client, "client@test.cm", CLIENT_PASSWORD)
    bad = client.post("/auth/password", headers=headers, json={"current_password": "faux" * 3,
                                                                "new_password": "nouveau-mot-de-passe"})
    assert bad.status_code == 400
    ok = client.post("/auth/password", headers=headers, json={"current_password": CLIENT_PASSWORD,
                                                               "new_password": "nouveau-mot-de-passe"})
    assert ok.status_code == 204 and client.post("/auth/refresh").status_code == 401
    login(client, "client@test.cm", "nouveau-mot-de-passe")


def test_jeton_expire_ou_falsifie_refuse(client, settings):
    claims = {"sub": "x", "type": "access", "exp": utcnow() - timedelta(minutes=1)}
    expired = jwt.encode(claims, settings.jwt_secret.get_secret_value(), algorithm="HS256")
    forged = jwt.encode({**claims, "exp": utcnow() + timedelta(hours=1)}, "autre-secret" * 4, algorithm="HS256")
    for token in (expired, forged, "pas-un-jeton"):
        assert client.get("/auth/me", headers={"Authorization": f"Bearer {token}"}).status_code == 401


def test_limite_de_debit_sur_l_inscription(settings, store):
    settings.register_per_hour = 2
    with TestClient(create_app(settings, store=store, embedder=FakeEmbedder())) as client:
        codes = [register(client, email=f"c{i}@test.cm").status_code for i in range(3)]
    assert codes == [201, 201, 429]
