"""Settings used by the whole project (paths, retry rules, API keys)."""
import logging
import os
from pathlib import Path

from dotenv import load_dotenv

# The project folder (the folder that contains app.py).
ROOT = Path(__file__).resolve().parents[1]

# Read the optional .env file. It holds the API keys and is never uploaded to GitHub.
load_dotenv(ROOT / ".env")

# Data folders
RAW_DIR = ROOT / "data" / "raw"              # raw JSON of every live download (one folder per dataset)
SAMPLE_DIR = ROOT / "data" / "sample"        # small SYNTHETIC files, used only as a last resort
PROCESSED_DIR = ROOT / "data" / "processed"  # cleaned CSV files written by the pipeline
DEFAULT_DB_PATH = ROOT / "data" / "ai_intelligence.db"

# API settings
REQUEST_TIMEOUT = 15          # seconds to wait for the server
MAX_ATTEMPTS = 3              # how many times we try an API
MAX_PAGES = 20                # safety limit for paginated APIs
MAX_RETRY_WAIT = 30           # never wait longer than this (seconds) for a "Retry-After" request
RETRY_STATUS_CODES = {429, 500, 502, 503, 504}   # temporary errors worth retrying


def get_api_key(env_name):
    """Read an API key from the environment (.env file or Streamlit secrets).
    Returns None if it is not set. Never print or log the key."""
    value = os.getenv(env_name) if env_name else None
    return value.strip() if value and value.strip() else None


def setup_logging():
    """Print log messages with time and level. Safe to call many times."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )
