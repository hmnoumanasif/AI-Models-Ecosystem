"""EDA functions for leaderboard datasets (image, video, speech, benchmarks).
They work for any dataset because the dataset description (ds) says which
column is the score, whether higher is better, and where the confidence interval is."""
import numpy as np
import pandas as pd


def best_first(df, ds):
    """Sort so the best model is on top (highest score, or lowest for error rates)."""
    return df.sort_values(ds.metric, ascending=not ds.higher_is_better, na_position="last").reset_index(drop=True)


def lb_stats(df, ds):
    """Headline numbers of a leaderboard."""
    scores = df[ds.metric].dropna()
    if scores.empty:
        return {}
    leader = best_first(df, ds).iloc[0]
    return {
        "models": len(df), "creators": int(df["creator"].nunique()), "leader": leader["model_name"],
        "best": leader[ds.metric], "median": scores.median(), "mean": scores.mean(),
        "min": scores.min(), "max": scores.max(), "p25": scores.quantile(0.25), "p75": scores.quantile(0.75),
        "missing_scores": int(df[ds.metric].isna().sum()),
    }


def creator_table(df, ds):
    """One row per creator (company). 'share' is the share of models in THIS table."""
    if df.empty:
        return pd.DataFrame()
    best = "max" if ds.higher_is_better else "min"
    table = df.groupby("creator").agg(
        models=("model_id", "count"), best_score=(ds.metric, best),
        mean_score=(ds.metric, "mean"), median_score=(ds.metric, "median"))
    table["share_pct"] = table["models"] / len(df) * 100
    table = table.reset_index().sort_values(["best_score", "models"], ascending=[not ds.higher_is_better, False])
    return table.reset_index(drop=True)


def tied_with_leader(df, ds):
    """Models whose 95% confidence interval overlaps the leader's.
    For these models the data cannot prove that the leader is really better."""
    if not ds.ci_column or df.empty:
        return df.iloc[0:0]
    ranked = best_first(df.dropna(subset=[ds.metric, ds.ci_column]), ds)
    if ranked.empty:
        return ranked
    leader = ranked.iloc[0]
    overlaps = (ranked[ds.metric] + ranked[ds.ci_column]) >= (leader[ds.metric] - leader[ds.ci_column])
    return ranked[overlaps]


def least_certain(df, ds, n=8):
    """Models with the widest confidence interval (their score is the least reliable)."""
    if not ds.ci_column:
        return df.iloc[0:0]
    return df.dropna(subset=[ds.ci_column]).sort_values(ds.ci_column, ascending=False).head(n)


def spearman_table(df, columns, labels=None):
    """Spearman correlation between columns (needs 5 complete rows).
    Correlation describes a pattern; it does NOT prove cause and effect."""
    data = df[columns].dropna()
    if len(data) < 5:
        return pd.DataFrame()
    corr = data.corr(method="spearman")
    if labels:
        corr = corr.rename(index=labels, columns=labels)
    return corr


def log_columns(df, columns):
    """Copy of df where the given columns are replaced by log10 values
    (rows with zero or negative values in them are removed)."""
    data = df.copy()
    for column in columns:
        data = data[data[column].isna() | (data[column] > 0)]
        data[column] = np.log10(data[column])
    return data


def filter_leaderboard(df, ds, search="", creators=None, min_score=None, max_score=None):
    """Apply all filters together (every filter must match)."""
    result = df
    if search:
        text = search.lower()
        result = result[result["model_name"].str.lower().str.contains(text, regex=False)
                        | result["creator"].str.lower().str.contains(text, regex=False)]
    if creators:
        result = result[result["creator"].isin(creators)]
    if min_score is not None:
        result = result[result[ds.metric] >= min_score]
    if max_score is not None:
        result = result[result[ds.metric] <= max_score]
    return result
