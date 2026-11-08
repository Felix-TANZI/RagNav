<!-- docs/runbook.md -->
# Runbook GANDAL-AI

Exploitation du RAG navigation sur la VM150. Toutes les commandes se lancent depuis le dossier du dépôt sur la VM.

## 1. Composants

| Conteneur | Rôle | Port | Données |
| --- | --- | --- | --- |
| `frontend` | Interface (nginx), renvoie `/api` vers le backend | 8080 | aucune |
| `backend` | GANDAL-AI (FastAPI), API, file d'indexation, journal | 8090 | volume `gandal_data` (`/app/data`) |
| `qdrant` | Index des passages (vecteur dense et mots-clés) | 6333, local uniquement | volume `qdrant_data` |

Hors de la VM150 : la passerelle LiteLLM d'EMILIA (port 4000) sert le modèle d'embedding et le modèle de génération.

`gandal_data` contient la base SQLite (`gandal.db` : comptes, clés, documents, journal) et les fichiers déposés
(`documents/`). C'est la seule donnée à sauvegarder : l'index Qdrant se reconstruit à partir des documents.

## 2. Prérequis

- Docker Engine et le plugin Compose sur la VM150.
- Accès réseau de la VM150 vers `http://EMILIA:4000/v1` et une clé LiteLLM.
- Dans LiteLLM, un modèle d'embedding bge-m3 (1024 dimensions) et un modèle de génération, avec leurs noms exacts.
- Un proxy HTTPS devant le port 8080 : le cookie de session est marqué `Secure` et le navigateur ne l'envoie qu'en
  HTTPS.

## 3. Installation

```bash
cp backend/.env.example backend/.env
chmod 600 backend/.env
openssl rand -base64 48        # valeur de JWT_SECRET
```

Variables de `backend/.env` à renseigner :

| Variable | Valeur sur GANDAL |
| --- | --- |
| `LLM_BASE_URL` | `http://EMILIA:4000/v1` |
| `LLM_API_KEY` | clé LiteLLM |
| `LLM_MODEL`, `EMBED_MODEL` | noms des modèles dans LiteLLM |
| `JWT_SECRET` | 32 caractères aléatoires au moins |
| `ADMIN_EMAIL`, `ADMIN_PASSWORD`, `ADMIN_NAME` | premier admin, créé au premier démarrage seulement |
| `CORS_ORIGINS` | `["https://adresse-de-l-interface"]` |
| `COOKIE_SECURE` | `true` |

`QDRANT_URL`, `REFRESH_COOKIE_PATH` et `FORWARDED_ALLOW_IPS` sont fixés par `docker-compose.yml`.

```bash
docker compose build --pull
docker compose up -d
curl -s localhost:8090/health
```

`/health` doit répondre `"status": "ok"`, avec `models.missing` vide et `qdrant.ok` à `true`. Se connecter ensuite à
l'interface avec le premier admin, changer son mot de passe (Mon compte), puis déposer les documents depuis
Administration > Documents. Retirer `ADMIN_PASSWORD` de `.env` une fois le compte créé.

## 4. Mise à jour

```bash
git pull
docker compose build --pull
docker compose up -d
```

Au démarrage, le backend applique les migrations de la base et vérifie l'index. Si le journal affiche l'erreur
« Index à vérifier au démarrage » (changement de modèle d'embedding ou nouvelle version de l'index), reconstruire
l'index :

```bash
docker compose exec backend python -m scripts.ingest --reset
```

L'assistant répond de nouveau dès la fin de la commande, dont la durée dépend du nombre de documents.

## 5. Exploitation courante

| Tâche | Où |
| --- | --- |
| Ajouter, remplacer, réindexer ou supprimer un document | Administration > Documents |
| Créer un compte admin ou client, désactiver un compte | Administration > Comptes |
| Donner l'accès à une application (groupe B1) | Administration > Clés de service, la clé s'affiche une seule fois |
| Retrouver une erreur signalée par un utilisateur | Administration > Journal, champ Référence |

Un document est indexé en arrière-plan : son état passe de « En attente » à « Indexé », ou à « Échec » avec l'étape
et la cause. Un document modifié est réécrit avant que l'ancienne version soit retirée, l'assistant n'est jamais
privé du document pendant la mise à jour.

Une application appelle `POST /chat` (ou `/chat/stream`) sur le port 8090 avec l'en-tête `X-API-Key`. La
documentation de l'API est sur `http://VM150:8090/docs`.

## 6. Sauvegarde et restauration

Sauvegarde (base copiée de façon cohérente même API en marche, 7 dernières archives gardées) :

```bash
docker compose exec backend python -m scripts.backup
mkdir -p sauvegardes
docker compose cp backend:/app/data/sauvegardes/. ./sauvegardes
```

Copier ensuite `./sauvegardes` sur ARCHIVE. Les archives contiennent les empreintes des mots de passe : dossier
réservé aux administrateurs, jamais versionné. Sauvegarde chaque nuit à 02 h 30, dans la crontab de l'utilisateur
qui exploite la VM :

```
30 2 * * * cd /chemin/du/depot && docker compose exec -T backend python -m scripts.backup && docker compose cp backend:/app/data/sauvegardes/. ./sauvegardes
```

Restauration :

```bash
docker compose stop backend
docker compose run --rm -v "$PWD/sauvegardes:/restore:ro" backend \
    python -m scripts.restore /restore/gandal-AAAAMMJJ-HHMMSS.tar.gz
docker compose run --rm backend python -m scripts.ingest --reset
docker compose up -d backend
```

## 7. Surveillance

- `GET /health` : `ok` ou `degraded`, avec l'état du serveur de modèles et de Qdrant. C'est la route à donner à la
  supervision.
- Journal (Administration > Journal) : erreurs avec leur trace, échecs d'indexation, connexions, actions des admins,
  alertes de sécurité. Chaque erreur affichée à un utilisateur porte une référence (en-tête `X-Request-ID`) qui
  retrouve l'événement. Conservation 90 jours (`EVENTS_RETENTION_DAYS`).
- Journaux des conteneurs : `docker compose logs --tail 200 backend`.

## 8. Pannes courantes

| Symptôme | Cause probable | Action |
| --- | --- | --- |
| `/health` en `degraded`, `models.ok` à `false` | LiteLLM ou EMILIA injoignable, clé refusée | vérifier `LLM_BASE_URL`, `LLM_API_KEY`, l'accès réseau vers EMILIA:4000 |
| `models.missing` non vide | nom de modèle absent de LiteLLM | corriger `LLM_MODEL` ou `EMBED_MODEL`, ou ajouter le modèle dans LiteLLM |
| `qdrant.ok` à `false` | conteneur qdrant arrêté | `docker compose up -d qdrant` |
| L'assistant renvoie une erreur 503 | modèle ou Qdrant en erreur | ouvrir le journal avec la référence, la cause y est |
| « Index à vérifier au démarrage » dans le journal | index créé par une version ou un modèle différent | `scripts.ingest --reset` (section 4) |
| Document en « Échec » | fichier protégé, illisible ou sans texte | la cause est sur la ligne du document et dans le journal |
| Déconnexion à chaque rechargement de page | interface servie en HTTP avec `COOKIE_SECURE=true` | passer par le proxy HTTPS |
| « compte temporairement bloqué » | 5 échecs de connexion | attendre 15 minutes, ou changer le mot de passe (ci-dessous) |
| Erreur 429 | limite de questions ou de connexions par minute | attendre une minute, ajuster `CHAT_PER_MINUTE` si besoin |
| Envoi refusé (413) | fichier de plus de 50 Mo | `MAX_UPLOAD_MB` et `client_max_body_size` de `frontend/nginx.conf` |

Mot de passe perdu, y compris celui du seul admin :

```bash
docker compose exec backend python -m scripts.set_password prenom.nom@exemple.cm
```

Le mot de passe est demandé deux fois sans être affiché. Le compte est réactivé et débloqué, ses sessions sont
fermées, l'action est inscrite au journal.

## 9. Réglages de la recherche

| Variable | Défaut | Effet |
| --- | --- | --- |
| `RETRIEVAL_MODE` | `hybride` | `hybride` combine le sens (bge-m3) et les mots exacts (BM25), `dense` le sens seul |
| `TOP_K` | 5 | passages donnés au modèle, moins de passages donne des réponses plus rapides |
| `MIN_SCORE` | 0,40 | similarité minimale d'un passage trouvé par le sens seul |
| `LLM_TIMEOUT` | 300 s | délai maximal d'une réponse du modèle |

Après un changement de réglage, rejouer l'évaluation avant de le garder. Le jeu `eval/questions.jsonl` porte sur le
corpus de test : à réécrire avec des questions sur les vrais documents GANDAL.

```bash
docker compose run --rm -v "$PWD/eval:/eval:ro" backend \
    python -m scripts.evaluate --questions /eval/questions.jsonl --out /app/data/resultats.csv
docker compose cp backend:/app/data/resultats.csv eval/
```
