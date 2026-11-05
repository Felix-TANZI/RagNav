# backend/app/llm.py
# Modèle de langue par l'API compatible OpenAI, la même pour Ollama sur le PC et LiteLLM sur GANDAL
import json
from collections.abc import Iterator

import httpx2 as httpx

from app.config import Settings


class LLMError(RuntimeError):
    pass


class ChatModel:
    def __init__(self, settings: Settings, http: httpx.Client | None = None):
        self.model = settings.llm_model
        self.temperature = settings.temperature
        self.max_tokens = settings.max_tokens
        self._url = f"{settings.llm_base_url.rstrip('/')}/chat/completions"
        self._headers = {"Authorization": f"Bearer {settings.llm_api_key.get_secret_value()}"}
        self._http = http or httpx.Client(timeout=settings.llm_timeout)

    def complete(self, messages: list[dict]) -> str:
        payload = {"model": self.model, "messages": messages, "temperature": self.temperature,
                   "max_tokens": self.max_tokens, "stream": False}
        try:
            r = self._http.post(self._url, headers=self._headers, json=payload)
            r.raise_for_status()
            content = r.json()["choices"][0]["message"]["content"]
        except httpx.HTTPStatusError as e:
            raise LLMError(f"{self._url} a répondu {e.response.status_code}, {e.response.text[:200]}") from e
        except httpx.TimeoutException as e:
            raise LLMError(f"le modèle {self.model} n'a pas répondu à temps ({self._url})") from e
        except httpx.HTTPError as e:
            raise LLMError(f"serveur de modèles injoignable ({self._url}, {e})") from e
        except (KeyError, IndexError, TypeError, ValueError) as e:
            raise LLMError(f"réponse du modèle inattendue ({e})") from e
        if not isinstance(content, str) or not content.strip():
            raise LLMError("le modèle a renvoyé une réponse vide")
        return content.strip()

    def stream(self, messages: list[dict]) -> Iterator[str]:
        payload = {"model": self.model, "messages": messages, "temperature": self.temperature,
                   "max_tokens": self.max_tokens, "stream": True}
        received = False
        try:
            with self._http.stream("POST", self._url, headers=self._headers, json=payload) as r:
                if r.status_code >= 400:
                    r.read()
                    raise LLMError(f"{self._url} a répondu {r.status_code}, {r.text[:200]}")
                for line in r.iter_lines():
                    data = line.removeprefix("data:").strip() if line.startswith("data:") else ""
                    if not data:
                        continue
                    if data == "[DONE]":
                        break
                    try:
                        piece = json.loads(data)["choices"][0].get("delta", {}).get("content")
                    except (KeyError, IndexError, TypeError, ValueError) as e:
                        raise LLMError(f"flux du modèle inattendu ({e})") from e
                    if piece:
                        received = True
                        yield piece
        except httpx.TimeoutException as e:
            raise LLMError(f"le modèle {self.model} n'a pas répondu à temps ({self._url})") from e
        except httpx.HTTPError as e:
            raise LLMError(f"serveur de modèles injoignable ({self._url}, {e})") from e
        if not received:
            raise LLMError("le modèle a renvoyé une réponse vide")
