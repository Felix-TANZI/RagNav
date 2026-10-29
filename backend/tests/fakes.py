# backend/tests/fakes.py
# Faux modèle d'embedding, sac de mots haché, les textes qui partagent des mots ont des vecteurs proches
import hashlib
import math
import re

DIM = 64


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
