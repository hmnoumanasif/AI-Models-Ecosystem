import sys
from unittest.mock import patch

import pytest

from src import pipeline
from src.datasets import BY_ID, DATASETS
from src.extraction import api_client
from src.extraction.api_client import ExtractionError
from src.loading.database import DatabaseError, read_dataset
from tests.conftest import make_arena

IMAGE = BY_ID["image_t2i"]


@pytest.fixture
def no_saved_files(tmp_path, monkeypatch):
    """No raw files and no samples: only live data can work."""
    monkeypatch.setattr(api_client, "RAW_DIR", tmp_path / "none_raw")
    monkeypatch.setattr(api_client, "SAMPLE_DIR", tmp_path / "none_sample")


def snapshot(records, source="saved_snapshot"):
    return {"data": records}, {"source": source, "source_detail": "x.json", "data_time": "2026-01-01 00:00:00"}


def test_live_run_saves_raw_csv_and_database():
    payload = {"data": [make_arena("1", elo=1300), make_arena("2", elo=1200), {"id": "", "name": "bad"}]}
    with patch.object(pipeline, "fetch_dataset", return_value=payload):
        result = pipeline.run_etl(IMAGE, use_live=True)
    info = result["info"]
    assert info["source"] == "live_api" and info["warning"] is None
    assert (info["raw_count"], info["valid_count"], info["rejected_count"]) == (3, 2, 1)
    assert result["saved"] and len(read_dataset(IMAGE)[0]) == 2
    assert len(list((pipeline.RAW_DIR / "image_t2i").glob("*.json"))) == 1
    assert (pipeline.PROCESSED_DIR / "image_t2i.csv").exists()


def test_api_failure_falls_back_and_says_so():
    with patch.object(pipeline, "fetch_dataset", side_effect=ExtractionError("down.")), \
         patch.object(pipeline, "load_saved_snapshot", return_value=snapshot([make_arena()])):
        result = pipeline.run_etl(IMAGE, use_live=True)
    assert result["info"]["source"] == "saved_snapshot" and "Live API failed" in result["info"]["warning"]


def test_missing_api_key_falls_back_to_saved_data_with_a_helpful_warning():
    result = pipeline.run_etl(IMAGE, use_live=True)            # no key configured, no mocks, no network used
    assert result["info"]["source"] in {"saved_snapshot", "synthetic_sample"}
    assert "ARTIFICIAL_ANALYSIS_API_KEY" in result["info"]["warning"]


def test_no_data_anywhere_raises(no_saved_files):
    with pytest.raises(ExtractionError, match="No saved snapshot"):
        pipeline.run_etl(IMAGE, use_live=False)


def test_all_records_invalid_raises_and_keeps_old_data():
    with patch.object(pipeline, "load_saved_snapshot", return_value=snapshot([make_arena()])):
        pipeline.run_etl(IMAGE, use_live=False)
    with patch.object(pipeline, "load_saved_snapshot", return_value=snapshot([{"bad": 1}])):
        with pytest.raises(ValueError):
            pipeline.run_etl(IMAGE, use_live=False)
    assert len(read_dataset(IMAGE)[0]) == 1


def test_database_failure_is_reported_not_hidden():
    with patch.object(pipeline, "load_saved_snapshot", return_value=snapshot([make_arena()])), \
         patch.object(pipeline, "save_dataset", side_effect=DatabaseError("disk full")):
        result = pipeline.run_etl(IMAGE, use_live=False)
    assert result["saved"] is False and "disk full" in result["save_error"]
    assert len(result["dataframe"]) == 1          # data still usable in memory


def test_duplicates_are_counted():
    records = [make_arena("1", name="One"), make_arena("1", name="Again")]
    with patch.object(pipeline, "load_saved_snapshot", return_value=snapshot(records)):
        result = pipeline.run_etl(IMAGE, use_live=False)
    assert result["info"]["duplicate_count"] == 1 and result["info"]["loaded_count"] == 1


def test_unwritable_output_folders_do_not_break_the_pipeline(monkeypatch, tmp_path):
    blocker = tmp_path / "blocker"
    blocker.write_text("file")
    monkeypatch.setattr(pipeline, "RAW_DIR", blocker / "raw")
    monkeypatch.setattr(pipeline, "PROCESSED_DIR", blocker / "processed")
    with patch.object(pipeline, "fetch_dataset", return_value={"data": [make_arena()]}):
        assert pipeline.run_etl(IMAGE, use_live=True)["saved"]


def test_one_failing_dataset_does_not_stop_the_others():
    real = pipeline.run_etl

    def sometimes_fails(dataset, use_live):
        if dataset.id == "video_t2v":
            raise RuntimeError("boom")
        return real(dataset, use_live)

    with patch.object(pipeline, "run_etl", side_effect=sometimes_fails):
        results = pipeline.run_all(use_live=False)
    assert set(results) == {d.id for d in DATASETS}
    assert results["video_t2v"] == {"error": "boom"}
    assert all("dataframe" in r for i, r in results.items() if i != "video_t2v")


def test_run_all_can_be_limited_to_some_datasets():
    results = pipeline.run_all(use_live=False, only=["image_t2i", "speech_stt"])
    assert set(results) == {"image_t2i", "speech_stt"}


def test_every_bundled_dataset_runs_through_the_whole_pipeline_offline():
    results = pipeline.run_all(use_live=False)
    for dataset_id, result in results.items():
        assert "error" not in result, dataset_id
        assert result["saved"] and result["info"]["loaded_count"] > 0
        assert len(read_dataset(BY_ID[dataset_id])[0]) == result["info"]["loaded_count"]


def test_command_line_summary(monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["pipeline", "--offline", "image_t2i"])
    pipeline.main()
    output = capsys.readouterr().out
    assert "image_t2i" in output and "synthetic_sample" in output and "video_t2v" not in output


def test_command_line_rejects_unknown_dataset(monkeypatch):
    monkeypatch.setattr(sys, "argv", ["pipeline", "--offline", "nope"])
    with pytest.raises(SystemExit):
        pipeline.main()
