"""
ui_theme.py
===========
Light & bright design system for SG UniNavigator.

Streamlit's native theme tokens live in .streamlit/config.toml. This module
layers the richer visual language on top via one injected <style> block plus a
few HTML helpers (hero banner, pill badges). Keeping it in one place means the
look is consistent and easy to tweak.

Public API:
    inject_css()                 -> push the global stylesheet (call once, early)
    hero()                       -> gradient hero header
    pill(text, kind)             -> coloured badge HTML string
    vibe_kind(vibe)              -> map a Reddit vibe to a pill kind
    admission_kind(verdict)      -> map an admission verdict to a pill kind
    verdict_kind(verdict)        -> map an EXPLORE verdict to a pill kind

Design tokens (light & bright):
    brand   #2F6BFF  (blue)  ->  #22D3EE (cyan) gradient
    ink     #15233B         text
    bg      #F7FAFF         app background
    card    #FFFFFF         surfaces
"""

import streamlit as st


# Single source of truth for the whole look. Google Fonts load from CDN with a
# graceful system-font fallback when offline.
_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=Plus+Jakarta+Sans:wght@600;700;800&display=swap');

:root{
  --brand:#2F6BFF;
  --brand-2:#22D3EE;
  --brand-grad:linear-gradient(135deg,#2F6BFF 0%,#5B8CFF 45%,#22D3EE 100%);
  --ink:#15233B;
  --muted:#5B6B85;
  --bg:#F7FAFF;
  --card:#FFFFFF;
  --line:#E6ECF5;
  --success:#16A34A; --warn:#F59E0B; --danger:#EF4444;
  --shadow:0 6px 24px rgba(31,69,128,.08);
  --shadow-lg:0 14px 44px rgba(31,69,128,.14);
  --radius:16px;
}

/* ---- App background: soft light wash with two faint colour glows ---- */
.stApp{
  background:
    radial-gradient(1200px 520px at 100% -10%, rgba(34,211,238,.12), transparent 60%),
    radial-gradient(900px 520px at -10% 0%, rgba(47,107,255,.12), transparent 55%),
    var(--bg);
}

/* ---- Typography ---- */
html, body, [class*="css"]{ font-family:'Inter',system-ui,-apple-system,sans-serif; color:var(--ink); }
h1,h2,h3,h4{ font-family:'Plus Jakarta Sans','Inter',sans-serif !important; color:var(--ink) !important; letter-spacing:-.01em; }

/* ---- Content width / spacing ---- */
.block-container, [data-testid="stMainBlockContainer"]{
  max-width:1080px; padding-top:1.1rem; padding-bottom:3rem;
}

/* ---- Hero ---- */
.hero{
  background:var(--brand-grad);
  border-radius:24px; padding:30px 34px; margin:4px 0 22px;
  color:#fff; box-shadow:var(--shadow-lg);
  position:relative; overflow:hidden;
}
.hero:after{
  content:""; position:absolute; right:-50px; top:-50px; width:230px; height:230px;
  background:radial-gradient(circle,rgba(255,255,255,.28),transparent 70%);
}
.hero-title{ font-family:'Plus Jakarta Sans',sans-serif; font-weight:800; font-size:2.15rem; line-height:1.08; margin:0; }
.hero-sub{ font-size:1.02rem; opacity:.96; margin-top:10px; max-width:720px; line-height:1.5; }
.hero-badges{ margin-top:18px; display:flex; gap:9px; flex-wrap:wrap; }
.hero-badge{
  background:rgba(255,255,255,.18); border:1px solid rgba(255,255,255,.40);
  color:#fff; padding:6px 13px; border-radius:999px; font-size:.84rem; font-weight:600;
}

/* ---- Cards (st.container(border=True)) ---- */
[data-testid="stVerticalBlockBorderWrapper"]{
  background:var(--card); border:1px solid var(--line) !important;
  border-radius:var(--radius) !important; box-shadow:var(--shadow);
  padding:8px 10px;
}

/* ---- Buttons ---- */
.stButton>button{
  background:var(--brand-grad); color:#fff; border:0; border-radius:12px;
  padding:.58rem 1.5rem; font-weight:700; font-size:.98rem;
  box-shadow:0 8px 20px rgba(47,107,255,.32);
  transition:transform .12s ease, box-shadow .12s ease, filter .12s ease;
}
.stButton>button:hover{ transform:translateY(-1px); filter:brightness(1.03); box-shadow:0 12px 26px rgba(47,107,255,.42); color:#fff; }
.stButton>button:active{ transform:translateY(0); }

/* ---- Inputs ---- */
[data-baseweb="input"], [data-baseweb="base-input"]{ border-radius:12px !important; }
[data-testid="stTextInput"] input, [data-testid="stNumberInput"] input{ border-radius:12px !important; }
[data-testid="stTextInput"] label, [data-testid="stNumberInput"] label{ font-weight:600; color:var(--ink); }

/* ---- Metrics ---- */
[data-testid="stMetric"]{
  background:linear-gradient(180deg,#FFFFFF,#F3F8FF);
  border:1px solid var(--line); border-radius:14px; padding:14px 16px; box-shadow:var(--shadow);
}
[data-testid="stMetricLabel"]{ color:var(--muted); font-weight:600; }
[data-testid="stMetricValue"]{ color:var(--ink); font-weight:800; }

/* ---- Alerts ---- */
[data-testid="stAlert"]{ border-radius:14px; box-shadow:var(--shadow); border:1px solid var(--line); }

/* ---- Sidebar ---- */
[data-testid="stSidebar"]{
  background:linear-gradient(180deg,#FFFFFF,#EFF5FF);
  border-right:1px solid var(--line);
}
[data-testid="stSidebar"] h2{ font-size:1.15rem; }
[data-testid="stSidebar"] [data-testid="stCode"]{ font-size:.78rem; }

/* ---- Dataframe ---- */
[data-testid="stDataFrame"]{ border-radius:14px; overflow:hidden; border:1px solid var(--line); box-shadow:var(--shadow); }

/* ---- Code blocks (admission math) ---- */
[data-testid="stCode"]{ border-radius:12px !important; }

/* ---- Pills ---- */
.pill{ display:inline-block; padding:4px 12px; border-radius:999px; font-size:.8rem; font-weight:700; line-height:1.4; }
.pill-success{ background:#DCFCE7; color:#166534; }
.pill-warn{ background:#FEF3C7; color:#92400E; }
.pill-danger{ background:#FEE2E2; color:#991B1B; }
.pill-info{ background:#E0EDFF; color:#1E40AF; }
.pill-neutral{ background:#EEF2F7; color:#475569; }

/* ---- Intent bar ---- */
.intent-bar{
  display:flex; gap:12px; flex-wrap:wrap; align-items:center;
  background:#FFFFFF; border:1px solid var(--line); border-radius:14px;
  padding:12px 16px; box-shadow:var(--shadow); margin:2px 0 16px;
}
.intent-chip{ font-size:.85rem; color:var(--muted); }
.intent-chip b{ color:var(--ink); font-weight:700; }

/* ---- Section headings ---- */
.section-h{ font-family:'Plus Jakarta Sans',sans-serif; font-weight:800; font-size:1.3rem; margin:2px 0 2px; color:var(--ink); }
.section-sub{ color:var(--muted); font-size:.9rem; margin:0 0 12px; }

/* ---- Hide default chrome for a cleaner demo ---- */
#MainMenu{ visibility:hidden; }
footer{ visibility:hidden; }
[data-testid="stHeader"]{ background:transparent; }
</style>
"""


def inject_css():
    """Inject the global stylesheet. Call once, right after set_page_config."""
    st.markdown(_CSS, unsafe_allow_html=True)


def hero():
    """Gradient hero header with the three-intent badges."""
    st.markdown(
        """
        <div class="hero">
          <div class="hero-title">🎓 SG UniNavigator</div>
          <div class="hero-sub">
            Ask in plain English. We read your intent and route you to the right tool —
            explore options for your RP, evaluate a course's vibe &amp; outlook, or check
            your admission odds.
          </div>
          <div class="hero-badges">
            <span class="hero-badge">🔭 Explore</span>
            <span class="hero-badge">📈 Evaluate</span>
            <span class="hero-badge">🎯 Admission</span>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def pill(text, kind="neutral"):
    """Return HTML for a coloured pill badge (use inside st.markdown(unsafe))."""
    return f'<span class="pill pill-{kind}">{text}</span>'


def vibe_kind(vibe):
    """Reddit vibe -> pill kind."""
    return {"Positive": "success", "Mixed": "warn", "Cautious": "danger"}.get(vibe, "neutral")


def admission_kind(verdict):
    """Admission verdict -> pill kind."""
    return {"LIKELY IN": "success", "BORDERLINE": "warn", "UNLIKELY": "danger"}.get(verdict, "neutral")


def verdict_kind(verdict):
    """EXPLORE Safe/Reach/Out of reach -> pill kind."""
    return {"Safe": "success", "Reach": "warn", "Out of reach": "neutral"}.get(verdict, "neutral")


def section(title, subtitle=None):
    """Render a styled section heading (+ optional subtitle)."""
    st.markdown(f'<div class="section-h">{title}</div>', unsafe_allow_html=True)
    if subtitle:
        st.markdown(f'<div class="section-sub">{subtitle}</div>', unsafe_allow_html=True)
