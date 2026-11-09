"""Central configuration. Every path can be overridden with an environment variable."""
import os
from pathlib import Path

ROOT = Path(os.environ.get("STORMSENSE_ROOT", Path(__file__).resolve().parents[3]))
RAW_DIR = Path(os.environ.get("STORMSENSE_RAW_DIR", ROOT / "data" / "raw"))
PROCESSED_DIR = Path(os.environ.get("STORMSENSE_PROCESSED_DIR", ROOT / "data" / "processed"))
UPLOAD_DIR = Path(os.environ.get("STORMSENSE_UPLOAD_DIR", ROOT / "data" / "uploads"))
DB_PATH = Path(os.environ.get("STORMSENSE_DB", ROOT / "data" / "stormsense.db"))

DETAILS_FILE = "StormEvents_details_2010_2020.csv"
LOCATIONS_FILE = "StormEvents_locations_2010_2020.csv"
FATALITIES_FILE = "StormEvents_fatalities_2010_2020.csv"

# Secrets must come from the environment in production. The fallback is for local development only.
JWT_SECRET = os.environ.get("STORMSENSE_JWT_SECRET", "dev-only-secret-change-me-in-production-0123456789")
JWT_EXPIRE_MINUTES = int(os.environ.get("STORMSENSE_JWT_EXPIRE_MINUTES", "480"))

MAX_UPLOAD_MB = int(os.environ.get("STORMSENSE_MAX_UPLOAD_MB", "100"))
MAX_PHOTO_MB = int(os.environ.get("STORMSENSE_MAX_PHOTO_MB", "5"))

# Agglomerative clustering stores an n x n distance structure. 15k rows is about 0.9 GB of
# condensed distances, which is a safe ceiling on a 16 GB laptop.
MAX_HIERARCHICAL_ROWS = int(os.environ.get("STORMSENSE_MAX_HIER_ROWS", "15000"))
DEFAULT_SEED = 42

NWS_BASE = os.environ.get("STORMSENSE_NWS_BASE", "https://api.weather.gov")
OSRM_BASE = os.environ.get("STORMSENSE_OSRM_BASE", "https://router.project-osrm.org")
HTTP_USER_AGENT = os.environ.get("STORMSENSE_USER_AGENT", "StormSenseAI/1.0 (contact: set STORMSENSE_USER_AGENT)")
HTTP_TIMEOUT = float(os.environ.get("STORMSENSE_HTTP_TIMEOUT", "10"))

for _d in (PROCESSED_DIR, UPLOAD_DIR):
    _d.mkdir(parents=True, exist_ok=True)
