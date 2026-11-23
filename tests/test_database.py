import sqlite3

import pandas as pd
import pytest

from src.datasets import BY_ID
from src.loading import database
from src.loading.database import DatabaseError, read_dataset, read_run_history, save_dataset
from tests.conftest import load_df

INFO = {"run_at": "2026-01-01 00:00:00", "source": "saved_snapshot", "source_detail": "x.json",
        "data_time": "2026-01-01 00:00:00", "raw_count": 7, "valid_count": 7, "rejected_count": 1,
        "duplicate_count": 0, "loaded_count": 7, "duration_seconds": 0.1, "warning": None,
        "rejected": [{"index": 3, "model_id": "bad", "reason": "id: too short"}]}

CATALOG, IMAGE, VIDEO = BY_ID["llm_catalog"], BY_ID["image_t2i"], BY_ID["video_t2v"]


def test_empty_database_is_created_automatically():
    df, info = read_dataset(IMAGE)
    assert df.empty and info is None
    assert list(df.columns) == list(IMAGE.transform([]).columns)


def test_roundtrip_keeps_values_and_types_for_openrouter_data():
    original = load_df("llm_catalog")
    assert save_dataset(CATALOG, original, INFO) == len(original)
    loaded, info = read_dataset(CATALOG)
    assert len(loaded) == len(original)
    assert loaded["is_multimodal"].dtype == bool
    assert str(loaded["created_at"].dtype).startswith("datetime64")
    assert loaded["input_price_per_million"].isna().sum() == original["input_price_per_million"].isna().sum()
    assert info["rejected"][0]["reason"] == "id: too short" and info["source"] == "saved_snapshot"


def test_roundtrip_for_leaderboard_data():
    original = load_df("image_t2i")
    save_dataset(IMAGE, original, INFO)
    loaded, _ = read_dataset(IMAGE)
    pd.testing.assert_series_equal(loaded["elo"], original["elo"], check_names=False)
    assert loaded["model_name"].tolist() == original["model_name"].tolist()


def test_benchmark_dates_are_restored():
    original = load_df("llm_benchmarks")
    dataset = BY_ID["llm_benchmarks"]
    save_dataset(dataset, original, INFO)
    assert str(read_dataset(dataset)[0]["release_date"].dtype).startswith("datetime64")


def test_saving_again_replaces_data_and_keeps_history():
    df = load_df("image_t2i")
    save_dataset(IMAGE, df, INFO)
    save_dataset(IMAGE, df.head(2), {**INFO, "loaded_count": 2})
    assert len(read_dataset(IMAGE)[0]) == 2
    assert len(read_run_history("image_t2i")) == 2


def test_datasets_are_stored_independently():
    save_dataset(IMAGE, load_df("image_t2i"), INFO)
    save_dataset(VIDEO, load_df("video_t2v").head(3), INFO)
    assert len(read_dataset(IMAGE)[0]) == len(load_df("image_t2i"))
    assert len(read_dataset(VIDEO)[0]) == 3
    assert set(read_run_history()["dataset"]) == {"image_t2i", "video_t2v"}
    assert len(read_run_history("video_t2v")) == 1


def test_failed_save_keeps_old_data_and_history():
    df = load_df("image_t2i")
    save_dataset(IMAGE, df, INFO)
    broken = df.copy().astype({"model_name": object})
    broken.at[1, "model_name"] = ["not", "allowed"]       # SQLite cannot store a list
    with pytest.raises(DatabaseError):
        save_dataset(IMAGE, broken, INFO)
    assert len(read_dataset(IMAGE)[0]) == len(df)          # rolled back, table not dropped
    assert len(read_run_history("image_t2i")) == 1


def test_wrong_table_format_is_reported():
    with pytest.raises(DatabaseError):
        save_dataset(IMAGE, pd.DataFrame({"x": [object()]}), INFO)


def test_table_with_old_columns_counts_as_empty_so_it_is_rebuilt():
    conn = database.connect()
    conn.execute("CREATE TABLE ds_image_t2i (old_column TEXT)")
    conn.execute("INSERT INTO ds_image_t2i VALUES ('x')")
    conn.execute("INSERT INTO etl_runs (dataset) VALUES ('image_t2i')")
    conn.commit()
    conn.close()
    assert read_dataset(IMAGE)[0].empty


def test_unusable_database_folder_falls_back_to_temp(tmp_path, monkeypatch):
    blocker = tmp_path / "file.txt"
    blocker.write_text("i am a file")
    monkeypatch.setenv("AI_MODELS_DB_PATH", str(blocker / "sub" / "db.sqlite"))
    assert database.get_database_path().parent != blocker


def test_corrupt_database_file_is_reported(tmp_path, monkeypatch):
    broken = tmp_path / "broken.db"
    broken.write_bytes(b"this is not a sqlite database" * 50)
    monkeypatch.setenv("AI_MODELS_DB_PATH", str(broken))
    with pytest.raises((DatabaseError, sqlite3.DatabaseError)):
        read_dataset(IMAGE)
