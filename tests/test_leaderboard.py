"""Tests for the generic leaderboard analysis (Image, Video, Speech, Benchmarks)."""
import pandas as pd
import pytest

from src.analysis import leaderboard
from src.datasets import BY_ID
from tests.conftest import load_df

IMAGE = BY_ID["image_t2i"]           # higher is better, has confidence intervals
STT = BY_ID["speech_stt"]            # LOWER is better (error rate), no confidence intervals


@pytest.fixture
def image():
    return load_df("image_t2i")


def test_best_first_respects_the_direction_of_the_metric(image):
    top = leaderboard.best_first(image, IMAGE)
    assert top[IMAGE.metric].is_monotonic_decreasing
    stt = load_df("speech_stt")
    assert leaderboard.best_first(stt, STT)[STT.metric].is_monotonic_increasing   # lowest error first


def test_stats_and_leader(image):
    stats = leaderboard.lb_stats(image, IMAGE)
    assert stats["models"] == len(image) and stats["best"] == image["elo"].max()
    assert stats["min"] <= stats["median"] <= stats["max"] and stats["leader"]
    assert leaderboard.lb_stats(image.iloc[0:0], IMAGE) == {}


def test_creator_table_shares_add_up(image):
    table = leaderboard.creator_table(image, IMAGE)
    assert table["share_pct"].sum() == pytest.approx(100)
    assert table["models"].sum() == len(image)
    assert leaderboard.creator_table(image.iloc[0:0], IMAGE).empty


def test_models_tied_with_the_leader_have_overlapping_intervals(image):
    tied = leaderboard.tied_with_leader(image, IMAGE)
    leader = leaderboard.best_first(image, IMAGE).iloc[0]
    assert leader["model_id"] in tied["model_id"].tolist()
    assert (tied["elo"] + tied["ci_95"] >= leader["elo"] - leader["ci_95"]).all()
    assert leaderboard.tied_with_leader(load_df("speech_stt"), STT).empty       # no interval column


def test_least_certain_models_have_the_widest_intervals(image):
    widest = leaderboard.least_certain(image, IMAGE, n=3)
    assert len(widest) == 3 and widest["ci_95"].is_monotonic_decreasing
    assert leaderboard.least_certain(load_df("speech_stt"), STT).empty


def test_filters_work_together(image):
    first = image.iloc[0]
    assert len(leaderboard.filter_leaderboard(image, IMAGE)) == len(image)
    assert len(leaderboard.filter_leaderboard(image, IMAGE, search=first["model_name"].upper())) >= 1
    assert set(leaderboard.filter_leaderboard(image, IMAGE, creators=[first["creator"]])["creator"]) == {first["creator"]}
    high = leaderboard.filter_leaderboard(image, IMAGE, min_score=image["elo"].median())
    assert (high["elo"] >= image["elo"].median()).all()
    assert leaderboard.filter_leaderboard(image, IMAGE, search="zzz-no-match").empty


def test_spearman_needs_enough_rows_and_log_columns_drop_non_positive_values():
    data = pd.DataFrame({"a": [1, 2, 3, 4, 5, 6], "b": [6, 5, 4, 3, 2, 1]})
    assert leaderboard.spearman_table(data, ["a", "b"]).loc["a", "b"] == pytest.approx(-1)
    assert leaderboard.spearman_table(data.head(3), ["a", "b"]).empty
    logged = leaderboard.log_columns(pd.DataFrame({"x": [0.0, 10.0, 100.0, None]}), ["x"])
    assert logged["x"].dropna().tolist() == [1.0, 2.0] and len(logged) == 3     # 0 removed, missing kept


def test_every_leaderboard_dataset_works_with_the_generic_functions():
    """This is why a new category needs no new analysis code."""
    for dataset in [d for d in BY_ID.values() if d.metric]:
        df = load_df(dataset.id)
        assert leaderboard.lb_stats(df, dataset)["models"] == len(df)
        assert not leaderboard.creator_table(df, dataset).empty
