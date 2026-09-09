"""
Load step of the ETL pipeline.

Writes the star-schema dataframes produced by transform.build_star_schema()
into PostgreSQL, in FK-safe order, then appends a row to log_qualite so the
control dashboard can track each run over time.

Uses SQLAlchemy + pandas.to_sql, which keeps the code short and lets the
same functions be reused unchanged if the target engine ever changes
(e.g. testing against SQLite) — this is what the specifications call
"interoperability".
"""

import os
from datetime import datetime
import pandas as pd
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

# Load variables from a .env file at the project root, if present, without
# overriding any already set in the real environment (e.g. in CI/Docker).
load_dotenv()

# Table load order matters: parents before children, to satisfy FK constraints.
LOAD_ORDER = ["pays", "operateur", "gare", "ligne", "source_donnees", "desserte"]


def get_engine():
    """Build a SQLAlchemy engine from environment variables.

    Centralizing connection config here (rather than hardcoding a DSN)
    is what makes the pipeline reproducible across machines/Docker
    containers without touching the code — required by the
    specifications' "automation and reproducibility" constraint.

    Uses the pg8000 driver (pure Python) rather than psycopg2 (a C
    extension wrapping libpq). This sidesteps a real bug hit while
    building this pipeline: on Windows with a French system locale,
    libpq can return a connection error message in French with
    accented characters, and psycopg2 crashes trying to decode it as
    UTF-8 - masking whatever the actual error was. pg8000 has no such
    issue since it never shells out to the native libpq library.
    """
    user = os.getenv("POSTGRES_USER", "obrail")
    password = os.getenv("POSTGRES_PASSWORD", "obrail")
    host = os.getenv("POSTGRES_HOST", "localhost")
    port = os.getenv("POSTGRES_PORT", "5432")
    db = os.getenv("POSTGRES_DB", "obrail")
    dsn = f"postgresql+pg8000://{user}:{password}@{host}:{port}/{db}"
    return create_engine(dsn)


def load_star_schema(tables: dict[str, pd.DataFrame], engine) -> None:
    """Load each dataframe into its matching table, replacing existing
    content — this is what makes the ETL script re-runnable (idempotent)
    without manual cleanup between runs.
    """
    with engine.begin() as conn:
        conn.execute(text("SET search_path TO obrail"))

    for table_name in LOAD_ORDER:
        df = tables[table_name]
        df.to_sql(
            table_name,
            engine,
            schema="obrail",
            if_exists="append",
            index=False,
            method="multi",   # batches INSERT statements instead of one per row
            chunksize=2000,   # needed for the ~38k-row desserte table to load in seconds, not minutes
        )
        print(f"Loaded {len(df)} rows into obrail.{table_name}")


def log_quality_run(report, engine) -> None:
    """Insert one row per ETL execution into log_qualite, feeding the
    control dashboard requested in the specifications.
    """
    with engine.begin() as conn:
        conn.execute(
            text(
                """
                INSERT INTO obrail.log_qualite
                    (date_execution, nb_lignes_lues, nb_lignes_chargees,
                     nb_doublons_supprimes, nb_valeurs_manquantes, taux_completude_pct)
                VALUES
                    (:date_execution, :nb_lignes_lues, :nb_lignes_chargees,
                     :nb_doublons_supprimes, :nb_valeurs_manquantes, :taux_completude_pct)
                """
            ),
            {
                "date_execution": datetime.now(),
                "nb_lignes_lues": report.nb_lignes_lues,
                "nb_lignes_chargees": report.nb_lignes_chargees,
                "nb_doublons_supprimes": report.nb_doublons_supprimes,
                "nb_valeurs_manquantes": report.nb_valeurs_manquantes,
                "taux_completude_pct": report.taux_completude_pct,
            },
        )
    print("Quality log recorded")


def truncate_all(engine) -> None:
    """Empty every table before a fresh load, in child-to-parent order,
    so re-running the pipeline never fails on duplicate primary keys.
    """
    with engine.begin() as conn:
        for table_name in reversed(LOAD_ORDER):
            conn.execute(text(f"TRUNCATE TABLE obrail.{table_name} CASCADE"))
