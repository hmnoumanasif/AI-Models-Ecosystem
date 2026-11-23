"""Tests for the dataset list. These show that the project is scalable:
a new dataset only needs one entry, no change in the pipeline or database."""
from unittest.mock import patch

import pytest

from src import pipeline
from src.datasets import CATEGORIES, DATASETS, Dataset, datasets_in
from src.extraction.api_client import load_saved_snapshot
from src.loading.database import read_dataset
from src.transformation.transform import transform_arena
from src.validation.schemas import ArenaRecord, validate_records
from tests.conftest import make_arena


def test_ids_are_unique_and_safe_for_table_names():
    ids = [d.id for d in DATASETS]
    assert len(ids) == len(set(ids))
    assert all(i.replace("_", "").isalnum() and i.islower() for i in ids)


def test_every_category_has_datasets_and_every_dataset_a_known_category():
    assert all(datasets_in(c) for c in CATEGORIES)
    assert {d.category for d in DATASETS} <= set(CATEGORIES)
    assert [c for c in CATEGORIES] == ["Language Models", "Image", "Video", "Speech"]


@pytest.mark.parametrize("dataset", DATASETS, ids=lambda d: d.id)
def test_each_dataset_has_a_working_sample_and_consistent_columns(dataset):
    payload, info = load_saved_snapshot(dataset)
    valid, rejected = validate_records(payload["data"], dataset.schema)
    df = dataset.transform(valid)
    assert len(df) > 0 and {"model_id", "model_name"} <= set(df.columns)
    assert set(dataset.bool_columns) <= set(df.columns) and set(dataset.date_columns) <= set(df.columns)
    if dataset.metric:
        assert dataset.metric in df.columns and "creator" in df.columns
    if dataset.ci_column:
        assert dataset.ci_column in df.columns
    if info["source"] == "synthetic_sample":
        assert len(rejected) >= 1              # samples include one bad record on purpose
    assert dataset.key_required is False or dataset.key_env


def test_artificial_analysis_data_is_attributed():
    for dataset in DATASETS:
        if dataset.key_env == "ARTIFICIAL_ANALYSIS_API_KEY":
            assert "Artificial Analysis" in dataset.attribution


def test_a_new_dataset_needs_only_one_entry():
    new = Dataset(id="demo_new", category="Image", title="Demo", url="http://example.test/api",
                  schema=ArenaRecord, transform=transform_arena, key_env=None,
                  metric="elo", metric_label="Demo Elo", ci_column="ci_95")
    payload = {"data": [make_arena("a", elo=1300), make_arena("b", elo=1250), {"id": "bad", "name": "B"}]}
    with patch.object(pipeline, "fetch_dataset", return_value=payload):
        result = pipeline.run_etl(new, use_live=True)
    assert result["info"]["loaded_count"] == 2 and result["info"]["rejected_count"] == 1
    assert result["saved"] and len(read_dataset(new)[0]) == 2          # database table created by itself
    assert (pipeline.RAW_DIR / "demo_new").exists()                    # own raw folder created by itself
