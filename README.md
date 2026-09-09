# ObRail Europe — Entrepôt de données, API et portail web

Plateforme de consultation et d'analyse des dessertes ferroviaires
européennes (trains de jour et de nuit) pour ObRail Europe : pipeline
ETL, entrepôt PostgreSQL, API REST, portail web et modèle prédictif.

## Démarrer l'application (une seule commande)

**Prérequis : [Docker Desktop](https://www.docker.com/products/docker-desktop/) installé et lancé.**
Docker Desktop doit rester ouvert (au moins son moteur, en arrière-plan)
tant que l'application tourne — c'est lui qui fait fonctionner les
conteneurs. Voir [la section "Pourquoi Docker ?"](#pourquoi-docker-) plus bas si ce n'est pas clair.

```bash
docker compose up --build
```

Cette commande construit et démarre 5 services : la base de données, l'API,
le frontend, et la supervision (Prometheus + Grafana).

**Première exécution uniquement** — la base démarre vide (schéma seul) ;
chargez les données réelles versionnées dans `data/raw/` :

```bash
pip install -r requirements.txt
POSTGRES_PORT=5433 python etl/run_pipeline.py
```

### Accéder à l'application

| Service | URL | Description |
|---|---|---|
| Portail web | http://localhost:8081 | Interface utilisateur (à ouvrir en premier) |
| API — documentation | http://localhost:8001/docs | Swagger interactif, testez les endpoints ici |
| API — santé | http://localhost:8001/health | Doit répondre `{"status": "ok"}` |
| Grafana | http://localhost:3001 | Supervision (identifiants : `admin` / `obrail` par défaut — voir ci-dessous) |
| Prometheus | http://localhost:9091 | Métriques brutes (usage technique) |
| PostgreSQL | localhost:5433 | Base de données (usage interne/debug) |

> Ports volontairement différents de ceux d'un éventuel autre projet
> ObRail déjà lancé sur la même machine (ex. 8000/5173/9090/3000) —
> les deux peuvent tourner en même temps sans conflit.

Pour arrêter : `Ctrl+C` puis `docker compose down` (ajoutez `-v` pour
aussi supprimer les données stockées).

## Pourquoi Docker ?

Docker fait tourner chaque composant (base de données, API, frontend,
supervision) dans son propre environnement isolé et reproductible
("conteneur"), avec exactement les mêmes versions de logiciels que sur
la machine où le projet a été développé — pas d'installation manuelle
de PostgreSQL, Python, Node.js, etc.

**Docker Desktop** est l'application qui fait tourner ce moteur sur
Windows/Mac. Tant qu'elle n'est pas ouverte, aucune commande `docker
compose ...` ne peut fonctionner : les conteneurs ne peuvent pas
démarrer, donc l'API ne peut pas joindre sa base de données, et le
portail web affiche des erreurs de connexion. C'est normal — ce n'est
pas un bug, c'est la dépendance attendue.

## Développement (sans Docker, service par service)

Utile pour modifier le code et voir les changements immédiatement,
sans reconstruire d'image à chaque fois.

```bash
# 1. Base de données seule, via Docker
docker compose up postgres

# 2. API (dans un autre terminal)
cd api
pip install -r requirements.txt
uvicorn main:app --reload --port 8001

# 3. Frontend (dans un autre terminal)
cd frontend
npm install
npm run dev
```

## Tests

```bash
# Backend (necessite la base de donnees demarree et alimentee, voir plus haut)
cd api
pip install -r requirements.txt
pytest -v

# Frontend : verification du build de production
cd frontend
npm run build

# End-to-end (Playwright) : necessite toute la pile Docker demarree et
# alimentee (docker compose up -d, voir plus haut) - les tests s'executent
# contre http://localhost:8081, le vrai frontend conteneurise.
cd frontend
npm install
npx playwright install chromium   # une seule fois
npm run test:e2e
```

Ces mêmes commandes (sauf E2E, pour l'instant local uniquement) tournent
automatiquement sur chaque push via GitHub Actions (voir
[.github/workflows/ci.yml](.github/workflows/ci.yml)).

## Architecture du dépôt

```
etl/         Extraction, nettoyage et chargement des donnees (pipeline ETL)
sql/         Modele physique de donnees (schema PostgreSQL)
api/         API REST (FastAPI) - consultation + endpoint de prediction
ml/          Entrainement, evaluation et sauvegarde du modele predictif
frontend/    Portail web (React)
dashboard/   Tableau de bord qualite des donnees (Streamlit)
monitoring/  Configuration Prometheus + Grafana
```

## Variables d'environnement

Voir `.env.example` (racine, pipeline ETL) et `frontend/.env.example`
(URL de l'API consommée par le portail web). Aucun secret réel n'est
committé — copiez ces fichiers en `.env` et ajustez si besoin.

Le mot de passe admin de Grafana suit ce même principe : le
`docker-compose.yml` le lit depuis `GRAFANA_ADMIN_PASSWORD` (dans
`.env`, à la racine), avec un repli sur `obrail` si la variable est
absente — pratique pour l'évaluation, mais **à changer avant tout
déploiement réel** en définissant `GRAFANA_ADMIN_PASSWORD` dans votre
propre `.env` (jamais committé).

## Documentation complémentaire

- Choix de modèle, limites et veille technique (IA) : [ml/VEILLE_ET_LIMITES.md](ml/VEILLE_ET_LIMITES.md)
- Documentation interactive de l'API : http://localhost:8001/docs (une fois l'application démarrée)
