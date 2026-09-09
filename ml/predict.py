"""
TPRE622 - Prediction script, simulating the future API integration.

Loads the saved model (joblib) and exposes it via a predict() function
reused as-is by the FastAPI /predict endpoint.

Command-line usage (demo):
    python predict.py --distance_km 850 --duree_h 6.5 --type_train "TGV inOui" \\
        --service_type Jour --nom_operateur SNCF --pays_origine FR --pays_destination FR
"""

import argparse
import json
from pathlib import Path

import joblib
import pandas as pd

MODEL_PATH = Path(__file__).resolve().parent / "models" / "modele_frequence.joblib"
_model = None  # loaded only once (module-level cache), reused on every call


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
    """Predicts the weekly frequency (0-7) of a hypothetical rail service.

    Column names and order must match exactly those used during
    training (train_models.py) - the saved scikit-learn pipeline
    includes preprocessing (encoding, scaling), so raw values are
    enough as input.
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
    # the real frequency is an integer 0-7; the regressor's output is
    # clamped and rounded so it stays interpretable from a business standpoint
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
