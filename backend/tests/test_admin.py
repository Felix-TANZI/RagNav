# backend/tests/test_admin.py
from fastapi import Depends

from app.deps import Caller, require_caller
from tests.conftest import login
from tests.fakes import ADMIN_EMAIL


def create(client, admin, email, role="client"):
    r = client.post("/admin/users", headers=admin, json={"name": "Nom", "email": email,
                                                          "password": "mot-de-passe-solide", "role": role})
    assert r.status_code == 201, r.text
    return r.json()


def test_creer_lister_et_supprimer_des_comptes(client, admin):
    second_admin = create(client, admin, "admin2@test.cm", "admin")
    create(client, admin, "client@test.cm")
    assert {u["email"] for u in client.get("/admin/users", headers=admin).json()} == \
        {ADMIN_EMAIL, "admin2@test.cm", "client@test.cm"}
    assert [u["email"] for u in client.get("/admin/users?role=admin", headers=admin).json()] == \
        ["admin2@test.cm", ADMIN_EMAIL]
    assert client.delete(f"/admin/users/{second_admin['id']}", headers=admin).status_code == 204


def test_un_admin_ne_peut_pas_se_retirer_ses_droits(client, admin):
    me = client.get("/auth/me", headers=admin).json()
    assert client.patch(f"/admin/users/{me['id']}", headers=admin, json={"is_active": False}).status_code == 400
    assert client.patch(f"/admin/users/{me['id']}", headers=admin, json={"role": "client"}).status_code == 400
    assert client.delete(f"/admin/users/{me['id']}", headers=admin).status_code == 400


def test_desactivation_coupe_l_acces(client, admin):
    user = create(client, admin, "client@test.cm")
    headers = login(client, "client@test.cm", "mot-de-passe-solide")
    assert client.patch(f"/admin/users/{user['id']}", headers=admin, json={"is_active": False}).status_code == 200
    assert client.get("/auth/me", headers=headers).status_code == 401
    assert client.post("/auth/token", data={"username": "client@test.cm",
                                            "password": "mot-de-passe-solide"}).status_code == 401


def test_routes_admin_refusees_sans_compte_ou_pour_un_client(client, admin):
    create(client, admin, "client@test.cm")
    headers = login(client, "client@test.cm", "mot-de-passe-solide")
    for path in ("/admin/users", "/admin/service-keys", "/admin/documents", "/admin/events"):
        assert client.get(path).status_code == 401
        assert client.get(path, headers=headers).status_code == 403


def test_cle_de_service_montree_une_fois_puis_revoquee(client, admin):
    created = client.post("/admin/service-keys", headers=admin, json={"name": "frontend-gandal-ai"})
    assert created.status_code == 201
    key = created.json()["key"]
    assert key.startswith("gai_") and created.json()["prefix"] == key[:12]
    listed = client.get("/admin/service-keys", headers=admin).json()
    assert "key" not in listed[0] and listed[0]["name"] == "frontend-gandal-ai"
    assert client.post("/admin/service-keys", headers=admin, json={"name": "frontend-gandal-ai"}).status_code == 409

    def caller_label(caller: Caller = Depends(require_caller)) -> str:
        return caller.label

    client.app.add_api_route("/test/appelant", caller_label)
    assert client.get("/test/appelant", headers={"X-API-Key": key}).json() == "frontend-gandal-ai"
    assert client.get("/test/appelant", headers={"X-API-Key": "gai_fausse"}).status_code == 401
    assert client.get("/test/appelant", headers=admin).json() == ADMIN_EMAIL
    assert client.delete(f"/admin/service-keys/{created.json()['id']}", headers=admin).status_code == 204
    assert client.get("/test/appelant", headers={"X-API-Key": key}).status_code == 401
