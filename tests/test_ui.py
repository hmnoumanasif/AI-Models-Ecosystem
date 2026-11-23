"""Tests of the interface layer: interactive charts and the theme-aware table."""
import pytest

from src.analysis import eda
from src.datasets import BY_ID
from src.ui import plots
from src.ui.palette import TOKENS
from src.ui.styles import build_css
from src.ui.tables import build_table_html
from tests.conftest import build_df, load_df


@pytest.mark.parametrize("mode", ["light", "dark"])
def test_all_language_model_plots_are_interactive_figures(df, mode):
    figures = [
        plots.bar_chart(eda.provider_table(df), "provider", "models", "t", "x", mode),
        plots.context_histogram(df, mode),
        plots.median_by_provider(df, "context_length", "t", "x", mode, min_models=1),
        plots.price_boxplot(df, mode),
        plots.price_vs_context(df, mode),
        plots.pricing_status_chart(df, mode),
        plots.missing_chart(df, mode),
    ]
    for fig in figures:
        assert fig is not None and len(fig.data) >= 1
        assert fig.layout.paper_bgcolor == "rgba(0,0,0,0)"          # transparent: the card colour shows through


@pytest.mark.parametrize("dataset_id", ["image_t2i", "video_t2v", "speech_tts", "speech_s2s", "speech_stt",
                                        "llm_benchmarks"])
def test_ranking_and_histogram_plots_work_for_every_leaderboard(dataset_id):
    ds, df = BY_ID[dataset_id], load_df(dataset_id)
    assert plots.ranking_chart(df, ds, 12, "light") is not None
    assert plots.metric_histogram(df, ds, "dark") is not None


def test_ranking_legend_groups_bars_and_labels_so_one_click_hides_both():
    ds, df = BY_ID["image_t2i"], load_df("image_t2i")
    fig = plots.ranking_chart(df, ds, 12, "light")
    groups = {}
    for trace in fig.data:
        groups.setdefault(trace.legendgroup, []).append(trace.type)
    assert all(types == ["bar", "scatter"] for types in groups.values())


def test_scatter_plot_has_one_trace_per_creator_and_hover_names():
    df = load_df("llm_benchmarks")
    fig = plots.scatter_chart(df, "input_price_per_million", "intelligence_index", "x", "y", "t", "light", True)
    assert len(fig.data) == df.dropna(subset=["input_price_per_million", "intelligence_index"]).query(
        "input_price_per_million > 0")["creator"].nunique()
    assert "customdata[0]" in fig.data[0].hovertemplate


def test_plots_return_none_when_data_is_not_enough():
    empty = build_df([])
    for make in (plots.context_histogram, plots.price_boxplot, plots.price_vs_context, plots.missing_chart):
        assert make(empty, "light") is None
    ds = BY_ID["image_t2i"]
    assert plots.ranking_chart(load_df("image_t2i").iloc[0:0], ds, 10, "light") is None


def test_same_creator_has_the_same_colour_in_every_chart():
    ds, df = BY_ID["llm_benchmarks"], load_df("llm_benchmarks")
    palette = plots.creator_colors(df, "light")
    rank = plots.ranking_chart(df, ds, 12, "light")
    for trace in rank.data:
        if trace.type == "bar":
            assert trace.marker.color == palette[trace.name]


def test_table_is_html_with_sorting_and_escapes_data():
    df = build_df([{"id": "a/b", "name": "<script>alert(1)</script>", "context_length": 5000,
                    "pricing": {"prompt": "0.000001", "completion": "0.000002"}}])
    html = build_table_html(df[["model_name", "context_length"]], {"context_length": "Context"}, "dark")
    assert "<script>alert(1)</script>" not in html and "&lt;script&gt;" in html
    assert 'data-kind="num"' in html and "Context" in html and "sortBy" in html


def test_table_formats_numbers_dates_and_missing_values():
    import pandas as pd
    import streamlit as st
    frame = pd.DataFrame({"price": [0.0153, None], "when": pd.to_datetime(["2026-01-02", None], utc=True)})
    html = build_table_html(frame, {"price": st.column_config.NumberColumn("Price", format="$%.3f"),
                                    "when": st.column_config.DatetimeColumn("Date", format="YYYY-MM-DD")})
    assert "$0.015" in html and "2026-01-02" in html and html.count('class="na"') == 2


@pytest.mark.parametrize("mode", ["light", "dark"])
def test_css_uses_the_theme_colours(mode):
    css = build_css(mode)
    assert TOKENS[mode]["bg"] in css and TOKENS[mode]["accent"] in css
    assert "stSidebarCollapseButton" in css                           # the collapse button is hidden on wide screens
