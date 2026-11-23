"""Colours for the Matplotlib charts.

The charts have a transparent background and mid-tone text and grid lines, so
they are readable on BOTH the light and the dark Streamlit theme. That way the
charts never clash with the page, whichever theme the user picks."""

NEUTRAL = {
    "backgroundColor": "none",     # transparent
    "textColor": "#7B8794",
    "grid": "#8A94A6",
    "accent": "#4C8DF6",
    "accent2": "#F2A33A",
    "muted": "#8A94A6",
}
THEMES = {"light": NEUTRAL, "dark": NEUTRAL}   # same palette on purpose


def chart_rc(mode="light"):
    """Matplotlib settings (rcParams) used for every chart."""
    t = THEMES[mode]
    return {
        "figure.facecolor": "none", "axes.facecolor": "none", "savefig.facecolor": "none",
        "axes.edgecolor": t["grid"], "axes.labelcolor": t["textColor"], "text.color": t["textColor"],
        "xtick.color": t["textColor"], "ytick.color": t["textColor"],
        "grid.color": t["grid"], "grid.alpha": 0.25, "axes.grid": True, "axes.axisbelow": True,
        "axes.spines.top": False, "axes.spines.right": False,
        "legend.facecolor": "none", "legend.edgecolor": "none", "legend.labelcolor": t["textColor"],
        "font.size": 10,
    }
