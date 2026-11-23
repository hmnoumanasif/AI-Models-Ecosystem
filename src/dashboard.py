"""The pages of the Streamlit app. Each page is one small function."""
import html
import inspect
import logging

import pandas as pd
import streamlit as st

from src.analysis import eda, leaderboard
from src.config import get_api_key
from src.datasets import DATASETS
from src.formatting import fmt_int, fmt_percent, fmt_score, fmt_tokens
from src.loading.database import DatabaseError, read_run_history
from src.ui import plots as charts                      # interactive Plotly charts
from src.ui.components import facts, kpis, subhead
from src.ui.plots import PLOT_CONFIG
from src.ui.tables import data_table

log = logging.getLogger(__name__)
CC = st.column_config

# st.plotly_chart takes width="stretch" in newer Streamlit versions, use_container_width in older ones.
FULL_WIDTH = ({"width": "stretch"} if "width" in inspect.signature(st.plotly_chart).parameters
              else {"use_container_width": True})

SOURCE_TEXT = {
    "live_api": "Live API",
    "saved_snapshot": "Saved snapshot (real data downloaded earlier)",
    "synthetic_sample": "Synthetic demo data (NOT real)",
}


def show_chart(make_chart, *args, empty_message="Not enough data for this chart."):
    """Draw one chart. If it fails, only this chart shows a warning."""
    try:
        fig = make_chart(*args)
    except Exception:
        log.exception("Chart failed: %s", getattr(make_chart, "__name__", make_chart))
        st.warning("This chart could not be drawn. The other charts still work.")
        return
    if fig is None:
        st.info(empty_message)
        return
    try:
        st.plotly_chart(fig, theme=None, config=PLOT_CONFIG, **FULL_WIDTH)
    except Exception:
        log.exception("Chart could not be shown: %s", getattr(make_chart, "__name__", make_chart))
        st.warning("This chart could not be drawn. The other charts still work.")


def section(title, question="", color=None):
    """A card with a title and the question the chart answers.
    (`color` is kept so existing calls still work; every card uses the theme accent.)"""
    number = st.session_state.get("_cards", 0)
    st.session_state["_cards"] = number + 1
    box = st.container(key=f"card_{number}")
    question_html = f'<div class="card-q">{html.escape(question)}</div>' if question else ""
    box.markdown(f'<div class="card-head"><span class="swatch"></span>'
                 f'<span class="card-title">{html.escape(title)}</span></div>{question_html}',
                 unsafe_allow_html=True)
    return box


def model_table(df, columns=None):
    """A nicely formatted, sortable table of models."""
    config = {
        "model_name": CC.TextColumn("Model"), "provider": CC.TextColumn("Provider"),
        "model_id": CC.TextColumn("ID"),
        "context_length": CC.NumberColumn("Context (tokens)", format="localized"),
        "input_price_per_million": CC.NumberColumn("Input $/1M", format="$%.3f"),
        "output_price_per_million": CC.NumberColumn("Output $/1M", format="$%.3f"),
        "pricing_status": CC.TextColumn("Pricing"),
        "created_at": CC.DatetimeColumn("Created", format="YYYY-MM-DD"),
    }
    data_table(df[columns] if columns else df, config)


# ---------------------------------------------------------------- Overview
def page_overview(ds, df, info, mode):
    m = eda.overview_metrics(df)
    kpis([("Models", fmt_int(m["models"])), ("Providers", fmt_int(m["providers"])),
          ("Known pricing", fmt_int(m["known_pricing"])), ("Missing pricing", fmt_int(m["missing_pricing"])),
          ("Free models", fmt_int(m["free_models"])), ("Multimodal", fmt_int(m["multimodal"])),
          ("Known context window", fmt_int(m["known_context"])), ("Median context", fmt_tokens(m["median_context"]))])

    facts(eda.key_facts(df))

    left, right = st.columns(2)
    with left:
        with section("Top providers", "Which providers list the most models?"):
            counts = df["provider"].value_counts().head(10).rename_axis("provider").reset_index(name="models")
            show_chart(charts.bar_chart, counts, "provider", "models", "Models per provider",
                       "Number of models", mode)
    with right:
        with section("Pricing information", "How many models have a price, are free, or have no price?"):
            show_chart(charts.pricing_status_chart, df, mode)


# --------------------------------------------------------------- Providers
def page_providers(ds, df, info, mode):
    st.caption("Catalog share = share of the models in THIS catalog. "
               "It is not the real market share (usage and revenue are not in the data).")
    n = st.slider("Number of providers to show", 5, 30, 12)
    table = eda.provider_table(df)

    with section("Models per provider", "Which providers have the biggest catalogs?"):
        show_chart(charts.bar_chart, table.head(n), "provider", "models",
                   "Models per provider", "Number of models", mode)

    left, right = st.columns(2)
    with left:
        with section("Median input price", "Which providers are cheaper? (paid models, 3+ models)"):
            show_chart(charts.median_by_provider, df.pipe(eda.paid_models), "input_price_per_million",
                       "Median input price", "USD per 1M tokens", mode, n)
    with right:
        with section("Median context window", "Which providers offer longer context? (3+ models)"):
            show_chart(charts.median_by_provider, df, "context_length", "Median context window",
                       "Tokens", mode, n)

    subhead("Provider comparison table", "Click a column header to sort.")
    data_table(table, {
        "provider": CC.TextColumn("Provider"), "models": CC.NumberColumn("Models"),
        "catalog_share_pct": CC.NumberColumn("Catalog share", format="%.1f%%"),
        "median_context": CC.NumberColumn("Median context", format="localized"),
        "median_input_price": CC.NumberColumn("Median input $/1M", format="$%.3f"),
        "median_output_price": CC.NumberColumn("Median output $/1M", format="$%.3f"),
        "multimodal_models": CC.NumberColumn("Multimodal models"),
        "multimodal_pct": CC.NumberColumn("Multimodal", format="%.0f%%"),
    })


# --------------------------------------------------------- Context windows
def page_context(ds, df, info, mode):
    stats = eda.context_stats(df)
    if not stats:
        st.info("No context-window values are available.")
        return
    kpis([(label, fmt_tokens(stats[key])) for label, key in
          [("Smallest", "min"), ("Median", "median"), ("Average", "mean"),
           ("90th percentile", "p90"), ("Largest", "max")]], columns=5)

    with section("Distribution", "Are most context windows small or large?"):
        show_chart(charts.context_histogram, df, mode)
        st.caption("The average is pulled up by a few huge models, so the median describes a typical model better.")

    with section("Percentiles", "What context size do 25%, 50%, ... of models reach?"):
        percentiles = pd.DataFrame({"Percentile": ["25%", "50%", "75%", "90%", "99%"],
                                    "Context (tokens)": [stats[k] for k in ["p25", "median", "p75", "p90", "p99"]]})
        data_table(percentiles, {"Context (tokens)": CC.NumberColumn(format="localized")})

    with section("Unusually large context windows",
                 "Which models are outliers? (above Q3 + 1.5 x IQR on a log scale)"):
        outliers = eda.context_outliers(df)
        if outliers.empty:
            st.info("No outliers found.")
        else:
            model_table(outliers, ["model_name", "provider", "context_length"])


# ----------------------------------------------------------------- Pricing
def page_pricing(ds, df, info, mode):
    st.caption("Prices are USD per 1 million tokens. A missing price is NOT a free model: "
               "free means the source says the price is exactly 0.")
    status = df["pricing_status"].value_counts()
    kpis([(name.capitalize(), fmt_int(status.get(name, 0))) for name in ["paid", "free", "partial", "missing"]])

    with section("Price spread by provider", "How different are prices inside each provider?"):
        show_chart(charts.price_boxplot, df, mode)
    with section("Price vs context window", "Do models with bigger context windows cost more?"):
        show_chart(charts.price_vs_context, df, mode)
        corr = eda.correlation_table(df)
        if not corr.empty:
            value = corr.loc["context length", "input price"]
            st.caption(f"Spearman correlation between context length and input price: {value:.2f}. "
                       "Correlation only describes a pattern; it does not prove that one thing causes the other.")

    with section("Cost calculator", "How much would a workload cost on each model?"):
        a, b, c = st.columns(3)
        input_tokens = a.number_input("Input tokens", 0, 1_000_000_000, 1_000_000, step=100_000)
        output_tokens = b.number_input("Output tokens", 0, 1_000_000_000, 200_000, step=100_000)
        count = c.slider("Show cheapest", 5, 50, 15)
        costs = eda.cost_estimate(df, input_tokens, output_tokens).head(count)
        st.caption("Assumes the listed per-token prices, no caching or discounts. "
                   "Only models with both prices known are included.")
        if costs.empty:
            st.info("No models with known prices.")
        else:
            data_table(costs[["model_name", "provider", "pricing_status", "estimated_cost_usd"]], {
                "model_name": "Model", "provider": "Provider", "pricing_status": "Pricing",
                "estimated_cost_usd": CC.NumberColumn("Estimated cost", format="$%.4f")})

    with st.expander("Free models and models with missing prices"):
        st.markdown("**Free (price is exactly 0)**")
        model_table(df[df["pricing_status"] == "free"], ["model_name", "provider", "pricing_status"])
        st.markdown("**Missing or partial price** (includes variable-price routers, where the API uses -1)")
        model_table(df[df["pricing_status"].isin(["missing", "partial"])],
                    ["model_name", "provider", "pricing_status"])


# -------------------------------------------------------------- Modalities
def page_modalities(ds, df, info, mode):
    st.caption("Modalities are exactly what the source lists. Nothing is guessed.")
    left, right = st.columns(2)
    with left:
        with section("Input types", "What can models read?"):
            show_chart(charts.bar_chart, eda.modality_counts(df, "input_modalities"), "modality",
                       "models", "Input modalities", "Number of models", mode)
    with right:
        with section("Output types", "What can models produce?"):
            show_chart(charts.bar_chart, eda.modality_counts(df, "output_modalities"), "modality",
                       "models", "Output modalities", "Number of models", mode)

    with section("Input support", "How many models accept image, audio, video or file input?"):
        data_table(eda.input_support_table(df), {"share_pct": CC.NumberColumn("Share of models", format="%.1f%%")})
    with section("Modality coverage by provider", "Which big providers support which input types?"):
        data_table(eda.provider_modality_table(df))
    with section("Most common modality combinations", "What do typical models look like?"):
        combos = df["modality"].value_counts().head(8).rename_axis("modality").reset_index(name="models")
        show_chart(charts.bar_chart, combos, "modality", "models", "Modality combinations",
                   "Number of models", mode)


# ------------------------------------------------------------ Data quality
def page_quality(ds, df, info, mode):
    kpis([("Completeness", fmt_percent(eda.completeness_pct(df)),
           "Share of filled cells in context, prices, modalities and date."),
          ("Records rejected", fmt_int(info["rejected_count"])),
          ("Duplicates removed", fmt_int(info["duplicate_count"])),
          ("Negative prices set to missing", fmt_int(df["price_was_negative"].sum()))])

    with section("Missing values", "Which fields have gaps?"):
        show_chart(charts.missing_chart, df, mode, empty_message="No missing values.")
        data_table(eda.missing_table(df), {"missing_pct": CC.NumberColumn("Missing %", format="%.1f%%")})

    with section("Rejected records", "Which records failed Pydantic validation, and why?"):
        rejected = info.get("rejected") or []
        if rejected:
            data_table(pd.DataFrame(rejected))
        else:
            st.success("No records were rejected in the last run.")


# ----------------------------------------------------------------- Explore
CONTEXT_STEPS = [0, 8_000, 32_000, 128_000, 200_000, 1_000_000, 10_000_000]


def page_explore(ds, df, info, mode):
    with st.container(border=True):
        a, b = st.columns(2)
        search = a.text_input("Search name or ID")
        providers = b.multiselect("Provider", sorted(df["provider"].unique()))
        c, d, e = st.columns(3)
        input_types = c.multiselect("Must accept input", list(eda.INPUT_FLAGS))
        statuses = d.multiselect("Pricing", ["paid", "free", "partial", "missing"])
        low, high = e.select_slider("Context window (tokens)", CONTEXT_STEPS, value=(0, CONTEXT_STEPS[-1]),
                                    format_func=fmt_tokens)
        max_price = st.number_input("Max input price (USD per 1M tokens, 0 = no limit)", 0.0, value=0.0)

    result = eda.filter_models(df, search, providers, input_types, statuses,
                               low if low > 0 else None, high if high < CONTEXT_STEPS[-1] else None,
                               max_price if max_price > 0 else None)
    sort_col, order = st.columns(2)
    sort_by = sort_col.selectbox("Sort by", ["model_name", "provider", "context_length",
                                             "input_price_per_million", "output_price_per_million", "created_at"])
    descending = order.toggle("Descending")
    result = result.sort_values(sort_by, ascending=not descending, na_position="last")

    st.markdown(f"**{len(result):,} of {len(df):,} models match**")
    if result.empty:
        st.info("No model matches these filters. Try removing one.")
        return
    model_table(result, ["model_name", "provider", "context_length", "input_price_per_million",
                         "output_price_per_million", "pricing_status", "input_modalities", "created_at"])
    st.download_button("Download filtered data (CSV)", eda.to_csv_bytes(result),
                       "ai_models_filtered.csv", "text/csv")

    with st.expander("Compare models side by side"):
        chosen = st.multiselect("Pick 2 to 4 models", result["model_id"].tolist(), max_selections=4)
        if len(chosen) >= 2:
            compare = result[result["model_id"].isin(chosen)].set_index("model_name")
            data_table(compare[["provider", "context_length", "input_price_per_million",
                                "output_price_per_million", "pricing_status", "input_modalities",
                                "output_modalities"]].T.astype(str), index=True, index_label="Field")
        else:
            st.caption("Select at least two models.")


# ------------------------------------------------------- Leaderboard pages
# These pages work for ANY leaderboard dataset (image, video, speech, benchmarks).
HIDDEN_COLUMNS = ["model_id", "slug", "ci_low", "ci_high"]


def lb_subtitle(ds):
    direction = "Higher" if ds.higher_is_better else "Lower"
    return f"{ds.metric_label} · {direction} is better"


def lb_table(df, ds):
    data_table(df[[c for c in df.columns if c not in HIDDEN_COLUMNS]], {
        "model_name": CC.TextColumn("Model"), "creator": CC.TextColumn("Creator"),
        "rank": CC.NumberColumn("Rank"), "ci_95": CC.NumberColumn("+/- 95% CI", format="%.0f"),
        "release_date": CC.DatetimeColumn("Released", format="YYYY-MM-DD"),
    })


def page_lb_ranking(ds, df, info, mode):
    stats = leaderboard.lb_stats(df, ds)
    if not stats:
        st.info("This dataset has no scores yet.")
        return
    kpis([("Models", fmt_int(stats["models"])), ("Creators", fmt_int(stats["creators"])),
          ("Leader", stats["leader"], f"{stats['leader']} · best score: {fmt_score(stats['best'])}"),
          ("Median score", fmt_score(stats["median"]))])

    top_n = st.slider("Models to show", 5, 30, 12, key=f"top_n_{ds.id}")
    with section(ds.title, lb_subtitle(ds), ds.color):
        show_chart(charts.ranking_chart, df, ds, top_n, mode)
        if ds.ci_column:
            st.caption("Whiskers show the 95% confidence interval. The vertical axis does not start at zero.")

    if ds.ci_column:
        tied = leaderboard.tied_with_leader(df, ds)
        with section("Statistically tied with the leader",
                     "Their confidence intervals overlap the leader's, so the data cannot prove the leader is better."):
            if len(tied) <= 1:
                st.write("The leader is clearly ahead of every other model.")
            else:
                st.markdown("\n".join(f"- {name}" for name in tied["model_name"]))

    subhead(f"Top {min(top_n, len(df))} models")
    lb_table(leaderboard.best_first(df, ds).head(top_n), ds)


def page_lb_creators(ds, df, info, mode):
    st.caption("Share = share of the models in THIS leaderboard. It is not market share.")
    table = leaderboard.creator_table(df, ds)
    if table.empty:
        st.info("No data.")
        return
    left, right = st.columns(2)
    with left:
        with section("Models per creator", "Which companies appear most often?", ds.color):
            counts = table.sort_values("models", ascending=False).head(12)
            show_chart(charts.bar_chart, counts, "creator", "models", "Models per creator", "Number of models", mode)
    with right:
        with section("Best score per creator", lb_subtitle(ds), ds.color):
            show_chart(charts.bar_chart, table.head(12), "creator", "best_score", "Best score", ds.metric_label, mode)
    subhead("Creator comparison", "Click a column header to sort.")
    data_table(table, {
        "creator": "Creator", "models": "Models", "best_score": CC.NumberColumn("Best score", format="%.3f"),
        "mean_score": CC.NumberColumn("Mean score", format="%.3f"),
        "median_score": CC.NumberColumn("Median score", format="%.3f"),
        "share_pct": CC.NumberColumn("Share", format="%.1f%%")})


def page_lb_distribution(ds, df, info, mode):
    stats = leaderboard.lb_stats(df, ds)
    if not stats:
        st.info("This dataset has no scores yet.")
        return
    kpis([(label, fmt_score(stats[key])) for label, key in
          [("Lowest", "min"), ("25%", "p25"), ("Median", "median"), ("75%", "p75"), ("Highest", "max")]], columns=5)
    with section("Distribution", "Are most models close together, or spread out?", ds.color):
        show_chart(charts.metric_histogram, df, ds, mode)
    if ds.ci_column:
        with section("Least certain scores", "Models with the widest 95% confidence interval. "
                                             "A wide interval means few votes, so the score is less reliable."):
            lb_table(leaderboard.least_certain(df, ds), ds)


def page_lb_quality(ds, df, info, mode):
    shown = df.drop(columns=[c for c in HIDDEN_COLUMNS if c in df.columns])
    kpis([("Completeness", fmt_percent(shown.notna().to_numpy().mean() * 100)),
          ("Records rejected", fmt_int(info["rejected_count"])),
          ("Duplicates removed", fmt_int(info["duplicate_count"])),
          ("Missing scores", fmt_int(df[ds.metric].isna().sum()))])
    with section("Missing values", "Which fields have gaps?"):
        show_chart(charts.missing_chart, shown, mode, empty_message="No missing values.")
        data_table(eda.missing_table(shown), {"missing_pct": CC.NumberColumn("Missing %", format="%.1f%%")})
    with section("Rejected records", "Which records failed Pydantic validation, and why?"):
        rejected = info.get("rejected") or []
        if rejected:
            data_table(pd.DataFrame(rejected))
        else:
            st.success("No records were rejected in the last run.")


def page_lb_explore(ds, df, info, mode):
    with st.container(border=True):
        a, b = st.columns(2)
        search = a.text_input("Search model or creator", key=f"search_{ds.id}")
        creators = b.multiselect("Creator", sorted(df["creator"].unique()), key=f"creators_{ds.id}")
        scores = df[ds.metric].dropna()
        low, high = (None, None)
        if len(scores) > 1 and scores.min() < scores.max():
            low, high = st.slider(ds.metric_label, float(scores.min()), float(scores.max()),
                                  (float(scores.min()), float(scores.max())), key=f"range_{ds.id}")
    result = leaderboard.filter_leaderboard(df, ds, search, creators, low, high)
    sort_col, order = st.columns(2)
    sort_by = sort_col.selectbox("Sort by", [ds.metric, "model_name", "creator"], key=f"sort_{ds.id}")
    descending = order.toggle("Descending", value=ds.higher_is_better, key=f"desc_{ds.id}")
    result = result.sort_values(sort_by, ascending=not descending, na_position="last")

    st.markdown(f"**{len(result):,} of {len(df):,} models match**")
    if result.empty:
        st.info("No model matches these filters. Try removing one.")
        return
    lb_table(result, ds)
    st.download_button("Download filtered data (CSV)", eda.to_csv_bytes(result), f"{ds.id}_filtered.csv",
                       "text/csv", key=f"download_{ds.id}")
    with st.expander("Compare models side by side"):
        chosen = st.multiselect("Pick 2 to 4 models", result["model_id"].tolist(), max_selections=4,
                                key=f"compare_{ds.id}")
        if len(chosen) >= 2:
            compare = result[result["model_id"].isin(chosen)].set_index("model_name")
            data_table(compare.drop(columns=[c for c in HIDDEN_COLUMNS if c in compare.columns]).T.astype(str),
                       index=True, index_label="Field")
        else:
            st.caption("Select at least two models.")


def page_benchmarks(ds, df, info, mode):
    """Language model benchmarks: the ranking plus cost, speed and price comparisons."""
    page_lb_ranking(ds, df, info, mode)
    with section("Cost vs intelligence", "Do smarter models cost more to run? "
                                         "(cost of one task of the Intelligence Index benchmark)", ds.color):
        show_chart(charts.scatter_chart, df, "cost_per_task_usd", "intelligence_index",
                   "Cost per task (USD, log scale)", "Intelligence Index", "Cost vs intelligence", mode, True, False)
    with section("Speed vs intelligence", "Are smarter models slower?", ds.color):
        show_chart(charts.scatter_chart, df, "output_tokens_per_second", "intelligence_index",
                   "Output speed (tokens per second)", "Intelligence Index", "Speed vs intelligence", mode)
    with section("Price vs intelligence", "Does a higher token price buy a smarter model?", ds.color):
        show_chart(charts.scatter_chart, df, "input_price_per_million", "intelligence_index",
                   "Input price (USD per 1M tokens, log scale)", "Intelligence Index", "Price vs intelligence",
                   mode, True, False)
        corr = leaderboard.spearman_table(df, ["intelligence_index", "cost_per_task_usd"])
        if not corr.empty:
            st.caption(f"Spearman correlation between intelligence and cost per task: "
                       f"{corr.loc['intelligence_index', 'cost_per_task_usd']:.2f}. "
                       "Correlation describes a pattern; it does not prove that one thing causes the other.")
    subhead("All benchmark data")
    data_table(df.drop(columns=["model_id", "slug"]), {
        "model_name": "Model", "creator": "Creator", "intelligence_index": "Intelligence",
        "coding_index": "Coding", "agentic_index": "Agentic",
        "cost_per_task_usd": CC.NumberColumn("Cost / task", format="$%.2f"),
        "input_price_per_million": CC.NumberColumn("Input $/1M", format="$%.2f"),
        "output_price_per_million": CC.NumberColumn("Output $/1M", format="$%.2f"),
        "release_date": CC.DatetimeColumn("Released", format="YYYY-MM-DD")})


# ---------------------------------------------------------------- Pipeline
def page_pipeline(ds, df, info, mode):
    results = st.session_state.get("results", {})
    subhead("All datasets")
    rows = []
    for d in DATASETS:
        result = results.get(d.id, {})
        if "error" in result or not result:
            rows.append({"Dataset": d.title, "Category": d.category, "Source": "FAILED", "Rows": 0,
                         "Data time (UTC)": "", "API key set": get_api_key(d.key_env) is not None,
                         "Note": result.get("error", "not loaded")})
            continue
        i = result["info"]
        rows.append({"Dataset": d.title, "Category": d.category, "Source": SOURCE_TEXT.get(i["source"], i["source"]),
                     "Rows": i["loaded_count"], "Data time (UTC)": i.get("data_time") or "n/a (synthetic)",
                     "API key set": get_api_key(d.key_env) is not None, "Note": i.get("warning") or ""})
    data_table(pd.DataFrame(rows))
    st.caption("A key is only needed for the live download. The key itself is never shown.")

    subhead(f"Last run: {ds.title}")
    summary = pd.DataFrame({"Item": ["Source", "Source detail", "Data time (UTC)", "Run time (UTC)", "Raw records",
                                     "Valid records", "Rejected", "Duplicates removed", "Rows loaded", "Duration (s)"],
                            "Value": [SOURCE_TEXT.get(info["source"], info["source"]), info["source_detail"],
                                      info.get("data_time") or "n/a (synthetic data)", info["run_at"],
                                      info["raw_count"], info["valid_count"], info["rejected_count"],
                                      info["duplicate_count"], info["loaded_count"], info["duration_seconds"]]})
    data_table(summary.astype(str))

    subhead("Run history")
    try:
        data_table(read_run_history(ds.id))
    except DatabaseError as error:
        st.warning(f"Run history is not available: {error}")

    subhead("The four ETL steps")
    st.markdown("1. **Extract** - download JSON from the API (retry on temporary errors, API key from `.env`).\n"
                "2. **Validate** - Pydantic checks every record; bad records are rejected with a reason.\n"
                "3. **Transform** - pandas builds one clean table for the dataset.\n"
                "4. **Load** - the table is saved to SQLite in one transaction, and a CSV is written.")
    st.caption("On Streamlit Community Cloud the local file system is temporary: "
               "the database can be reset when the app restarts, and the app rebuilds it automatically.")
