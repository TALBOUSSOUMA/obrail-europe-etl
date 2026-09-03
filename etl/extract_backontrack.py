"""
Real-data extractor for the Back-on-Track Open Night Train Database
(https://github.com/Back-on-Track-eu/night-train-data).

This is what turns the project from "one French operator" into a genuine
pan-European comparison: it covers ~30 agencies (OBB Nightjet, European
Sleeper, Trenitalia, CFR, CD, GWR Caledonian Sleeper...) and is, by
construction, entirely night services - it complements the SNCF GTFS
extractor, which is mostly Jour.

Same output contract as extract_gtfs.py: a flat DataFrame with the exact
same columns as data/raw/dessertes_raw.csv, so transform.py needs no
per-source logic.

Methodological choices worth defending in the soutenance:

- service_type is always "Nuit": by construction, every trip in this
  database is a night train (that is the database's whole purpose) -
  no heuristic needed, it is a property of the source itself.
- origin/destination stations are looked up directly in stops.json,
  which gives an authoritative stop_country per station - no manual
  country-guessing list needed here (unlike the SNCF extractor).
- frequency_per_week is parsed from a free-text field (e.g. "Daily",
  "Tue, Thu, Sun", "2-3 times per week") with a small parser. Free-text
  frequency is a real data-quality issue this source has, and it is
  handled the same way as elsewhere in this pipeline: parse what can be
  parsed, leave the rest as NULL rather than guessing.
"""

import json
import re
from pathlib import Path

import pandas as pd

from geo_utils import haversine_km

DAY_TOKENS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]


def _parse_frequency(text: str):
    if not text:
        return None
    t = text.lower()
    if "daily" in t:
        if "except" in t:
            excepted = sum(1 for d in DAY_TOKENS if d in t.split("except", 1)[1])
            return max(7 - excepted, 1)
        return 7
    if "every 2nd day" in t:
        return 3.5
    m = re.search(r"(\d+)\s*-\s*(\d+)\s*times per week", t)
    if m:
        return (int(m.group(1)) + int(m.group(2))) / 2
    day_count = sum(1 for d in DAY_TOKENS if d in t)
    return float(day_count) if day_count else None


def _extract_hhmm(iso_ts: str):
    """Back-on-Track stores times as ISO datetimes on a dummy date
    ('1899-12-30T19:28:00.000Z'); only the time-of-day is meaningful."""
    if not iso_ts:
        return None
    return iso_ts[11:16]


def _duration_hours(dep_hhmm: str, arr_hhmm: str) -> float:
    dep_h, dep_m = int(dep_hhmm[:2]), int(dep_hhmm[3:5])
    arr_h, arr_m = int(arr_hhmm[:2]), int(arr_hhmm[3:5])
    dep_total = dep_h * 60 + dep_m
    arr_total = arr_h * 60 + arr_m
    if arr_total <= dep_total:  # crosses midnight, as almost every night train does
        arr_total += 24 * 60
    return round((arr_total - dep_total) / 60, 2)


def extract_back_on_track(data_dir: Path) -> pd.DataFrame:
    with open(data_dir / "agencies.json", encoding="utf-8") as f:
        agencies = json.load(f)
    with open(data_dir / "trips.json", encoding="utf-8") as f:
        trips = json.load(f)
    with open(data_dir / "stops.json", encoding="utf-8") as f:
        stops = json.load(f)

    rows = []
    for trip_id, t in trips.items():
        if t.get("is_active") != "Y":
            continue  # skip discontinued/announced-only services

        origin_name = t.get("trip_origin")
        dest_name = t.get("trip_headsign")
        if not origin_name or not dest_name or origin_name not in stops or dest_name not in stops:
            continue  # can't place this trip without both endpoints known

        origin_stop = stops[origin_name]
        dest_stop = stops[dest_name]

        dep_hhmm = _extract_hhmm(t.get("origin_departure_time"))
        arr_hhmm = _extract_hhmm(t.get("destination_arrival_time"))
        if not dep_hhmm or not arr_hhmm:
            continue

        agency_name = agencies.get(t.get("agency_id"), {}).get("agency_name", t.get("agency_id"))
        distance_km = round(
            haversine_km(
                origin_stop["stop_lat"], origin_stop["stop_lon"],
                dest_stop["stop_lat"], dest_stop["stop_lon"],
            ), 1
        )

        rows.append({
            "trip_id": f"BOT_{trip_id}",
            "agency_name": agency_name,
            "route_name": f"{origin_name} - {dest_name}",
            "train_type": "Train de nuit international",
            "service_type": "Nuit",  # by construction of this source
            "origin_stop_name": origin_name,
            "origin_country": origin_stop.get("stop_country"),
            "destination_stop_name": dest_name,
            "destination_country": dest_stop.get("stop_country"),
            "departure_time": dep_hhmm,
            "arrival_time": arr_hhmm,
            "distance_km": distance_km,
            "duration_h": _duration_hours(dep_hhmm, arr_hhmm),
            "emission_gco2e_pkm": 4.0,  # approximation: reuses the SNCF long-distance
            # electric factor in the absence of a published per-operator figure -
            # documented limitation, see technical report.
            "total_emission_gco2e": round(distance_km * 4.0, 2),
            "frequency_per_week": _parse_frequency(t.get("service_id", "")),
            "source_dataset": "Back-on-Track Open Night Train Database",
            "traction": pd.NA,
        })

    columns = [
        "trip_id", "agency_name", "route_name", "train_type", "service_type",
        "origin_stop_name", "origin_country", "destination_stop_name", "destination_country",
        "departure_time", "arrival_time", "distance_km", "duration_h",
        "emission_gco2e_pkm", "total_emission_gco2e", "frequency_per_week",
        "source_dataset", "traction",
    ]
    return pd.DataFrame(rows, columns=columns)


if __name__ == "__main__":
    base_dir = Path(__file__).resolve().parent.parent
    data_dir = base_dir / "data" / "raw" / "back-on-track"
    result = extract_back_on_track(data_dir)
    print(f"Extracted {len(result)} real night-train trips")
    print(result["origin_country"].value_counts())
    print(result[["agency_name", "route_name", "origin_country", "destination_country"]].head(15))