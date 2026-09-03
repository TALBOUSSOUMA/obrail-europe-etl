"""
Real-data extractor for the SNCF GTFS export.

Design goal: output a flat DataFrame with EXACTLY the same columns as
data/raw/dessertes_raw.csv, so transform.clean_raw() and
transform.build_star_schema() require zero changes. Only this file
(and, symmetrically, a future extract_<other_source>.py) needs to know
about the source's native format.

Key decisions, each documented because they will come up in the
soutenance:

- Scope: only route_type == '2' (rail) trips are kept. GTFS also lists
  a handful of substitute bus/tram services (route_type 0 and 3) which
  are not "train" services and are out of scope for this study.
- service_type (Jour/Nuit): GTFS represents a trip that runs past
  midnight by giving its later stop_times an hour >= 24 (e.g. 33:38:00
  for 09:38 the next day), because all times in a trip are anchored to
  a single "service day". We reuse that native signal directly instead
  of guessing from clock hours - it is the ground truth already encoded
  by SNCF (a night Intercites trip's stops are even literally named
  "...INTERCITES de nuit...", which we can spot-check against).
- train_type: SNCF encodes the commercial brand as a short code inside
  trip_id (TER, OUI=TGV inOui, OGO=OuiGo, CTE/IC=Intercites,
  ICN=Intercites de nuit, LYR=TGV Lyria, ICE=international ICE...).
  This is undocumented in the GTFS spec itself but consistent across
  the whole export, so we decode it with a lookup table.
- distance_km: not provided by GTFS; computed with the haversine
  formula between the first and last stop's coordinates. This gives
  the great-circle distance, not the real track distance (a documented
  simplification/limitation).
- emission_gco2e_pkm: not provided by GTFS; applied from a published,
  cited factor (SNCF Voyageurs / ADEME Base Empreinte 2024): 4 gCO2e/pkm
  for TGV inOui, OuiGo and Intercites circulating in France, 34 gCO2e/pkm
  for TER. International services (Lyria, ICE) reuse the domestic
  long-distance factor as an approximation - a limitation to state
  explicitly in the technical report.
- origin_country / destination_country: SNCF's GTFS export is
  France-centric but includes a handful of genuine cross-border
  terminus stations. Rather than a full geocoding pipeline (out of
  scope here), we tag the known foreign termini by name and default
  everything else to FR - documented as a limitation/improvement path.
"""

import zipfile
from pathlib import Path

import pandas as pd

from geo_utils import haversine_km

BRAND_TO_TRAIN_TYPE = {
    "TER": "Regional",
    "OUI": "TGV inOui",
    "OGO": "OuiGo",
    "CTE": "Corail Intercites",
    "IC": "Intercites",
    "ICN": "Intercites de nuit",
    "ICE": "ICE (international)",
    "LYR": "TGV Lyria (international)",
    "CRE": "Autre",
    "TT": "Autre",
    "TRN": "Train",
    "NAV": "Navette",
}

# gCO2e per passenger-km. Source: SNCF Voyageurs, sncf-connect.com/train/eco-responsable,
# itself based on ADEME Base Empreinte 2024 + Carbone 4 methodology study (2021).
EMISSION_FACTOR_GCO2E_PKM = {
    "Regional": 34.0,
    "TGV inOui": 4.0,
    "OuiGo": 4.0,
    "Corail Intercites": 4.0,
    "Intercites": 4.0,
    "Intercites de nuit": 4.0,
    "ICE (international)": 4.0,
    "TGV Lyria (international)": 4.0,
    "Autre": 34.0,
    "Train": 34.0,
    "Navette": 34.0,
}

# Manually curated, non-exhaustive list of the foreign termini present in
# the SNCF export (identified by inspecting stops.txt). Everything else
# defaults to France.
FOREIGN_STATIONS = {
    "FIGUERES-VILAFANT": "ES", "Barcelone-Sants": "ES",
    "Francfort sur le Main": "DE", "Karlsruhe Hbf": "DE", "Stuttgart Hbf": "DE",
    "Kehl": "DE",
    "Luxembourg": "LU", "Luxembourg secteur Hollerich": "LU", "Luxembourg Gare": "LU",
    "Turin Porta Susa": "IT", "TORINO PORTA NUOVA": "IT", "TORINO LINGOTTO": "IT",
    "MILANO PORTA GARIBALDI": "IT",
    "Basel SBB": "CH", "La Plaine (Suisse)": "CH", "Geneve-Aeroport": "CH",
    "Lausanne": "CH", "Bâle Saint-Jean": "CH",
    "Bruxelles Midi": "BE",
}


def _country_of(stop_name: str) -> str:
    return FOREIGN_STATIONS.get(stop_name, "FR")


def _brand_code(trip_id: str) -> str:
    for part in trip_id.split(":"):
        if part.isalpha() and part.isupper() and len(part) in (2, 3):
            return part
    return "TRN"


def _haversine_km(lat1, lon1, lat2, lon2) -> float:
    return haversine_km(lat1, lon1, lat2, lon2)


def extract_gtfs(zip_path: Path) -> pd.DataFrame:
    z = zipfile.ZipFile(zip_path)

    agency = pd.read_csv(z.open("agency.txt"))
    routes = pd.read_csv(z.open("routes.txt"))
    trips = pd.read_csv(z.open("trips.txt"), dtype={"service_id": str})
    stops = pd.read_csv(z.open("stops.txt"))
    stop_times = pd.read_csv(z.open("stop_times.txt"), dtype={"trip_id": str})
    calendar_dates = pd.read_csv(z.open("calendar_dates.txt"), dtype={"service_id": str})

    # ---- 1. Keep rail trips only (route_type == 2) -----------------------
    rail_routes = routes[routes["route_type"] == 2]
    trips = trips.merge(rail_routes[["route_id", "route_long_name", "agency_id"]], on="route_id")
    trips = trips.merge(agency[["agency_id", "agency_name"]], on="agency_id")
    trips["agency_name"] = "SNCF"  # consolidate the 4 legal SNCF entities into one operator

    # ---- 2. First/last stop_time per trip (O-D model) --------------------
    stop_times = stop_times[stop_times["trip_id"].isin(trips["trip_id"])]
    stop_times = stop_times.merge(
        stops[["stop_id", "stop_name", "stop_lat", "stop_lon"]], on="stop_id"
    )
    stop_times["hour"] = stop_times["arrival_time"].str.slice(0, 2).astype(int)

    first_stops = stop_times.sort_values("stop_sequence").groupby("trip_id").first()
    last_stops = stop_times.sort_values("stop_sequence").groupby("trip_id").last()

    od = first_stops[["stop_name", "stop_lat", "stop_lon", "departure_time"]].join(
        last_stops[["stop_name", "stop_lat", "stop_lon", "arrival_time", "hour"]],
        lsuffix="_origin", rsuffix="_destination",
    )
    # drop single-stop trips (no real origin/destination pair, likely data noise)
    od = od[od["stop_name_origin"] != od["stop_name_destination"]]

    # ---- 3. Frequency per week from calendar_dates.txt --------------------
    added = calendar_dates[calendar_dates["exception_type"] == 1].copy()
    added["date"] = pd.to_datetime(added["date"], format="%Y%m%d")
    freq = added.groupby("service_id")["date"].agg(["count", "min", "max"])
    freq["span_weeks"] = ((freq["max"] - freq["min"]).dt.days / 7).clip(lower=1)
    freq["frequency_per_week"] = (freq["count"] / freq["span_weeks"]).round().clip(upper=7).astype(int)

    # ---- 4. Assemble the flat table matching the bootstrap CSV schema -----
    df = trips[["trip_id", "agency_name", "route_long_name", "service_id"]].merge(
        od, left_on="trip_id", right_index=True
    )
    df = df.merge(freq[["frequency_per_week"]], left_on="service_id", right_index=True, how="left")
    df["frequency_per_week"] = df["frequency_per_week"].fillna(1)

    df["train_type"] = df["trip_id"].map(_brand_code).map(BRAND_TO_TRAIN_TYPE)
    df["service_type"] = df["hour"].apply(lambda h: "Nuit" if h >= 24 else "Jour")
    df["origin_country"] = df["stop_name_origin"].map(_country_of)
    df["destination_country"] = df["stop_name_destination"].map(_country_of)
    df["distance_km"] = df.apply(
        lambda r: round(_haversine_km(
            r["stop_lat_origin"], r["stop_lon_origin"],
            r["stop_lat_destination"], r["stop_lon_destination"]
        ), 1), axis=1
    )

    dep_h, dep_m = df["departure_time"].str.slice(0, 2).astype(int), df["departure_time"].str.slice(3, 5).astype(int)
    df["duration_h"] = round((df["hour"] * 60 + df["arrival_time"].str.slice(3, 5).astype(int) - (dep_h * 60 + dep_m)) / 60, 2)

    df["emission_gco2e_pkm"] = df["train_type"].map(EMISSION_FACTOR_GCO2E_PKM)
    df["total_emission_gco2e"] = round(df["distance_km"] * df["emission_gco2e_pkm"], 2)

    df["departure_time"] = df["departure_time"].str.slice(0, 5)
    df["arrival_time"] = df["arrival_time"].str.slice(0, 5)

    df["source_dataset"] = "SNCF GTFS (transport.data.gouv.fr)"
    df["traction"] = pd.NA  # not provided by GTFS - left NULL rather than guessed

    df = df.rename(columns={
        "route_long_name": "route_name",
        "stop_name_origin": "origin_stop_name",
        "stop_name_destination": "destination_stop_name",
    })

    columns = [
        "trip_id", "agency_name", "route_name", "train_type", "service_type",
        "origin_stop_name", "origin_country", "destination_stop_name", "destination_country",
        "departure_time", "arrival_time", "distance_km", "duration_h",
        "emission_gco2e_pkm", "total_emission_gco2e", "frequency_per_week",
        "source_dataset", "traction",
    ]
    return df[columns].reset_index(drop=True)


if __name__ == "__main__":
    base_dir = Path(__file__).resolve().parent.parent
    zip_path = base_dir / "data" / "raw" / "Export_OpenData_SNCF_GTFS_NewTripId.zip"
    result = extract_gtfs(zip_path)
    print(f"Extracted {len(result)} real trips")
    print(result["train_type"].value_counts())
    print(result["service_type"].value_counts())
    print(result[result["destination_country"] != "FR"][
        ["route_name", "destination_stop_name", "destination_country"]
    ].drop_duplicates().head(20))
    result.to_csv(base_dir / "data" / "interim" / "dessertes_gtfs.csv", index=False)
    print("Saved to data/interim/dessertes_gtfs.csv")
