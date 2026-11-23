"""Tests that start the real Streamlit app (without a browser) and click through it."""
import json
import shutil
from pathlib import Path
from unittest.mock import patch

import pytest
from streamlit.testing.v1 import AppTest

from src import datasets
from src.config import SAMPLE_DIR
from src.datasets import CATEGORIES, Dataset
from src.extraction import api_client
from src.transformation.transform import transform_arena
from src.validation.schemas import ArenaRecord
from tests.conftest import make_arena

APP = str(Path(__file__).resolve().parents[1] / "app.py")
SYNTHETIC_NOTE = "made-up demo data"        # the red banner shown for synthetic sample data


@pytest.fixture
def app():
    at = AppTest.from_file(APP, default_timeout=90).run()
    assert not at.exception
    return at


def go(at, category, page=None):
    """Open a category (and a page of it). The tabs and the navigation are buttons that
    set these session-state values, so the tests set them directly."""
    at.session_state["category"] = category
    at.run()
    if page:
        at.session_state[f"page_{category}"] = page
        at.run()
    return at


def nav_pages(at, category):
    """Names of the pages in the sidebar navigation."""
    return [b.label for b in at.sidebar.button if (b.key or "").startswith(f"nav_{category}_")]


def tab_names(at):
    return [b.label for b in at.button if (b.key or "").startswith("tab_")]


def unexpected_errors(at):
    return [e.value for e in at.error if SYNTHETIC_NOTE not in e.value]


def test_app_starts_on_language_models_with_a_source_pill(app):
    assert any("pill" in m.value for m in app.markdown)
    assert tab_names(app) == CATEGORIES == ["Language Models", "Image", "Video", "Speech"]


@pytest.mark.parametrize("category", CATEGORIES)
def test_every_page_of_every_category_works(app, category):
    go(app, category)
    pages = nav_pages(app, category)
    assert len(pages) >= 5
    for page in pages:
        go(app, category, page)
        assert not app.exception, (category, page)
        assert not unexpected_errors(app), (category, page)
        assert not app.warning, (category, page)       # a failed chart would show a warning


def test_every_model_type_of_every_category_can_be_chosen(app):
    for category in CATEGORIES[1:]:
        go(app, category)
        for dataset in datasets.datasets_in(category):
            app.session_state[f"dataset_{category}"] = dataset.id
            app.run()
            assert not app.exception, (category, dataset.id)
            assert not unexpected_errors(app), (category, dataset.id)
            assert any(dataset.title in t.value for t in app.title)


def test_switching_categories_back_and_forth_is_stable(app):
    """Each category has its own page list; moving between them never breaks a page."""
    for category in CATEGORIES * 2 + ["Language Models"]:
        go(app, category)
        assert not app.exception, category
        assert not unexpected_errors(app), category
        first = nav_pages(app, category)[0]                                       # starts on the first page
        assert any(f"{category}  /  {first}" in m.value for m in app.markdown)


def test_language_models_explore_filters_and_empty_state(app):
    go(app, "Language Models", "Explore models")
    app.text_input[0].set_value("zzz-no-such-model").run()
    assert not app.exception
    assert any("No model matches" in i.value for i in app.info)
    app.text_input[0].set_value("gpt").run()
    assert any("models match" in m.value for m in app.markdown)


def test_leaderboard_explore_filters_and_empty_state(app):
    go(app, "Image", "Explore")
    app.text_input[0].set_value("zzz-no-such-model").run()
    assert not app.exception
    assert not unexpected_errors(app)


# ------------------------------------------------------------ fault tolerance
def test_fetch_live_data_without_a_key_keeps_the_app_working(app):
    """No ARTIFICIAL_ANALYSIS_API_KEY: the user gets a clear warning, never a crash."""
    go(app, "Image")
    next(b for b in app.sidebar.button if "Fetch live" in b.label).click().run()
    assert not app.exception
    assert any("ARTIFICIAL_ANALYSIS_API_KEY" in w.value for w in app.warning)
    assert app.session_state["results"]["image_t2i"]["info"]["source"] in {"saved_snapshot", "synthetic_sample"}


def test_no_internet_shows_a_warning_and_saved_data(app):
    go(app, "Language Models")
    with patch("src.extraction.api_client.requests.get", side_effect=api_client.requests.ConnectionError("down")), \
         patch("src.extraction.api_client.time.sleep"):
        next(b for b in app.sidebar.button if "Fetch live" in b.label).click().run()
    assert not app.exception
    assert any("Live API failed" in w.value for w in app.warning)
    assert len(app.session_state["results"]["llm_catalog"]["dataframe"]) > 0


def test_failed_refresh_keeps_old_data_and_hides_technical_details(app, monkeypatch):
    import src.pipeline

    def boom(dataset, use_live):
        raise RuntimeError("secret internal detail")

    before = len(app.session_state["results"]["llm_catalog"]["dataframe"])
    monkeypatch.setattr(src.pipeline, "run_etl", boom)      # app.py imports run_etl on every run
    next(b for b in app.sidebar.button if "Fetch live" in b.label).click().run()
    assert not app.exception
    assert any("Previous data was kept" in e.value for e in app.error)
    assert all("secret internal detail" not in e.value for e in app.error)
    assert len(app.session_state["results"]["llm_catalog"]["dataframe"]) == before


def test_one_broken_dataset_does_not_break_the_other_categories(monkeypatch):
    import src.pipeline
    real = src.pipeline.run_etl

    def broken_for_speech(dataset, use_live):
        if dataset.id == "speech_tts":
            raise RuntimeError("boom")
        return real(dataset, use_live)

    monkeypatch.setattr(src.pipeline, "run_etl", broken_for_speech)
    at = AppTest.from_file(APP, default_timeout=90).run()
    assert not at.exception
    go(at, "Image", "Ranking")
    assert not at.exception and not unexpected_errors(at)
    go(at, "Speech", "Ranking")
    assert not at.exception
    assert any("No data is available" in e.value for e in at.error)         # clear message, not a crash
    at.session_state["dataset_Speech"] = "speech_stt"
    at.run()
    assert not at.exception and not unexpected_errors(at)                   # sibling dataset still works


def test_app_starts_even_if_the_database_cannot_be_used(monkeypatch, tmp_path):
    blocker = tmp_path / "file.txt"
    blocker.write_text("not a folder")
    monkeypatch.setenv("AI_MODELS_DB_PATH", str(blocker / "x.db"))          # impossible path -> temp fallback
    at = AppTest.from_file(APP, default_timeout=90).run()
    assert not at.exception


# ------------------------------------------------------------- scalability
def test_a_whole_new_category_appears_after_adding_one_dataset(monkeypatch, tmp_path):
    """Scalability test: a new 'Music' category needs one Dataset entry, no UI code."""
    sample = tmp_path / "sample"
    shutil.copytree(SAMPLE_DIR, sample)
    payload = {"data": [make_arena("m1", "Song AI 1", "Lab A", 1300, 8), make_arena("m2", "Song AI 2", "Lab B", 1250, 9),
                        make_arena("m3", "Song AI 3", "Lab A", 1200, 12)]}
    (sample / "music_demo.json").write_text(json.dumps(payload))
    new = Dataset(id="music_demo", category="Music", title="Text to Music", url="http://example.test/music",
                  schema=ArenaRecord, transform=transform_arena, metric="elo", metric_label="Music Arena Elo",
                  ci_column="ci_95")
    monkeypatch.setattr(api_client, "SAMPLE_DIR", sample)
    monkeypatch.setattr(api_client, "RAW_DIR", tmp_path / "no_raw")
    monkeypatch.setattr(datasets, "DATASETS", datasets.DATASETS + [new])
    monkeypatch.setattr(datasets, "CATEGORIES", datasets.CATEGORIES + ["Music"])
    monkeypatch.setitem(datasets.BY_ID, "music_demo", new)

    at = AppTest.from_file(APP, default_timeout=90).run()
    assert not at.exception
    assert "Music" in tab_names(at)
    go(at, "Music")
    for page in nav_pages(at, "Music"):
        go(at, "Music", page)
        assert not at.exception, page
        assert not unexpected_errors(at), page
    assert any("Text to Music" in t.value for t in at.title)


# ------------------------------------------------------------------- theme
def test_theme_switch_flips_between_bright_and_dark(app):
    assert app.session_state["theme"] == "light"
    app.button(key="theme_switch").click().run()
    assert app.session_state["theme"] == "dark" and not app.exception
    assert any("--bg: #101214" in m.value for m in app.markdown)           # the dark colours are in the page
    app.button(key="theme_switch").click().run()
    assert app.session_state["theme"] == "light"


def test_dark_theme_works_on_every_category(app):
    app.button(key="theme_switch").click().run()
    for category in CATEGORIES:
        go(app, category)
        assert not app.exception and not unexpected_errors(app), category
