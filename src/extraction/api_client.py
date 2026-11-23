"""EXTRACT step: download a dataset from its API (or read a saved copy of it)."""
import json
import logging
import time
from datetime import datetime
from math import ceil

import requests

from src.config import (
    MAX_ATTEMPTS,
    MAX_PAGES,
    MAX_RETRY_WAIT,
    RAW_DIR,
    REQUEST_TIMEOUT,
    RETRY_STATUS_CODES,
    SAMPLE_DIR,
    get_api_key,
)

log = logging.getLogger(__name__)


class ExtractionError(Exception):
    """Raised when we cannot get usable data."""


class MissingKeyError(ExtractionError):
    """Raised when a dataset needs an API key and none is configured."""


def check_payload(payload):
    """Every API answer must be an object that has a list called 'data'."""
    if not isinstance(payload, dict) or not isinstance(payload.get("data"), list):
        raise ExtractionError("Unexpected response: expected an object with a 'data' list.")
    return payload


def build_headers(dataset):
    """Add the API key header if the dataset uses a key.
    The key itself is never logged or shown."""
    headers = {"Accept": "application/json"}
    key = get_api_key(dataset.key_env)
    if key:
        headers[dataset.key_header] = f"{dataset.key_prefix}{key}"
    elif dataset.key_required:
        raise MissingKeyError(f"No API key found. Set {dataset.key_env} in your .env file.")
    return headers


def retry_after_seconds(response):
    """How long the server asks us to wait (the Retry-After header), or None."""
    try:
        return float(response.headers.get("Retry-After"))
    except (TypeError, ValueError):
        return None


def fetch_json(url, headers, params=None):
    """Download one JSON answer.

    Temporary problems (no internet, timeout, HTTP 429/5xx) are retried and we
    wait 1 s, then 2 s between attempts (exponential backoff).
    Permanent problems (HTTP 401, 404, broken JSON ...) are NOT retried.
    If the server says "wait longer than a few seconds" (daily limit reached),
    we stop at once instead of wasting requests.
    """
    last_problem = ""
    for attempt in range(1, MAX_ATTEMPTS + 1):
        wait = 2 ** (attempt - 1)               # 1 s, then 2 s
        try:
            response = requests.get(url, headers=headers, params=params, timeout=REQUEST_TIMEOUT)
        except (requests.ConnectionError, requests.Timeout) as error:
            last_problem = f"network problem ({type(error).__name__})"
        else:
            if response.status_code in RETRY_STATUS_CODES:
                last_problem = f"temporary server problem (HTTP {response.status_code})"
                asked = retry_after_seconds(response) if response.status_code == 429 else None
                if asked is not None and asked > MAX_RETRY_WAIT:
                    raise ExtractionError(
                        f"Request limit reached. Try again in about {ceil(asked / 60)} minutes.")
                if asked is not None:
                    wait = asked
            elif response.status_code in (401, 403):
                raise ExtractionError(f"The API key was rejected (HTTP {response.status_code}).")
            elif response.status_code != 200:
                raise ExtractionError(f"API returned HTTP {response.status_code}.")
            else:
                try:
                    return response.json()
                except ValueError:
                    raise ExtractionError("API response was not valid JSON.")

        log.warning("API attempt %s of %s failed: %s", attempt, MAX_ATTEMPTS, last_problem)
        if attempt < MAX_ATTEMPTS:
            time.sleep(wait)

    raise ExtractionError(f"Could not reach the API after {MAX_ATTEMPTS} attempts: {last_problem}.")


def fetch_dataset(dataset):
    """Download a whole dataset. Paginated APIs are read page by page."""
    headers = build_headers(dataset)
    if not dataset.paged:
        return check_payload(fetch_json(dataset.url, headers))

    records = []
    for page in range(1, MAX_PAGES + 1):
        payload = check_payload(fetch_json(dataset.url, headers, {"page": page}))
        records.extend(payload["data"])
        if not (payload.get("pagination") or {}).get("has_more"):
            break
    return {"data": records}


# --------------------------------------------------------- saved snapshots
def read_json_file(path):
    """Read one saved JSON file and check its structure."""
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        raise ExtractionError(f"Cannot read {path.name}: {error}")
    return check_payload(payload)


def snapshot_time(path):
    """Raw files are named YYYYMMDDTHHMMSSZ.json -> '2026-10-30 06:14:20'."""
    try:
        return datetime.strptime(path.stem, "%Y%m%dT%H%M%SZ").strftime("%Y-%m-%d %H:%M:%S")
    except ValueError:
        return None


def load_saved_snapshot(dataset):
    """Offline data. Newest real download first, synthetic sample as last resort.

    Returns (payload, info) where info says exactly where the data came from.
    """
    real_files = sorted((RAW_DIR / dataset.id).glob("*.json"))
    if real_files:
        path = real_files[-1]
        info = {"source": "saved_snapshot", "source_detail": path.name, "data_time": snapshot_time(path)}
        return read_json_file(path), info

    sample = SAMPLE_DIR / f"{dataset.id}.json"
    if sample.exists():
        info = {"source": "synthetic_sample", "source_detail": sample.name, "data_time": None}
        return read_json_file(sample), info

    raise ExtractionError(f"No saved snapshot is available for '{dataset.id}'.")
