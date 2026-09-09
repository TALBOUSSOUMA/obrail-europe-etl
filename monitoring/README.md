# Supervision — Prometheus + Grafana

Démarrés automatiquement par `docker compose up` (services `prometheus`
et `grafana`, voir [../docker-compose.yml](../docker-compose.yml)).

## Comment ça marche

```
API (FastAPI)  --/metrics-->  Prometheus  --datasource-->  Grafana
```

1. `api/main.py` instrumente l'application avec
   `prometheus-fastapi-instrumentator`, qui expose automatiquement un
   endpoint `/metrics` (nombre de requêtes, latence, codes de statut,
   par endpoint) — http://localhost:8001/metrics.
2. Prometheus (config : [prometheus.yml](prometheus.yml)) interroge
   cet endpoint toutes les 5 secondes et stocke l'historique.
3. Grafana se connecte à Prometheus automatiquement au démarrage
   (provisionnement dans [grafana/provisioning/](grafana/provisioning/))
   et affiche le tableau de bord "ObRail API - Supervision", déjà
   préchargé — aucun import manuel nécessaire.

## Accès

| | URL | Identifiants |
|---|---|---|
| Tableau de bord Grafana | http://localhost:3001 | `admin` / `obrail` par défaut (voir Sécurité ci-dessous) |
| Requêtes Prometheus brutes | http://localhost:9091 | — |

Ports 3001/9091 (et non 3000/9090) pour ne pas entrer en conflit avec
une autre pile Grafana/Prometheus deja lancee sur la meme machine.

## Panneaux du tableau de bord

- **Disponibilité de l'API** — `up{job="obrail-api"}` (1 = en ligne, 0 = injoignable)
- **Requêtes par seconde**, par endpoint
- **Taux d'erreurs HTTP 5xx**, sur une fenêtre glissante de 5 minutes
- **Latence p95** par endpoint (temps de réponse dépassé par seulement 5 % des requêtes)
- **Répartition des requêtes par code HTTP**

## Sécurité

Le mot de passe admin n'est pas écrit en clair dans `docker-compose.yml` :
il est lu depuis la variable d'environnement `GRAFANA_ADMIN_PASSWORD`
(définie dans `.env` à la racine, non committé — voir `.env.example`),
avec un repli sur `obrail` si elle est absente, pour que `docker
compose up` fonctionne aussi sans configuration (démo/évaluation).

Cette valeur de repli reste volontairement simple pour l'évaluation de
ce projet pédagogique. Avant tout déploiement réel, définissez un vrai
mot de passe dans votre `.env` :

```bash
echo "GRAFANA_ADMIN_PASSWORD=<mot-de-passe-fort>" >> .env
docker compose up -d grafana
```

⚠️ **Piège vérifié en pratique** : Grafana n'applique
`GRAFANA_ADMIN_PASSWORD` qu'au tout premier démarrage sur un volume
vide (`obrail_grafana_data`). Si Grafana a déjà tourné au moins une
fois (volume déjà créé), changer `.env` puis relancer le conteneur
**ne suffit pas** — l'ancien mot de passe reste actif. Pour le changer
sur une instance existante sans perdre les dashboards, utilisez plutôt :

```bash
docker compose exec grafana grafana-cli admin reset-admin-password <mot-de-passe-fort>
```

(ou, si vous acceptez de tout réinitialiser : `docker compose down -v`
supprime aussi les données PostgreSQL, à ne pas faire à la légère).
