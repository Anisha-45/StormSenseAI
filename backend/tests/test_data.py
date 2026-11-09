import math

import pandas as pd
import pytest

from app.services import processing, quality
from app.services.damage import parse_damage, parse_damage_series


# ---- damage suffix conversion -------------------------------------------------------------
@pytest.mark.parametrize("raw,expected", [("10.00K", 10_000), ("1.5M", 1_500_000), ("2B", 2e9), ("0.00K", 0), ("500", 500), ("  7k ", 7000), (".5M", 500_000)])
def test_damage_suffixes(raw, expected):
    assert parse_damage(raw) == pytest.approx(expected)


@pytest.mark.parametrize("raw", [None, float("nan"), "", "nan"])
def test_damage_missing_is_nan(raw):
    assert math.isnan(parse_damage(raw))


def test_damage_garbage_raises_not_silently_zero():
    with pytest.raises(ValueError):
        parse_damage("abc")


def test_damage_series_reports_bad_values():
    out, bad = parse_damage_series(pd.Series(["1K", "xyz", None]))
    assert out.iloc[0] == 1000 and math.isnan(out.iloc[1]) and len(bad) == 1


# ---- quality ------------------------------------------------------------------------------
def test_quality_detects_problems():
    df = pd.DataFrame({"EVENT_ID": [1, 1, 2], "BEGIN_DATE_TIME": ["01-JAN-20 00:00:00", "garbage", None], "BEGIN_LAT": [10.0, 95.0, None],
                       "BEGIN_LON": [10.0, 10.0, None], "DEATHS_DIRECT": [0, -1, 2], "EVENT_TYPE": ["Hail", "hail ", "Flood"]})
    r = quality.profile_dataframe(df, "t")
    assert r["rows"] == 3 and r["identifier"]["duplicated_ids"] == 1
    assert r["date_checks"]["BEGIN_DATE_TIME"]["invalid"] == 1
    assert r["coordinate_checks"]["BEGIN_LAT/BEGIN_LON"]["invalid"] == 1
    assert r["numeric_checks"]["DEATHS_DIRECT"]["invalid"] == 1
    assert "hail" in r["event_types"]["inconsistent_variants"]
    assert 0 <= r["quality_score"] <= 100 and "NOAA" in r["score_note"]


def test_quality_duplicate_rows_counted():
    df = pd.DataFrame({"a": [1, 1, 2], "b": ["x", "x", "y"]})
    assert quality.profile_dataframe(df)["duplicate_rows"] == 1


def test_quality_empty_dataset():
    r = quality.profile_dataframe(pd.DataFrame())
    assert r["empty"] and r["quality_score"] == 0.0


def test_quality_unevaluated_components_flagged():
    r = quality.profile_dataframe(pd.DataFrame({"a": [1, 2], "b": [3, 4]}))
    assert set(r["not_evaluated"]) == {"date_validity", "coordinate_validity", "numeric_validity"}


def test_upload_validation_rejects_bad_shapes():
    assert quality.validate_upload_frame(pd.DataFrame({"a": []}))


# ---- processing on tiny NOAA-shaped fixtures ----------------------------------------------
@pytest.fixture()
def processed(small_raw, tmp_path):
    m = processing.process(small_raw, tmp_path)
    return m, processing.load_events(out_dir=tmp_path)


def test_join_does_not_multiply_events(processed):
    m, ev = processed
    assert len(ev) == 4 and ev["event_id"].is_unique  # 5 detail rows, one duplicate id removed
    assert m["unique_events"] == 4


def test_duplicate_event_id_logged_not_silent(processed):
    m, _ = processed
    assert any("duplicate EVENT_ID" in i["issue"] for i in m["issues"])


def test_one_to_many_locations_aggregated(processed):
    _, ev = processed
    row = ev[ev.event_id == 101].iloc[0]
    assert row.loc_row_count == 2 and row.loc_mean_lat == pytest.approx(31.25)


def test_orphan_rows_logged_and_not_joined(processed):
    m, ev = processed
    issues = {i["issue"]: i["count"] for i in m["issues"]}
    assert issues["rows whose EVENT_ID is not in the details file (not joined)"] >= 1
    assert 999 not in set(ev.event_id) and 888 not in set(ev.event_id)


def test_damage_converted_and_originals_preserved(processed):
    _, ev = processed
    r = ev[ev.event_id == 101].iloc[0]
    assert r.property_damage_usd == 1_500_000 and r.crop_damage_usd == 2e9
    assert r.DAMAGE_PROPERTY == "1.5M" and r.DAMAGE_CROPS == "2B"


def test_missing_damage_stays_nan_with_flag(processed):
    _, ev = processed
    r = ev[ev.event_id == 102].iloc[0]
    assert math.isnan(r.property_damage_usd) and not r.property_damage_reported


def test_unparseable_date_and_damage_are_logged_not_dropped(processed):
    m, ev = processed
    issues = [i["issue"] for i in m["issues"]]
    assert any("unparseable BEGIN_DATE_TIME" in i for i in issues) and any("unparseable DAMAGE_PROPERTY" in i for i in issues)
    r = ev[ev.event_id == 103].iloc[0]          # the record is KEPT, with NaN derived values
    assert pd.isna(r.property_damage_usd) and pd.isna(r.duration_hours) and r.DAMAGE_PROPERTY == "abc"


def test_missing_coordinates_kept_and_flagged(processed):
    m, ev = processed
    assert not ev[ev.event_id == 102].iloc[0].has_coordinates and len(ev) == 4
    assert any("without coordinates" in i["issue"] for i in m["issues"])


def test_date_features_and_duration(processed):
    _, ev = processed
    r = ev[ev.event_id == 101].iloc[0]
    assert r.year == 2020 and r.month == 6 and r.season == "Summer" and r.duration_hours == pytest.approx(2.0)


def test_fatality_aggregation(processed):
    _, ev = processed
    r = ev[ev.event_id == 101].iloc[0]
    assert r.fatality_rows == 1 and r.fatality_mean_age == 45 and r.deaths_total == 1


def test_impact_totals(processed):
    _, ev = processed
    r = ev[ev.event_id == 101].iloc[0]
    assert r.injuries_total == 3 and r.has_impact


def test_manifest_records_config_and_versions(processed):
    m, _ = processed
    assert m["dataset_version"] and m["config"]["name"] == "default" and "year_counts" in m


def test_empty_details_file_is_handled(tmp_path, small_raw):
    import shutil
    d = tmp_path / "raw"
    d.mkdir()
    for f in small_raw.iterdir():
        shutil.copy(f, d / f.name)
    header = (d / "StormEvents_details_2010_2020.csv").read_text().splitlines()[0]
    (d / "StormEvents_details_2010_2020.csv").write_text(header + "\n")
    m = processing.process(d, tmp_path / "out")
    assert m["unique_events"] == 0


# ---- the real project data ----------------------------------------------------------------
def test_real_data_counts(real_events):
    assert len(real_events) == 32671 and real_events["event_id"].is_unique
    assert int(real_events["has_coordinates"].sum()) == 25251
    assert set(real_events["year"].unique()) == {2017, 2018, 2019, 2020}


def test_real_data_no_negative_durations(real_events):
    assert (real_events["duration_hours"].dropna() >= 0).all()
