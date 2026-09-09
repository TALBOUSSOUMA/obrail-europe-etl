# Rapport 4 — Réalisation d'une application intégrant un service d'IA

**Épreuve : Évaluation 4 — durée 20 min — soutenance orale + démonstration live**

## Points clés à retenir avant d'entrer

- Application complète : base de données + API + frontend + supervision, **5 services
  Docker**, démarrée en une seule commande.
- CI/CD fonctionnelle et **vérifiée verte sur GitHub Actions** (pas juste un fichier YAML
  écrit et jamais exécuté).
- 30 tests automatisés (26 backend + 4 E2E) qui passent réellement.
- Un vrai incident a été provoqué, diagnostiqué et corrigé — détaillé dans le rapport 5.

## 1. Objectif et périmètre

Faire passer la solution ObRail Europe d'un prototype (API seule, déploiement manuel,
aucun test automatisé, aucune supervision) à une application de production :
conteneurisée, testée, supervisée, livrée par une chaîne CI/CD. Le modèle d'IA
(rapport 3) est intégré dans cette application, pas ajouté à côté.

## 2. Architecture technique

```
┌─────────────┐    ┌─────────────┐    ┌──────────────┐
│  Frontend    │───▶│  API REST    │───▶│  PostgreSQL   │
│  (React/nginx)│    │  (FastAPI)   │    │  (entrepôt)   │
│  port 8081   │    │  port 8001   │    │  port 5433    │
└─────────────┘    └──────┬──────┘    └──────────────┘
                          │ /metrics
                          ▼
                   ┌─────────────┐    ┌──────────────┐
                   │ Prometheus  │───▶│   Grafana     │
                   │ port 9091   │    │  port 3001    │
                   └─────────────┘    └──────────────┘
```

5 services orchestrés par un seul `docker-compose.yml` : `postgres`, `api`, `frontend`,
`prometheus`, `grafana`. Démarrage complet :

```bash
docker compose up --build
```

**Détail technique volontaire, à mentionner** : aucun `container_name` fixe n'est
imposé, et les ports (8081/8001/9091/3001) diffèrent des ports par défaut
(5173/8000/9090/3000) — pour permettre à cette application de tourner sans conflit à
côté d'une autre pile Docker sur la même machine. Une contrainte de déploiement réelle,
rencontrée et résolue pendant le projet, pas anticipée en théorie.

## 3. Backend

- FastAPI, endpoints REST documentés automatiquement (Swagger sur `/docs`).
- Validation stricte des entrées via Pydantic (types, bornes — ex. `limit` plafonné à 500).
- Gestion d'erreurs maîtrisée : 404 pour une ressource absente, 422 pour une entrée
  invalide, et **503 explicite** (pas une 500 muette) si la base de données devient
  injoignable — voir rapport 5 pour le détail de cet incident et de son correctif.
- Sécurité basique : requêtes SQL exclusivement paramétrées (aucune concaténation de
  chaîne dans une requête SQL), CORS configuré explicitement.

## 4. Frontend

React, 4 pages (Dessertes, Indicateurs, Prédiction, État du service), pensées pour un
public non technique (partenaires ObRail : ONG, institutions, opérateurs) :

- Accessibilité numérique (RGAA) concrète, pas seulement déclarée : labels associés à
  chaque champ, `aria-live` sur les zones dynamiques, lien d'évitement ("aller au contenu
  principal"), focus clavier visible, contrastes de couleur testés.
- Champs de recherche pensés pour l'utilisateur : menu déroulant pour le type de train
  (liste fermée), auto-complétion pour les 756 gares (liste trop longue pour un menu
  classique) — remplace un champ texte libre où l'utilisateur ne savait pas quoi saisir.
- Navigation par onglets simple, chaque route servie correctement même en rechargement
  direct (configuration nginx dédiée pour le routage côté client).

## 5. Conteneurisation

- Un `Dockerfile` par service applicatif (API, frontend), tous deux **multi-étapes** :
  le frontend n'embarque ni Node ni `node_modules` dans l'image finale, seulement le
  HTML/CSS/JS compilé servi par nginx.
- Persistance garantie par des volumes Docker nommés (`obrail_pgdata`,
  `obrail_grafana_data`) : les données survivent à un redémarrage des conteneurs
  (vérifié : recréation du conteneur API, données toujours présentes derrière).
- `HEALTHCHECK` sur l'API (vérifie que la base est réellement joignable, pas juste que
  le process tourne) et sur le frontend, utilisés par `docker-compose.yml` pour ordonner
  le démarrage des services (`depends_on: condition: service_healthy`).

## 6. Pipeline CI/CD

`.github/workflows/ci.yml`, déclenché à chaque push sur `main`, 3 jobs :

1. **backend** : recrée une vraie base PostgreSQL, y rejoue le pipeline ETL complet à
   partir des données réelles versionnées, puis exécute les 26 tests d'intégration.
2. **frontend** : installe les dépendances, lint, vérifie que le build de production
   compile.
3. **docker-build** : construit réellement les images Docker de l'API et du frontend.

**Vérifié vert sur GitHub après le push** — pas seulement écrit, réellement exécuté avec
succès.

## 7. Tests automatisés

- **26 tests backend** (pytest) : dessertes, référentiels, prédiction, santé, incident.
- **4 tests end-to-end** (Playwright), exécutés contre la vraie pile Docker (pas des
  mocks) : recherche de dessertes avec filtre réel, réinitialisation, et le parcours de
  prédiction complet jusqu'à un résultat vérifié dans la plage métier valide.

## 8. Script de démonstration (à minuter, ~10 min dans les 20)

1. **(2 min)** `docker compose up --build` (ou, si déjà lancé, `docker compose ps` pour
   montrer les 5 services "Up"/"healthy").
2. **(3 min)** Parcourir le frontend : Dessertes (filtrer par ville/type/pays), Indicateurs,
   État du service (disponibilité + historique qualité).
3. **(2 min)** Ouvrir `http://localhost:8001/docs`, exécuter un appel Swagger en direct.
4. **(2 min)** `pytest -v` dans `api/` puis `npm run test:e2e` dans `frontend/` en direct.
5. **(1 min)** Montrer l'onglet **Actions** du dépôt GitHub, coche verte sur le dernier
   commit.

## 9. Limites assumées

- Pas de gestion de secrets industrielle (Vault, AWS Secrets Manager) : les identifiants
  de démonstration sont dans `.env`/`.env.example`, une approche adaptée à un contexte
  pédagogique mais explicitement signalée comme à ne pas reproduire en production réelle.
- Un seul environnement (pas de séparation dev/staging/prod) : acceptable pour ce
  périmètre, cité comme axe d'évolution.
- Pas encore de déploiement automatique sur un environnement de test distant (la CI
  construit les images mais ne les publie sur aucun registre) — un choix délibéré, faute
  de registre configuré, documenté comme tel plutôt que laissé implicite.
