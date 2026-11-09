"""Table storage. Uses Parquet when pyarrow is installed (the intended format) and falls back to
gzip CSV so the project still runs where pyarrow is missing. Callers never need to care."""
from pathlib import Path

import pandas as pd

try:  # pragma: no cover - depends on the environment
    import pyarrow  # noqa: F401
    HAS_PARQUET = True
except Exception:  # pragma: no cover
    HAS_PARQUET = False


def table_path(directory: Path, name: str) -> Path:
    return directory / (f"{name}.parquet" if HAS_PARQUET else f"{name}.csv.gz")


def find_table(directory: Path, name: str) -> Path | None:
    """Return whichever stored form exists, preferring Parquet."""
    for ext in ("parquet", "csv.gz"):
        p = directory / f"{name}.{ext}"
        if p.exists():
            return p
    return None


def save_table(df: pd.DataFrame, directory: Path, name: str) -> Path:
    path = table_path(directory, name)
    if HAS_PARQUET:
        df.to_parquet(path, index=False)
    else:
        df.to_csv(path, index=False, compression="gzip")
    return path


def load_table(directory: Path, name: str, columns: list[str] | None = None) -> pd.DataFrame:
    path = find_table(directory, name)
    if path is None:
        raise FileNotFoundError(f"Table '{name}' not found in {directory}. Run the processing pipeline first.")
    if path.suffix == ".parquet":
        return pd.read_parquet(path, columns=columns)
    return pd.read_csv(path, usecols=columns, low_memory=False, compression="gzip")
