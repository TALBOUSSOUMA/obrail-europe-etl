"""
TPRE622 - Deliverable 1: exploratory analysis and table of selected variables.

Generates:
- eda/variables_retenues.csv   (variable table: role, type, description)
- eda/distributions.png         (distribution of the target and numeric variables)
- eda/frequence_par_categorie.png
- eda/feature_importance.png    (most influential variables per the chosen model)
"""

from pathlib import Path

import joblib
import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns

BASE_DIR = Path(__file__).resolve().parent
DATA_PATH = BASE_DIR.parent / "data" / "ml_dataset.csv"
EDA_DIR = BASE_DIR / "eda"
EDA_DIR.mkdir(exist_ok=True)

sns.set_style("whitegrid")
COLOR = "#12436D"

VARIABLES = [
    {"variable": "distance_km", "role": "Feature", "type": "Numerique continue",
     "description": "Distance a vol d'oiseau entre gare d'origine et de destination"},
    {"variable": "duree_h", "role": "Feature", "type": "Numerique continue",
     "description": "Duree du trajet en heures"},
    {"variable": "service_type", "role": "Feature", "type": "Categorielle (2 modalites)",
     "description": "Jour ou Nuit"},
    {"variable": "type_train", "role": "Feature", "type": "Categorielle (12 modalites)",
     "description": "Marque commerciale du service (TER, TGV inOui, Intercites de nuit...)"},
    {"variable": "nom_operateur", "role": "Feature", "type": "Categorielle (39 modalites)",
     "description": "Operateur ferroviaire exploitant la desserte"},
    {"variable": "pays_origine / pays_destination", "role": "Feature", "type": "Categorielle (26 modalites chacune)",
     "description": "Codes pays ISO des gares de depart et d'arrivee"},
    {"variable": "trajet_domestique", "role": "Feature (derivee)", "type": "Booleenne",
     "description": "Vrai si pays_origine == pays_destination"},
    {"variable": "frequence_semaine", "role": "Cible (target)", "type": "Numerique discrete (0-7)",
     "description": "Nombre de jours par semaine ou la desserte circule"},
    {"variable": "traction", "role": "Exclue", "type": "-",
     "description": "100% manquante (non fournie par le GTFS) - retiree des features"},
    {"variable": "trip_id", "role": "Exclue", "type": "Identifiant",
     "description": "Cle technique, aucune valeur predictive - retiree des features"},
]


def main():
    df = pd.read_csv(DATA_PATH)

    # ---- Table of selected variables ----------------------------------
    var_df = pd.DataFrame(VARIABLES)
    var_df.to_csv(EDA_DIR / "variables_retenues.csv", index=False)
    print(var_df.to_string(index=False))

    # ---- Distributions ---------------------------------------------------
    fig, axes = plt.subplots(1, 3, figsize=(15, 4))
    sns.histplot(df["frequence_semaine"], bins=8, color=COLOR, ax=axes[0])
    axes[0].set_title("Distribution de la cible (frequence_semaine)")
    sns.histplot(df["distance_km"], bins=40, color=COLOR, ax=axes[1])
    axes[1].set_title("Distribution de distance_km")
    sns.histplot(df["duree_h"], bins=40, color=COLOR, ax=axes[2])
    axes[2].set_title("Distribution de duree_h")
    plt.tight_layout()
    plt.savefig(EDA_DIR / "distributions.png", dpi=150)
    plt.close()

    # ---- Average frequency per train type -------------------------------
    plt.figure(figsize=(9, 5))
    order = df.groupby("type_train")["frequence_semaine"].mean().sort_values(ascending=False).index
    sns.barplot(data=df, x="frequence_semaine", y="type_train", order=order, color=COLOR, errorbar=None)
    plt.title("Frequence hebdomadaire moyenne par type de train")
    plt.xlabel("Frequence moyenne (jours/semaine)")
    plt.tight_layout()
    plt.savefig(EDA_DIR / "frequence_par_categorie.png", dpi=150)
    plt.close()

    # ---- Feature importance (already-trained model) ---------------------
    model_path = BASE_DIR / "models" / "modele_frequence.joblib"
    if model_path.exists():
        pipe = joblib.load(model_path)
        preprocess = pipe.named_steps["preprocess"]
        model = pipe.named_steps["model"]
        if hasattr(model, "feature_importances_"):
            feature_names = preprocess.get_feature_names_out()
            importances = pd.Series(model.feature_importances_, index=feature_names)
            top20 = importances.sort_values(ascending=False).head(20)
            plt.figure(figsize=(9, 7))
            sns.barplot(x=top20.values, y=top20.index, color=COLOR)
            plt.title("20 variables les plus influentes (Random Forest)")
            plt.xlabel("Importance")
            plt.ylabel("Variable (apres encodage)")
            plt.tight_layout()
            plt.savefig(EDA_DIR / "feature_importance.png", dpi=150)
            plt.close()
            print("\nTop 10 variables influentes:")
            print(top20.head(10))

    print(f"\nFigures sauvegardees dans {EDA_DIR}")


if __name__ == "__main__":
    main()
