"""
TPRE622 - Training and comparison of several candidate models.

Problem: predict frequence_semaine (0 to 7) from a rail service's
structural characteristics. Regression task (the target is a discrete
but bounded, ordered count; regression gives an interpretable
continuous prediction, rounded if needed - a classification
alternative is discussed in the report).

Models compared (per the specifications: "regression, RandomForest,
boosting, simple neural networks"):
    1. Regularized linear regression (Ridge)   -> interpretable baseline
    2. Random Forest Regressor                  -> non-linear, robust
    3. Gradient Boosting (XGBoost)               -> tabular state of the art
    4. MLP (simple neural network)               -> deep learning comparison

Each model is tuned via hyperparameter search (GridSearchCV) with
cross-validation (5 folds), then evaluated on a test set never seen
during training.
"""

import json
import time
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestRegressor
from sklearn.linear_model import Ridge
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.model_selection import GridSearchCV, train_test_split
from sklearn.neural_network import MLPRegressor
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from xgboost import XGBRegressor

RANDOM_STATE = 42  # fixed seed for reproducibility (required by the specifications)

BASE_DIR = Path(__file__).resolve().parent
DATA_PATH = BASE_DIR.parent / "data" / "ml_dataset.csv"
MODELS_DIR = BASE_DIR / "models"
MODELS_DIR.mkdir(exist_ok=True)

NUMERIC_FEATURES = ["distance_km", "duree_h"]
CATEGORICAL_FEATURES = [
    "service_type", "type_train", "nom_operateur",
    "pays_origine", "pays_destination", "trajet_domestique",
]
TARGET = "frequence_semaine"


def load_data():
    df = pd.read_csv(DATA_PATH)
    df = df.drop(columns=["trip_id", "traction"])  # non-predictive ID; traction is 100% empty
    X = df[NUMERIC_FEATURES + CATEGORICAL_FEATURES]
    y = df[TARGET]
    return X, y


def build_preprocessor():
    return ColumnTransformer([
        ("num", StandardScaler(), NUMERIC_FEATURES),
        ("cat", OneHotEncoder(handle_unknown="ignore"), CATEGORICAL_FEATURES),
    ])


CANDIDATES = {
    "ridge": {
        "estimator": Ridge(random_state=RANDOM_STATE),
        "param_grid": {"model__alpha": [0.1, 1.0, 10.0]},
    },
    "random_forest": {
        "estimator": RandomForestRegressor(random_state=RANDOM_STATE, n_jobs=1),
        "param_grid": {
            "model__n_estimators": [100],
            "model__max_depth": [12, None],
        },
    },
    "xgboost": {
        "estimator": XGBRegressor(random_state=RANDOM_STATE, n_jobs=1, verbosity=0),
        "param_grid": {
            "model__n_estimators": [100],
            "model__max_depth": [4, 6],
            "model__learning_rate": [0.1],
        },
    },
    "mlp": {
        "estimator": MLPRegressor(random_state=RANDOM_STATE, max_iter=200, early_stopping=True),
        "param_grid": {
            "model__hidden_layer_sizes": [(32,)],
            "model__alpha": [0.001],
        },
    },
}


def main():
    X, y = load_data()
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=RANDOM_STATE
    )
    X_train, X_val, y_train, y_val = train_test_split(
        X_train, y_train, test_size=0.125, random_state=RANDOM_STATE  # 0.125*0.8=10% of the total set
    )
    print(f"Train: {len(X_train)} | Validation: {len(X_val)} | Test: {len(X_test)}")

    results = []
    fitted_models = {}

    for name, cfg in CANDIDATES.items():
        print(f"\n=== {name} ===")
        t0 = time.time()
        pipe = Pipeline([
            ("preprocess", build_preprocessor()),
            ("model", cfg["estimator"]),
        ])
        search = GridSearchCV(
            pipe, cfg["param_grid"], cv=3,
            scoring="neg_mean_absolute_error", n_jobs=1, verbose=1,
        )
        search.fit(X_train, y_train)
        elapsed = time.time() - t0

        best = search.best_estimator_
        y_pred_val = best.predict(X_val)
        y_pred_test = best.predict(X_test)

        metrics = {
            "modele": name,
            "meilleurs_hyperparametres": search.best_params_,
            "temps_entrainement_s": round(elapsed, 1),
            "mae_validation": round(mean_absolute_error(y_val, y_pred_val), 3),
            "mae_test": round(mean_absolute_error(y_test, y_pred_test), 3),
            "rmse_test": round(np.sqrt(mean_squared_error(y_test, y_pred_test)), 3),
            "r2_test": round(r2_score(y_test, y_pred_test), 3),
        }
        print(json.dumps(metrics, indent=2, ensure_ascii=False))
        results.append(metrics)
        fitted_models[name] = best

    results_df = pd.DataFrame(results).sort_values("mae_test")
    print("\n=== TABLEAU COMPARATIF ===")
    print(results_df.to_string(index=False))
    results_df.to_csv(MODELS_DIR / "comparatif_modeles.csv", index=False)

    best_name = results_df.iloc[0]["modele"]
    best_model = fitted_models[best_name]
    print(f"\nModele retenu : {best_name}")
    joblib.dump(best_model, MODELS_DIR / "modele_frequence.joblib")

    with open(MODELS_DIR / "metadata.json", "w") as f:
        json.dump({
            "modele_retenu": best_name,
            "features_numeriques": NUMERIC_FEATURES,
            "features_categorielles": CATEGORICAL_FEATURES,
            "cible": TARGET,
            "metriques": results_df.to_dict(orient="records"),
        }, f, indent=2, ensure_ascii=False)

    print(f"\nModele sauvegarde dans {MODELS_DIR / 'modele_frequence.joblib'}")


if __name__ == "__main__":
    main()
