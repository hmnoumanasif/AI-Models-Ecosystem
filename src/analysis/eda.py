"""EDA functions. Each one takes the clean DataFrame and returns a small
table or dictionary. They contain no Streamlit code, so they are easy to test."""
import numpy as np
import pandas as pd

PRICE_COLUMNS = ["input_price_per_million", "output_price_per_million"]
INPUT_FLAGS = {"image": "accepts_image", "audio": "accepts_audio",
               "video": "accepts_video", "file": "accepts_file"}


def paid_models(df):
    """Models with a real, non-zero price. Free and missing prices are left out
    so they do not distort medians."""
    return df[df["pricing_status"] == "paid"]


def overview_metrics(df):
    """The headline numbers for the Overview page."""
    status = df["pricing_status"].value_counts()
    return {
        "models": len(df),
        "providers": int(df["provider"].nunique()),
        "known_pricing": int(status.get("paid", 0) + status.get("free", 0)),
        "missing_pricing": int(status.get("missing", 0) + status.get("partial", 0)),
        "free_models": int(status.get("free", 0)),
        "multimodal": int(df["is_multimodal"].sum()),
        "known_context": int(df["context_length"].notna().sum()),
        "median_context": df["context_length"].median(),
    }


def key_facts(df):
    """Sentences computed from the data (nothing is typed in by hand)."""
    facts = []
    if df.empty:
        return facts
    counts = df["provider"].value_counts()
    facts.append(f"{counts.index[0]} has the most models in this catalog: "
                 f"{counts.iloc[0]} of {len(df)} ({counts.iloc[0] / len(df):.0%}).")
    ctx = df["context_length"].dropna()
    if not ctx.empty:
        biggest = df.loc[ctx.idxmax()]
        facts.append(f"The largest context window is {int(ctx.max()):,} tokens ({biggest['model_name']}).")
    paid = paid_models(df)
    if not paid.empty:
        cheapest = paid.loc[paid["input_price_per_million"].idxmin()]
        facts.append(f"The cheapest paid input price is ${cheapest['input_price_per_million']:.3f} "
                     f"per 1M tokens ({cheapest['model_name']}).")
    free = int((df["pricing_status"] == "free").sum())
    missing = int((df["pricing_status"] == "missing").sum())
    facts.append(f"{free} models are free and {missing} have no price information (not the same thing).")
    return facts


def pricing_status_counts(df):
    order = ["paid", "free", "partial", "missing"]
    counts = df["pricing_status"].value_counts().reindex(order, fill_value=0)
    return counts.rename_axis("pricing_status").reset_index(name="models")


def provider_table(df):
    """One row per provider. Share = share of THIS catalog, not market share."""
    if df.empty:
        return pd.DataFrame()
    paid = paid_models(df)
    table = df.groupby("provider").agg(
        models=("model_id", "count"),
        median_context=("context_length", "median"),
        multimodal_models=("is_multimodal", "sum"),
    )
    table["catalog_share_pct"] = table["models"] / len(df) * 100
    table["multimodal_pct"] = table["multimodal_models"] / table["models"] * 100
    medians = paid.groupby("provider")[PRICE_COLUMNS].median()
    table = table.join(medians.rename(columns={
        "input_price_per_million": "median_input_price",
        "output_price_per_million": "median_output_price"}))
    return table.reset_index().sort_values("models", ascending=False).reset_index(drop=True)


def top_providers(df, n):
    """Names of the n providers with the most models."""
    return df["provider"].value_counts().head(n).index.tolist()


def context_stats(df):
    ctx = df["context_length"].dropna()
    if ctx.empty:
        return {}
    return {
        "min": ctx.min(), "p25": ctx.quantile(0.25), "median": ctx.median(),
        "mean": ctx.mean(), "p75": ctx.quantile(0.75), "p90": ctx.quantile(0.90),
        "p99": ctx.quantile(0.99), "max": ctx.max(),
    }


def context_outliers(df):
    """Unusually large context windows.
    Context sizes are very skewed, so we work on log10 values and flag anything
    above Q3 + 1.5 x IQR (the usual boxplot rule)."""
    ctx = df.dropna(subset=["context_length"])
    if len(ctx) < 4:
        return ctx.iloc[0:0]
    logs = np.log10(ctx["context_length"])
    q1, q3 = logs.quantile(0.25), logs.quantile(0.75)
    limit = q3 + 1.5 * (q3 - q1)
    out = ctx[logs > limit]
    return out.sort_values("context_length", ascending=False)


def cost_estimate(df, input_tokens, output_tokens):
    """Cost of one workload for every model whose two prices are both known.
    cost = input_tokens x input price + output_tokens x output price"""
    known = df[df["pricing_status"].isin(["paid", "free"])].copy()
    known["estimated_cost_usd"] = (
        input_tokens * known["input_price_per_million"] / 1_000_000
        + output_tokens * known["output_price_per_million"] / 1_000_000)
    return known.sort_values("estimated_cost_usd").reset_index(drop=True)


def modality_counts(df, column):
    """Count how many models list each modality in a comma-separated column."""
    values = []
    for text in df[column].dropna():
        values.extend(part.strip() for part in text.split(",") if part.strip())
    counts = pd.Series(values, dtype="object").value_counts()
    return counts.rename_axis("modality").reset_index(name="models")


def input_support_table(df):
    rows = [{"input type": name, "models": int(df[col].sum()),
             "share_pct": df[col].mean() * 100 if len(df) else 0}
            for name, col in INPUT_FLAGS.items()]
    return pd.DataFrame(rows)


def provider_modality_table(df, n=10):
    """For the biggest providers: how many models accept each input type."""
    top = df[df["provider"].isin(top_providers(df, n))]
    table = top.groupby("provider")[list(INPUT_FLAGS.values())].sum()
    table.columns = list(INPUT_FLAGS.keys())
    table.insert(0, "models", top.groupby("provider").size())
    return table.sort_values("models", ascending=False).reset_index()


def missing_table(df):
    """Missing values per column. Pricing/context are the important ones."""
    table = pd.DataFrame({
        "column": df.columns,
        "missing": [int(df[c].isna().sum()) for c in df.columns],
    })
    table["missing_pct"] = table["missing"] / max(len(df), 1) * 100
    return table.sort_values("missing", ascending=False).reset_index(drop=True)


def completeness_pct(df):
    """Share of cells that are filled in, over the important analysis columns."""
    columns = ["context_length", *PRICE_COLUMNS, "input_modalities", "output_modalities", "created_at"]
    if df.empty:
        return 0.0
    return float(df[columns].notna().to_numpy().mean() * 100)


def correlation_table(df):
    """Spearman correlation of context length and prices (paid models, log10).
    Needs at least 5 models. Correlation does NOT prove cause and effect."""
    paid = paid_models(df).dropna(subset=["context_length", *PRICE_COLUMNS])
    paid = paid[(paid[PRICE_COLUMNS] > 0).all(axis=1)]   # log10 needs prices above 0
    if len(paid) < 5:
        return pd.DataFrame()
    logs = np.log10(paid[["context_length", *PRICE_COLUMNS]])
    logs.columns = ["context length", "input price", "output price"]
    return logs.corr(method="spearman")


def filter_models(df, search="", providers=None, input_types=None, statuses=None,
                  min_context=None, max_context=None, max_input_price=None):
    """Apply all filters together (every filter must match)."""
    result = df
    if search:
        text = search.lower()
        match = (result["model_name"].str.lower().str.contains(text, regex=False)
                 | result["model_id"].str.lower().str.contains(text, regex=False))
        result = result[match]
    if providers:
        result = result[result["provider"].isin(providers)]
    for name in input_types or []:
        result = result[result[INPUT_FLAGS[name]]]
    if statuses:
        result = result[result["pricing_status"].isin(statuses)]
    if min_context is not None:
        result = result[result["context_length"] >= min_context]
    if max_context is not None:
        result = result[result["context_length"] <= max_context]
    if max_input_price is not None:
        result = result[result["input_price_per_million"] <= max_input_price]
    return result


def to_csv_bytes(df):
    """Bytes for the download button."""
    return df.to_csv(index=False).encode("utf-8")
