"""Matplotlib / Seaborn charts. Each function returns a figure, or None when
there is not enough data. `mode` is "light" or "dark"."""
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from src.analysis import eda, leaderboard
from src.theme import THEMES, chart_rc


def _finish(fig, ax, title, xlabel, ylabel):
    ax.set_title(title, loc="left", fontweight="bold")
    ax.set_xlabel(xlabel)
    ax.set_ylabel(ylabel)
    fig.tight_layout()
    return fig


def bar_chart(table, label_col, value_col, title, xlabel, mode, color="accent"):
    """Horizontal bar chart (biggest bar on top)."""
    if table is None or table.empty:
        return None
    colors = THEMES[mode]
    with plt.rc_context(chart_rc(mode)):
        fig, ax = plt.subplots(figsize=(8, max(2.5, 0.35 * len(table) + 1)))
        ax.barh(table[label_col].astype(str), table[value_col], color=colors[color])
        ax.invert_yaxis()
        ax.grid(axis="y", visible=False)
        biggest = table[value_col].max()
        whole = (table[value_col] % 1 == 0).all() or biggest >= 100
        pattern = " {:,.0f}" if whole else (" {:,.3f}" if biggest < 1 else " {:,.2f}")
        for y, value in enumerate(table[value_col]):
            ax.text(value, y, pattern.format(value), va="center", fontsize=8, color=colors["textColor"])
        return _finish(fig, ax, title, xlabel, "")


def context_histogram(df, mode):
    ctx = df["context_length"].dropna()
    if ctx.empty:
        return None
    colors = THEMES[mode]
    with plt.rc_context(chart_rc(mode)):
        fig, ax = plt.subplots(figsize=(8, 4))
        bins = np.logspace(np.log10(ctx.min()), np.log10(ctx.max()), 25) if ctx.min() < ctx.max() else 5
        ax.hist(ctx, bins=bins, color=colors["accent"], edgecolor=colors["backgroundColor"])
        ax.set_xscale("log")
        ax.axvline(ctx.median(), color=colors["accent2"], linestyle="--", label=f"median: {ctx.median():,.0f}")
        ax.legend()
        return _finish(fig, ax, "How big are context windows?", "Context window (tokens, log scale)",
                       "Number of models")


def median_by_provider(df, column, title, xlabel, mode, n=12, min_models=3):
    """Median of one column for the biggest providers."""
    names = [p for p in eda.top_providers(df, n) if (df["provider"] == p).sum() >= min_models]
    data = df[df["provider"].isin(names)].groupby("provider")[column].median().dropna()
    data = data.sort_values(ascending=False).reset_index()
    return bar_chart(data, "provider", column, title, xlabel, mode)


def price_boxplot(df, mode, n=10):
    """Input and output price boxes side by side for each big provider."""
    paid = eda.paid_models(df)
    names = eda.top_providers(paid, n) if not paid.empty else []
    if len(paid[paid["provider"].isin(names)]) < 2:
        return None
    colors = THEMES[mode]
    with plt.rc_context(chart_rc(mode)):
        fig, ax = plt.subplots(figsize=(9, 4.5))
        for offset, column, color, label in [(-0.2, "input_price_per_million", "accent", "input"),
                                             (0.2, "output_price_per_million", "accent2", "output")]:
            groups = [paid.loc[(paid["provider"] == name) & (paid[column] > 0), column] for name in names]
            positions = [i + offset for i in range(len(names))]
            box = ax.boxplot([g for g in groups], positions=positions, widths=0.35, patch_artist=True,
                             flierprops={"markersize": 2, "markeredgecolor": colors["muted"]},
                             medianprops={"color": colors["textColor"]},
                             whiskerprops={"color": colors["muted"]}, capprops={"color": colors["muted"]})
            for patch in box["boxes"]:
                patch.set_facecolor(colors[color])
            ax.plot([], [], "s", color=colors[color], label=label)   # legend entry
        ax.set_xticks(range(len(names)))
        ax.set_xticklabels(names, rotation=45, ha="right")
        ax.set_yscale("log")
        ax.legend()
        return _finish(fig, ax, "Price spread by provider (paid models)", "",
                       "USD per 1M tokens (log scale)")


def price_vs_context(df, mode, n=6):
    paid = eda.paid_models(df).dropna(subset=["context_length"])
    paid = paid[paid["input_price_per_million"] > 0]   # log scale cannot show 0
    if len(paid) < 3:
        return None
    colors = THEMES[mode]
    with plt.rc_context(chart_rc(mode)):
        fig, ax = plt.subplots(figsize=(8, 4.5))
        ax.scatter(paid["context_length"], paid["input_price_per_million"],
                   s=18, alpha=0.6, color=colors["muted"], label="other providers")
        for index, name in enumerate(eda.top_providers(paid, n)):
            color = plt.cm.tab10(index)
            part = paid[paid["provider"] == name]
            ax.scatter(part["context_length"], part["input_price_per_million"],
                       s=26, alpha=0.9, color=color, label=name)
        ax.set_xscale("log")
        ax.set_yscale("log")
        ax.legend(fontsize=8)
        return _finish(fig, ax, "Does a bigger context window cost more?",
                       "Context window (tokens, log scale)", "Input price (USD per 1M tokens, log scale)")


def correlation_heatmap(df, mode):
    corr = eda.correlation_table(df)
    if corr.empty:
        return None
    with plt.rc_context(chart_rc(mode)):
        fig, ax = plt.subplots(figsize=(5, 4))
        image = ax.imshow(corr.to_numpy(), vmin=-1, vmax=1, cmap="coolwarm")
        ax.set_xticks(range(len(corr)))
        ax.set_xticklabels(corr.columns, rotation=30, ha="right")
        ax.set_yticks(range(len(corr)))
        ax.set_yticklabels(corr.index)
        ax.grid(False)
        for i in range(len(corr)):
            for j in range(len(corr)):
                ax.text(j, i, f"{corr.iloc[i, j]:.2f}", ha="center", va="center", color="#0F172A")
        fig.colorbar(image, ax=ax, shrink=0.8)
        ax.set_title("Spearman correlation (log values)", loc="left", fontweight="bold")
        fig.tight_layout()
        return fig


def pricing_status_chart(df, mode):
    return bar_chart(eda.pricing_status_counts(df), "pricing_status", "models",
                     "Pricing information", "Number of models", mode, color="accent2")


def missing_chart(df, mode):
    table = eda.missing_table(df)
    table = table[table["missing"] > 0]
    if table.empty:
        return None
    return bar_chart(table, "column", "missing", "Missing values per column",
                     "Number of models", mode, color="accent2")


# ------------------------------------------------- leaderboard charts
CREATOR_COLORS = ["#4C8DF6", "#F2A33A", "#2DBE8D", "#E5584F", "#9B6BF2", "#17B8C9",
                  "#D96BA0", "#8C9A3A", "#6C7A89", "#C9772A", "#3F6FD1", "#7BC96F"]


def creator_colors(df):
    """Same creator = same colour in every chart of one dataset."""
    names = sorted(df["creator"].dropna().unique())
    return {name: CREATOR_COLORS[i % len(CREATOR_COLORS)] for i, name in enumerate(names)}


def ranking_chart(df, ds, top_n, mode):
    """Vertical bars, best model first, coloured by creator, with 95% confidence
    interval whiskers when the dataset has them (like the Artificial Analysis site)."""
    data = leaderboard.best_first(df.dropna(subset=[ds.metric]), ds).head(top_n)
    if data.empty:
        return None
    colors = THEMES[mode]
    palette = creator_colors(df)
    with plt.rc_context(chart_rc(mode)):
        fig, ax = plt.subplots(figsize=(max(6.5, 0.6 * len(data) + 2), 5))
        positions = np.arange(len(data))
        ax.bar(positions, data[ds.metric], color=[palette[c] for c in data["creator"]], width=0.7)
        top = float(data[ds.metric].max())
        if ds.ci_column and data[ds.ci_column].notna().any():
            errors = data[ds.ci_column].fillna(0)
            ax.errorbar(positions, data[ds.metric], yerr=errors, fmt="none", ecolor=colors["textColor"],
                        capsize=3, linewidth=1)
            low = float((data[ds.metric] - errors).min())
            ax.set_ylim(bottom=max(0, np.floor((low - 20) / 50) * 50), top=top + errors.max() * 1.8)
        else:
            ax.set_ylim(bottom=0, top=top * 1.12 if top > 0 else 1)
        pattern = "{:,.0f}" if top >= 100 else ("{:.1f}" if top >= 10 else "{:.2f}")
        label_height = data[ds.metric] + (data[ds.ci_column].fillna(0) if ds.ci_column else 0)
        for x, value, height in zip(positions, data[ds.metric], label_height):
            ax.text(x, height, pattern.format(value), ha="center", va="bottom", fontsize=8,
                    color=colors["textColor"], clip_on=True)
        ax.set_xticks(positions)
        ax.set_xticklabels(data["model_name"], rotation=60, ha="right", fontsize=8)
        ax.grid(axis="x", visible=False)
        handles = [plt.Rectangle((0, 0), 1, 1, color=palette[c]) for c in data["creator"].unique()]
        ax.legend(handles, list(data["creator"].unique()), fontsize=7, ncol=2, loc="upper right")
        return _finish(fig, ax, "", "", ds.metric_label)


def metric_histogram(df, ds, mode):
    values = df[ds.metric].dropna()
    if values.empty:
        return None
    colors = THEMES[mode]
    with plt.rc_context(chart_rc(mode)):
        fig, ax = plt.subplots(figsize=(8, 4))
        ax.hist(values, bins=min(15, max(3, len(values) // 2)), color=colors["accent"], edgecolor="none")
        ax.axvline(values.median(), color=colors["accent2"], linestyle="--", label=f"median: {values.median():,.3g}")
        ax.legend()
        return _finish(fig, ax, "How are the scores spread?", ds.metric_label, "Number of models")


def scatter_chart(df, x, y, xlabel, ylabel, title, mode, log_x=False, log_y=False):
    """Scatter plot of two columns, coloured by creator."""
    data = df.dropna(subset=[x, y])
    if log_x:
        data = data[data[x] > 0]
    if log_y:
        data = data[data[y] > 0]
    if len(data) < 3:
        return None
    palette = creator_colors(data)
    with plt.rc_context(chart_rc(mode)):
        fig, ax = plt.subplots(figsize=(8, 4.5))
        for creator, part in data.groupby("creator"):
            ax.scatter(part[x], part[y], s=36, alpha=0.9, color=palette[creator], label=creator)
        if log_x:
            ax.set_xscale("log")
        if log_y:
            ax.set_yscale("log")
        ax.legend(fontsize=7, ncol=2)
        return _finish(fig, ax, title, xlabel, ylabel)
