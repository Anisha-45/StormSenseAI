import sys
import warnings
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
warnings.filterwarnings("ignore")

from app.core import config  # noqa: E402
from app.db import database as db  # noqa: E402

REAL_RAW = config.RAW_DIR


@pytest.fixture()
def tmp_app(tmp_path, monkeypatch):
    """Isolated database + upload folders so tests never touch real application state."""
    monkeypatch.setattr(config, "DB_PATH", tmp_path / "test.db")
    monkeypatch.setattr(config, "UPLOAD_DIR", tmp_path / "uploads")
    (tmp_path / "uploads").mkdir()
    db.init_db()
    return tmp_path


@pytest.fixture()
def con(tmp_app):
    c = db.connect()
    yield c
    c.commit()
    c.close()


@pytest.fixture(scope="session")
def real_events():
    """The real processed events table (built from the project's CSVs). Skips if not processed."""
    from app.services import processing
    try:
        return processing.load_events()
    except FileNotFoundError:
        pytest.skip("Run `python -m app.cli process` first")


@pytest.fixture(scope="session")
def small_raw(tmp_path_factory):
    """Tiny NOAA-shaped raw files that exercise the tricky cases: one-to-many joins, orphans, K/M/B damage,
    missing coordinates, bad dates, duplicate event ids."""
    d = tmp_path_factory.mktemp("raw")
    det = (
        "BEGIN_YEARMONTH,BEGIN_DAY,BEGIN_TIME,END_YEARMONTH,END_DAY,END_TIME,EPISODE_ID,EVENT_ID,STATE,STATE_FIPS,YEAR,MONTH_NAME,EVENT_TYPE,CZ_TYPE,CZ_FIPS,CZ_NAME,WFO,BEGIN_DATE_TIME,CZ_TIMEZONE,END_DATE_TIME,INJURIES_DIRECT,INJURIES_INDIRECT,DEATHS_DIRECT,DEATHS_INDIRECT,DAMAGE_PROPERTY,DAMAGE_CROPS,SOURCE,MAGNITUDE,MAGNITUDE_TYPE,BEGIN_LAT,BEGIN_LON,END_LAT,END_LON\n"
        "202006,1,1200,202006,1,1300,1,100,TEXAS,48,2020,June,Hail,C,1,A,W,01-JUN-20 12:00:00,CST,01-JUN-20 13:00:00,0,0,0,0,10.00K,0.00K,Spotter,1.5,,30.0,-97.0,30.0,-97.0\n"
        "202006,2,1200,202006,2,1400,1,101,TEXAS,48,2020,June,Thunderstorm Wind,C,1,A,W,02-JUN-20 12:00:00,CST,02-JUN-20 14:00:00,2,1,1,0,1.5M,2B,Spotter,60,EG,31.0,-98.0,31.0,-98.0\n"
        "202007,3,0100,202007,4,0100,2,102,OKLAHOMA,40,2020,July,Heat,Z,2,B,W,03-JUL-20 01:00:00,CST,04-JUL-20 01:00:00,0,0,0,0,,,Official,,,,,,\n"
        "202007,5,0100,202007,5,0200,2,103,OKLAHOMA,40,2020,July,Flash Flood,C,3,C,W,not a date,CST,05-JUL-20 02:00:00,0,0,0,0,abc,0.00K,Public,,,35.0,-97.0,35.0,-97.0\n"
        "202007,5,0100,202007,5,0200,2,103,OKLAHOMA,40,2020,July,Flash Flood,C,3,C,W,05-JUL-20 01:00:00,CST,05-JUL-20 02:00:00,0,0,0,0,5K,0.00K,Public,,,35.0,-97.0,35.0,-97.0\n"
    )
    loc = (
        "YEARMONTH,EPISODE_ID,EVENT_ID,LOCATION_INDEX,RANGE,AZIMUTH,LOCATION,LATITUDE,LONGITUDE,LAT2,LON2\n"
        "202006,1,100,1,1.0,N,A,30.0,-97.0,3000,9700\n"
        "202006,1,101,1,2.0,S,B,31.0,-98.0,3100,9800\n"
        "202006,1,101,2,3.0,E,C,31.5,-98.5,3150,9850\n"
        "202006,9,999,1,1.0,N,Z,40.0,-90.0,4000,9000\n"
    )
    fat = (
        "FAT_YEARMONTH,FAT_DAY,FAT_TIME,FATALITY_ID,EVENT_ID,FATALITY_TYPE,FATALITY_DATE,FATALITY_AGE,FATALITY_SEX,FATALITY_LOCATION,EVENT_YEARMONTH\n"
        "202006,2,1200,1,101,D,02/06/2020 12:00:00,45,M,OU,202006\n"
        "202006,3,1200,2,888,D,03/06/2020 12:00:00,30,F,BF,202006\n"
    )
    (d / config.DETAILS_FILE).write_text(det)
    (d / config.LOCATIONS_FILE).write_text(loc)
    (d / config.FATALITIES_FILE).write_text(fat)
    return d
