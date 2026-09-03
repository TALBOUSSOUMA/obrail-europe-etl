# TPRE622 — Veille et recommandations

## Veille technique menée

- **Algorithmes tabulaires** : comparaison de 4 familles (régression régularisée, forêt aléatoire,
  boosting de gradient, réseau de neurones simple), conformément à la recommandation du cahier
  des charges. Le Random Forest s'est imposé (MAE test 1,42 vs 1,63-1,78 pour les alternatives),
  cohérent avec la littérature sur les données tabulaires de taille moyenne, où les méthodes
  d'ensemble à base d'arbres dominent généralement les réseaux de neurones.
- **Services IA cloud** : veille sur AWS SageMaker Autopilot, Azure ML AutoML, Google Vertex AI
  AutoML et HuggingFace AutoTrain (voir tableau comparatif). Constat notable : HuggingFace
  AutoTrain utilise en interne les mêmes algorithmes (XGBoost, Random Forest, Ridge) que ceux
  retenus manuellement ici — validation indirecte de la pertinence des choix effectués.
- **Bonnes pratiques MLOps** : fixation d'une graine aléatoire unique (`random_state=42`) sur
  l'ensemble du pipeline pour garantir la reproductibilité exigée par le cahier des charges.

## Risques, limites et biais identifiés

| Limite | Description | Impact |
|---|---|---|
| Pouvoir explicatif modéré | R² = 0,20 sur le meilleur modèle | La fréquence dépend de facteurs non capturés par les données (décisions commerciales, subventions publiques, historique d'infrastructure) |
| Biais de représentation géographique | 96,5 % des lignes sont domestiques françaises (SNCF) | Le modèle généralise mal aux dynamiques d'autres marchés ferroviaires européens, sous-représentés dans les données d'entraînement |
| Cible bornée artificiellement | frequence_semaine plafonnée à 7 lors de l'ETL | Un modèle de régression peut prédire des valeurs hors bornes ; le script `predict.py` les tronque explicitement à [0, 7] |
| Variable traction inutilisable | 100 % de valeurs manquantes | Une variable pourtant pertinente a priori (train électrique vs diesel) n'a pas pu être testée comme feature |
| Pas de test d'équité | Aucune vérification que le modèle ne défavorise pas systématiquement certains pays/opérateurs minoritaires | À creuser avant tout usage réel en recommandation stratégique auprès d'institutions |

## Recommandations pour la suite

1. **Enrichir les features** : population des villes desservies, présence d'un aéroport concurrent,
   subventions publiques connues — pourrait significativement améliorer le R².
2. **Reformuler en classification** : prédire une catégorie ("faible/moyenne/forte fréquence")
   plutôt qu'une valeur continue pourrait être plus robuste et plus interprétable pour les
   décideurs institutionnels visés par ObRail.
3. **Ré-entraînement périodique** : documenté dans `ml/predict.py` — relancer
   `data_extraction.py` puis `train_models.py` après chaque mise à jour du pipeline ETL,
   idéalement automatisé dans la chaîne CI/CD de TPRE532.
4. **Ne pas migrer vers un service cloud** à ce stade (cf. section benchmark) — réévaluer
   uniquement si le volume de données croît de plusieurs ordres de grandeur.
