# Rapport 2 — Installation et configuration du service d'IA préconisé

**Épreuve : Évaluation 2 — durée 15 min — soutenance orale, sans démonstration**

## Points clés à retenir avant d'entrer

- Benchmark de 4 services IA cloud réalisé **avant** de choisir une solution — pas un
  choix par défaut.
- Décision argumentée : **ne pas migrer vers le cloud à ce stade**, et le dire clairement
  plutôt que de le cacher.
- Le "service d'IA préconisé" est donc une chaîne scikit-learn locale, installée et
  configurée avec une séparation nette entraînement / inférence.
- Reproductibilité : graine aléatoire fixée partout, dépendances versionnées, modèle
  sérialisé dans un format standard (joblib).

## 1. Démarche de sélection : benchmark avant décision

Avant d'installer quoi que ce soit, une veille comparative a été menée sur les services
d'IA proposés dans le cahier des charges : **AWS SageMaker Autopilot**, **Azure ML
AutoML**, **Google Vertex AI AutoML**, **HuggingFace AutoTrain**. Critères retenus :
capacités techniques, coût, contraintes d'intégration, explicabilité — pas seulement la
performance brute.

**Constat déterminant** : HuggingFace AutoTrain utilise en interne les mêmes familles
d'algorithmes (XGBoost, Random Forest, régression régularisée) que celles testées
manuellement dans ce projet. C'est une validation indirecte forte : la démarche manuelle
n'est pas une solution de repli faute de mieux, elle converge avec ce qu'un service
spécialisé ferait automatiquement.

## 2. Décision et justification

**Choix : ne pas migrer vers un service cloud à ce stade.** Raisons concrètes :

- Volume de données modeste (38 412 lignes, quelques dizaines de features après
  encodage) : largement dans les capacités d'une machine standard, sans bénéfice
  attendu d'un service managé à grande échelle.
- Un service cloud introduit un coût récurrent, une dépendance à un fournisseur externe,
  et une latence réseau supplémentaire pour un gain de performance non démontré sur ce
  volume.
- La chaîne scikit-learn locale reste **entièrement explicable et rejouable** : chaque
  étape (préparation, entraînement, sélection, sauvegarde) est un script Python versionné,
  pas une boîte noire hébergée.

Cette décision est explicitement documentée comme réversible : `ml/VEILLE_ET_LIMITES.md`
précise qu'elle est à réévaluer si le volume de données croît de plusieurs ordres de
grandeur — ce n'est pas un choix figé mais un choix daté et justifié.

## 3. Installation et configuration du service retenu

Le "service d'IA" installé est donc un environnement Python dédié, avec une séparation
volontaire entre deux besoins différents :

### 3.1 Environnement d'entraînement (`ml/requirements.txt`)

```
pandas, scikit-learn, xgboost, joblib, matplotlib, seaborn, SQLAlchemy, pg8000, python-dotenv
```

Installé une seule fois, sur la machine de développement, pour exécuter
`train_models.py` et `eda.py`. Comprend des dépendances lourdes (xgboost, matplotlib,
seaborn) qui n'ont aucune utilité en production.

### 3.2 Environnement d'inférence (`ml/requirements-predict.txt`)

```
pandas, scikit-learn, joblib
```

Créé spécifiquement pour ne **pas** embarquer les dépendances d'entraînement dans l'image
Docker de l'API — une configuration délibérée, pas un oubli : l'API n'a besoin que de
charger un modèle déjà entraîné et de l'appeler, jamais de le ré-entraîner. Résultat
concret : image Docker de l'API significativement plus légère et plus rapide à construire.

### 3.3 Configuration de la persistance et du chargement du modèle

- Format de sauvegarde : **joblib** (`modele_frequence.joblib`), standard pour les
  pipelines scikit-learn, portable entre machines.
- Chargement paresseux et mis en cache (`ml/predict.py`) : le modèle est chargé une seule
  fois en mémoire au premier appel (`_model` en cache module), puis réutilisé — une
  configuration pensée pour la performance en production, pas juste pour que "ça marche".
- Reproductibilité : `RANDOM_STATE = 42` fixé une seule fois et propagé à tous les
  modèles candidats et aux découpages train/validation/test.

### 3.4 Intégration dans l'infrastructure conteneurisée

Le `Dockerfile` de l'API (`api/Dockerfile`) copie explicitement et uniquement :
`ml/predict.py` et `ml/models/` — jamais les scripts d'entraînement ni les données
brutes. C'est la configuration qui fait le lien concret entre ce rapport et l'application
en production (rapport 4) : le service d'IA installé ici est le même que celui qui
répond réellement aux requêtes `/predict` de l'application.

## 4. Vérification de l'installation

L'installation est validée par des tests automatisés, pas seulement par une exécution
manuelle ponctuelle : `api/tests/test_predict.py` vérifie que le service répond, que la
prédiction est déterministe (même entrée → même sortie, aucune composante aléatoire à
l'inférence), et qu'elle reste dans la plage métier valide (0 à 7 jours/semaine).

## 5. Limites assumées

- Le choix de ne pas utiliser de service cloud managé n'a pas été comparé empiriquement
  (pas d'entraînement réel lancé sur AWS/Azure/GCP pour chiffrer un coût exact) — le
  benchmark reste qualitatif, faute de budget et de temps pour un test payant réel.
- La configuration actuelle suppose un seul modèle en mémoire par instance API ; un
  changement de modèle nécessite un redéploiement (pas de rechargement à chaud) — un
  choix simple, documenté comme limite plutôt que comme un défaut caché.
