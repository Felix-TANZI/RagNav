# backend/tests/test_prompt.py
from app.prompt import REFUSAL, build_messages, cited_numbers, is_refusal, renumber
from app.store import Hit


def hit(text: str, **payload) -> Hit:
    return Hit("id", 0.8, {"title": "Architecture", "section_path": "3. Machines", "page": 2, "text": text, **payload})


def test_extraits_numerotes_avec_leur_origine():
    messages = build_messages("Port de LiteLLM ?", [hit("EMILIA 4000"), hit("REM 11434", page=None)])
    user = messages[1]["content"]
    assert "[1] Architecture, 3. Machines, page 2\nEMILIA 4000" in user
    assert "[2] Architecture, 3. Machines\nREM 11434" in user and user.endswith("Question\nPort de LiteLLM ?")
    assert REFUSAL in messages[0]["content"]


def test_citations_valides_dans_l_ordre_sans_doublon():
    assert cited_numbers("Port 4000 [2], voir aussi [1][2] et [9].", 3) == [2, 1]


def test_renumerotation_et_citation_inventee_retiree():
    assert renumber("Port 4000 [3]. Ollama sur 11434 [1][7].", {3: 1, 1: 2}) == "Port 4000 [1]. Ollama sur 11434 [2]."


def test_detection_du_refus():
    assert is_refusal(REFUSAL) and is_refusal(f"« {REFUSAL} »") and is_refusal("Je ne trouve pas d'information.")
    assert not is_refusal("LiteLLM écoute sur le port 4000 [1].")
