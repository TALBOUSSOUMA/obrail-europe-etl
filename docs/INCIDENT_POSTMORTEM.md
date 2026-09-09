# Post-mortem — Panne de base de données non gérée gracieusement

| | |
|---|---|
| **Service concerné** | API ObRail Europe (FastAPI) |
| **Sévérité** | Élevée (dégrade tous les endpoints exposant des données) |
| **Type** | Incident reproduit intentionnellement (exercice de type *game day* / chaos engineering) pour valider la robustesse du service avant mise en production, dans le cadre de la démarche de supervision continue exigée par le cahier des charges. |
| **Statut** | Résolu — correctif déployé et testé |

## 1. Résumé

Lorsque la base de données PostgreSQL devient injoignable (arrêt du
conteneur, coupure réseau, redémarrage planifié...), l'API renvoyait à
ses clients une erreur **500 Internal Server Error** générique,
accompagnée d'une trace Python brute côté serveur — sans message
exploitable pour un client (le frontend ne pouvait pas distinguer
"vos critères de recherche sont invalides" d'"le service est en
panne"), et sans ligne de log claire pour un diagnostic rapide.

## 2. Comment l'incident a été détecté

Deux signaux, tous deux visibles dans le tableau de bord Grafana
("ObRail API - Supervision", panneau **Taux d'erreurs (HTTP 5xx)**) :

1. Le taux d'erreurs 5xx passe de ~0 % à 100 % sur les endpoints
   consultant la base de données, quasi instantanément.
2. Le panneau **Disponibilité de l'API** reste pourtant à 1 ("up") —
   observation importante : ce panneau mesure la disponibilité du
   *processus* (répond-il sur `/metrics` ?), pas sa disponibilité
   *fonctionnelle*. Un service peut être "up" au sens infrastructure
   tout en étant cassé pour l'utilisateur. C'est le taux d'erreurs, pas
   la simple disponibilité du process, qui a révélé l'incident.

## 3. Reproduction (utilisée aussi comme scénario de démonstration)

```bash
docker compose stop postgres        # simule la panne
curl -i http://localhost:8001/health
curl -i "http://localhost:8001/dessertes?limit=1"
```

**Avant correctif**, les deux commandes renvoyaient :

```
HTTP/1.1 500 Internal Server Error
Internal Server Error
```

— sans corps JSON exploitable.

## 4. Diagnostic

Les logs applicatifs (`docker compose logs api`) contenaient la trace
complète :

```
sqlalchemy.exc.InterfaceError: (pg8000.exceptions.InterfaceError)
Can't create a connection to host postgres and port 5432
(timeout is None and source_address is None).
```

**Cause racine** : `api/main.py` ne définissait aucun gestionnaire
d'exception pour les erreurs de connexion à la base de données
(`sqlalchemy.exc.DBAPIError` et ses sous-classes). FastAPI retombait
donc sur son comportement par défaut : 500 générique + trace complète
non filtrée.

## 5. Résolution

Ajout d'un gestionnaire d'exception dédié dans `api/main.py`
([voir le code](../api/main.py)) :

- Intercepte `sqlalchemy.exc.DBAPIError` (classe parente de toutes les
  erreurs de connexion/exécution SQLAlchemy, y compris
  `InterfaceError` et `OperationalError`) à l'échelle de l'application
  entière — un seul endroit à maintenir, pas un `try/except` par route.
- Renvoie **503 Service Unavailable** (le bon code HTTP : le problème
  est temporaire et côté serveur, pas une erreur du client) avec un
  message clair : *"Service temporairement indisponible : impossible
  de joindre la base de données. Réessayez dans quelques instants."*
- Journalise une ligne de log dédiée et *grep-able*
  (`Base de donnees injoignable sur GET /dessertes : ...`), au lieu de
  dizaines de lignes de trace brute.

**Après correctif**, mêmes commandes :

```
HTTP/1.1 503 Service Unavailable
{"detail":"Service temporairement indisponible : impossible de joindre
la base de données. Réessayez dans quelques instants."}
```

## 6. Vérification

```bash
docker compose stop postgres   # panne
curl -i http://localhost:8001/health          # -> 503, message clair
docker compose start postgres  # retour a la normale
curl -i http://localhost:8001/health          # -> 200, aucune action manuelle necessaire
```

La reprise est **automatique** dès que la base redevient joignable
(grâce à `pool_pre_ping=True`, déjà présent dans `api/database.py` :
chaque connexion est vérifiée avant réutilisation, les connexions
mortes sont silencieusement recréées).

**Test de non-régression** ajouté :
[`api/tests/test_incident_db_unavailable.py`](../api/tests/test_incident_db_unavailable.py)
— simule la panne via `dependency_overrides` (sans dépendre d'un vrai
arrêt de conteneur, pour rester rapide et fiable en CI) et vérifie le
503 sur `/health` et `/dessertes`, plus la non-régression sur les
requêtes suivantes. 23/23 tests passent, y compris ces 3 nouveaux.

## 7. Actions préventives et limites identifiées

- **Fait** : réponse claire + log exploitable + test de non-régression.
- **Pas encore fait** (limite assumée, à mentionner en soutenance) :
  pas de *retry* automatique côté client frontend en cas de 503 —
  l'utilisateur doit recharger manuellement. Amélioration possible :
  un intercepteur HTTP côté frontend avec backoff exponentiel.
  Le dimensionnement du pool de connexions SQLAlchemy (valeurs par
  défaut : 5 connexions + 10 en débordement) n'a pas été mis en cause
  ici mais reste un point de vigilance sous forte charge — hors
  périmètre de cet incident précis.
- Un futur `/health` pourrait distinguer plus finement "vivant" de
  "pleinement opérationnel" (pattern *liveness vs readiness probe*,
  standard en Kubernetes) plutôt que de tout faire reposer sur un seul
  endpoint.
