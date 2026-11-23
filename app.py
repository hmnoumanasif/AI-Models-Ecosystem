"""Streamlit app. Start it with:  streamlit run app.py"""
import logging
from pathlib import Path

import streamlit as st

from src import dashboard
from src.config import setup_logging
from src.datasets import BY_ID, CATEGORIES, DATASETS, datasets_in
from src.loading.database import DatabaseError, read_dataset
from src.pipeline import run_etl
from src.ui import components as ui
from src.ui.styles import build_css

setup_logging()
log = logging.getLogger(__name__)

FAVICON = Path(__file__).parent / "assets" / "favicon.png"

st.set_page_config(page_title="AI Models Ecosystem", page_icon=str(FAVICON) if FAVICON.exists() else "📊",
                   layout="wide", initial_sidebar_state="expanded")

# Page name -> (function that draws it, dataset id or None, one-line description)
# None means "the dataset chosen with the chips above the page".
LANGUAGE_PAGES = {
    "Overview": (dashboard.page_overview, "llm_catalog", "Key numbers and the main picture of the model catalog."),
    "Providers": (dashboard.page_providers, "llm_catalog", "Who offers how many models, at what price and context size."),
    "Context windows": (dashboard.page_context, "llm_catalog", "How much text a model can read at once."),
    "Pricing": (dashboard.page_pricing, "llm_catalog", "Token prices, free vs. missing prices, and a cost calculator."),
    "Modalities": (dashboard.page_modalities, "llm_catalog", "What kinds of input and output models support."),
    "Benchmarks": (dashboard.page_benchmarks, "llm_benchmarks", "Intelligence, speed and cost of language models."),
    "Data quality": (dashboard.page_quality, "llm_catalog", "Missing values, rejected records and duplicates."),
    "Explore models": (dashboard.page_explore, "llm_catalog", "Search, filter, compare and download the data."),
    "Pipeline": (dashboard.page_pipeline, "llm_catalog", "How the ETL pipeline ran and where the data came from."),
}
LEADERBOARD_PAGES = {
    "Ranking": (dashboard.page_lb_ranking, None, "Which models are the best, and how sure are we?"),
    "Creators": (dashboard.page_lb_creators, None, "Which companies build the top models."),
    "Distribution": (dashboard.page_lb_distribution, None, "How the scores are spread."),
    "Data quality": (dashboard.page_lb_quality, None, "Missing values, rejected records and duplicates."),
    "Explore": (dashboard.page_lb_explore, None, "Search, filter, compare and download the data."),
    "Pipeline": (dashboard.page_pipeline, None, "How the ETL pipeline ran and where the data came from."),
}

SOURCE_KIND = {"live_api": "ok", "saved_snapshot": "info", "synthetic_sample": "bad"}


# ------------------------------------------------------------ state / callbacks
def set_state(key, value):
    st.session_state[key] = value


def flip_theme():
    """The Bright/Dark switch. The choice is also kept in the address (?theme=dark), so a reload keeps it."""
    st.session_state["theme"] = "light" if st.session_state["theme"] == "dark" else "dark"
    st.query_params["theme"] = st.session_state["theme"]


if "theme" not in st.session_state:
    st.session_state["theme"] = "dark" if st.query_params.get("theme") == "dark" else "light"
mode = st.session_state["theme"]
st.session_state["_cards"] = 0          # numbers the cards of one page (see dashboard.section)


# --------------------------------------------------------------------- data
def load_first_results():
    """For every dataset: use the saved database if it has data, otherwise build
    it from the saved snapshot (no internet needed). One failing dataset never
    stops the others - it is stored as {"error": message}."""
    results = {}
    for ds in DATASETS:
        try:
            df, info = read_dataset(ds)
            if not df.empty:
                results[ds.id] = {"dataframe": df, "info": info, "saved": True, "save_error": None}
                continue
        except DatabaseError as error:
            log.warning("Could not read the database for %s: %s", ds.id, error)
        try:
            results[ds.id] = run_etl(ds, use_live=False)
        except Exception as error:
            log.exception("Startup failed for %s", ds.id)
            results[ds.id] = {"error": str(error)}
    return results


def refresh(datasets, use_live, slot):
    """Run the pipeline again for some datasets (with the loader animation).
    If one fails, its previous data is kept."""
    slot.markdown(ui.loader_html("Downloading and processing the data..."), unsafe_allow_html=True)
    failed = []
    for ds in datasets:
        try:
            st.session_state["results"][ds.id] = run_etl(ds, use_live=use_live)
        except Exception:
            log.exception("Pipeline failed for %s", ds.id)
            failed.append(ds.title)
    if failed:
        st.session_state["refresh_error"] = (
            f"The pipeline failed for: {', '.join(failed)}. "
            "Previous data was kept. Check the terminal log for details."
        )
    slot.empty()


st.markdown(build_css(mode), unsafe_allow_html=True)
loader_slot = st.empty()

if "results" not in st.session_state:
    loader_slot.markdown(ui.loader_html("Loading the AI model data..."), unsafe_allow_html=True)
    st.session_state["results"] = load_first_results()
    loader_slot.empty()

results = st.session_state["results"]

# ----------------------------------------------------------------- category
if st.session_state.get("category") not in CATEGORIES:
    st.session_state["category"] = CATEGORIES[0]
category = st.session_state["category"]
pages = LANGUAGE_PAGES if category == "Language Models" else LEADERBOARD_PAGES
category_datasets = datasets_in(category)

with st.container(key="topbar"):
    columns = st.columns(len(CATEGORIES) + 2)
    for index, (column, name) in enumerate(zip(columns, CATEGORIES)):
        column.button(name, key=f"tab_{index}", type="primary" if name == category else "secondary",
                      on_click=set_state, args=("category", name))
    columns[-1].button(
        "Switch to bright mode" if mode == "dark" else "Switch to dark mode", key="theme_switch", on_click=flip_theme,
        help="Switch to bright mode" if mode == "dark" else "Switch to dark mode")

# dataset chips (only for categories that have more than one dataset)
selected_id = st.session_state.get(f"dataset_{category}")
if selected_id not in [d.id for d in category_datasets]:
    selected_id = category_datasets[0].id
if category != "Language Models" and len(category_datasets) > 1:
    with st.container(key="datasets"):
        for column, d in zip(st.columns(len(category_datasets)), category_datasets):
            column.button(d.title, key=f"dataset_btn_{d.id}", type="primary" if d.id == selected_id else "secondary",
                          on_click=set_state, args=(f"dataset_{category}", d.id))

# ------------------------------------------------------------------ sidebar
page = st.session_state.get(f"page_{category}")
if page not in pages:
    page = list(pages)[0]

with st.sidebar:
    st.markdown(ui.brand_html(), unsafe_allow_html=True)
    st.markdown(ui.label_html("Views"), unsafe_allow_html=True)
    with st.container(key="nav"):
        for name in pages:
            st.button(name, key=f"nav_{category}_{name}", type="primary" if name == page else "secondary",
                      width="stretch", on_click=set_state, args=(f"page_{category}", name))

    st.markdown('<div class="side-rule"></div>' + ui.label_html(f"Data controls · {category}"),
                unsafe_allow_html=True)
    if st.button(
        "Fetch live data",
        type="primary",
        width="stretch",
        help="Download the newest data for this category from the APIs",
    ):
        refresh(category_datasets, True, loader_slot)
        st.rerun()
    if st.button(
        "Reload saved snapshot",
        width="stretch",
        help="Use the saved files, no internet needed",
    ):
        refresh(category_datasets, False, loader_slot)
        st.rerun()

# ------------------------------------------------------------------- header
draw_page, fixed_id, description = pages[page]
ds = BY_ID[fixed_id or selected_id]
page_title = f"{page}" if category == "Language Models" else f"{category}: {ds.title}"

ui.hero_eyebrow(f"{category}  /  {page}")
st.title(page_title, anchor=False)

result = results.get(ds.id, {"error": "not loaded"})
if "error" in result:
    st.error(
        f"No data is available for '{ds.title}': {result['error']} "
        "Press 'Fetch live data' or check the files in data/raw and data/sample."
    )
    st.stop()

df, info = result["dataframe"], result["info"]
when = info.get("data_time") or "date unknown"
source = info["source"]
ui.hero_details(
    description,
    ui.pill_html(SOURCE_KIND.get(source, "info"), dashboard.SOURCE_TEXT.get(source, source)),
    [ui.chip_html("UTC", when), ui.chip_html("Models", f"{len(df):,}")],
    ds.attribution,
)

if info["source"] == "synthetic_sample":
    st.error("This is made-up demo data, not real models.")
if info.get("warning"):
    st.warning(info["warning"])
if not result["saved"]:
    st.warning(
        f"The data could not be stored in the database ({result['save_error']}). "
        "It is shown for this session only."
    )
if "refresh_error" in st.session_state:
    st.error(st.session_state.pop("refresh_error"))

# ---------------------------------------------------------------- the page
try:
    draw_page(ds, df, info, mode)
except Exception:
    log.exception("Page %s failed", page)
    st.error("This section could not be displayed. Other sections still work.")
