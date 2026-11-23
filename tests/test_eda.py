"""Tests for the OpenRouter (Language Models) analysis functions."""
import pandas as pd
import pytest

from src.analysis import eda
from tests.conftest import build_df


def test_overview_metrics(df):
    m = eda.overview_metrics(df)
    assert m["models"] == 7 and m["providers"] == 3
    assert m["free_models"] == 1 and m["missing_pricing"] == 2   # google/d and meta/e
    assert m["known_pricing"] == 5 and m["multimodal"] == 1 and m["known_context"] == 6


def test_provider_table_share_and_medians(df):
    table = eda.provider_table(df).set_index("provider")
    assert table["catalog_share_pct"].sum() == pytest.approx(100)
    assert table.loc["openai", "median_input_price"] == 5.5        # (1 + 10) / 2
    assert pd.isna(table.loc["google", "median_input_price"])      # only free/missing models


def test_context_stats_and_outliers(df):
    stats = eda.context_stats(df)
    assert stats["min"] == 8000 and stats["max"] == 1000000
    assert stats["p25"] <= stats["median"] <= stats["p90"]
    big = pd.concat([df] + [df.assign(model_id=df["model_id"] + str(i), context_length=130000) for i in range(3)])
    assert 1000000 in eda.context_outliers(big)["context_length"].tolist()


def test_cost_estimate(df):
    costs = eda.cost_estimate(df, 1_000_000, 1_000_000).set_index("model_id")
    assert costs.loc["openai/a", "estimated_cost_usd"] == 3.0      # $1 + $2
    assert costs.loc["google/c", "estimated_cost_usd"] == 0.0      # free
    assert "meta/e" not in costs.index and "google/d" not in costs.index   # unknown prices left out
    assert costs["estimated_cost_usd"].is_monotonic_increasing


def test_modality_tables(df):
    counts = eda.modality_counts(df, "input_modalities").set_index("modality")["models"]
    assert counts["text"] == 7 and counts["image"] == 1
    support = eda.input_support_table(df).set_index("input type")
    assert support.loc["image", "models"] == 1 and support.loc["video", "models"] == 0


def test_filters_work_together(df):
    assert len(eda.filter_models(df)) == 7
    assert len(eda.filter_models(df, search="OPENAI")) == 2
    assert len(eda.filter_models(df, providers=["meta"], statuses=["paid"])) == 2
    assert len(eda.filter_models(df, input_types=["image"])) == 1
    assert len(eda.filter_models(df, min_context=100000)) == 4
    assert len(eda.filter_models(df, providers=["meta"], max_input_price=1.0, min_context=10000)) == 1
    assert eda.filter_models(df, search="zzz-no-match").empty


def test_quality_functions(df):
    missing = eda.missing_table(df).set_index("column")
    assert missing.loc["context_length", "missing"] == 1
    assert 0 < eda.completeness_pct(df) < 100


def test_correlation_needs_enough_models(df):
    assert eda.correlation_table(df.head(3)).empty
    big = pd.concat([df.assign(model_id=df["model_id"] + str(i)) for i in range(2)])
    corr = eda.correlation_table(big)
    assert corr.shape == (3, 3) and corr.loc["input price", "input price"] == 1


def test_empty_and_single_row_tables():
    empty = build_df([])
    assert eda.overview_metrics(empty)["models"] == 0
    assert eda.key_facts(empty) == []
    assert eda.provider_table(empty).empty and eda.context_stats(empty) == {}
    one = build_df([{"id": "a/b", "name": "X", "context_length": 5}])
    assert len(eda.provider_table(one)) == 1 and eda.correlation_table(one).empty
    assert eda.key_facts(one)


def test_csv_download_bytes(df):
    data = eda.to_csv_bytes(df)
    assert data.startswith(b"model_id") and data.count(b"\n") == len(df) + 1
