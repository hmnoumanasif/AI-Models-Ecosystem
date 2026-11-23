"""The ETL pipeline. Run it from the project folder with:

    python -m src.pipeline                      (all datasets: live API, fall back to saved data)
    python -m src.pipeline --offline            (saved data only)
    python -m src.pipeline image_t2i video_t2v  (only these datasets)
"""
import json
import logging
import sys
import time
from datetime import datetime, timezone

from src.config import PROCESSED_DIR, RAW_DIR, setup_logging
from src.datasets import BY_ID, DATASETS
from src.extraction.api_client import ExtractionError, fetch_dataset, load_saved_snapshot
from src.loading.database import DatabaseError, save_dataset
from src.validation.schemas import validate_records

log = logging.getLogger(__name__)


def utc_now():
    return datetime.now(timezone.utc)


def extract(dataset, use_live):
    """Step 1. Returns (payload, source_info). Never hides a fallback."""
    warning = None
    if use_live:
        try:
            payload = fetch_dataset(dataset)
            info = {"source": "live_api", "source_detail": dataset.url,
                    "data_time": utc_now().strftime("%Y-%m-%d %H:%M:%S"), "warning": None}
            return payload, info
        except ExtractionError as error:
            warning = f"Live API failed: {error} Saved data is shown instead."
            log.warning("%s: %s", dataset.id, warning)

    payload, info = load_saved_snapshot(dataset)
    info["warning"] = warning
    return payload, info


def save_file(path, text):
    """Write a file, but only warn if the disk is not writable."""
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    except OSError as error:
        log.warning("Could not write %s: %s", path, error)


def run_etl(dataset, use_live=True):
    """Run Extract -> Validate -> Transform -> Load for ONE dataset.

    Returns a dict with the DataFrame, an info dict (counts, source, timing),
    and whether saving to the database worked.
    """
    started = time.perf_counter()
    log.info("[%s] pipeline started (live API: %s)", dataset.id, use_live)

    # 1. EXTRACT
    payload, info = extract(dataset, use_live)
    records = payload["data"]
    log.info("[%s] extracted %s records from %s", dataset.id, len(records), info["source"])
    if info["source"] == "live_api":
        stamp = utc_now().strftime("%Y%m%dT%H%M%SZ")
        save_file(RAW_DIR / dataset.id / f"{stamp}.json", json.dumps(payload))

    # 2. VALIDATE (Pydantic)
    valid, rejected = validate_records(records, dataset.schema)
    log.info("[%s] validation: %s valid, %s rejected", dataset.id, len(valid), len(rejected))

    # 3. TRANSFORM (pandas)
    df = dataset.transform(valid)
    if df.empty:
        raise ValueError(f"No valid records were left for '{dataset.id}' after validation.")
    duplicates = len(valid) - len(df)
    save_file(PROCESSED_DIR / f"{dataset.id}.csv", df.to_csv(index=False))

    info.update({
        "run_at": utc_now().strftime("%Y-%m-%d %H:%M:%S"),
        "raw_count": len(records), "valid_count": len(valid),
        "rejected_count": len(rejected), "duplicate_count": duplicates,
        "loaded_count": len(df), "rejected": rejected,
    })

    # 4. LOAD (SQLite). A failure here must be visible, not hidden.
    saved, save_error = True, None
    try:
        save_dataset(dataset, df, {**info, "duration_seconds": round(time.perf_counter() - started, 2)})
    except DatabaseError as error:
        saved, save_error = False, str(error)
        log.error("[%s] database problem: %s", dataset.id, error)

    info["duration_seconds"] = round(time.perf_counter() - started, 2)
    log.info("[%s] pipeline finished in %.2f s", dataset.id, info["duration_seconds"])
    return {"dataframe": df, "info": info, "saved": saved, "save_error": save_error}


def run_all(use_live=True, only=None):
    """Run the pipeline for many datasets. Each one is isolated: if one fails,
    the others still run. Returns {dataset id: result or {"error": message}}."""
    results = {}
    for dataset in DATASETS:
        if only and dataset.id not in only:
            continue
        try:
            results[dataset.id] = run_etl(dataset, use_live)
        except Exception as error:
            log.exception("[%s] failed", dataset.id)
            results[dataset.id] = {"error": str(error)}
    return results


def main():
    setup_logging()
    names = [arg for arg in sys.argv[1:] if not arg.startswith("--")]
    unknown = [n for n in names if n not in BY_ID]
    if unknown:
        sys.exit(f"Unknown dataset(s): {unknown}. Choose from: {list(BY_ID)}")
    results = run_all(use_live="--offline" not in sys.argv, only=names or None)

    print(f"\n{'dataset':<18}{'source':<18}{'rows':>6}  {'rejected':>8}  saved  note")
    for dataset_id, result in results.items():
        if "error" in result:
            print(f"{dataset_id:<18}{'FAILED':<18}{'':>6}  {'':>8}  {'':<5}  {result['error']}")
            continue
        info = result["info"]
        print(f"{dataset_id:<18}{info['source']:<18}{info['loaded_count']:>6}  {info['rejected_count']:>8}  "
              f"{str(result['saved']):<5}  {info.get('warning') or ''}")


if __name__ == "__main__":
    main()
