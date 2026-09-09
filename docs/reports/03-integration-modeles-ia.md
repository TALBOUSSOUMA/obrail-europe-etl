# Rapport 3 — Intégration des modèles et services d'intelligence artificielle

**Épreuve : Évaluation 3 — durée 20 min — soutenance orale + démonstration live**

## Points clés à retenir avant d'entrer

- 4 familles de modèles comparées objectivement (régression régularisée, forêt aléatoire,
  boosting, réseau de neurones), pas un seul modèle choisi a priori.
- Modèle retenu : **Random Forest** (MAE test 1,425), meilleur des 4 malgré un temps
  d'entraînement plus long — un choix justifié, pas une évidence.
- Le modèle est réellement intégré dans l'API (`/predict`) et dans le frontend, pas juste
  un notebook isolé.
- R² = 0,20 : performance modeste, assumée et expliquée, pas cachée.

## 1. Problème posé

Prédire `frequence_semaine` (0 à 7 jours/semaine) d'une desserte à partir de ses
caractéristiques structurelles : distance, durée, type de train, service jour/nuit,
opérateur, pays d'origine/destination. Tâche de **régression** : la cible est un comptage
discret mais borné et ordonné, une régression donne une prédiction continue interprétable
et facilement arrondie côté métier.

## 2. Préparation des données

- Variables numériques : `distance_km`, `duree_h` → standardisées (`StandardScaler`).
- Variables catégorielles : `service_type`, `type_train`, `nom_operateur`,
  `pays_origine`, `pays_destination`, et **`trajet_domestique`** (variable dérivée :
  `pays_origine == pays_destination`) → encodage one-hot (`handle_unknown="ignore"` pour
  ne jamais planter sur une valeur inédite en production).
- Colonnes exclues explicitement et justifiées : `trip_id` (identifiant technique, aucune
  valeur prédictive), `traction` (100 % de valeurs manquantes dans les données GTFS).
- Découpage 70 % entraînement / 10 % validation / 20 % test, graine fixée (`random_state=42`)
  pour la reproductibilité.

## 3. Modèles candidats et comparaison

Quatre familles testées, chacune avec recherche d'hyperparamètres (`GridSearchCV`,
validation croisée 3 folds), conformément à la demande du cahier des charges de comparer
régression / RandomForest / boosting / réseau de neurones simple :

| Modèle | MAE validation | **MAE test** | RMSE test | R² test | Temps d'entraînement |
|---|---|---|---|---|---|
| **Random Forest** | 1,469 | **1,425** | 1,82 | **0,201** | 211,9 s |
| XGBoost | 1,669 | 1,634 | 1,856 | 0,169 | 2,4 s |
| MLP (réseau de neurones) | 1,772 | 1,735 | 1,954 | 0,079 | 15,1 s |
| Ridge (régression régularisée) | 1,814 | 1,779 | 1,972 | 0,062 | 1,4 s |

**Modèle retenu : Random Forest.** Meilleur sur toutes les métriques d'erreur (MAE, RMSE)
et sur le R². Le temps d'entraînement, très supérieur aux autres (211,9 s vs quelques
secondes), n'est **pas disqualifiant** : c'est un coût unique, hors ligne, qui n'a aucun
impact sur le temps de réponse de l'API en production — c'est la vitesse d'*inférence*
qui compte pour l'utilisateur final, et elle est immédiate.

**Pourquoi ce résultat est cohérent avec la littérature** : sur des données tabulaires de
taille moyenne comme ici, les méthodes d'ensemble à base d'arbres dominent généralement
les réseaux de neurones — le MLP arrive d'ailleurs dernier sur le R².

## 4. Intégration réelle dans l'application

Le modèle n'est pas un artefact isolé : il est branché de bout en bout.

```
Requête HTTP  →  POST /predict (api/main.py)
                       │
                       ▼
              ml/predict.py : predict()
                       │  charge modele_frequence.joblib (mis en cache)
                       ▼
              pipeline scikit-learn (preprocessing + Random Forest)
                       │
                       ▼
              résultat borné [0, 7], arrondi à 1 décimale
                       │
                       ▼
              Frontend : page "Prédiction" (formulaire → résultat affiché)
```

Chaîne vérifiée par des tests automatisés réels (pas seulement exécutée à la main) :
`api/tests/test_predict.py` (4 tests : réponse plausible, erreur 422 si champ manquant,
déterminisme, différence jour/nuit) et `frontend/e2e/prediction.spec.js` (test Playwright
de bout en bout, formulaire jusqu'au résultat affiché) — **26 + 4 tests passent au total**
sur l'ensemble du projet.

## 5. Script de démonstration (à minuter, ~8 min dans les 20)

1. **(2 min)** Montrer `ml/eda/distributions.png` et `feature_importance.png` : les
   variables numériques les plus influentes selon le modèle retenu.
2. **(2 min)** Montrer `ml/models/comparatif_modeles.csv` et `metadata.json` : le tableau
   comparatif réel, pas recopié — expliquer le choix du Random Forest.
3. **(3 min) Démo live** : `docker compose up -d` déjà lancé →
   ouvrir `http://localhost:8081/prediction` → remplir le formulaire (ex. TGV inOui,
   850 km, 6h30, Jour, FR→FR) → cliquer "Estimer" → montrer le résultat affiché, puis
   ouvrir `http://localhost:8001/docs` et refaire le même appel via Swagger pour prouver
   que c'est la même API, pas une simulation front-end.
4. **(1 min)** Lancer `pytest -v tests/test_predict.py` en direct pour montrer les tests
   passer.

## 6. Limites assumées

- **R² = 0,201** : pouvoir explicatif modéré. La fréquence réelle dépend aussi de
  décisions commerciales et de subventions publiques, des facteurs absents des données
  disponibles — à dire clairement, pas à minimiser.
- **Biais de représentation géographique** : 96,5 % des lignes sont domestiques
  françaises (SNCF) ; le modèle généralise moins bien aux dynamiques des autres marchés
  européens, sous-représentés.
- **Cible bornée artificiellement** : `frequence_semaine` est plafonnée à 7 dans l'ETL ;
  `predict.py` tronque explicitement la sortie du régresseur à `[0, 7]` pour rester
  interprétable, plutôt que de laisser une valeur hors plage.
- Aucun test d'équité formel (le modèle ne défavorise-t-il pas certains pays/opérateurs
  minoritaires) n'a été mené — piste d'amélioration citée dans `ml/VEILLE_ET_LIMITES.md`.
