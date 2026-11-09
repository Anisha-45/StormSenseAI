"""NOAA damage strings such as '10.00K', '1.5M', '2B' converted to US dollars."""
import math
import re

import pandas as pd

_MULT = {"K": 1e3, "M": 1e6, "B": 1e9}
_PATTERN = re.compile(r"^\s*(\d*\.?\d+)\s*([KkMmBb]?)\s*$")


def parse_damage(value) -> float:
    """Return dollars as float. Missing/blank returns NaN. Unparseable text raises ValueError so the
    caller can log it instead of silently dropping the record."""
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return float("nan")
    text = str(value).strip()
    if text == "" or text.lower() == "nan":
        return float("nan")
    m = _PATTERN.match(text)
    if not m:
        raise ValueError(f"Unparseable damage value: {value!r}")
    number, suffix = m.groups()
    return float(number) * _MULT.get(suffix.upper(), 1.0)


def parse_damage_series(series: pd.Series) -> tuple[pd.Series, pd.Series]:
    """Vectorised-ish conversion. Returns (dollars, bad_values). bad_values holds the raw strings that
    could not be parsed (their dollars are NaN) so they can be written to the issues log."""
    out = []
    bad_idx = []
    for idx, v in series.items():
        try:
            out.append(parse_damage(v))
        except ValueError:
            out.append(float("nan"))
            bad_idx.append(idx)
    return pd.Series(out, index=series.index, dtype="float64"), series.loc[bad_idx]
