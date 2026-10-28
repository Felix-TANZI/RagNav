<!-- README.md -->
# GANDAL-AI, RAG navigation

Assistant du projet GANDAL GI27 (sous-cellule IA AI1). Il répond en français aux questions sur le mini data
center (machines, services, ports, procédures, architecture) à partir des documents du projet, en citant
document, section et page, et dit quand l'information n'existe pas.

Auteurs Felix NZIKO, Atchine Hanniel. Référence de conception le Chapitre 2 validé (méthodologie, analyse et conception).

## Architecture

| Couche | Choix |
| --- | --- |
| Service | GANDAL-AI, FastAPI (Python 3.12), port 8090, routes `/health` et `/chat` |
| Embeddings | bge-m3 (multilingue, 1024 dimensions) servi par Ollama |
| Génération | qwen3:4b-instruct-2507 via Ollama sur le PC, via LiteLLM (EMILIA:4000) sur GANDAL |
| Index vectoriel | Qdrant 1.19.2, une collection par corpus (`navigation`) |
| Recherche par mots-clés | BM25 natif Qdrant, prévu pour l'architecture B si l'évaluation le justifie |
| Interface | React + TypeScript (Vite), espace client (questions) et espace admin (documents) |

Les modèles sont appelés par l'API compatible OpenAI, la même pour Ollama et LiteLLM. Passer du PC à GANDAL
ne demande que de changer `LLM_BASE_URL` et `LLM_API_KEY` dans `backend/.env`.

Aucun secret n'est écrit dans le code. Les clés n'ont pas de valeur par défaut, elles viennent de
`backend/.env` (jamais versionné) ou des variables d'environnement, et le service refuse de démarrer sans elles.

## Structure

| Dossier | Rôle |
| --- | --- |
| `backend/` | Service GANDAL-AI (FastAPI), tests pytest, Dockerfile |
| `backend/app/ingest/` | Lecture des documents, découpage en passages, liste du corpus |
| `frontend/` | Interface React (client et admin) |
| `corpus/` | Documents indexés et leur liste `inventaire.csv`, `corpus/test/` contient le corpus de test fictif |
| `eval/questions.jsonl` | Jeu de questions d'évaluation (réponse attendue, document, section) |
| `docker-compose.yml` | Qdrant (PC et VM150) et backend (VM150) |

## Corpus

Chaque document est ramené à du Markdown puis découpé par section, en passages d'environ 300 mots avec 45 mots
de recouvrement. Chaque passage garde le document, le chemin des titres et la page.

| Formats | Lecture |
| --- | --- |
| PDF, XPS | PyMuPDF et pymupdf4llm, page par page, OCR Tesseract des pages sans texte (scans) |
| Images .png .jpg .tif .bmp .gif | OCR Tesseract (français et anglais) |
| .docx .odt .pptx .xlsx .csv .tsv .rtf .epub .html .tex .rst .ipynb .adoc .org .typ | Pandoc |
| .doc .xls .ppt .pps .ods .odp .dot | LibreOffice (vers .docx, .xlsx, .pptx) puis Pandoc |
| .md .txt | Lecture directe, UTF-8 ou Windows-1252 |
| .yml .json .xml .toml .ini .conf .cfg .sh .ps1 .py .sql .log | Lu comme du code, sous le nom du fichier |

`corpus/inventaire.csv` liste les documents de référence, un par ligne, séparateur `;` :

```
fichier;titre;source;version;date
test/architecture_generale.pdf;Architecture générale du mini data center GANDAL;Cellule Infrastructure (I1);1.2;2026-10-20
```

```powershell
cd backend
.\.venv\Scripts\python.exe -m scripts.inspect_corpus                        # contrôle de lecture et de découpage
.\.venv\Scripts\python.exe -m scripts.inspect_corpus --detail apercu.md     # écrit tous les passages
.\.venv\Scripts\python.exe -m scripts.build_test_corpus                     # régénère les PDF de test
```

Un document protégé par mot de passe, sans texte même après OCR ou dans un format inconnu est signalé et
ignoré. L'OCR est plus lent (quelques secondes par page) et moins fiable qu'un texte numérique. L'image Docker
pèse environ 1,6 Go à cause de LibreOffice et de Tesseract.
Dans un PDF, un petit tableau sans bordure (moins de 5 lignes) est restitué comme du texte dans l'ordre de
lecture : son contenu est conservé mais la séparation des lignes du tableau est perdue.

## Démarrer sur le PC

Prérequis installés Python 3.12, Node.js 22, Docker Desktop, Ollama, Tesseract 5 avec le fichier
`fra.traineddata` dans `C:\Program Files\Tesseract-OCR\tessdata`, LibreOffice. Tesseract et LibreOffice sont
trouvés automatiquement, `TESSDATA_PATH` et `LIBREOFFICE_PATH` dans `backend/.env` servent seulement s'ils sont
installés ailleurs.

```powershell
winget install --id tesseract-ocr.tesseract -e
winget install --id TheDocumentFoundation.LibreOffice -e
```

```powershell
# Modèles (une seule fois)
ollama pull bge-m3
ollama pull qwen3:4b-instruct-2507-q4_K_M

# Index vectoriel
docker compose up -d qdrant

# Backend
cd backend
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
Copy-Item .env.example .env       # puis renseigner LLM_API_KEY (toute valeur non vide pour Ollama)
.\.venv\Scripts\python.exe -m uvicorn app.main:create_app --factory --port 8090 --reload

# Frontend (autre terminal)
cd frontend
npm install
npm run dev
```

Ouvrir <http://localhost:5173>, la page affiche l'état du serveur de modèles et de Qdrant.
Documentation de l'API sur <http://localhost:8090/docs>.

## Tests

```powershell
cd backend
.\.venv\Scripts\python.exe -m pytest           # tests unitaires, sans Ollama ni Qdrant
.\.venv\Scripts\python.exe -m pytest -m live   # vérifie les vrais services de la machine
cd ..\frontend
npm run build; npm run lint
```

## Déployer sur la VM150

```bash
cp backend/.env.example backend/.env   # LLM_BASE_URL=http://EMILIA:4000/v1, clé et noms de modèles LiteLLM
docker compose build --pull     # repart de l'image de base Python la plus récente (correctifs de sécurité)
docker compose up -d
curl localhost:8090/health
```

## Étapes

| Étape | Contenu | État |
| --- | --- | --- |
| 0 | Environnement de travail, `/health`, squelettes backend et frontend | fait |
| 1 | Corpus de test fictif, lecture et découpage par section, jeu d'évaluation | fait |
| 2 | Index, embeddings bge-m3 et collection Qdrant `navigation` | à faire |
| 3 | Comptes utilisateurs (rôles admin et client) et API de gestion des documents | à faire |
| 4 | Route `/chat`, seuil de pertinence, citations et refus | à faire |
| 5 | Interface, espace admin (documents) et espace client (questions) | à faire |
| 6 | Évaluation (rappel, fidélité, citations, refus), BM25 si nécessaire, runbook | à faire |
