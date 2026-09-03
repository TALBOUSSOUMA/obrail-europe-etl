"""
Transform step of the ETL pipeline.

Two responsibilities, kept in separate functions on purpose so each
is independently testable and easy to explain in the technical report:

1. clean_raw()        -> fixes data quality issues, returns (clean_df, quality_report)
2. build_star_schema() -> reshapes the flat clean_df into the normalized
                          tables that mirror sql/init_db.sql (pays, operateur,
                          gare, ligne, source_donnees, desserte)
"""

import datetime
from dataclasses import dataclass, asdict
import pandas as pd

# Minimal static reference used to turn ISO country codes into readable names.
# In a production version this would come from an open data reference table
# (e.g. Eurostat's country nomenclature) instead of being hardcoded.
COUNTRY_NAMES = {
    "AT": "Autriche", "BE": "Belgique", "BG": "Bulgarie", "CH": "Suisse",
    "CZ": "Tchequie", "DE": "Allemagne", "ES": "Espagne", "FI": "Finlande",
    "FR": "France", "GB": "Royaume-Uni", "HR": "Croatie", "HU": "Hongrie",
    "IT": "Italie", "LT": "Lituanie", "LU": "Luxembourg", "MD": "Moldavie",
    "ME": "Montenegro", "NL": "Pays-Bas", "NO": "Norvege", "PL": "Pologne",
    "RO": "Roumanie", "RS": "Serbie", "SE": "Suede", "SI": "Slovenie",
    "SK": "Slovaquie", "TR": "Turquie", "UA": "Ukraine", "UK": "Royaume-Uni",
    "AQ": "Antarctique",
}

VALID_SERVICE_TYPES = {"jour": "Jour", "nuit": "Nuit"}
VALID_TRACTIONS = {"electrique", "diesel", "mixte"}


def _parse_hhmm(hhmm) -> "datetime.time | None":
    """Parse an 'HH:MM' string into a datetime.time.

    GTFS allows service-day hours >= 24 for a trip that continues past
    midnight (e.g. "25:40" for 01:40 the next day); wrap the hour into
    [0, 24) so it fits PostgreSQL's TIME type. Returns None for
    anything that isn't a well-formed "H:MM"/"HH:MM" string.
    """
    if not isinstance(hhmm, str) or ":" not in hhmm:
        return None
    hour_str, minute_str = hhmm.split(":")[:2]
    try:
        return datetime.time(int(hour_str) % 24, int(minute_str))
    except ValueError:
        return None


@dataclass
class QualityReport:
    nb_lignes_lues: int
    nb_lignes_chargees: int
    nb_doublons_supprimes: int
    nb_valeurs_manquantes: int
    taux_completude_pct: float

    def as_dict(self) -> dict:
        return asdict(self)


def clean_raw(raw_df: pd.DataFrame) -> tuple[pd.DataFrame, QualityReport]:
    """Apply data-quality rules to the flat raw dataframe.

    Rules applied (each maps to a bullet of the "contraintes fonctionnelles"
    section of the cahier des charges):
      - trim whitespace on every text column
      - drop exact duplicate trip_id (keep first occurrence)
      - drop rows missing a field that is structurally required
        (a trip without an origin/destination station or a schedule
        cannot be modeled as a DESSERTE at all)
      - standardize service_type ("jour"/"Jour"/"JOUR" -> "Jour")
      - standardize country codes to uppercase
      - parse "HH:MM" departure/arrival strings into real time values,
        wrapping GTFS service-day hours >= 24 (a trip past midnight,
        e.g. "25:40") into the [0, 24) range PostgreSQL's TIME can store
      - leave numeric fields that are legitimately unknown (distance,
        emissions) as NULL rather than inventing a value: fabricating
        numbers would silently corrupt downstream analyses
    """
    df = raw_df.copy()
    nb_lignes_lues = len(df)

    # 1. Trim whitespace on text values only.
    #    NB: do NOT use pandas' .str.strip() column-wide here. After
    #    concatenating several sources, numeric columns can end up with
    #    dtype "object" (a mix of Python floats and strings). Calling
    #    .str.strip() on such a column silently turns every non-string
    #    value (e.g. a float distance) into NaN - a real bug caught while
    #    testing this pipeline on combined sources. Stripping value-by-value
    #    and leaving non-strings untouched avoids that trap.
    str_cols = df.select_dtypes(include=["object", "string"]).columns
    df[str_cols] = df[str_cols].apply(
        lambda col: col.map(lambda v: v.strip() if isinstance(v, str) else v)
    )

    # 2. Deduplication on the natural key (trip_id)
    nb_before = len(df)
    df = df.drop_duplicates(subset="trip_id", keep="first")
    nb_doublons_supprimes = nb_before - len(df)

    # 3. Standardize service_type
    df["service_type"] = (
        df["service_type"].str.lower().map(VALID_SERVICE_TYPES)
    )

    # 4. Standardize country codes
    df["origin_country"] = df["origin_country"].str.upper()
    df["destination_country"] = df["destination_country"].str.upper()

    # 5. Standardize traction, fall back to NaN if unrecognised value
    df["traction"] = df["traction"].str.lower()
    df.loc[~df["traction"].isin(VALID_TRACTIONS), "traction"] = pd.NA

    # 6. Parse "HH:MM" strings into real datetime.time values. Left as
    #    plain strings, pandas' to_sql sends them to PostgreSQL as
    #    VARCHAR parameters, which it refuses to implicitly cast into
    #    the desserte table's TIME columns - a real error caught while
    #    building this pipeline. GTFS also allows service-day hours
    #    >= 24 for a trip that continues past midnight (e.g. "25:40"),
    #    which TIME cannot represent at all, so the hour is wrapped
    #    into [0, 24) before conversion.
    for col in ["departure_time", "arrival_time"]:
        df[col] = df[col].map(_parse_hhmm)

    # 7. Cast numeric columns; invalid or empty strings become NaN (NULL)
    numeric_cols = [
        "distance_km", "duration_h", "emission_gco2e_pkm",
        "total_emission_gco2e", "frequency_per_week",
    ]
    for col in numeric_cols:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    # 8. Count missing values across the fields that matter for analysis
    #    BEFORE dropping structurally-required rows, so the log reflects
    #    the true state of the raw extract.
    tracked_cols = [
        "destination_stop_name", "origin_stop_name", "departure_time",
        "arrival_time", "distance_km", "total_emission_gco2e",
    ]
    nb_valeurs_manquantes = int(df[tracked_cols].isna().sum().sum())

    # 9. Drop rows missing a structurally required field
    required_cols = [
        "trip_id", "origin_stop_name", "origin_country",
        "destination_stop_name", "destination_country",
        "departure_time", "arrival_time", "service_type",
    ]
    df = df.dropna(subset=required_cols)

    nb_lignes_chargees = len(df)
    taux_completude_pct = round(100 * nb_lignes_chargees / nb_lignes_lues, 2)

    report = QualityReport(
        nb_lignes_lues=nb_lignes_lues,
        nb_lignes_chargees=nb_lignes_chargees,
        nb_doublons_supprimes=nb_doublons_supprimes,
        nb_valeurs_manquantes=nb_valeurs_manquantes,
        taux_completude_pct=taux_completude_pct,
    )
    return df.reset_index(drop=True), report


def build_star_schema(df: pd.DataFrame) -> dict[str, pd.DataFrame]:
    """Reshape the flat, clean dataframe into the normalized tables
    that mirror the physical model in sql/init_db.sql.

    Returns a dict of dataframes keyed by table name, each already
    carrying the surrogate keys needed to load them in FK-safe order:
    pays -> operateur -> gare -> ligne -> source_donnees -> desserte.
    """
    # ---- pays --------------------------------------------------------
    all_codes = pd.unique(
        pd.concat([df["origin_country"], df["destination_country"]])
    )
    df_pays = pd.DataFrame({
        "code_pays": all_codes,
        "nom_pays": [COUNTRY_NAMES.get(c, c) for c in all_codes],
    })

    # ---- operateur -----------------------------------------------------
    df_operateur = (
        df[["agency_name"]].drop_duplicates().reset_index(drop=True)
    )
    df_operateur.insert(0, "id_operateur", df_operateur.index + 1)
    df_operateur = df_operateur.rename(columns={"agency_name": "nom_operateur"})

    # ---- gare (union of origin and destination stations) ---------------
    origin_stations = df[["origin_stop_name", "origin_country"]].rename(
        columns={"origin_stop_name": "nom_gare", "origin_country": "code_pays"}
    )
    dest_stations = df[["destination_stop_name", "destination_country"]].rename(
        columns={"destination_stop_name": "nom_gare", "destination_country": "code_pays"}
    )
    df_gare = (
        pd.concat([origin_stations, dest_stations])
        .drop_duplicates()
        .reset_index(drop=True)
    )
    df_gare.insert(0, "id_gare", df_gare.index + 1)

    # ---- ligne -----------------------------------------------------------
    # A ligne's business key is (route_name, agency_name) only, matching the
    # UNIQUE (nom_ligne, id_operateur) constraint in sql/init_db.sql -
    # type_train is just an attribute of the line, not part of its identity.
    # Deduplicating on all three columns (as an earlier version of this code
    # did) let the same route+operator produce two "ligne" rows whenever it
    # was served by more than one train type (e.g. a corridor shared by a
    # Regional and an Intercites service), which violated that constraint
    # at load time. Keeping the first train_type seen per (route, agency)
    # matches the schema's one-type-per-line model.
    df_ligne = (
        df[["route_name", "train_type", "agency_name"]]
        .drop_duplicates(subset=["route_name", "agency_name"], keep="first")
        .reset_index(drop=True)
    )
    df_ligne = df_ligne.merge(
        df_operateur, left_on="agency_name", right_on="nom_operateur"
    )
    df_ligne.insert(0, "id_ligne", df_ligne.index + 1)
    df_ligne = df_ligne.rename(columns={"route_name": "nom_ligne", "train_type": "type_train"})
    df_ligne = df_ligne[["id_ligne", "nom_ligne", "type_train", "id_operateur"]]

    # ---- source_donnees ----------------------------------------------
    df_source = (
        df[["source_dataset"]].drop_duplicates().reset_index(drop=True)
    )
    df_source.insert(0, "id_source", df_source.index + 1)
    df_source = df_source.rename(columns={"source_dataset": "nom_source"})

    # ---- desserte (fact table): resolve all foreign keys ----------------
    fact = df.merge(
        df_operateur[["id_operateur", "nom_operateur"]],
        left_on="agency_name", right_on="nom_operateur",
    )
    # Match on route_name + operator only, mirroring df_ligne's business
    # key above: a ligne row now stands for one (route, operator) pair
    # regardless of train_type, so every trip on that route/operator
    # attaches to that single ligne row.
    fact = fact.merge(
        df_ligne[["id_ligne", "nom_ligne", "id_operateur"]],
        left_on=["route_name", "id_operateur"],
        right_on=["nom_ligne", "id_operateur"],
    )
    fact = fact.merge(
        df_gare.rename(columns={"id_gare": "id_gare_origine"}),
        left_on=["origin_stop_name", "origin_country"],
        right_on=["nom_gare", "code_pays"],
    )
    fact = fact.merge(
        df_gare.rename(columns={"id_gare": "id_gare_destination"}),
        left_on=["destination_stop_name", "destination_country"],
        right_on=["nom_gare", "code_pays"],
        suffixes=("_origine", "_destination"),
    )
    fact = fact.merge(
        df_source, left_on="source_dataset", right_on="nom_source"
    )

    df_desserte = fact.rename(columns={
        "departure_time": "heure_depart",
        "arrival_time": "heure_arrivee",
        "distance_km": "distance_km",
        "duration_h": "duree_h",
        "emission_gco2e_pkm": "emission_gco2e_pkm",
        "total_emission_gco2e": "emission_totale_gco2e",
        "frequency_per_week": "frequence_semaine",
    })[[
        "trip_id", "id_ligne", "id_gare_origine", "id_gare_destination",
        "service_type", "heure_depart", "heure_arrivee", "distance_km",
        "duree_h", "emission_gco2e_pkm", "emission_totale_gco2e",
        "frequence_semaine", "traction", "id_source",
    ]]

    return {
        "pays": df_pays,
        "operateur": df_operateur[["id_operateur", "nom_operateur"]],
        "gare": df_gare,
        "ligne": df_ligne,
        "source_donnees": df_source,
        "desserte": df_desserte,
    }


if __name__ == "__main__":
    from pathlib import Path
    from extract_gtfs import extract_gtfs
    from extract_backontrack import extract_back_on_track

    base_dir = Path(__file__).resolve().parent.parent
    raw_gtfs = extract_gtfs(base_dir / "data" / "raw" / "Export_OpenData_SNCF_GTFS_NewTripId.zip")
    raw_bot = extract_back_on_track(base_dir / "data" / "raw" / "back-on-track")
    raw = pd.concat([raw_gtfs, raw_bot], ignore_index=True)

    clean, report = clean_raw(raw)
    print("Quality report:", report.as_dict())

    tables = build_star_schema(clean)
    for name, tdf in tables.items():
        print(f"\n--- {name} ({len(tdf)} rows) ---")
        print(tdf.head(3))