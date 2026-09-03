"""
Extraction du jeu de donnees pour la modelisation (TPRE622).

Enjeu retenu : anticiper la demande en mobilite ferroviaire, en predisant
la frequence hebdomadaire (frequence_semaine) d'une desserte a partir de
ses caracteristiques structurelles (distance, duree, type de train,
service jour/nuit, pays).

Justification du choix :
- frequence_semaine est deja disponible pour les 38 412 dessertes reelles
  (pas de nouvelle collecte necessaire, conforme a "vous pouvez reutiliser
  vos derniers travaux" du cahier des charges TPRE622)
- Pas de fuite de donnee (data leakage) : contrairement a l'emission CO2
  (calculee par une formule deterministe a partir de la distance, donc
  triviale a "predire"), la frequence resulte de choix commerciaux des
  operateurs, un vrai signal a apprendre.
- Utilite metier directe : identifie les lignes sous-exploitees ou a fort
  potentiel, en lien avec l'enjeu "detecter les zones de sous-desserte"
  egalement propose par le cahier des charges.
"""

import os
import pandas as pd
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

# Charge les variables depuis le .env a la racine du projet (meme mecanisme
# que etl/load.py) - sans ca, ce script retombe sur le port 5432 par defaut
# et se connecte au mauvais serveur PostgreSQL (le service Windows natif,
# pas le conteneur Docker sur le port 5433).
load_dotenv()

engine = create_engine(
    f"postgresql+pg8000://{os.getenv('POSTGRES_USER','obrail')}:"
    f"{os.getenv('POSTGRES_PASSWORD','obrail')}@"
    f"{os.getenv('POSTGRES_HOST','localhost')}:"
    f"{os.getenv('POSTGRES_PORT','5432')}/"
    f"{os.getenv('POSTGRES_DB','obrail')}"
)

QUERY = """
SELECT
    d.trip_id,
    d.service_type,
    d.distance_km,
    d.duree_h,
    d.traction,
    l.type_train,
    o.nom_operateur,
    po.code_pays AS pays_origine,
    pd.code_pays AS pays_destination,
    (po.code_pays = pd.code_pays) AS trajet_domestique,
    d.frequence_semaine
FROM obrail.desserte d
JOIN obrail.ligne l ON d.id_ligne = l.id_ligne
JOIN obrail.operateur o ON l.id_operateur = o.id_operateur
JOIN obrail.gare go ON d.id_gare_origine = go.id_gare
JOIN obrail.pays po ON go.code_pays = po.code_pays
JOIN obrail.gare gd ON d.id_gare_destination = gd.id_gare
JOIN obrail.pays pd ON gd.code_pays = pd.code_pays
WHERE d.distance_km IS NOT NULL
  AND d.duree_h IS NOT NULL
  AND d.frequence_semaine IS NOT NULL
"""

if __name__ == "__main__":
    df = pd.read_sql(text(QUERY), engine)
    print(f"{len(df)} dessertes extraites pour la modelisation")
    print(df.dtypes)
    print(df.describe(include="all").T)
    out_path = os.path.join(os.path.dirname(__file__), "..", "data", "ml_dataset.csv")
    df.to_csv(out_path, index=False)
    print(f"Sauve dans {out_path}")
