"""LOAD step: store the clean tables in SQLite (a single local file).

All database code lives in this one file. If you later want a different
database, only this file has to change.

Tables
  ds_<dataset id>   the latest data of one dataset (replaced in one transaction)
  etl_runs          one row per successful pipeline run (history)

Note: on Streamlit Community Cloud the file system is temporary, so the
database can be reset when the app restarts. The app rebuilds it automatically.
"""
import json
import logging
import os
import sqlite3
import tempfile
from pathlib import Path

import pandas as pd

from src.config import DEFAULT_DB_PATH

log = logging.getLogger(__name__)

CREATE_RUNS = """
CREATE TABLE IF NOT EXISTS etl_runs (
    run_id INTEGER PRIMARY KEY AUTOINCREMENT, dataset TEXT, run_at TEXT, source TEXT,
    source_detail TEXT, data_time TEXT, raw_count INTEGER, valid_count INTEGER,
    rejected_count INTEGER, duplicate_count INTEGER, loaded_count INTEGER,
    duration_seconds REAL, warning TEXT, rejected_json TEXT
)"""

RUN_FIELDS = ["run_at", "source", "source_detail", "data_time", "raw_count", "valid_count",
              "rejected_count", "duplicate_count", "loaded_count", "duration_seconds", "warning"]


class DatabaseError(Exception):
    """Raised when the database cannot be read or written."""


def get_database_path():
    """Use AI_MODELS_DB_PATH if set, otherwise data/ai_intelligence.db.
    If that folder is read-only, use the system temp folder instead."""
    configured = os.getenv("AI_MODELS_DB_PATH")
    path = Path(configured) if configured else DEFAULT_DB_PATH
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        if os.access(path.parent, os.W_OK):
            return path
    except OSError:
        pass
    fallback = Path(tempfile.gettempdir()) / "ai_intelligence.db"
    log.warning("Cannot write to %s, using %s instead", path.parent, fallback)
    return fallback


def connect():
    """Open the database and create the history table if it does not exist yet."""
    try:
        conn = sqlite3.connect(get_database_path(), timeout=10)
        conn.execute(CREATE_RUNS)
        conn.commit()
        return conn
    except (sqlite3.Error, OSError) as error:
        raise DatabaseError(f"Cannot open the database: {error}")


def table_name(dataset):
    return f"ds_{dataset.id}"      # ids come from our own list in datasets.py


def sql_type(series):
    """Choose the SQLite column type from the pandas column type."""
    kind = series.dtype.kind
    if kind in "biu":
        return "INTEGER"
    if kind == "f":
        return "REAL"
    return "TEXT"                   # text and dates


def dataframe_to_rows(df):
    """Convert the DataFrame into plain Python tuples that SQLite accepts."""
    data = df.copy()
    for column in data.columns:
        if data[column].dtype.kind == "M":                    # dates -> text
            data[column] = data[column].dt.strftime("%Y-%m-%d %H:%M:%S")
    data = data.astype(object).where(data.notna(), None)
    return [tuple(row) for row in data.itertuples(index=False, name=None)]


def save_dataset(dataset, df, info):
    """Replace the table and add a history row - all in ONE transaction.
    If anything fails, SQLite rolls back and the old data stays untouched."""
    try:
        rows = dataframe_to_rows(df)
    except (KeyError, AttributeError, ValueError) as error:
        raise DatabaseError(f"The table has an unexpected format: {error}")

    table = table_name(dataset)
    columns = ", ".join(f'"{c}" {sql_type(df[c])}' for c in df.columns)
    names = ", ".join(f'"{c}"' for c in df.columns)
    conn = connect()
    try:
        with conn:  # commits on success, rolls back on error
            conn.execute("BEGIN")
            conn.execute(f"DROP TABLE IF EXISTS {table}")
            conn.execute(f"CREATE TABLE {table} ({columns})")
            conn.executemany(f"INSERT INTO {table} ({names}) VALUES ({', '.join('?' * len(df.columns))})", rows)
            values = [dataset.id] + [info.get(name) for name in RUN_FIELDS] + [json.dumps(info.get("rejected", [])[:200])]
            conn.execute(
                f"INSERT INTO etl_runs (dataset, {', '.join(RUN_FIELDS)}, rejected_json) "
                f"VALUES ({', '.join('?' * (len(RUN_FIELDS) + 2))})", values)
    except (sqlite3.Error, TypeError) as error:
        raise DatabaseError(f"Could not save the data (old data was kept): {error}")
    finally:
        conn.close()
    log.info("Saved %s rows to %s", len(rows), table)
    return len(rows)


def read_dataset(dataset):
    """Return (DataFrame, info of the run that created it).
    The DataFrame is empty if nothing usable has been saved yet. A table with
    old columns (from an older version of the project) also counts as empty,
    so it is rebuilt automatically."""
    empty = dataset.transform([])
    conn = connect()
    try:
        exists = conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
                              (table_name(dataset),)).fetchone()
        if not exists:
            return empty, None
        df = pd.read_sql_query(f"SELECT * FROM {table_name(dataset)}", conn)
        run = conn.execute(
            f"SELECT {', '.join(RUN_FIELDS)}, rejected_json FROM etl_runs WHERE dataset=? "
            "ORDER BY run_id DESC LIMIT 1", (dataset.id,)).fetchone()
    except sqlite3.Error as error:
        raise DatabaseError(f"Could not read the data: {error}")
    finally:
        conn.close()

    if df.empty or run is None or set(df.columns) != set(empty.columns):
        return empty, None
    for column in dataset.date_columns:
        df[column] = pd.to_datetime(df[column], utc=True, errors="coerce")
    for column in dataset.bool_columns:
        df[column] = df[column].astype(bool)
    info = dict(zip(RUN_FIELDS, run[:-1]))
    info["rejected"] = json.loads(run[-1] or "[]")
    return df, info


def read_run_history(dataset_id=None, limit=20):
    """Return the last pipeline runs as a DataFrame (newest first)."""
    conn = connect()
    try:
        where, params = ("WHERE dataset=?", (dataset_id, limit)) if dataset_id else ("", (limit,))
        return pd.read_sql_query(
            f"SELECT dataset, {', '.join(RUN_FIELDS)} FROM etl_runs {where} ORDER BY run_id DESC LIMIT ?",
            conn, params=params)
    except sqlite3.Error as error:
        raise DatabaseError(f"Could not read the run history: {error}")
    finally:
        conn.close()
