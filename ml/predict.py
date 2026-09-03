"""
TPRE622 - Script de prediction, simulant la future integration API.

Charge le modele sauvegarde (joblib) et l'expose via une fonction predict()
reutilisable telle quelle par l'endpoint FastAPI /predict.

Usage en ligne de commande (demo) :
    python predict.py --distance_km 850 --duree_h 6.5 --type_train "TGV inOui" \\
        --service_type Jour --nom_operateur SNCF --pays_origine FR --pays_destination FR
"""

import argparse
import json
from pathlib import Path

import joblib
import pandas as pd

MODEL_PATH = Path(__file__).resolve().parent / "models" / "modele_frequence.joblib"
_model = None  # charge une seule fois (cache module-level), reutilise a chaque appel


def get_model():
    global _model
    if _model is None:
        _model = joblib.load(MODEL_PATH)
    return _model


def predict(
    distance_km: float,
    duree_h: float,
    type_train: str,
    service_type: str,
    nom_operateur: str,
    pays_origine: str,
    pays_destination: str,
) -> float:
    """Predit la frequence hebdomadaire (0-7) d'une desserte hypothetique.

    Les noms et l'ordre des colonnes doivent correspondre exactement a
    ceux utilises pendant l'entrainement (train_models.py) - le pipeline
    scikit-learn sauvegarde inclut le preprocessing (encodage, mise a
    l'echelle), donc les valeurs brutes suffisent en entree.
    """
    model = get_model()
    trajet_domestique = pays_origine == pays_destination
    row = pd.DataFrame([{
        "distance_km": distance_km,
        "duree_h": duree_h,
        "service_type": service_type,
        "type_train": type_train,
        "nom_operateur": nom_operateur,
        "pays_origine": pays_origine,
        "pays_destination": pays_destination,
        "trajet_domestique": trajet_domestique,
    }])
    pred = model.predict(row)[0]
    # la frequence reelle est un entier 0-7 ; on borne et arrondit la
    # sortie du regresseur pour qu'elle reste interpretable metier
    return round(max(0, min(7, pred)), 1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--distance_km", type=float, required=True)
    parser.add_argument("--duree_h", type=float, required=True)
    parser.add_argument("--type_train", required=True)
    parser.add_argument("--service_type", choices=["Jour", "Nuit"], required=True)
    parser.add_argument("--nom_operateur", required=True)
    parser.add_argument("--pays_origine", required=True)
    parser.add_argument("--pays_destination", required=True)
    args = parser.parse_args()

    result = predict(**vars(args))
    print(json.dumps({"frequence_semaine_predite": result}, ensure_ascii=False))
