"""
Extract step of the ETL pipeline.

Reads raw, heterogeneous source files (currently CSV; designed to be
extended to GTFS folders or JSON APIs without changing the rest of
the pipeline) and returns a single raw pandas DataFrame.
"""

from pathlib import Path
import pandas as pd


def extract_csv_sources(csv_paths: list[Path]) -> pd.DataFrame:
    """Read one or more CSV files sharing the same schema and concatenate them.

    Using a list (rather than a single path) is what makes the pipeline
    ready to aggregate several operators' exports later, as required by
    the "centraliser l'information" objective of the cahier des charges.
    """
    frames = []
    for path in csv_paths:
        df = pd.read_csv(path, dtype=str)  # read everything as string first;
        # type casting happens explicitly in the transform step so we stay
        # in control of how each column is parsed (dates, floats, etc.)
        frames.append(df)

    raw_df = pd.concat(frames, ignore_index=True)
    return raw_df


if __name__ == "__main__":
    base_dir = Path(__file__).resolve().parent.parent
    raw = extract_csv_sources([base_dir / "data" / "raw" / "dessertes_raw.csv"])
    print(f"Extracted {len(raw)} raw rows")
    print(raw.head())