"""Small HTML building blocks (brand, KPI cards, chips, headings).

Everything is plain markup styled by `src/ui/styles.py`, so it follows the light/dark
theme automatically. All text that comes from data is escaped.
"""
import html

import streamlit as st


def logo_svg(size=36):
    """The brand mark: a tiny ranking list with a highlighted leader."""
    return (
        f'<svg class="logo" width="{size}" height="{size}" viewBox="0 0 40 40" role="img" aria-label="logo">'
        '<rect width="40" height="40" rx="10" style="fill:var(--accent)"/>'
        '<rect x="9" y="11" width="19" height="5" rx="2.5" style="fill:var(--accent-ink)"/>'
        '<rect x="9" y="19" width="13" height="5" rx="2.5" style="fill:var(--accent-ink);opacity:.8"/>'
        '<rect x="9" y="27" width="7" height="5" rx="2.5" style="fill:var(--accent-ink);opacity:.55"/>'
        '<circle cx="32" cy="13.5" r="3" style="fill:var(--warm)"/></svg>'
    )


def brand_html():
    return (f'<div class="brand">{logo_svg(38)}<div><div class="brand-name">AI Model Ecosystem</div>'
            '<div class="brand-sub">Intelligence Hub</div></div></div>')


def label_html(text):
    """Small uppercase label above a group of controls."""
    return f'<div class="side-label">{html.escape(text)}</div>'


def loader_html(text):
    return (f'<div class="loader" role="status"><div class="loader-box"><div class="loader-bar"></div>'
            f'<p>{html.escape(text)}</p></div></div>')


def pill_html(kind, text):
    """Status pill. kind: ok | info | bad"""
    return f'<span class="pill {kind}">{html.escape(text)}</span>'


def chip_html(label, value=""):
    value_html = f'<b>{html.escape(str(value))}</b>' if value != "" else ""
    return f'<span class="chip">{html.escape(label)}{value_html}</span>'


def hero_eyebrow(text):
    st.markdown(f'<div class="eyebrow">{html.escape(text)}</div>', unsafe_allow_html=True)


def hero_details(subtitle, pill, chips, attribution=""):
    """Subtitle, status pill and facts under the page title. `pill` and `chips` are ready HTML."""
    attr = f'<div class="attribution">{html.escape(attribution)}</div>' if attribution else ""
    st.markdown(
        f'<div class="hero-sub">{html.escape(subtitle)}</div>'
        f'<div class="chips">{pill}{"".join(chips)}</div>{attr}',
        unsafe_allow_html=True,
    )


def kpis(items, columns=4):
    """A responsive row of key numbers. items: (label, value) or (label, value, hint)."""
    cards = []
    for item in items:
        label, value = str(item[0]), str(item[1])
        hint = f' title="{html.escape(str(item[2]), quote=True)}"' if len(item) > 2 and item[2] else ""
        size = " long" if len(value) > 11 else ""
        cards.append(f'<div class="kpi"{hint}><div class="kpi-label">{html.escape(label)}</div>'
                     f'<div class="kpi-value{size}">{html.escape(value)}</div></div>')
    st.markdown(f'<div class="kpis" style="--cols:{int(columns)}">{"".join(cards)}</div>', unsafe_allow_html=True)


def facts(items):
    """A short list of sentences calculated from the data."""
    rows = "".join(f"<li>{html.escape(str(text))}</li>" for text in items)
    st.markdown(f'<div class="facts"><div class="facts-title">Key facts, calculated from the data</div>'
                f'<ul>{rows}</ul></div>', unsafe_allow_html=True)


def subhead(title, note=""):
    """A heading for a table or block that is not inside a card."""
    note_html = f'<span class="subhead-note">{html.escape(note)}</span>' if note else ""
    st.markdown(f'<div class="subhead"><span class="subhead-title">{html.escape(title)}</span>{note_html}</div>',
                unsafe_allow_html=True)
