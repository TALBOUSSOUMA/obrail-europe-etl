# Rapport 1 — Collecte, stockage et mise à disposition des données

**Épreuve : Évaluation 1 — durée 15 min — soutenance orale, sans démonstration**

## Points clés à retenir avant d'entrer

- 2 sources réelles et hétérogènes, 38 412 dessertes après nettoyage.
- Pipeline ETL en 3 étapes indépendantes (extract → transform → load), rejouable à volonté.
- Modèle physique en étoile (6 tables), conforme au 3FN, avec traçabilité de la source.
- Les données sont exposées via une API REST (pas un accès direct à la base).
- Une table dédiée (`log_qualite`) trace chaque exécution pour prouver la qualité dans le temps.

## 1. Contexte et objectif

ObRail Europe a besoin d'un référentiel de données ferroviaires harmonisé pour comparer
la contribution des trains de jour et de nuit au maillage européen. Le problème de départ :
les données sont dispersées, hétérogènes dans leur format, et sans référentiel commun
entre opérateurs. L'objectif de ce livrable est de construire un entrepôt unique, fiable
et automatisable à partir de sources réelles — pas un jeu de données fictif.

## 2. Sources et collecte

Deux sources réelles, choisies pour leur complémentarité :

| Source | Format | Contenu | Volume brut |
|---|---|---|---|
| SNCF GTFS (transport.data.gouv.fr) | ZIP GTFS (fichiers `.txt` normalisés) | Trains de jour, principalement domestiques France | 38 004 trajets |
| Back-on-Track Open Night Train Database | JSON | Trains de nuit, ~30 opérateurs européens | 408 trajets |

**Pourquoi ces deux sources et pas une seule ?** La source SNCF seule aurait donné un jeu
100 % domestique et 100 % diurne — inutilisable pour comparer jour/nuit à l'échelle
européenne, l'objectif même du projet. Back-on-Track comble ce trou par construction
(toutes ses données sont des trains de nuit internationaux).

La collecte est scriptée (`etl/extract_gtfs.py`, `etl/extract_backontrack.py`), pas manuelle :
chaque source a son propre extracteur, mais tous deux produisent la même structure de
sortie à plat, pour que la suite du pipeline n'ait aucune connaissance du format d'origine.

## 3. Transformation et qualité des données

`etl/transform.py` applique des règles de nettoyage systématiques, chacune répondant à un
problème réel identifié dans les données brutes (pas hypothétique) :

- suppression des doublons sur `trip_id` (clé naturelle)
- standardisation de `service_type` (jour/Jour/JOUR → "Jour")
- passage des codes pays en majuscules
- conversion des horaires GTFS "> 24h" (ex. `25:40` pour un trajet après minuit) vers une
  plage `[0, 24)` compatible avec le type `TIME` de PostgreSQL
- suppression des lignes qui manquent un champ structurellement obligatoire (une desserte
  sans gare d'origine n'a pas de sens)
- les champs numériques légitimement inconnus (distance, émissions) restent `NULL` plutôt
  que d'être devinés — une valeur inventée fausserait silencieusement les analyses

**Résultat mesuré sur le dernier passage réel** (traçable via `/qualite`) :
38 412 lignes lues, 38 412 chargées, 0 doublon, 2 valeurs manquantes, taux de complétude
100,0 %. Ces chiffres ne sont pas illustratifs : ils viennent d'une exécution réelle du
pipeline, rejouable à l'identique.

## 4. Modèle de données (MPD)

Modèle en étoile, 6 tables (`sql/init_db.sql`), pensé pour l'analyse :

```
pays ──┬── gare ──┬── desserte (table de faits) ── ligne ── operateur
       │          │        │
       └──────────┘   source_donnees
```

- **`pays`, `operateur`, `gare`, `ligne`** : référentiels, dédupliqués.
- **`desserte`** : la table de faits — une ligne = un trajet précis, avec toutes les
  clés étrangères résolues, une contrainte `CHECK` interdisant une gare d'origine
  identique à la destination, et un `frequence_semaine` borné 0–7.
- **`source_donnees`** : traçabilité de chaque ligne jusqu'à sa source d'origine — une
  exigence explicite (transparence des données, dans l'esprit RGPD même en l'absence de
  données personnelles).
- **`log_qualite`** : une ligne par exécution du pipeline, seule preuve dans le temps que
  la qualité reste maîtrisée après chaque mise à jour.

Script **idempotent** (`DROP` puis `CREATE`) : rejouable sans intervention manuelle,
condition nécessaire pour l'automatisation exigée.

## 5. Mise à disposition des données

Les données ne sont **jamais** consultées directement en base par les autres composants :
tout passe par l'API REST (FastAPI), qui expose :

- `/dessertes` (filtrable par ville, type de train, pays, service) et `/dessertes/{id}`
- les référentiels : `/pays`, `/operateurs`, `/gares`, `/types-train`
- `/qualite` : historique des exécutions ETL, pour le tableau de bord de contrôle

Ce découpage (API entre la base et ses consommateurs) permet au frontend, au dashboard
Streamlit et à un futur consommateur tiers d'accéder aux mêmes données sans jamais
connaître le schéma SQL — une vraie séparation des responsabilités, pas juste un détail
d'implémentation.

## 6. Automatisation et reproductibilité

`etl/run_pipeline.py` enchaîne extract → transform → load en une seule commande
(`python run_pipeline.py`), sans paramètre manuel. C'est ce même script qui tourne dans le
pipeline CI/CD à chaque push (voir `.github/workflows/ci.yml`) : le schéma est recréé,
les deux sources réelles sont ré-extraites, transformées et chargées dans une base neuve —
la preuve que le processus est réellement rejouable, pas seulement documenté comme tel.

## 7. Limites assumées

- La distance est calculée à vol d'oiseau (formule de Haversine), pas la distance réelle
  du réseau — écart documenté, acceptable pour une analyse comparative.
- Les facteurs d'émission CO2 sont des valeurs publiées (SNCF/ADEME) appliquées par type
  de train, pas mesurées trajet par trajet.
- La source SNCF reste France-centrique (96 % du volume) ; Back-on-Track compense
  partiellement mais le déséquilibre reste réel — à assumer, pas à masquer.
