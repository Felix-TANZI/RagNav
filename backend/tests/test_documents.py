# backend/tests/test_documents.py
from pathlib import Path

import pytest

from app.storage import safe_filename

GUIDE = "# Guide\n\n## VPN\n\nLe VPN WireGuard écoute sur le port 51820 du pare-feu GARDIEN.\n"
FORM = {"title": "Guide VPN", "source": "Cellule Réseau", "version": "1.0", "document_date": "2026-10-29"}


def upload(client, admin, content=GUIDE, filename="guide.md", **fields):
    return client.post("/admin/documents", headers=admin, data={**FORM, **fields},
                       files={"file": (filename, content.encode("utf-8"), "text/markdown")})


def settle(client):
    client.app.state.worker.wait_idle(60)


def test_ajout_puis_indexation_en_arriere_plan(client, admin, store):
    r = upload(client, admin)
    assert r.status_code == 202 and r.json()["status"] in ("pending", "indexing", "indexed")
    settle(client)
    doc = client.get(f"/admin/documents/{r.json()['id']}", headers=admin).json()
    assert doc["status"] == "indexed" and doc["chunks"] == 1 and doc["error"] is None
    assert store.documents("navigation") == {doc["id"]: 1}


def test_doublon_format_et_taille_refuses(client, admin, settings):
    assert upload(client, admin).status_code == 202
    duplicate = upload(client, admin, filename="copie.md")
    assert duplicate.status_code == 409 and "Guide VPN" in duplicate.json()["detail"]
    assert upload(client, admin, filename="virus.exe").status_code == 415
    big = upload(client, admin, content="a" * (settings.max_upload_mb * 1024 * 1024 + 10), filename="gros.txt")
    assert big.status_code == 413
    assert len(list(settings.documents_dir.iterdir())) == 1


def test_remplacement_du_fichier_et_ancienne_version_retiree(client, admin, store, settings):
    doc_id = upload(client, admin).json()["id"]
    settle(client)
    new = GUIDE.replace("51820", "51821")
    r = client.put(f"/admin/documents/{doc_id}/file", headers=admin, data={"version": "1.1"},
                   files={"file": ("guide-v2.md", new.encode("utf-8"), "text/markdown")})
    assert r.status_code == 202 and r.json()["version"] == "1.1" and r.json()["filename"] == "guide-v2.md"
    settle(client)
    assert client.get(f"/admin/documents/{doc_id}", headers=admin).json()["status"] == "indexed"
    versions = list((settings.documents_dir / doc_id).iterdir())
    assert len(versions) == 1 and (versions[0] / "guide-v2.md").exists()
    same = client.put(f"/admin/documents/{doc_id}/file", headers=admin,
                      files={"file": ("guide-v2.md", new.encode("utf-8"), "text/markdown")})
    assert same.status_code == 409


def test_modification_des_metadonnees_reindexe(client, admin, store):
    doc_id = upload(client, admin).json()["id"]
    settle(client)
    r = client.patch(f"/admin/documents/{doc_id}", headers=admin, json={"title": "Accès VPN", "version": "2.0"})
    assert r.status_code == 202
    settle(client)
    payload = store.client.scroll("navigation", limit=10)[0][0].payload
    assert payload["title"] == "Accès VPN" and payload["version"] == "2.0"


def test_telechargement_et_suppression(client, admin, store, settings):
    doc_id = upload(client, admin).json()["id"]
    settle(client)
    download = client.get(f"/admin/documents/{doc_id}/file", headers=admin)
    assert download.status_code == 200 and download.content.decode("utf-8") == GUIDE
    assert "guide.md" in download.headers["content-disposition"]
    assert client.delete(f"/admin/documents/{doc_id}", headers=admin).status_code == 202
    settle(client)
    assert client.get(f"/admin/documents/{doc_id}", headers=admin).status_code == 404
    assert store.documents("navigation") == {} and not (settings.documents_dir / doc_id).exists()


def test_formats_annonces(client, admin):
    body = client.get("/admin/documents/formats", headers=admin).json()
    assert ".pdf" in body["extensions"] and ".docx" in body["extensions"] and body["max_upload_mb"] == 50


@pytest.mark.parametrize("raw, safe", [("../../etc/passwd", "passwd"), ("C:\\Windows\\rapport.PDF", "rapport.pdf"),
                                       (".htaccess", "htaccess"), ("plan réseau v2.md", "plan réseau v2.md"),
                                       ("a<b>|c?.docx", "a_b_c_.docx"), ("", "document")])
def test_noms_de_fichier_assainis(raw, safe):
    assert safe_filename(raw) == safe
    assert Path(safe_filename(raw)).name == safe_filename(raw)
