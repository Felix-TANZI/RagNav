# backend/app/health.py
import httpx2 as httpx

from app.config import Settings


def _base_name(model: str) -> str:
    return model.removesuffix(":latest")


def check_models(settings: Settings, http: httpx.Client) -> dict:
    try:
        r = http.get(f"{settings.llm_base_url.rstrip('/')}/models",
                     headers={"Authorization": f"Bearer {settings.llm_api_key.get_secret_value()}"})
        r.raise_for_status()
        available = {_base_name(m["id"]) for m in r.json()["data"]}
    except (httpx.HTTPError, KeyError, TypeError, ValueError) as e:
        return {"ok": False, "url": settings.llm_base_url, "error": str(e)}
    wanted = [settings.llm_model, settings.embed_model]
    missing = [m for m in wanted if _base_name(m) not in available]
    return {"ok": not missing, "url": settings.llm_base_url, "models": wanted, "missing": missing}


def check_qdrant(settings: Settings, http: httpx.Client) -> dict:
    try:
        r = http.get(f"{settings.qdrant_url.rstrip('/')}/")
        r.raise_for_status()
        version = r.json().get("version")
    except (httpx.HTTPError, ValueError) as e:
        return {"ok": False, "url": settings.qdrant_url, "error": str(e)}
    return {"ok": True, "url": settings.qdrant_url, "version": version}
