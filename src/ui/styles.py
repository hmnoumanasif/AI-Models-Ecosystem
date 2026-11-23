"""All CSS of the app. `build_css(mode)` returns a <style> block for "light" or "dark".

Streamlit has no switch for its own theme at run time, so this stylesheet takes over
the whole look (page, sidebar, inputs, menus, tables, charts). Colours are CSS
variables filled from `src/ui/palette.py`.
"""
from urllib.parse import quote

from src.ui.palette import FONT_DISPLAY, FONT_MONO, FONT_UI, FONTS_URL, tokens

VARIABLES = {
    "bg": "--bg", "sidebar": "--sidebar", "surface": "--surface", "surface2": "--surface2",
    "line": "--line", "line_strong": "--line-strong", "ink": "--ink", "muted": "--muted",
    "faint": "--faint", "accent": "--accent", "accent_ink": "--accent-ink", "accent_soft": "--accent-soft",
    "warm": "--warm", "ok": "--ok", "info": "--info", "bad": "--bad", "warn": "--warn",
    "grid": "--grid", "overlay": "--overlay",
}

BASE = """
/* ---------- page ---------- */
html, body, .stApp, [data-testid="stApp"], [data-testid="stAppViewContainer"], [data-testid="stMain"] {
    background: var(--bg) !important; color: var(--ink);
}
.stApp { font-family: var(--font-ui); font-size: 15px; line-height: 1.55; -webkit-font-smoothing: antialiased; }
[data-testid="stMainBlockContainer"], .block-container {
    max-width: 1280px; padding: 2rem 2.8rem 4.5rem !important;
}
[data-testid="stHeader"] { background: transparent !important; height: 0 !important; min-height: 0 !important; }
[data-testid="stToolbarActions"], [data-testid="stMainMenu"], [data-testid="stDecoration"], [data-testid="stStatusWidget"],
[data-testid="stAppDeployButton"], #MainMenu, footer { display: none !important; }
.stApp h1, .stApp h2, .stApp h3, .stApp h4 { color: var(--ink); }
.stApp a { color: var(--accent); }
[data-testid="stMarkdownContainer"], [data-testid="stMarkdownContainer"] p,
[data-testid="stMarkdownContainer"] li { color: var(--ink); }
[data-testid="stCaptionContainer"], [data-testid="stCaptionContainer"] * { color: var(--muted) !important; }
hr { border-color: var(--line) !important; }
code { font-family: var(--font-mono) !important; background: var(--surface2) !important; color: var(--ink) !important;
       border-radius: 4px; padding: .1em .35em; }
* { scrollbar-width: thin; scrollbar-color: var(--line-strong) transparent; }
::selection { background: var(--accent-soft); }

/* ---------- sidebar ---------- */
[data-testid="stSidebar"] { background: var(--sidebar) !important; border-right: 1px solid var(--line); }
[data-testid="stSidebarContent"], [data-testid="stSidebarUserContent"] { background: transparent !important; }
[data-testid="stSidebarUserContent"] { padding: 1.6rem 1.1rem 1.5rem !important; }
.brand { display: flex; align-items: center; gap: .8rem; padding: 0 .35rem 1.2rem; }
.brand .logo { flex: none; }
.brand-name { font-family: var(--font-display); font-weight: 600; font-size: 1.12rem; line-height: 1.15; letter-spacing: -.01em; }
.brand-sub { font-family: var(--font-mono); font-size: .66rem; letter-spacing: .14em; text-transform: uppercase;
             color: var(--muted); margin-top: .22rem; }
.side-label { font-family: var(--font-mono); font-size: .66rem; letter-spacing: .16em; text-transform: uppercase;
              color: var(--faint); margin: 1.1rem .35rem .55rem; }
.side-rule { height: 1px; background: var(--line); margin: 1.2rem .35rem 0; }

/* Navigation: plain list of links, numbered with a CSS counter */
.st-key-nav { counter-reset: nav; gap: 2px !important; }
.st-key-nav button {
    justify-content: flex-start !important; width: 100%; min-height: 2.3rem !important;
    padding: .38rem .8rem .38rem .7rem !important; background: transparent !important;
    border: 0 !important; border-left: 2px solid transparent !important; border-radius: 0 6px 6px 0 !important;
    color: var(--muted) !important; box-shadow: none !important; text-align: left;
}
.st-key-nav button > div, .st-key-nav button p { justify-content: flex-start !important; text-align: left !important;
    color: inherit !important; font-weight: 500; font-size: .95rem; margin: 0; }
.st-key-nav button::before {
    counter-increment: nav; content: counter(nav, decimal-leading-zero); display: inline-block; width: 1.7rem;
    font-family: var(--font-mono); font-size: .7rem; color: var(--faint); flex: none;
}
.st-key-nav button:hover { background: var(--surface2) !important; color: var(--ink) !important; }
.st-key-nav button[data-testid="stBaseButton-primary"] {
    background: var(--accent-soft) !important; color: var(--ink) !important; border-left-color: var(--accent) !important;
}
.st-key-nav button[data-testid="stBaseButton-primary"] p { font-weight: 600; }
.st-key-nav button[data-testid="stBaseButton-primary"]::before { color: var(--accent); }

/* ---------- top bar: category tabs + theme switch ---------- */
.st-key-topbar { border-bottom: 1px solid var(--line); margin-bottom: 1.6rem; }
.st-key-topbar [data-testid="stHorizontalBlock"] { flex-wrap: nowrap !important; align-items: flex-end; gap: 0 !important; }
.st-key-topbar [data-testid="stColumn"] { flex: 0 0 auto !important; width: auto !important; min-width: 0 !important; }
.st-key-topbar [data-testid="stColumn"]:nth-last-child(2) { flex: 1 1 auto !important; }
.st-key-topbar [data-testid="stColumn"]:last-child { align-self: center; }
[class*="st-key-tab_"] button {
    background: transparent !important; border: 0 !important; border-bottom: 2px solid transparent !important;
    border-radius: 0 !important; color: var(--muted) !important; box-shadow: none !important;
    padding: .55rem .15rem .6rem !important; margin: 0 1.7rem 0 0; min-height: 0 !important;
}
[class*="st-key-tab_"] button p { font-family: var(--font-display); font-size: 1.18rem !important;
    font-weight: 500; letter-spacing: -.005em; color: inherit !important; }
[class*="st-key-tab_"] button:hover { color: var(--ink) !important; }
[class*="st-key-tab_"] button[data-testid="stBaseButton-primary"] { color: var(--ink) !important;
    border-bottom-color: var(--accent) !important; }
[class*="st-key-tab_"] button[data-testid="stBaseButton-primary"] p { font-weight: 600; }

/* dataset chips (Image, Video, Speech) */
.st-key-datasets [data-testid="stHorizontalBlock"] { flex-wrap: wrap !important; gap: .5rem !important; }
.st-key-datasets [data-testid="stColumn"] { flex: 0 0 auto !important; width: auto !important; min-width: 0 !important; }
.st-key-datasets button { min-height: 0 !important; padding: .28rem .85rem !important; border-radius: 999px !important;
    background: transparent !important; border: 1px solid var(--line-strong) !important; color: var(--muted) !important;
    box-shadow: none !important; }
.st-key-datasets button p { font-size: .84rem !important; font-weight: 500; color: inherit !important; }
.st-key-datasets button:hover { border-color: var(--accent) !important; color: var(--ink) !important; }
.st-key-datasets button[data-testid="stBaseButton-primary"] { background: var(--accent-soft) !important;
    border-color: var(--accent) !important; color: var(--ink) !important; }

/* ---------- page header ---------- */
.eyebrow { font-family: var(--font-mono); font-size: .7rem; letter-spacing: .16em; text-transform: uppercase;
           color: var(--accent); margin-bottom: -.55rem; }
.stApp h1 { font-family: var(--font-display) !important; font-weight: 500 !important; font-size: 2.7rem !important;
            letter-spacing: -.02em !important; line-height: 1.08 !important; padding: 0 !important; margin: 0 !important; }
.hero-sub { color: var(--muted); font-size: 1.05rem; max-width: 62ch; margin-top: -.1rem; }
.chips { display: flex; flex-wrap: wrap; align-items: center; gap: .55rem; margin-top: .85rem; margin-bottom: .6rem; }
.chip { font-family: var(--font-mono); font-size: .74rem; padding: .22rem .65rem; color: var(--muted);
        border: 1px solid var(--line-strong); border-radius: 999px; white-space: nowrap; }
.chip b { color: var(--ink); font-weight: 500; margin-left: .5rem; }
.attribution { margin-top: .7rem; font-size: .78rem; color: var(--faint); }
.pill { display: inline-flex; align-items: center; gap: .5rem; padding: .24rem .75rem; border-radius: 999px;
        font-size: .76rem; font-weight: 600; border: 1px solid currentColor; }
.pill::before { content: ""; width: 7px; height: 7px; border-radius: 50%; background: currentColor; }
.pill.ok { color: var(--ok); background: color-mix(in srgb, var(--ok) 12%, transparent); }
.pill.info { color: var(--info); background: color-mix(in srgb, var(--info) 12%, transparent); }
.pill.bad { color: var(--bad); background: color-mix(in srgb, var(--bad) 12%, transparent); }

/* ---------- key numbers ---------- */
.kpis { display: grid; grid-template-columns: repeat(var(--cols, 4), minmax(0, 1fr)); gap: .75rem; margin: .6rem 0 .3rem; }
.kpi { background: var(--surface); border: 1px solid var(--line); border-radius: 10px; padding: .95rem 1.1rem 1rem; }
.kpi-label { font-family: var(--font-mono); font-size: .66rem; letter-spacing: .13em; text-transform: uppercase; color: var(--muted); }
.kpi-value { font-family: var(--font-display); font-size: 2.15rem; font-weight: 500; letter-spacing: -.02em;
             line-height: 1.15; margin-top: .3rem; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.kpi-value.long { font-size: 1.3rem; line-height: 2.2rem; white-space: normal; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; }
.facts { border-left: 2px solid var(--accent); padding: .15rem 0 .15rem 1.15rem; margin: .5rem 0; }
.facts-title { font-family: var(--font-mono); font-size: .66rem; letter-spacing: .14em; text-transform: uppercase; color: var(--muted); }
.facts ul { list-style: none; margin: .5rem 0 0; padding: 0; }
.facts li { position: relative; padding-left: 1.2rem; margin: .32rem 0; }
.facts li::before { content: ""; position: absolute; left: 0; top: .62em; width: 6px; height: 6px; background: var(--warm); border-radius: 1px; }
.subhead { display: flex; align-items: baseline; flex-wrap: wrap; gap: .3rem .8rem; margin: 1.1rem 0 .1rem; }
.subhead-title { font-family: var(--font-display); font-size: 1.3rem; font-weight: 500; letter-spacing: -.01em; }
.subhead-note { color: var(--muted); font-size: .84rem; }

/* ---------- cards ---------- */
[class*="st-key-card"] { background: var(--surface); border: 1px solid var(--line); border-radius: 10px;
                         padding: 1.1rem 1.3rem 1.2rem; gap: .5rem !important; }
.card-head { display: flex; align-items: center; gap: .6rem; }
.swatch { width: 9px; height: 9px; border-radius: 2px; background: var(--accent); flex: none; }
.card-title { font-family: var(--font-display); font-size: 1.2rem; font-weight: 500; letter-spacing: -.005em; }
.card-q { color: var(--muted); font-size: .86rem; margin: .15rem 0 .2rem; }

/* ---------- buttons ---------- */
[data-testid="stBaseButton-secondary"], [data-testid="stBaseButton-primary"], [data-testid="stBaseButton-tertiary"] {
    border-radius: 7px !important; font-weight: 500; min-height: 2.5rem; box-shadow: none !important;
}
[data-testid="stBaseButton-secondary"] { background: var(--surface) !important; border: 1px solid var(--line-strong) !important; color: var(--ink) !important; }
[data-testid="stBaseButton-secondary"]:hover { border-color: var(--accent) !important; background: var(--surface2) !important; }
[data-testid="stBaseButton-primary"] { background: var(--accent) !important; border: 1px solid var(--accent) !important; color: var(--accent-ink) !important; }
[data-testid="stBaseButton-primary"]:hover { filter: brightness(1.08); }
[data-testid="stBaseButton-primary"] p, [data-testid="stBaseButton-secondary"] p { color: inherit !important; }
button:focus-visible { outline: 2px solid var(--accent) !important; outline-offset: 2px; }

/* ---------- inputs ---------- */
[data-testid="stWidgetLabel"], [data-testid="stWidgetLabel"] p, [data-testid="stWidgetLabel"] * {
    color: var(--muted) !important; font-size: .8rem !important; font-weight: 500; letter-spacing: .01em; }
[data-testid="stTextInputRootElement"], [data-testid="stNumberInputContainer"], [data-baseweb="input"],
[data-baseweb="select"] > div, [data-testid="stSelectbox"] [role="group"], [data-testid="stMultiSelect"] [role="group"] {
    background: var(--surface) !important; border: 1px solid var(--line-strong) !important;
    border-radius: 7px !important; box-shadow: none !important; color: var(--ink) !important;
}
[data-baseweb="base-input"] { background: transparent !important; border: 0 !important; }
[data-testid="stTextInputRootElement"]:focus-within, [data-testid="stNumberInputContainer"]:focus-within,
[data-baseweb="input"]:focus-within, [data-baseweb="select"] > div:focus-within,
[data-testid="stSelectbox"] [role="group"]:focus-within, [data-testid="stMultiSelect"] [role="group"]:focus-within {
    border-color: var(--accent) !important; box-shadow: 0 0 0 3px var(--accent-soft) !important;
}
[data-testid="stTextInput"] input, [data-testid="stNumberInput"] input, [data-testid="stSelectbox"] input,
[data-testid="stMultiSelect"] input, textarea {
    background: transparent !important; color: var(--ink) !important; -webkit-text-fill-color: var(--ink) !important;
    caret-color: var(--accent); font-family: var(--font-ui);
}
input::placeholder, textarea::placeholder { color: var(--faint) !important; -webkit-text-fill-color: var(--faint) !important; opacity: 1; }
[data-testid="stNumberInputStepUp"], [data-testid="stNumberInputStepDown"] { background: transparent !important; color: var(--muted) !important; }
[data-testid="stNumberInputStepUp"]:hover, [data-testid="stNumberInputStepDown"]:hover { background: var(--surface2) !important; color: var(--ink) !important; }
[data-testid="stSelectbox"] svg, [data-testid="stMultiSelect"] svg, [data-testid="stNumberInput"] svg {
    color: var(--muted) !important; fill: var(--muted) !important; }
[data-testid="stSelectbox"] [role="group"] *, [data-testid="stMultiSelect"] [role="group"] > button { background: transparent !important; }
[data-baseweb="select"] > div > div:first-child > div:nth-child(2) { color: var(--muted) !important; }
[data-baseweb="tag"], [data-testid="stMultiSelectTagsContainer"] [data-testid="stMultiSelectTag"] {
    background: var(--accent-soft) !important; color: var(--ink) !important; border-radius: 5px !important; }
[data-baseweb="tag"] span, [data-baseweb="tag"] svg { color: var(--ink) !important; fill: var(--ink) !important; }

/* menus and tooltips (drawn outside the page flow) */
[data-baseweb="popover"] > div, [data-baseweb="menu"], [data-testid$="Dropdown"], ul[role="listbox"] {
    background: var(--surface) !important; color: var(--ink) !important; border: 1px solid var(--line-strong) !important;
    border-radius: 9px !important; box-shadow: 0 14px 34px rgba(0, 0, 0, .22) !important; }
[role="option"], [data-baseweb="menu"] li { background: transparent !important; color: var(--ink) !important; }
[role="option"]:hover, [role="option"][data-focused="true"], [role="option"][aria-selected="true"],
[data-baseweb="menu"] li:hover { background: var(--surface2) !important; }
[data-testid="stTooltipContent"], [data-baseweb="tooltip"] > div, [role="tooltip"] {
    background: var(--ink) !important; color: var(--bg) !important; border-radius: 6px !important; }
[data-testid="stTooltipContent"] *, [role="tooltip"] * { color: var(--bg) !important; }
[data-testid="stTooltipIcon"] svg { color: var(--faint) !important; fill: var(--faint) !important; }

/* sliders, switches */
[data-testid="stSlider"] [data-testid="stSliderThumbValue"], [data-testid="stSlider"] [data-testid="stSliderThumbValue"] *,
[data-testid="stSliderTickBar"] * { color: var(--ink) !important; font-family: var(--font-mono); font-size: .75rem !important; }
[data-testid="stSliderTickBar"] * { color: var(--faint) !important; }
[data-testid="stCheckbox"] label span, [data-testid="stCheckbox"] p { color: var(--ink) !important; }

/* toggle (Streamlit's switch): track and knob */
[data-testid="stCheckbox"] label > div:nth-of-type(1) { background: var(--line-strong) !important; border-radius: 999px !important; }
[data-testid="stCheckbox"] label:has(input:checked) > div:nth-of-type(1) { background: var(--accent) !important; }
[data-testid="stCheckbox"] label > div:nth-of-type(1) > div { background: var(--surface) !important; box-shadow: none !important; }
[data-baseweb="checkbox"] > div:first-child { background: var(--line-strong) !important; }
[data-baseweb="checkbox"] > div:first-child > div { background: var(--surface) !important; }
[data-baseweb="checkbox"]:has(input:checked) > div:first-child { background: var(--accent) !important; }

/* expander, alerts */
[data-testid="stExpander"] details { background: var(--surface) !important; border: 1px solid var(--line) !important; border-radius: 10px !important; }
[data-testid="stExpander"] summary, [data-testid="stExpander"] summary * { color: var(--ink) !important; }
[data-testid="stExpander"] summary:hover { background: var(--surface2) !important; border-radius: 10px; }
[data-testid="stAlert"], [data-testid="stAlertContainer"] { background: var(--surface) !important; color: var(--ink) !important;
    border: 1px solid var(--line) !important; border-left: 3px solid var(--info) !important; border-radius: 8px !important; }
[data-testid="stAlert"] *, [data-testid="stAlertContainer"] * { color: var(--ink) !important; }
[data-testid="stAlert"]:has([data-testid="stAlertContentWarning"]), [data-testid="stAlertContainer"]:has([data-testid="stAlertContentWarning"]) { border-left-color: var(--warn) !important; }
[data-testid="stAlert"]:has([data-testid="stAlertContentError"]), [data-testid="stAlertContainer"]:has([data-testid="stAlertContentError"]) { border-left-color: var(--bad) !important; }
[data-testid="stAlert"]:has([data-testid="stAlertContentSuccess"]), [data-testid="stAlertContainer"]:has([data-testid="stAlertContentSuccess"]) { border-left-color: var(--ok) !important; }

/* charts and tables */
[data-testid="stPlotlyChart"] { border-radius: 6px; }
iframe { border: 0 !important; color-scheme: normal; }

/* ---------- theme switch (a button drawn as a switch) ---------- */
.st-key-theme_switch button {
    position: relative; width: 66px !important; min-width: 66px !important; height: 32px !important; min-height: 32px !important;
    padding: 0 !important; border-radius: 999px !important; background: var(--surface2) !important;
    border: 1px solid var(--line-strong) !important; box-shadow: none !important; overflow: hidden;
}
.st-key-theme_switch button * { font-size: 0 !important; color: transparent !important; }
.st-key-theme_switch button::before, .st-key-theme_switch button::after {
    content: ""; position: absolute; top: 50%; width: 24px; height: 24px; margin-top: -12px; background-repeat: no-repeat;
    background-position: center; background-size: 15px 15px; transition: left .18s ease; }
.st-key-theme_switch button::after { border-radius: 50%; background-color: var(--accent); }

/* ---------- loading overlay ---------- */
.loader { position: fixed; inset: 0; z-index: 999999; display: flex; align-items: center; justify-content: center;
          background: var(--overlay); backdrop-filter: blur(3px); }
.loader-box { width: min(340px, 80vw); text-align: left; }
.loader-bar { height: 2px; background: var(--line-strong); position: relative; overflow: hidden; }
.loader-bar::after { content: ""; position: absolute; inset: 0 auto 0 0; width: 38%; background: var(--accent);
                     animation: slide 1.1s ease-in-out infinite; }
.loader p { margin: .8rem 0 0; font-family: var(--font-mono); font-size: .78rem; letter-spacing: .06em; color: var(--muted); }
@keyframes slide { 0% { left: -40%; } 100% { left: 102%; } }

/* ---------- wide screens keep the sidebar fixed (no collapse button) ---------- */
@media (min-width: 769px) {
    [data-testid="stSidebar"] { width: 284px !important; min-width: 284px !important; }
    [data-testid="stSidebarHeader"], [data-testid="stSidebarCollapseButton"],
    [data-testid="stSidebarCollapsedControl"], [data-testid="collapsedControl"], [data-testid="stExpandSidebarButton"],
    [data-testid="stSidebarResizeHandle"] { display: none !important; }
}
@media (max-width: 960px) { .kpis { grid-template-columns: repeat(2, minmax(0, 1fr)) !important; } }
/* small screens: the sidebar slides over the page, so keep a small menu button */
@media (max-width: 768px) {
    [data-testid="stMainBlockContainer"], .block-container { padding: 3.4rem 1.1rem 3rem !important; }
    .stApp h1 { font-size: 2.1rem !important; }
    .st-key-topbar [data-testid="stHorizontalBlock"] { overflow-x: auto; }
    [data-testid="stSidebarCollapsedControl"], [data-testid="collapsedControl"], [data-testid="stExpandSidebarButton"] {
        position: fixed !important; top: .6rem; left: .7rem; z-index: 1000; }
    [data-testid="stExpandSidebarButton"] { color: var(--ink) !important; background: var(--surface) !important;
        border: 1px solid var(--line-strong) !important; border-radius: 8px !important; }
    [data-testid="stExpandSidebarButton"] * { color: var(--ink) !important; }
    [class*="st-key-tab_"] button { margin-right: .9rem !important; }
    [class*="st-key-tab_"] button p { font-size: 1.02rem !important; }
    [data-testid="stSidebarCollapsedControl"] button, [data-testid="collapsedControl"] button,
    [data-testid="stSidebarCollapseButton"] button { color: var(--ink) !important; background: var(--surface) !important;
        border: 1px solid var(--line-strong) !important; border-radius: 8px !important; }
}
"""


def _svg(inner, color):
    """Inline SVG icon (24x24, stroked) as a CSS url()."""
    svg = ("<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='" + color +
           "' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'>" + inner + "</svg>")
    return "url(\"data:image/svg+xml;utf8," + quote(svg, safe="/:=' ") + "\")"


SUN = ("<circle cx='12' cy='12' r='4'/><path d='M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4"
       "M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4'/>")
MOON = "<path d='M20 14.5A8 8 0 1 1 9.5 4a6.5 6.5 0 0 0 10.5 10.5z'/>"


def switch_css(mode):
    """Position and icons of the theme switch: the knob shows the current theme."""
    t = tokens(mode)
    dark = mode == "dark"
    knob_left, ghost_left = ("38px", "5px") if dark else ("4px", "37px")
    knob_icon, ghost_icon = (MOON, SUN) if dark else (SUN, MOON)
    return (
        f".st-key-theme_switch button::after {{ left: {knob_left}; background-image: {_svg(knob_icon, t['accent_ink'])}; }}\n"
        f".st-key-theme_switch button::before {{ left: {ghost_left}; background-image: {_svg(ghost_icon, t['faint'])}; }}\n"
    )


def build_css(mode="light"):
    t = tokens(mode)
    variables = "".join(f"{css}: {t[key]};" for key, css in VARIABLES.items())
    fonts = f"--font-ui: {FONT_UI}; --font-display: {FONT_DISPLAY}; --font-mono: {FONT_MONO};"
    scheme = f"color-scheme: {'dark' if mode == 'dark' else 'light'};"
    return (f"<style>@import url('{FONTS_URL}');\n:root {{ {variables} {fonts} {scheme} }}\n"
            f"{BASE}\n{switch_css(mode)}</style>")
