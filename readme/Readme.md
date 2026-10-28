# Quiz API — Backend FastAPI de Quiz App Pro

API REST du projet **Quiz App Pro**, une application de quiz sécurisée avec détection de triche.
Elle gère l'authentification, les packs de questions, le calcul des scores côté serveur, le classement et l'administration.

Application Android (Java) associée : [quizAppMobile](https://github.com/Noumbibou/quizAppMobile)

## Stack

| Rôle | Technologie |
|---|---|
| API | FastAPI, Uvicorn |
| Base de données | MySQL via SQLAlchemy 2 et PyMySQL |
| Authentification | Firebase Admin SDK (tokens Firebase, rôles par *custom claims*) |
| Validation | Pydantic 2 |
| Import / IA | openpyxl, openai |
| Configuration | python-dotenv |

## Fonctionnalités

- **Authentification** : chaque route protégée vérifie un token Firebase ; les routes d'administration exigent le rôle `admin`.
- **Packs de questions par niveau** (`beginner`, `intermediate`, `advanced`) : un seul pack actif par niveau.
- **Questions sécurisées** : l'ordre des questions et des options est mélangé côté serveur, et la bonne réponse n'est **jamais envoyée au client**.
- **Score calculé par le serveur** à partir de la session de quiz, puis enregistré avec les données anti-triche.
- **Anti-triche** : score de suspicion et sanctions (voir plus bas).
- **Classement top 10**, historique et statistiques par utilisateur et par niveau.
- **Administration** : gestion des utilisateurs (désactiver, réactiver, ajouter ou retirer le rôle admin), gestion des packs de questions, rapports de fraude.

## Routes principales

| Méthode | Route | Accès | Description |
|---|---|---|---|
| GET | `/health` | public | Vérifie que l'API tourne |
| GET | `/me` | utilisateur | Infos du compte connecté |
| PUT | `/user/update-profile` | utilisateur | Met à jour le nom d'utilisateur (base locale + Firebase) |
| GET | `/quiz/questions?level=` | utilisateur | Questions mélangées du pack actif + clé de session |
| POST | `/quiz/score` | utilisateur | Calcule et enregistre le score |
| GET | `/stats/my-scores` | utilisateur | Historique des scores |
| GET | `/stats/my-summary` | utilisateur | Résumé personnel (parties, moyenne, meilleur score) |
| GET | `/stats/leaderboard?level=` | public | Top 10 du niveau |
| GET | `/stats/summary?level=` | public | Statistiques globales du niveau |
| GET | `/admin/frauds` | admin | Scores signalés comme frauduleux |
| GET / PUT | `/admin/users…` | admin | Liste, détails, activer / désactiver, rôle admin |
| POST / GET / PUT / DELETE | `/admin/question-sets…` | admin | Création, liste, activation, suppression des packs |

La documentation interactive complète (Swagger UI) est disponible sur `http://127.0.0.1:8000/docs` quand le serveur tourne.

## Système anti-triche

Le serveur additionne un score de suspicion à partir des informations envoyées avec le quiz :

| Signal | Points |
|---|---|
| Triche détectée par l'application | +3 |
| Visage non vérifié (ML Kit) | +3 |
| Temps moyen par question inférieur à 1 seconde | +2 |
| Caméra inactive | +1 |
| Position GPS absente | +1 |

Sanctions : score de suspicion **≥ 3** → score mis à 0 et partie signalée ; score **= 2** → score réduit de 50 % et partie signalée.

> Ces signaux sont envoyés par l'application cliente et peuvent donc être falsifiés. Le système sert à repérer et signaler les comportements suspects, pas à les empêcher de façon absolue.

## Installation

```bash
git clone https://github.com/Noumbibou/fast_Api_QuizApp.git
cd fast_Api_QuizApp
python -m venv venv
source venv/bin/activate        # Windows : venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env            # puis renseigner les variables du fichier
uvicorn main:app --reload --port 8000
```

Au démarrage, l'API initialise la base de données (`init_database()` dans `seed_data.py`).

Prérequis : Python 3, un serveur MySQL, un projet Firebase avec l'authentification par e-mail / mot de passe activée et une clé de compte de service. <!-- À compléter : nom exact des variables de .env.example et emplacement de la clé Firebase -->

## Structure du projet

```
auth/        Vérification des tokens Firebase et rôle admin
models/      Modèles SQLAlchemy (questions, packs, scores, utilisateurs)
services/    Logique métier
schemas.py   Schémas Pydantic (requêtes et réponses)
database.py  Connexion à la base
seed_data.py Initialisation et données de départ
main.py      Routes de l'API
```

## Limites connues et pistes d'amélioration

- Les sessions de quiz (réponses mélangées) sont gardées en mémoire : elles sont perdues au redémarrage et ne fonctionnent pas avec plusieurs workers. Piste : Redis ou une table avec date d'expiration.
- `main.py` regroupe toutes les routes. Piste : les séparer avec des `APIRouter` (quiz, stats, admin).
- Les tests sont des scripts à la racine. Piste : un dossier `tests/` avec pytest.
- Les migrations sont des scripts manuels. Piste : Alembic.
