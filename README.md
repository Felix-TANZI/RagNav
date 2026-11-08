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
| Recherche par mots-clés | BM25, vecteur creux par passage dans Qdrant (IDF calculé par Qdrant), fusion RRF avec la recherche dense |
| Interface | React 19 + TypeScript (Vite), servie par nginx sur le port 8080, espace client et espace admin |

Les modèles sont appelés par l'API compatible OpenAI, la même pour Ollama et LiteLLM. Passer du PC à GANDAL
ne demande que de changer `LLM_BASE_URL` et `LLM_API_KEY` dans `backend/.env`.

Aucun secret n'est écrit dans le code. Les clés n'ont pas de valeur par défaut, elles viennent de
`backend/.env` (jamais versionné) ou des variables d'environnement, et le service refuse de démarrer sans elles.

## Structure

| Dossier | Rôle |
| --- | --- |
| `backend/` | Service GANDAL-AI (FastAPI), tests pytest, Dockerfile |
| `backend/app/ingest/` | Lecture des documents, découpage en passages, liste du corpus |
| `frontend/` | Interface React (client et admin), tests Vitest, Dockerfile et configuration nginx |
| `corpus/` | Documents indexés et leur liste `inventaire.csv`, `corpus/test/` contient le corpus de test fictif |
| `eval/questions.jsonl` | Jeu de questions d'évaluation (réponse attendue, document, section) |
| `docs/runbook.md` | Exploitation sur la VM150 : installation, mise à jour, sauvegarde, pannes courantes |
| `docker-compose.yml` | Qdrant, backend et interface (VM150), `docker-compose.dev.yml` adapte au PC |

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
Copy-Item .env.example .env       # puis renseigner les secrets (voir Comptes et sécurité)
.\.venv\Scripts\python.exe -m scripts.import_corpus      # charge le corpus de test dans la base (une fois)
.\.venv\Scripts\python.exe -m uvicorn app.main:create_app --factory --port 8090 --reload

# Frontend (autre terminal)
cd frontend
npx npm@11.6.2 ci       # npm 10.9 livré avec Node 22 échoue sur ce lockfile
npm run dev
```

Ouvrir <http://localhost:5173>. Vite renvoie `/api` vers le backend sur le port 8090, comme nginx en conteneur, ce
qui demande `REFRESH_COOKIE_PATH=/api/auth` et `COOKIE_SECURE=false` dans `backend/.env`.
Documentation de l'API sur <http://127.0.0.1:8090/docs>.

## Index

Les passages sont vectorisés par bge-m3 et rangés dans la collection Qdrant `navigation` (vecteur nommé `dense`,
distance cosinus). Chaque passage reçoit aussi un vecteur creux BM25 (`mots`) : les mots sont mis en minuscules,
sans accents ni mots vides, et les identifiants techniques restent entiers (`10.10.40.30`, `dcgm-exporter`,
`/mnt/projets`). Chaque passage garde document, titre, source, version, date, section, chemin des titres, page
et texte. Le texte vectorisé est précédé du titre du document et du chemin des sections.

Une collection créée avant l'index par mots-clés est signalée au démarrage dans le journal, `scripts.ingest --reset`
la reconstruit.

Les documents sont gérés par l'espace admin (API `/admin/documents`) et indexés en arrière-plan par une file à un
seul fil. Seuls les documents nouveaux ou modifiés sont recalculés : l'empreinte d'un document couvre son contenu,
ses métadonnées, le modèle d'embedding et les réglages de découpage. Une nouvelle version est écrite avant que
l'ancienne soit retirée. La base SQLite et les fichiers sont dans `backend/data/` (volume `gandal_data` en Docker).

```powershell
cd backend
.\.venv\Scripts\python.exe -m scripts.import_corpus      # importe ../corpus/inventaire.csv dans la base
.\.venv\Scripts\python.exe -m scripts.ingest             # indexe les documents de la base
.\.venv\Scripts\python.exe -m scripts.ingest --force     # recalcule tout
.\.venv\Scripts\python.exe -m scripts.ingest --reset     # supprime la collection puis réindexe (changement de modèle)
.\.venv\Scripts\python.exe -m scripts.eval_retrieval              # rappel@k sur eval/questions.jsonl
.\.venv\Scripts\python.exe -m scripts.eval_retrieval --mode dense # même mesure sans les mots-clés
```

Sur le corpus de test (40 questions avec réponse), en comptant seulement les passages réellement donnés au modèle :

| Recherche | Rappel@1 | Rappel@3 | Rappel@5 | MRR |
| --- | --- | --- | --- | --- |
| dense | 75 % | 92 % | 95 % | 0,844 |
| hybride | 80 % | 100 % | 100 % | 0,896 |

En recherche dense, une question avec une faute de frappe (« prometeus ») et une question sur un nom exact (« CT310 »)
trouvaient le bon passage mais sous le seuil de similarité, l'assistant aurait refusé. La recherche hybride les
retrouve.

## Assistant, route /chat

`POST /chat` reçoit `{"message": "...", "corpus": "navigation", "top_k": 5}` et renvoie `answer`, `found` et
`sources` (document, titre, section, page, version, score). La source n correspond à la citation [n] de la réponse.
Accès avec un compte (client ou admin) ou une clé de service dans l'en-tête `X-API-Key`.

Déroulement (Chapitre 2, section 3.3) : la question est vectorisée, les passages proches par le sens sous le seuil
`MIN_SCORE` (0,40) sont écartés, ceux qui partagent des mots avec la question sont gardés, et la fusion par rang
réciproque (RRF) en retient 5. S'il n'en reste aucun, l'assistant refuse sans appeler le modèle. Sinon le modèle reçoit les extraits numérotés et la consigne de citer, de ne rien inventer et de répondre
« Je ne trouve pas cette information dans la documentation GANDAL. » si les extraits ne suffisent pas. Les
citations sont ensuite vérifiées et renumérotées, une citation inventée est retirée.

```powershell
cd backend
.\.venv\Scripts\python.exe -m scripts.evaluate                    # évaluation complète, détail dans eval/resultats.csv
.\.venv\Scripts\python.exe -m scripts.evaluate --ids Q01,Q19,H01  # rejouer quelques questions
```

Sur le corpus de test : refus justifiés 6/6, faux refus 0/20, bonne section citée 19/20. Sur ce PC sans GPU
(i7-8665U), une réponse prend environ 75 s (médiane), dont l'essentiel pour la lecture du prompt par le modèle. Sur
le GPU de GANDAL la même réponse prend quelques secondes. `TOP_K=3` ramène la médiane à 50 s mais fait refuser à
tort une question sur un nom exact (Q01), ce que la recherche hybride BM25 de l'étape 6 doit corriger.

`POST /chat/stream` renvoie la même réponse au fil de l'eau (Server-Sent Events `statut`, `texte`, `fin`,
`erreur`), c'est la route utilisée par l'interface.

## Interface

Elle suit la charte graphique GANDAL (version 3) : police Geist, couleurs et rayons repris comme variables CSS
dans `frontend/src/styles/tokens.css`, contrastes AA vérifiés par un test. Français par défaut, anglais au choix.

| Espace | Pages |
| --- | --- |
| Client | Accueil (état des services, question, réponse en continu avec citations et sources), Documentation (documents consultables), Mon compte |
| Admin | Documents (ajout, remplacement, informations, réindexation, suppression), Comptes, Clés de service, Journal |

Une citation [n] ou une source ouvre le document à la page citée. Le jeton d'accès reste en mémoire, la session est
reprise par le cookie de renouvellement. Le logo est provisoire en attendant le logo officiel.

## Comptes et sécurité

| Rôle | Création | Droits |
| --- | --- | --- |
| admin | premier admin depuis `ADMIN_EMAIL` et `ADMIN_PASSWORD` au démarrage, puis par un admin | documents, comptes, clés, journal |
| client | inscription libre (`POST /auth/register`) | poser des questions |
| application | clé de service créée par un admin, en-tête `X-API-Key` | appeler `/chat` |

- Mots de passe hachés en Argon2, 12 caractères au moins, blocage 15 min après 5 échecs.
- Jeton d'accès JWT de 15 min, à garder en mémoire côté interface. Jeton de renouvellement dans un cookie HttpOnly
  SameSite=Strict limité à `REFRESH_COOKIE_PATH` (`/api/auth` derrière nginx), renouvelé à chaque usage, session de 8 h au plus. Un jeton réutilisé révoque
  toute la session.
- Limite de débit par adresse IP sur la connexion et l'inscription.
- Secrets uniquement dans `backend/.env` : `LLM_API_KEY`, `JWT_SECRET` (32 caractères au moins), `ADMIN_PASSWORD`.
  `COOKIE_SECURE=false` seulement en développement HTTP.

Documentation interactive sur <http://127.0.0.1:8090/docs>, bouton Authorize pour se connecter.

## Journal et erreurs

Chaque réponse porte l'en-tête `X-Request-ID`, repris dans tout message d'erreur. Le journal (`/admin/events`)
garde les erreurs avec leur trace technique, les échecs d'indexation avec l'étape et la cause, les connexions, les
actions des admins et les alertes de sécurité. Aucun mot de passe, jeton ou clé n'y est écrit. Conservation 90 jours
(`EVENTS_RETENTION_DAYS`).

## Tests

```powershell
cd backend
.\.venv\Scripts\python.exe -m pytest           # tests unitaires, sans Ollama ni Qdrant
.\.venv\Scripts\python.exe -m pytest -m live   # vérifie les vrais services de la machine
cd ..\frontend
npm test; npm run lint; npm run build
```

133 tests backend, 29 tests frontend (pages, citations, réponse en continu, contrastes de la charte).

## Vérifier une étape

Toute la chaîne tourne en conteneurs sur le PC, Ollama restant installé sur Windows.

```powershell
docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d --build
docker compose exec -T backend python -m scripts.import_corpus --corpus-dir /corpus   # première fois
docker compose exec -T backend python -m scripts.ingest --reset
```

Puis ouvrir l'interface sur <http://127.0.0.1:8080> et l'API sur <http://127.0.0.1:8090/docs>. Le conteneur a sa propre base (volume `gandal_data`) et partage Qdrant
avec le backend lancé à la main : après être passé de l'un à l'autre, `scripts.ingest --reset` remet l'index en
accord avec la base utilisée. Lancer les commandes `docker compose exec` depuis PowerShell, Git Bash réécrit
`/corpus` en chemin Windows.

## Déployer sur la VM150

Procédure complète, sauvegarde et pannes courantes dans [docs/runbook.md](docs/runbook.md).

```bash
cp backend/.env.example backend/.env   # LLM_BASE_URL=http://EMILIA:4000/v1, clé et noms de modèles LiteLLM
docker compose build --pull     # repart de l'image de base Python la plus récente (correctifs de sécurité)
docker compose up -d
curl localhost:8090/health
```

L'interface est sur le port 8080. Avec `COOKIE_SECURE=true` le navigateur n'envoie le cookie de session qu'en HTTPS,
il faut donc placer l'interface derrière le proxy HTTPS de GANDAL.

## Étapes

| Étape | Contenu | État |
| --- | --- | --- |
| 0 | Environnement de travail, `/health`, squelettes backend et frontend | fait |
| 1 | Corpus de test fictif, lecture et découpage par section, jeu d'évaluation | fait |
| 2 | Index, embeddings bge-m3 et collection Qdrant `navigation`, rappel@k | fait |
| 3 | Comptes (admin, client, clés de service), API des documents, journal des événements | fait |
| 4 | Route `/chat`, seuil de pertinence, citations vérifiées, refus, évaluation de bout en bout | fait |
| 5 | Interface selon la charte GANDAL, espace client (questions) et espace admin (documents, comptes, clés, journal) | fait |
| 6 | Évaluation (rappel, fidélité, citations, refus), BM25 si nécessaire, runbook | à faire |
