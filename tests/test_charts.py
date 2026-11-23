import matplotlib.pyplot as plt
import pytest

from src.analysis import charts, eda
from src.datasets import BY_ID
from src.theme import chart_rc
from tests.conftest import build_df, load_df


@pytest.mark.parametrize("mode", ["light", "dark"])
def test_all_language_model_charts_draw_in_both_themes(df, mode):
    figures = [
        charts.bar_chart(eda.provider_table(df), "provider", "models", "t", "x", mode),
        charts.context_histogram(df, mode),
        charts.median_by_provider(df, "context_length", "t", "x", mode, min_models=1),
        charts.price_boxplot(df, mode),
        charts.price_vs_context(df, mode),
        charts.pricing_status_chart(df, mode),
        charts.missing_chart(df, mode),
    ]
    for fig in figures:
        assert fig is not None
        assert fig.get_facecolor()[3] == 0        # transparent: readable on light and dark pages
        plt.close(fig)


@pytest.mark.parametrize("dataset_id", ["image_t2i", "video_t2v", "speech_tts", "speech_s2s", "speech_stt",
                                        "llm_benchmarks"])
def test_ranking_and_histogram_work_for_every_leaderboard(dataset_id):
    ds, df = BY_ID[dataset_id], load_df(dataset_id)
    for fig in (charts.ranking_chart(df, ds, 12, "light"), charts.metric_histogram(df, ds, "dark")):
        assert fig is not None
        plt.close(fig)


def test_scatter_chart_with_and_without_log_axes():
    df = load_df("llm_benchmarks")
    for log in (True, False):
        fig = charts.scatter_chart(df, "input_price_per_million", "intelligence_index", "x", "y", "t", "light", log)
        assert fig is not None
        plt.close(fig)


def test_charts_return_none_when_data_is_not_enough():
    empty = build_df([])
    for make in (charts.context_histogram, charts.price_boxplot, charts.price_vs_context,
                 charts.correlation_heatmap, charts.missing_chart):
        assert make(empty, "light") is None
    ds = BY_ID["image_t2i"]
    assert charts.ranking_chart(load_df("image_t2i").iloc[0:0], ds, 10, "light") is None
    assert charts.metric_histogram(load_df("image_t2i").iloc[0:0], ds, "light") is None


def test_single_record_charts_do_not_crash():
    one = build_df([{"id": "a/b", "name": "X", "context_length": 5000,
                     "pricing": {"prompt": "0.000001", "completion": "0.000002"}}])
    fig = charts.context_histogram(one, "dark")
    assert fig is not None
    plt.close(fig)
    ds = BY_ID["image_t2i"]
    fig = charts.ranking_chart(load_df("image_t2i").head(1), ds, 10, "light")
    assert fig is not None
    plt.close(fig)


def test_chart_text_is_readable_on_light_and_dark_pages():
    """Text must be neither near-white nor near-black, so it shows on both backgrounds."""
    color = chart_rc("light")["text.color"].lstrip("#")
    brightness = sum(int(color[i:i + 2], 16) for i in (0, 2, 4)) / 3
    assert 90 < brightness < 170
