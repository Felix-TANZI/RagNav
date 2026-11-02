# backend/tests/fakes.py
# Faux modèle d'embedding (sac de mots haché) et réglages factices, sans réseau ni secret réel
import hashlib
import math
import re
from pathlib import Path

from app.config import Settings

DIM = 64
ADMIN_EMAIL = "admin@test.cm"
ADMIN_PASSWORD = "mot-de-passe-admin-de-test"


def make_settings(data_dir: Path, **overrides) -> Settings:
    values = dict(_env_file=None, llm_api_key="cle-de-test", jwt_secret="secret-de-test-" * 4,
                  embed_model="faux-modele", data_dir=data_dir, cookie_secure=False, admin_email=ADMIN_EMAIL,
                  admin_password=ADMIN_PASSWORD, chunk_words=60, chunk_overlap_words=10)
    values.update(overrides)
    return Settings(**values)


class FakeEmbedder:
    model = "faux-modele"

    def __init__(self):
        self.calls = 0

    def embed(self, texts: list[str]) -> list[list[float]]:
        self.calls += 1
        vectors = []
        for text in texts:
            v = [0.0] * DIM
            for word in re.findall(r"\w+", text.lower()):
                v[int(hashlib.md5(word.encode()).hexdigest(), 16) % DIM] += 1.0
            norm = math.sqrt(sum(x * x for x in v)) or 1.0
            vectors.append([x / norm for x in v])
        return vectors
