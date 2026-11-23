"""Small helpers so numbers look the same everywhere in the app."""
import pandas as pd


def fmt_int(value):
    return "n/a" if pd.isna(value) else f"{int(value):,}"


def fmt_tokens(value):
    """1048576 -> '1.05M', 128000 -> '128K'."""
    if pd.isna(value):
        return "n/a"
    if value >= 1_000_000:
        return f"{value / 1_000_000:.2f}M"
    if value >= 1_000:
        return f"{value / 1_000:.0f}K"
    return f"{int(value)}"


def fmt_price(value):
    """USD per 1M tokens: $0.25, $15.00, $0.003."""
    if pd.isna(value):
        return "n/a"
    if value >= 1:
        return f"${value:,.2f}"
    return f"${value:.3f}"


def fmt_percent(value):
    return "n/a" if pd.isna(value) else f"{value:.1f}%"


def fmt_score(value):
    """Scores of any size: 1262, 65.4, 0.045."""
    if pd.isna(value):
        return "n/a"
    if abs(value) >= 100:
        return f"{value:,.0f}"
    if abs(value) >= 10:
        return f"{value:.1f}"
    return f"{value:.3f}"
