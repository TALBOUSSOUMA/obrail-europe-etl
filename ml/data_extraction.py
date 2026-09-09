"""
Dataset extraction for modeling (TPRE622).

Problem chosen: anticipate rail mobility demand, by predicting a rail
service's weekly frequency (frequence_semaine) from its structural
characteristics (distance, duration, train type, day/night service,
country).

Justification for this choice:
- frequence_semaine is already available for the 38,412 real rail
  services (no new collection needed, consistent with the "you may
  reuse your latest work" clause of the TPRE622 specifications)
- No data leakage: unlike CO2 emissions (computed with a deterministic
  formula from distance, hence trivial to "predict"), frequency results
  from operators' commercial choices - a genuine signal to learn.
- Direct business value: identifies underused or high-potential lines,
  tying into the "detect under-served areas" problem also proposed by
  the specifications.
"""

import os
import pandas as pd
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

# Loads variables from the .env file at the project root (same mechanism
# as etl/load.py) - without this, this script falls back to the default
# port 5432 and connects to the wrong PostgreSQL server (the native
# Windows service, not the Docker container on port 5433).
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
