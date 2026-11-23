"""Interactive Plotly charts (hover, zoom, pan, legend toggles, PNG download).

Same function names and arguments as the Matplotlib versions in
`src/analysis/charts.py`. Each function returns a figure, or None when there is
not enough data. `mode` is "light" or "dark" and decides the colours.
"""
import numpy as np
import plotly.graph_objects as go

from src.analysis import eda, leaderboard
from src.ui.palette import FONT_UI, series, tokens

# Passed to st.plotly_chart: no Plotly logo, no lasso/box select, PNG export at 2x.
PLOT_CONFIG = {
    "displaylogo": False,
    "responsive": True,
    "modeBarButtonsToRemove": ["select2d", "lasso2d", "autoScale2d"],
    "toImageButtonOptions": {"format": "png", "scale": 2, "filename": "ai-model-intelligence"},
}


# ------------------------------------------------------------------ helpers
def _alpha(hex_color, alpha):
    """'#12806C' -> 'rgba(18,128,108,0.25)'"""
    h = hex_color.lstrip("#")
    r, g, b = (int(h[i:i + 2], 16) for i in (0, 2, 4))
    return f"rgba({r},{g},{b},{alpha})"


def _axis_title(t, text):
    return {"text": text, "font": {"size": 12, "color": t["muted"]}, "standoff": 10}


def _axis(t, title="", **extra):
    axis = {
        "showgrid": True, "gridcolor": t["grid"], "gridwidth": 1, "zeroline": False,
        "showline": True, "linecolor": t["line_strong"], "ticks": "outside", "ticklen": 4,
        "tickcolor": t["line_strong"], "tickfont": {"size": 11, "color": t["muted"]},
        "title": _axis_title(t, title), "automargin": True,
    }
    axis.update(extra)
    return axis


def _figure(mode, height, **layout):
    """An empty figure with the shared look: transparent, quiet grid, tidy tooltips."""
    t = tokens(mode)
    fig = go.Figure()
    fig.update_layout(
        height=height, margin={"l": 8, "r": 18, "t": 10, "b": 8},
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font={"family": FONT_UI, "size": 12, "color": t["muted"]},
        colorway=series(mode),
        hoverlabel={"bgcolor": t["surface"], "bordercolor": t["line_strong"],
                    "font": {"family": FONT_UI, "size": 12, "color": t["ink"]}, "align": "left"},
        modebar={"bgcolor": "rgba(0,0,0,0)", "color": t["faint"], "activecolor": t["accent"]},
        legend={"font": {"size": 11, "color": t["muted"]}, "bgcolor": "rgba(0,0,0,0)",
                "orientation": "h", "yanchor": "bottom", "y": 1.02, "xanchor": "left", "x": 0},
        **layout,
    )
    return fig


def _decade_label(power):
    """3 -> '1K', 6 -> '1M' (labels for the log-scale histogram axis)."""
    value = 10 ** power
    if value >= 1_000_000:
        return f"{value / 1_000_000:g}M"
    if value >= 1_000:
        return f"{value / 1_000:g}K"
    return f"{value:g}"


def _median_line(fig, t, x, text):
    fig.add_vline(x=x, line_dash="dash", line_color=t["warm"], line_width=1.5)
    fig.add_annotation(x=x, y=1, yref="paper", text=text, showarrow=False, xanchor="left", yanchor="top",
                       xshift=6, font={"size": 11, "color": t["warm"]})


# ----------------------------------------------------------- generic charts
def bar_chart(table, label_col, value_col, title, xlabel, mode, color="accent"):
    """Horizontal bars, biggest on top, with the value at the end of each bar."""
    if table is None or table.empty:
        return None
    t = tokens(mode)
    bar_color = t["warm"] if color == "accent2" else t["accent"]
    labels = table[label_col].astype(str).tolist()
    values = table[value_col].astype(float).tolist()
    biggest = max(values)
    whole = all(v.is_integer() for v in values) or biggest >= 100
    fmt = ",.0f" if whole else (",.3f" if biggest < 1 else ",.2f")

    fig = _figure(mode, max(240, 32 * len(labels) + 76))
    fig.add_trace(go.Bar(
        x=values, y=labels, orientation="h", marker={"color": bar_color},
        text=values, texttemplate="%{x:" + fmt + "}", textposition="outside", cliponaxis=False,
        textfont={"size": 11, "color": t["ink"]},
        hovertemplate="<b>%{y}</b><br>" + xlabel + ": <b>%{x:" + fmt + "}</b><extra></extra>",
    ))
    fig.update_layout(
        bargap=0.34,
        xaxis=_axis(t, xlabel, range=[0, biggest * 1.14 if biggest > 0 else 1], fixedrange=True),
        yaxis=_axis(t, "", autorange="reversed", showgrid=False, fixedrange=True,
                    categoryorder="array", categoryarray=labels, tickfont={"size": 12, "color": t["ink"]}),
    )
    return fig


def median_by_provider(df, column, title, xlabel, mode, n=12, min_models=3):
    """Median of one column for the biggest providers."""
    names = [p for p in eda.top_providers(df, n) if (df["provider"] == p).sum() >= min_models]
    data = df[df["provider"].isin(names)].groupby("provider")[column].median().dropna()
    data = data.sort_values(ascending=False).reset_index()
    return bar_chart(data, "provider", column, title, xlabel, mode)


def context_histogram(df, mode):
    """How big are context windows? Bins are equal-width on a log scale."""
    ctx = df["context_length"].dropna()
    ctx = ctx[ctx > 0]
    if ctx.empty:
        return None
    t = tokens(mode)
    logs = np.log10(ctx.to_numpy(dtype=float))
    low, high = float(logs.min()), float(logs.max())
    edges = np.linspace(low, high, 25) if low < high else np.array([low - 0.1, high + 0.1])
    counts, edges = np.histogram(logs, bins=edges)
    centres = (edges[:-1] + edges[1:]) / 2
    ranges = [f"{_tok(10 ** a)} to {_tok(10 ** b)} tokens" for a, b in zip(edges[:-1], edges[1:])]

    fig = _figure(mode, 330)
    fig.add_trace(go.Bar(
        x=centres, y=counts, width=np.diff(edges) * 0.94, marker={"color": t["accent"]},
        customdata=ranges, hovertemplate="%{customdata}<br><b>%{y}</b> models<extra></extra>",
    ))
    powers = list(range(int(np.floor(edges[0])), int(np.ceil(edges[-1])) + 1))
    fig.update_layout(
        xaxis=_axis(t, "Context window (tokens, log scale)", tickvals=powers,
                    ticktext=[_decade_label(p) for p in powers], showgrid=False),
        yaxis=_axis(t, "Number of models"),
    )
    _median_line(fig, t, float(np.log10(ctx.median())), f"median {ctx.median():,.0f}")
    return fig


def _tok(value):
    if value >= 1_000_000:
        return f"{value / 1_000_000:.2f}M"
    if value >= 1_000:
        return f"{value / 1_000:.0f}K"
    return f"{value:.0f}"


def price_boxplot(df, mode, n=10):
    """Input and output price boxes side by side for each big provider (every model is a dot)."""
    paid = eda.paid_models(df)
    names = eda.top_providers(paid, n) if not paid.empty else []
    if len(paid[paid["provider"].isin(names)]) < 2:
        return None
    t = tokens(mode)
    fig = _figure(mode, 470)
    for column, key, label in [("input_price_per_million", "accent", "Input"),
                               ("output_price_per_million", "warm", "Output")]:
        part = paid[paid["provider"].isin(names) & (paid[column] > 0)]
        fig.add_trace(go.Box(
            x=part["provider"], y=part[column], name=label, boxpoints="all", jitter=0.55, pointpos=0,
            marker={"color": _alpha(t[key], 0.6), "size": 4}, line={"color": t[key], "width": 1.5},
            fillcolor=_alpha(t[key], 0.16), hovertext=part["model_name"],
            hovertemplate="<b>%{hovertext}</b><br>%{x}<br>" + label + ": <b>$%{y:,.3f}</b> per 1M tokens<extra></extra>",
        ))
    fig.update_layout(
        boxmode="group",
        xaxis=_axis(t, "", categoryorder="array", categoryarray=names, showgrid=False, tickangle=-35),
        yaxis=_axis(t, "USD per 1M tokens (log scale)", type="log"),
    )
    return fig


def price_vs_context(df, mode, n=6):
    """Does a bigger context window cost more? Biggest providers in colour, the rest in grey."""
    paid = eda.paid_models(df).dropna(subset=["context_length"])
    paid = paid[paid["input_price_per_million"] > 0]      # log scale cannot show 0
    if len(paid) < 3:
        return None
    t = tokens(mode)
    colors = series(mode)
    top = eda.top_providers(paid, n)
    fig = _figure(mode, 450)

    def add(part, name, color, size, opacity):
        fig.add_trace(go.Scatter(
            x=part["context_length"], y=part["input_price_per_million"], mode="markers", name=name,
            marker={"color": color, "size": size, "opacity": opacity, "line": {"width": 0}},
            customdata=part[["model_name", "provider"]].to_numpy(),
            hovertemplate="<b>%{customdata[0]}</b><br>%{customdata[1]}<br>"
                          "Context: <b>%{x:,.0f}</b> tokens<br>Input: <b>$%{y:,.3f}</b> per 1M<extra></extra>"))

    others = paid[~paid["provider"].isin(top)]
    if not others.empty:
        add(others, "other providers", _alpha(t["faint"], 0.7), 7, 0.7)
    for i, name in enumerate(top):
        add(paid[paid["provider"] == name], name, colors[i % len(colors)], 9, 0.92)
    fig.update_layout(
        xaxis=_axis(t, "Context window (tokens, log scale)", type="log"),
        yaxis=_axis(t, "Input price (USD per 1M tokens, log scale)", type="log"),
        hovermode="closest",
    )
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


# ------------------------------------------------------- leaderboard charts
def creator_colors(df, mode):
    """Same creator = same colour in every chart of one dataset."""
    palette = series(mode)
    names = sorted(df["creator"].dropna().unique())
    return {name: palette[i % len(palette)] for i, name in enumerate(names)}


def ranking_chart(df, ds, top_n, mode):
    """Bars for the best models, coloured by creator, with 95% confidence whiskers when
    the dataset has them. Click a creator in the legend to hide or show its models."""
    data = leaderboard.best_first(df.dropna(subset=[ds.metric]), ds).head(top_n).reset_index(drop=True)
    if data.empty:
        return None
    t = tokens(mode)
    palette = creator_colors(df, mode)
    has_ci = bool(ds.ci_column) and data[ds.ci_column].notna().any()
    errors = data[ds.ci_column].fillna(0) if has_ci else None
    has_rank = "rank" in data.columns
    top = float(data[ds.metric].max())
    label_fmt = "{:,.0f}" if top >= 100 else ("{:.1f}" if top >= 10 else "{:.2f}")

    fig = _figure(mode, 500 if top_n <= 16 else 560, bargap=0.28, barmode="overlay")
    for creator in data["creator"].unique():
        part = data[data["creator"] == creator]
        err = errors[part.index] if has_ci else None
        hover = "<b>%{customdata[0]}</b><br>%{customdata[1]}<br>" + ds.metric_label + ": <b>%{y:,.5~g}</b>"
        custom = [part["model_name"], part["creator"]]
        if has_ci:
            hover += " ± %{customdata[2]:,.0f}"
            custom.append(err)
        if has_rank:
            hover += "<br>Rank #%{customdata[" + str(len(custom)) + "]}"
            custom.append(part["rank"])
        fig.add_trace(go.Bar(
            x=part.index, y=part[ds.metric], width=0.72, name=creator, legendgroup=creator,
            marker={"color": palette[creator]},
            error_y={"type": "data", "array": err, "color": t["ink"], "thickness": 1.2, "width": 3} if has_ci else None,
            customdata=np.column_stack(custom), hovertemplate=hover + "<extra></extra>"))
        label_y = part[ds.metric] + (err if has_ci else 0)
        fig.add_trace(go.Scatter(
            x=part.index, y=label_y, mode="text", text=[label_fmt.format(v) for v in part[ds.metric]],
            textposition="top center", textfont={"size": 11, "color": t["ink"]}, legendgroup=creator,
            showlegend=False, hoverinfo="skip", cliponaxis=False))

    if has_ci:
        low = float((data[ds.metric] - errors).min())
        y_range = [max(0, np.floor((low - 20) / 50) * 50), top + float(errors.max()) * 1.8]
    else:
        y_range = [0, top * 1.12 if top > 0 else 1]
    fig.update_layout(
        xaxis=_axis(t, "", tickvals=list(data.index), ticktext=data["model_name"].tolist(),
                    tickangle=-40, showgrid=False, tickfont={"size": 11, "color": t["ink"]}, fixedrange=True),
        yaxis=_axis(t, ds.metric_label, range=y_range),
    )
    return fig


def metric_histogram(df, ds, mode):
    """How are the scores spread? Hover a bar to see its score range and model count."""
    values = df[ds.metric].dropna()
    if values.empty:
        return None
    t = tokens(mode)
    counts, edges = np.histogram(values.to_numpy(dtype=float), bins=min(15, max(3, len(values) // 2)))
    centres = (edges[:-1] + edges[1:]) / 2
    ranges = [f"{a:,.3g} to {b:,.3g}" for a, b in zip(edges[:-1], edges[1:])]

    fig = _figure(mode, 330)
    fig.add_trace(go.Bar(
        x=centres, y=counts, width=np.diff(edges) * 0.94, marker={"color": t["accent"]}, customdata=ranges,
        hovertemplate="Score " + "%{customdata}<br><b>%{y}</b> models<extra></extra>"))
    fig.update_layout(xaxis=_axis(t, ds.metric_label, showgrid=False), yaxis=_axis(t, "Number of models"))
    _median_line(fig, t, float(values.median()), f"median {values.median():,.3g}")
    return fig


def scatter_chart(df, x, y, xlabel, ylabel, title, mode, log_x=False, log_y=False):
    """Two columns against each other, coloured by creator. Hover for the model name;
    drag to zoom, double-click to reset, click a creator in the legend to hide it."""
    data = df.dropna(subset=[x, y])
    if log_x:
        data = data[data[x] > 0]
    if log_y:
        data = data[data[y] > 0]
    if len(data) < 3:
        return None
    t = tokens(mode)
    palette = creator_colors(df, mode)
    fig = _figure(mode, 450)
    for creator, part in data.groupby("creator"):
        fig.add_trace(go.Scatter(
            x=part[x], y=part[y], mode="markers", name=creator, legendgroup=creator,
            marker={"color": palette[creator], "size": 9, "opacity": 0.9, "line": {"width": 0}},
            customdata=part[["model_name", "creator"]].to_numpy(),
            hovertemplate="<b>%{customdata[0]}</b><br>%{customdata[1]}<br>" + xlabel.split(" (")[0]
                          + ": <b>%{x:,.4~g}</b><br>" + ylabel + ": <b>%{y:,.4~g}</b><extra></extra>"))
    fig.update_layout(
        xaxis=_axis(t, xlabel, type="log" if log_x else "linear"),
        yaxis=_axis(t, ylabel, type="log" if log_y else "linear"),
        hovermode="closest",
    )
    return fig
