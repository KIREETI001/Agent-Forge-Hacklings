"""
ui_theme.py
===========
Soft, cute & playful design system for SG UniNavigator.

Streamlit's native theme tokens live in .streamlit/config.toml. This module
layers the richer visual language on top via one injected <style> block plus a
few HTML helpers (hero banner, pill badges). Keeping it in one place means the
look is consistent and easy to tweak.

Public API (UNCHANGED — streamlit_app.py imports these):
    inject_css()                 -> push the global stylesheet (call once, early)
    hero()                       -> gradient hero header
    pill(text, kind)             -> coloured badge HTML string
    vibe_kind(vibe)              -> map a Reddit vibe to a pill kind
    admission_kind(verdict)      -> map an admission verdict to a pill kind
    verdict_kind(verdict)        -> map an EXPLORE verdict to a pill kind
    section(title, subtitle)     -> styled section heading

Design tokens (soft & cute pastel):
    lavender #A78BFA  +  blush #FB7BA2  ->  sky #7CC6FE gradient
    ink      #3A2E55         text (dark plum for strong contrast on pastel)
    bg       #FFF6F2         warm cream app background
    card     #FFFFFF         surfaces
    mint     #7EE8C8         accent
"""

import streamlit as st


# Single source of truth for the whole look. Friendly rounded Google Fonts load
# from CDN with a graceful system-font fallback when offline.
_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Baloo+2:wght@500;600;700;800&family=Quicksand:wght@500;600;700&family=Nunito:wght@400;500;600;700;800&display=swap');

:root{
  --brand:#A78BFA;
  --brand-2:#7CC6FE;
  --blush:#FB7BA2;
  --mint:#7EE8C8;
  --sky:#7CC6FE;
  --lav:#A78BFA;
  /* dreamy pastel rainbow — lavender -> blush -> sky */
  --brand-grad:linear-gradient(135deg,#A78BFA 0%,#C9A7FF 30%,#FB7BA2 65%,#7CC6FE 100%);
  --ink:#3A2E55;
  --muted:#8A7BA8;
  --bg:#FFF6F2;
  --card:#FFFFFF;
  --line:#F2E4F0;
  --success:#2BB673; --warn:#F0A92B; --danger:#F2607A;
  /* gentle pillowy shadows with a soft lavender tint */
  --shadow:0 10px 30px rgba(167,139,250,.16);
  --shadow-lg:0 20px 50px rgba(167,139,250,.28);
  --radius:22px;
}

/* ---- App background: warm cream with dreamy pastel colour clouds ---- */
.stApp{
  background:
    radial-gradient(900px 480px at 100% -10%, rgba(124,198,254,.22), transparent 60%),
    radial-gradient(820px 500px at -8% 4%, rgba(251,123,162,.18), transparent 58%),
    radial-gradient(700px 460px at 50% 110%, rgba(126,232,200,.18), transparent 60%),
    var(--bg);
}

/* ---- Typography ---- */
html, body, [class*="css"]{ font-family:'Nunito',system-ui,-apple-system,sans-serif; color:var(--ink); }
h1,h2,h3,h4{ font-family:'Baloo 2','Quicksand',sans-serif !important; color:var(--ink) !important; letter-spacing:0; font-weight:700; }

/* ---- Content width / spacing (a little extra breathing room) ---- */
.block-container, [data-testid="stMainBlockContainer"]{
  max-width:1080px; padding-top:1.4rem; padding-bottom:3.4rem;
}

/* ---- Hero: cute mascot vibe with floating sparkles ---- */
.hero{
  background:var(--brand-grad);
  border-radius:30px; padding:34px 38px; margin:6px 0 26px;
  color:#fff; box-shadow:var(--shadow-lg);
  position:relative; overflow:hidden;
}
.hero:before{
  content:"✨"; position:absolute; left:26px; bottom:18px; font-size:1.5rem;
  opacity:.85; animation:floaty 4s ease-in-out infinite;
}
.hero:after{
  content:""; position:absolute; right:-40px; top:-50px; width:240px; height:240px;
  background:radial-gradient(circle,rgba(255,255,255,.40),transparent 70%);
}
@keyframes floaty{ 0%,100%{ transform:translateY(0) rotate(-4deg); } 50%{ transform:translateY(-8px) rotate(6deg); } }
.hero-title{
  font-family:'Baloo 2',sans-serif; font-weight:800; font-size:2.25rem; line-height:1.12; margin:0;
  text-shadow:0 2px 0 rgba(0,0,0,.06);
}
.hero-sub{ font-family:'Nunito',sans-serif; font-weight:500; font-size:1.04rem; opacity:.98; margin-top:11px; max-width:720px; line-height:1.55; }
.hero-badges{ margin-top:20px; display:flex; gap:10px; flex-wrap:wrap; }
.hero-badge{
  background:rgba(255,255,255,.26); border:1.5px solid rgba(255,255,255,.55);
  color:#fff; padding:7px 15px; border-radius:999px; font-size:.86rem; font-weight:700;
  font-family:'Quicksand',sans-serif; backdrop-filter:blur(2px);
  transition:transform .15s ease;
}
.hero-badge:hover{ transform:translateY(-2px) scale(1.05); }

/* ---- Cards (st.container(border=True)): pillowy & rounded ---- */
[data-testid="stVerticalBlockBorderWrapper"]{
  background:var(--card); border:1.5px solid var(--line) !important;
  border-radius:var(--radius) !important; box-shadow:var(--shadow);
  padding:10px 12px;
  transition:transform .18s ease, box-shadow .18s ease;
}
[data-testid="stVerticalBlockBorderWrapper"]:hover{
  transform:translateY(-2px); box-shadow:var(--shadow-lg);
}

/* ---- Buttons: pill-shaped, soft gradient, bouncy hover ---- */
.stButton>button{
  background:var(--brand-grad); color:#fff; border:0; border-radius:999px;
  padding:.62rem 1.7rem; font-weight:800; font-size:.98rem;
  font-family:'Quicksand',sans-serif; letter-spacing:.01em;
  box-shadow:0 10px 24px rgba(167,139,250,.40);
  transition:transform .16s cubic-bezier(.34,1.56,.64,1), box-shadow .16s ease, filter .16s ease;
}
.stButton>button:hover{
  transform:translateY(-2px) scale(1.04); filter:brightness(1.04) saturate(1.06);
  box-shadow:0 14px 30px rgba(251,123,162,.45); color:#fff;
}
.stButton>button:active{ transform:translateY(0) scale(.98); }

/* ---- Inputs: rounder & friendly ---- */
[data-baseweb="input"], [data-baseweb="base-input"]{ border-radius:16px !important; }
[data-testid="stTextInput"] input, [data-testid="stNumberInput"] input{ border-radius:16px !important; }
[data-testid="stTextInput"] input:focus, [data-testid="stNumberInput"] input:focus{
  border-color:var(--lav) !important; box-shadow:0 0 0 3px rgba(167,139,250,.18) !important;
}
[data-testid="stTextInput"] label, [data-testid="stNumberInput"] label{
  font-weight:700; color:var(--ink); font-family:'Quicksand',sans-serif;
}

/* ---- Metrics: soft pastel tiles ---- */
[data-testid="stMetric"]{
  background:linear-gradient(180deg,#FFFFFF,#FCF3FB);
  border:1.5px solid var(--line); border-radius:20px; padding:16px 18px; box-shadow:var(--shadow);
}
[data-testid="stMetricLabel"]{ color:var(--muted); font-weight:700; font-family:'Quicksand',sans-serif; }
[data-testid="stMetricValue"]{ color:var(--ink); font-weight:800; font-family:'Baloo 2',sans-serif; }

/* ---- Alerts: rounded & gentle ---- */
[data-testid="stAlert"]{ border-radius:20px; box-shadow:var(--shadow); border:1.5px solid var(--line); }

/* ---- Sidebar: dreamy cream gradient ---- */
[data-testid="stSidebar"]{
  background:linear-gradient(180deg,#FFFFFF,#FBEFF8 60%,#F1ECFF);
  border-right:1.5px solid var(--line);
}
[data-testid="stSidebar"] h2{ font-size:1.18rem; font-family:'Baloo 2',sans-serif; }
[data-testid="stSidebar"] [data-testid="stCode"]{ font-size:.78rem; }

/* ---- Dataframe: rounded clip ---- */
[data-testid="stDataFrame"]{ border-radius:20px; overflow:hidden; border:1.5px solid var(--line); box-shadow:var(--shadow); }

/* ---- Code blocks (admission math) ---- */
[data-testid="stCode"]{ border-radius:16px !important; }

/* ---- Pills: rounded candy badges ---- */
.pill{
  display:inline-block; padding:5px 14px; border-radius:999px; font-size:.8rem;
  font-weight:800; line-height:1.4; font-family:'Quicksand',sans-serif;
}
.pill-success{ background:#D6F5E6; color:#157A4D; }
.pill-warn{ background:#FDEFD2; color:#92590E; }
.pill-danger{ background:#FCDEE5; color:#9E2440; }
.pill-info{ background:#E3EEFF; color:#2D52A8; }
.pill-neutral{ background:#F1ECFA; color:#6A5C86; }

/* ---- Intent bar: soft rounded shelf ---- */
.intent-bar{
  display:flex; gap:12px; flex-wrap:wrap; align-items:center;
  background:#FFFFFF; border:1.5px solid var(--line); border-radius:20px;
  padding:14px 18px; box-shadow:var(--shadow); margin:2px 0 18px;
}
.intent-chip{ font-size:.86rem; color:var(--muted); font-family:'Quicksand',sans-serif; }
.intent-chip b{ color:var(--ink); font-weight:800; }

/* ---- Section headings ---- */
.section-h{
  font-family:'Baloo 2',sans-serif; font-weight:800; font-size:1.4rem; margin:2px 0 2px; color:var(--ink);
}
.section-sub{ color:var(--muted); font-size:.92rem; margin:0 0 13px; font-family:'Nunito',sans-serif; font-weight:500; }

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
    """Cute gradient hero header with mascot sparkles and three-intent badges."""
    st.markdown(
        """
        <div class="hero">
          <div class="hero-title">🎓✨ SG UniNavigator</div>
          <div class="hero-sub">
            Ask in plain English and we'll read your intent &amp; gently guide you to the right tool —
            explore options for your RP, evaluate a course's vibe &amp; outlook, or check
            your admission odds. 🌸
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
