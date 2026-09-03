"""
Orchestrator: runs Extract -> Transform -> Load end to end.

Usage:
    python run_pipeline.py

Designed to be scheduled (cron, Airflow, GitHub Action...) so the data
warehouse stays up to date without manual intervention, as required by
the cahier des charges' "automatisation et reproductibilite" constraint.
"""

from pathlib import Path

import pandas as pd

from extract_gtfs import extract_gtfs
from extract_backontrack import extract_back_on_track
from transform import clean_raw, build_star_schema
from load import get_engine, truncate_all, load_star_schema, log_quality_run


def main():
    base_dir = Path(__file__).resolve().parent.parent

    print("== EXTRACT ==")
    # Source 1: real, open SNCF GTFS export (transport.data.gouv.fr) -
    # mostly Jour services (TER, TGV, Intercites), France-centric with
    # some genuine cross-border termini.
    gtfs_zip = base_dir / "data" / "raw" / "Export_OpenData_SNCF_GTFS_NewTripId.zip"
    raw_gtfs = extract_gtfs(gtfs_zip)
    print(f"{len(raw_gtfs)} rows from the real SNCF GTFS export")

    # Source 2: real Back-on-Track Open Night Train Database - entirely
    # Nuit services, ~30 European operators, 24 countries.
    bot_dir = base_dir / "data" / "raw" / "back-on-track"
    raw_bot = extract_back_on_track(bot_dir)
    print(f"{len(raw_bot)} rows from the Back-on-Track night train database")

    raw_df = pd.concat([raw_gtfs, raw_bot], ignore_index=True)
    print(f"{len(raw_df)} raw rows total from 2 heterogeneous real source(s)")

    print("\n== TRANSFORM ==")
    clean_df, report = clean_raw(raw_df)
    print(report.as_dict())
    tables = build_star_schema(clean_df)

    print("\n== LOAD ==")
    engine = get_engine()
    truncate_all(engine)
    load_star_schema(tables, engine)
    log_quality_run(report, engine)

    print("\nPipeline finished successfully.")


if __name__ == "__main__":
    main()