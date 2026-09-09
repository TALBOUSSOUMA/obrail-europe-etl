# Rapport 5 — Monitorage applicatif et résolution d'un incident technique

**Épreuve : Évaluation 5 — durée 10 min — soutenance orale (démonstration courte possible)**

## Points clés à retenir avant d'entrer

- Chaîne de supervision complète et fonctionnelle : API → Prometheus → Grafana,
  vérifiée en direct (pas seulement configurée).
- Un incident réel a été **provoqué délibérément** (exercice de type *game day*), détecté
  via le monitoring, diagnostiqué via les logs, corrigé dans le code, puis vérifié.
- Leçon technique à mettre en avant : "disponible" (process vivant) et "fonctionnel"
  (répond correctement aux utilisateurs) sont deux choses différentes — le monitoring
  doit distinguer les deux.
- Un test de non-régression protège désormais ce correctif.

## 1. Mise en place du monitorage applicatif

### 1.1 Chaîne technique

```
API (FastAPI)  --/metrics-->  Prometheus  --datasource-->  Grafana
```

1. `api/main.py` instrumente l'application avec `prometheus-fastapi-instrumentator` :
   une seule ligne de code (`Instrumentator().instrument(app).expose(app, ...)`) suffit à
   exposer automatiquement `/metrics` (nombre de requêtes, latence, codes de statut, par
   endpoint) — pas de métrique codée à la main.
2. Prometheus (`monitoring/prometheus.yml`) interroge cet endpoint toutes les 5 secondes.
3. Grafana se connecte à Prometheus **automatiquement au démarrage** (datasource et
   tableau de bord provisionnés par fichiers, `monitoring/grafana/provisioning/`) —
   aucun import manuel requis de la part de l'évaluateur.

### 1.2 Métriques suivies (tableau de bord "ObRail API - Supervision")

- **Disponibilité de l'API** (`up{job="obrail-api"}`)
- **Requêtes par seconde**, par endpoint
- **Taux d'erreurs HTTP 5xx**, fenêtre glissante de 5 minutes
- **Latence p95** par endpoint
- **Répartition des requêtes par code HTTP**

### 1.3 Vérification réelle (pas seulement une configuration statique)

Le scraping Prometheus a été vérifié en interrogeant son API (`/api/v1/targets`) :
statut `"health": "up"` confirmé pour la cible `obrail-api`. Le provisionnement Grafana
a été vérifié via son API : la datasource "Prometheus" et le tableau de bord
"ObRail API - Supervision" apparaissent bien automatiquement, sans action manuelle.

## 2. L'incident : détection, diagnostic, résolution

### 2.1 Résumé

Une base de données injoignable (conteneur arrêté, coupure réseau...) faisait remonter
une **500 Internal Server Error générique**, avec une trace Python brute côté serveur —
aucun message exploitable pour le client, aucune ligne de log claire pour diagnostiquer
rapidement. Exactement le type de défaut que la supervision doit permettre de détecter
et de corriger.

### 2.2 Détection

Deux signaux observés dans Grafana lors de la reproduction de la panne :

1. Le panneau **Taux d'erreurs 5xx** passe de ~0 % à 100 % sur les endpoints consultant
   la base — signal net.
2. Le panneau **Disponibilité** reste pourtant à 1 ("up") — **enseignement important** :
   ce panneau mesure la disponibilité du *processus* (répond-il sur `/metrics` ?), pas sa
   disponibilité *fonctionnelle*. Un service peut être "up" au sens infrastructure tout
   en étant cassé pour l'utilisateur. C'est le taux d'erreurs, pas la simple présence du
   processus, qui révèle l'incident.

### 2.3 Diagnostic

Les logs applicatifs (`docker compose logs api`) contenaient la trace complète :

```
sqlalchemy.exc.InterfaceError: (pg8000.exceptions.InterfaceError)
Can't create a connection to host postgres and port 5432 (...)
```

**Cause racine** : aucun gestionnaire d'exception dédié pour les erreurs de connexion
base de données dans `api/main.py`. FastAPI retombait sur son comportement par défaut :
500 générique et trace non filtrée.

### 2.4 Résolution

Ajout d'un gestionnaire d'exception applicatif (`database_unavailable_handler`,
`api/main.py`), déclenché sur `sqlalchemy.exc.DBAPIError` (classe parente de toutes les
erreurs de connexion SQLAlchemy) :

- renvoie **503 Service Unavailable** avec un message clair pour le client, plutôt
  qu'une 500 muette ;
- journalise une ligne de log dédiée et *grep-able*, au lieu d'une trace de plusieurs
  dizaines de lignes.

### 2.5 Vérification avant/après

| | Avant correctif | Après correctif |
|---|---|---|
| `GET /health` (base coupée) | `500` + trace brute | `503` + message explicite |
| `GET /dessertes` (base coupée) | `500` + trace brute | `503` + message explicite |
| Log applicatif | trace Python complète | 1 ligne dédiée, exploitable |
| Reprise après rétablissement de la base | automatique (`pool_pre_ping=True`) | inchangée, toujours automatique |

### 2.6 Non-régression

`api/tests/test_incident_db_unavailable.py` (3 tests) simule la panne via
`dependency_overrides` de FastAPI et vérifie le 503 sur `/health` et `/dessertes`, plus
la non-fuite de l'override vers les tests suivants. Ces 3 tests font partie des 26 tests
backend qui passent dans la CI à chaque push.

Documentation complète, au format post-mortem professionnel :
[`docs/INCIDENT_POSTMORTEM.md`](../INCIDENT_POSTMORTEM.md).

## 3. Script de démonstration (si le temps le permet, ~5 min)

```bash
docker compose stop postgres                              # 1. declenche la panne
curl -i http://localhost:8001/dessertes?limit=1            # 2. montrer la 503 claire
docker compose logs api --tail 5                            # 3. montrer le log exploitable
# 4. montrer le panneau "Taux d'erreurs" passer au rouge dans Grafana
docker compose start postgres                               # 5. retablissement
curl -i http://localhost:8001/dessertes?limit=1             # 6. retour a 200, sans action manuelle
```

## 4. Limites assumées

- Pas de *retry* automatique côté frontend en cas de 503 : l'utilisateur doit recharger
  manuellement — amélioration possible (intercepteur HTTP avec backoff exponentiel),
  citée mais non implémentée par manque de temps.
- Le dimensionnement du pool de connexions SQLAlchemy (valeurs par défaut) n'a pas été
  mis en cause dans cet incident précis mais reste un point de vigilance sous forte
  charge, non testé ici.
- Pas de canal d'alerte automatique (email/Slack) sur dépassement de seuil Grafana — la
  supervision est *visuelle* (tableau de bord), pas encore *proactive* (alerting).
