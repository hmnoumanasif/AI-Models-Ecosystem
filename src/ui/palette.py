"""Colour and font tokens for the two interface themes.

"light" is a warm paper-and-ink look, "dark" is the same design on near-black ink.
Every part of the interface (CSS, Plotly charts, HTML tables) reads its colours from
here, so the two themes can never drift apart.
"""

FONTS_URL = (
    "https://fonts.googleapis.com/css2?"
    "family=IBM+Plex+Mono:wght@400;500&"
    "family=IBM+Plex+Sans:wght@400;500;600&"
    "family=Newsreader:opsz,wght@6..72,400;6..72,500;6..72,600&display=swap"
)
FONT_UI = '"IBM Plex Sans", "Segoe UI", system-ui, -apple-system, "Helvetica Neue", Arial, sans-serif'
FONT_DISPLAY = '"Newsreader", "Iowan Old Style", "Palatino Linotype", Palatino, Georgia, serif'
FONT_MONO = '"IBM Plex Mono", "Cascadia Mono", "SF Mono", Consolas, "Liberation Mono", monospace'

TOKENS = {
    "light": {
        "bg": "#F2EFE7",            # page
        "sidebar": "#E9E5D9",
        "surface": "#FAF8F3",       # cards, inputs
        "surface2": "#ECE8DD",      # hover, table header
        "line": "#DAD4C5",
        "line_strong": "#BFB8A4",
        "ink": "#1E1C17",
        "muted": "#6A6557",
        "faint": "#8C8672",
        "accent": "#12806C",
        "accent_ink": "#F7F5EE",    # text on top of the accent colour
        "accent_soft": "rgba(18, 128, 108, 0.11)",
        "warm": "#C9582A",          # second data colour
        "ok": "#2F7D4A",
        "info": "#2F5F9E",
        "bad": "#B3372F",
        "warn": "#9A6A12",
        "grid": "rgba(30, 28, 23, 0.09)",
        "overlay": "rgba(242, 239, 231, 0.82)",
    },
    "dark": {
        "bg": "#101214",
        "sidebar": "#0B0D0F",
        "surface": "#171A1D",
        "surface2": "#20252A",
        "line": "#2B3137",
        "line_strong": "#434B53",
        "ink": "#ECE8DC",
        "muted": "#A29E91",
        "faint": "#7C796E",
        "accent": "#46BFA3",
        "accent_ink": "#0A1411",
        "accent_soft": "rgba(70, 191, 163, 0.14)",
        "warm": "#F0925A",
        "ok": "#6CC48A",
        "info": "#86ABEA",
        "bad": "#F07B72",
        "warn": "#E2B14F",
        "grid": "rgba(236, 232, 220, 0.09)",
        "overlay": "rgba(16, 18, 20, 0.82)",
    },
}

# Colours for categories (creators, providers). Same order in both themes, so a
# creator keeps its colour when the theme changes.
SERIES = {
    "light": ["#12806C", "#C9582A", "#3C5FA8", "#C29B1B", "#8A4B8C", "#5E9E55",
              "#B1384C", "#2F86A6", "#7B7B34", "#CB7C86", "#5B6A73", "#9E5A32"],
    "dark": ["#46BFA3", "#F0925A", "#7F9FEC", "#E6C24F", "#C98BD0", "#86C77D",
             "#E86A7E", "#5DB6DA", "#B8B85C", "#EBA3AB", "#95A6AF", "#D98E62"],
}


def tokens(mode):
    """Colour tokens for 'light' or 'dark' (anything else falls back to light)."""
    return TOKENS.get(mode, TOKENS["light"])


def series(mode):
    return SERIES.get(mode, SERIES["light"])
