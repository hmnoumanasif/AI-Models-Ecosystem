"""A sortable table that follows the light/dark theme.

Streamlit's own table (st.dataframe) is drawn on a canvas, so CSS cannot recolour it
when the user flips the theme switch. This table is plain HTML inside a small frame:
click a column header to sort, the header stays visible while the body scrolls, and
the colours always match the page.
"""
import html
import math

import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

from src.ui.palette import FONT_MONO, FONT_UI, FONTS_URL, tokens

MAX_ROWS = 1500        # safety limit: a frame with more rows than this gets slow
ROW_HEIGHT = 35
HEAD_HEIGHT = 40


# ------------------------------------------------------------ cell formatting
def _missing(value):
    if isinstance(value, (list, tuple, set, dict)):
        return False
    try:
        return bool(pd.isna(value))
    except (TypeError, ValueError):
        return False


def _auto_number(value):
    value = float(value)
    return f"{value:,.0f}" if value.is_integer() else f"{value:,.4g}"


def _number(value, fmt):
    if fmt in (None, "", "plain", "automatic"):
        return _auto_number(value)
    if fmt == "localized":
        text = f"{float(value):,.3f}".rstrip("0").rstrip(".")
        return text or "0"
    try:
        return fmt % value                   # printf style, e.g. "$%.3f" or "%.1f%%"
    except (TypeError, ValueError):
        return _auto_number(value)


def _date(value, fmt):
    stamp = pd.Timestamp(value)
    if stamp.tzinfo is not None:
        stamp = stamp.tz_convert("UTC")
    if fmt and "Y" in fmt:                   # "YYYY-MM-DD" -> "%Y-%m-%d"
        pattern = (fmt.replace("YYYY", "%Y").replace("MM", "%m").replace("DD", "%d")
                   .replace("HH", "%H").replace("mm", "%M").replace("ss", "%S"))
        return stamp.strftime(pattern)
    return stamp.strftime("%Y-%m-%d") if stamp == stamp.normalize() else stamp.strftime("%Y-%m-%d %H:%M")


def _column_kind(series):
    if pd.api.types.is_bool_dtype(series):
        return "bool"
    if pd.api.types.is_datetime64_any_dtype(series):
        return "date"
    if pd.api.types.is_numeric_dtype(series):
        return "num"
    present = [v for v in series if not _missing(v)]
    if present and all(isinstance(v, (int, float)) and not isinstance(v, bool) for v in present):
        return "num"
    return "text"


def _settings(name, config):
    """Label and number/date format for one column, from a Streamlit column_config entry."""
    entry = (config or {}).get(name)
    if isinstance(entry, str):
        return entry, None
    if isinstance(entry, dict):
        return entry.get("label") or name, (entry.get("type_config") or {}).get("format")
    return name, None


def _cell(value, kind, fmt):
    """-> (text shown, raw value used for sorting, extra css class)"""
    if _missing(value):
        return "—", "", "na"
    if kind == "num":
        return _number(value, fmt), repr(float(value)), "num"
    if kind == "date":
        return _date(value, fmt), pd.Timestamp(value).isoformat(), ""
    if kind == "bool":
        return ("Yes" if bool(value) else "No"), "1" if bool(value) else "0", "flag"
    text = ", ".join(map(str, value)) if isinstance(value, (list, tuple, set)) else str(value)
    return text, text.lower(), ""


# --------------------------------------------------------------------- build
def _css(t, mode):
    return f"""
    :root {{ color-scheme: {'dark' if mode == 'dark' else 'light'}; }}
    * {{ box-sizing: border-box; }}
    html, body {{ margin: 0; height: 100%; background: transparent; }}
    body {{ font-family: {FONT_UI}; color: {t['ink']}; font-size: 13px; }}
    .wrap {{ height: 100%; overflow: auto; background: {t['surface']}; border: 1px solid {t['line']};
             border-radius: 8px; scrollbar-width: thin; scrollbar-color: {t['line_strong']} transparent; }}
    table {{ border-collapse: separate; border-spacing: 0; min-width: 100%; }}
    th, td {{ padding: 0 14px; height: {ROW_HEIGHT}px; white-space: nowrap; text-align: left;
              border-bottom: 1px solid {t['line']}; max-width: 360px; overflow: hidden; text-overflow: ellipsis; }}
    thead th {{ position: sticky; top: 0; z-index: 2; height: {HEAD_HEIGHT}px; background: {t['surface2']};
                color: {t['muted']}; font-size: 11px; font-weight: 600; letter-spacing: .06em;
                text-transform: uppercase; cursor: pointer; user-select: none; border-bottom: 1px solid {t['line_strong']}; }}
    thead th:hover, thead th:focus-visible {{ color: {t['ink']}; outline: none; }}
    thead th::after {{ content: ""; display: inline-block; width: 0; height: 0; margin-left: 7px;
                       vertical-align: middle; opacity: 0; border-left: 4px solid transparent;
                       border-right: 4px solid transparent; border-top: 5px solid {t['accent']}; }}
    thead th[aria-sort="ascending"]::after {{ opacity: 1; border-top: 0; border-bottom: 5px solid {t['accent']}; }}
    thead th[aria-sort="descending"]::after {{ opacity: 1; }}
    thead th[aria-sort] {{ color: {t['ink']}; }}
    tbody tr:last-child td {{ border-bottom: 0; }}
    tbody tr:hover td {{ background: {t['accent_soft']}; }}
    td.num, th.num {{ text-align: right; font-family: {FONT_MONO}; font-size: 12.5px; font-variant-numeric: tabular-nums; }}
    thead th.num {{ font-family: {FONT_UI}; font-size: 11px; }}
    td.na {{ color: {t['faint']}; }}
    td.idx {{ font-weight: 600; color: {t['muted']}; }}
    td.flag {{ color: {t['muted']}; }}
    .empty {{ padding: 18px; color: {t['muted']}; }}
    """


_JS = """
const table = document.getElementById('t');
if (table && table.tBodies.length) {
  const heads = Array.from(table.tHead.rows[0].cells);
  let active = -1, direction = 1;
  const empty = v => v === '' || v == null;
  function sortBy(index) {
    direction = (active === index) ? -direction : 1;
    active = index;
    const numeric = heads[index].dataset.kind === 'num' || heads[index].dataset.kind === 'bool';
    const body = table.tBodies[0];
    const rows = Array.from(body.rows);
    rows.sort((a, b) => {
      const x = a.cells[index].dataset.v, y = b.cells[index].dataset.v;
      if (empty(x) && empty(y)) return 0;
      if (empty(x)) return 1;              // missing values always last
      if (empty(y)) return -1;
      const r = numeric ? (parseFloat(x) - parseFloat(y))
                        : x.localeCompare(y, undefined, {numeric: true, sensitivity: 'base'});
      return r * direction;
    });
    rows.forEach(r => body.appendChild(r));
    heads.forEach((h, i) => h.setAttribute('aria-sort', i === index ? (direction === 1 ? 'ascending' : 'descending') : 'none'));
  }
  heads.forEach((h, i) => {
    h.tabIndex = 0;
    h.addEventListener('click', () => sortBy(i));
    h.addEventListener('keydown', e => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); sortBy(i); } });
  });
}
"""


def build_table_html(df, config=None, mode="light", index=False, index_label=""):
    """The full HTML document of the table (separate from Streamlit so it is easy to test)."""
    t = tokens(mode)
    if index:
        df = df.rename_axis(index_label or "").reset_index()
    truncated = len(df) > MAX_ROWS
    df = df.head(MAX_ROWS)

    head, kinds, formats = [], [], []
    for position, name in enumerate(df.columns):
        kind = _column_kind(df[name])
        label, fmt = _settings(name, config)
        if index and position == 0:
            kind = "text"
        kinds.append(kind)
        formats.append(fmt)
        css = "num" if kind == "num" else ""
        head.append(f'<th class="{css}" data-kind="{kind}" title="{html.escape(str(label))}" '
                    f'aria-sort="none">{html.escape(str(label))}</th>')

    body = []
    for values in df.itertuples(index=False, name=None):
        cells = []
        for position, value in enumerate(values):
            text, raw, css = _cell(value, kinds[position], formats[position])
            if index and position == 0:
                css = "idx"
            safe = html.escape(text)
            cells.append(f'<td class="{css}" data-v="{html.escape(raw, quote=True)}" title="{safe}">{safe}</td>')
        body.append("<tr>" + "".join(cells) + "</tr>")

    note = ""
    if truncated:
        note = f'<div class="empty">Showing the first {MAX_ROWS:,} rows.</div>'
    content = (f'<div class="wrap"><table id="t"><thead><tr>{"".join(head)}</tr></thead>'
               f'<tbody>{"".join(body)}</tbody></table>{note}</div>')
    return (f'<!doctype html><html><head><meta charset="utf-8">'
            f'<meta name="color-scheme" content="{"dark" if mode == "dark" else "light"}">'
            f'<link rel="stylesheet" href="{FONTS_URL}"><style>{_css(t, mode)}</style></head>'
            f'<body>{content}<script>{_JS}</script></body></html>')


def table_height(rows, max_height=440):
    return int(min(max_height, HEAD_HEIGHT + ROW_HEIGHT * max(rows, 1) + 4))


def data_table(df, config=None, *, index=False, index_label="", max_height=440):
    """Show a DataFrame as a sortable, theme-aware table."""
    if df is None or df.empty:
        st.caption("No rows to show.")
        return
    mode = st.session_state.get("theme", "light")
    document = build_table_html(df, config, mode, index, index_label)
    components.html(document, height=table_height(min(len(df), MAX_ROWS), max_height), scrolling=False)
