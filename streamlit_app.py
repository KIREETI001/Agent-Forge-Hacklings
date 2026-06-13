"""
streamlit_app.py
================
SG UniNavigator — Streamlit front-end (intent-routed architecture, light & bright UI).

Flow (matches the architecture diagram):

    User free-text input
            |
            v
    classify_intent  (TokenRouter + Kimi in Live Mode, rules in Demo Mode)
            |
      +-----+-----------------------+-----------------------+
      v                             v                       v
    EXPLORE                       EVALUATE                ADMISSION
    (only RP -> all options)      (named course ->        (named course ->
                                   vibe + hiring news)     pass/fail math)
            |
            v
    Streamlit dashboard — branch-specific render

Run with:
    streamlit run streamlit_app.py

Visual layer lives in ui_theme.py (+ .streamlit/config.toml). This file owns
layout and behaviour; styling is delegated so the look stays consistent.
"""

from datetime import datetime

import streamlit as st

# Local modules. (live_backend is imported lazily inside Live Mode so Demo
# Mode never needs Person B's heavier scraping dependencies.)
from agent_core import (
    route_query,
    INTENT_EXPLORE,
    INTENT_EVALUATE,
    INTENT_ADMISSION,
)
from fallback_data import FALLBACK_SNAPSHOT_AGE_MIN
import ui_theme

# python-dotenv is optional; load .env if present so the LLM classifier can read
# TokenRouter / Kimi keys. Never hard-fail the UI if it's missing.
try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass


# ──────────────────────────────────────────────────────────────────────────
# Page config + theme (inject CSS first, then the hero)
# ──────────────────────────────────────────────────────────────────────────
st.set_page_config(page_title="SG UniNavigator", page_icon="🎓", layout="wide")
ui_theme.inject_css()
ui_theme.hero()


# ──────────────────────────────────────────────────────────────────────────
# Sidebar — how it works + example prompts
# ──────────────────────────────────────────────────────────────────────────
with st.sidebar:
    st.header("🧭 How it works")
    st.markdown(
        "Your message is classified into one of three intents, then routed to a "
        "dedicated branch:"
    )
    st.markdown(
        f"{ui_theme.pill('EXPLORE', 'info')} &nbsp; *“What can I do with my RP?”*",
        unsafe_allow_html=True,
    )
    st.markdown(
        f"{ui_theme.pill('EVALUATE', 'info')} &nbsp; *“Is NUS Computer Science worth it?”*",
        unsafe_allow_html=True,
    )
    st.markdown(
        f"{ui_theme.pill('ADMISSION', 'info')} &nbsp; *“Can I get into NTU Data Science?”*",
        unsafe_allow_html=True,
    )
    st.divider()
    st.caption("Try these 👇")
    st.code("What courses fit my RP?", language=None)
    st.code("Tell me about SMU Information Systems", language=None)
    st.code("Can I get into NUS Computer Science?", language=None)


# ──────────────────────────────────────────────────────────────────────────
# Inputs (inside a bright card)
# ──────────────────────────────────────────────────────────────────────────
with st.container(border=True):
    query = st.text_input(
        "Ask me anything about SG university courses",
        value="What courses can I do with my RP?",
        help="Free text. e.g. 'Can I get into NTU EEE?', 'Is NUS Business Analytics good?'",
    )
    col_rp, col_demo, col_btn = st.columns([1.1, 1.4, 1])
    with col_rp:
        student_rp = st.number_input(
            "Your RP score",
            min_value=0.0, max_value=90.0, value=85.0, step=0.5,
            help="A-level University Admission Rank Points (0-90). Used for EXPLORE / ADMISSION.",
        )
    with col_demo:
        st.write("")
        st.write("")
        demo_mode = st.checkbox("Demo Mode (use cached data)", value=True)
    with col_btn:
        st.write("")
        st.write("")
        run = st.button("Navigate ▶", type="primary", use_container_width=True)


# ──────────────────────────────────────────────────────────────────────────
# Run the intent router
# ──────────────────────────────────────────────────────────────────────────
intent_obj = None
result = None
live_payload = None          # set in Live Mode from Person B's backend
backend_error = None
data_source = "CACHED" if demo_mode else "LIVE"
scraped_age_min = FALLBACK_SNAPSHOT_AGE_MIN

if query.strip():
    try:
        if demo_mode:
            # Demo Mode: my self-contained intent router over cached data.
            intent_obj, result = route_query(query, student_rp, demo_mode=True)
        else:
            # Live Mode: stream Person B's agentic backend (live_backend.py).
            # If Bright Data keys are present we run the real scrape; otherwise
            # the backend's own fallback path runs so the demo still works.
            import os
            import live_backend

            has_brightdata = bool(
                os.getenv("BRIGHTDATA_API_KEY") or os.getenv("BRIGHTDATA_API_TOKEN")
            )
            run_started = datetime.now()
            final_event = None
            prog = st.progress(0.0, text="Starting live pipeline…")
            with st.status("Live mode: routing + scraping via sponsors…", expanded=True) as box:
                for event in live_backend.route_and_scrape_with_sponsors_streaming(
                    query, use_fallback=not has_brightdata
                ):
                    msg = event.get("message")
                    if msg:
                        box.write(f"• {msg}")
                    if event.get("progress") is not None:
                        prog.progress(min(1.0, float(event["progress"])), text=msg or "Working…")
                    if event.get("status") == "complete":
                        final_event = event
                box.update(label="Live pass complete", state="complete")
            prog.empty()
            scraped_age_min = max(0, int((datetime.now() - run_started).total_seconds() // 60))
            if final_event is not None:
                live_payload = {
                    "branch": final_event.get("branch", "EVALUATE"),
                    "data": final_event.get("data", []) or [],
                    "summary": final_event.get("summary"),
                    "used_fallback": not has_brightdata,
                }
    except Exception as exc:  # noqa: BLE001 — surface any backend failure.
        backend_error = exc
        st.error(f"⚠️ Backend error while handling your query: {exc}")


# ──────────────────────────────────────────────────────────────────────────
# Intent bar (custom, bright)
# ──────────────────────────────────────────────────────────────────────────
if intent_obj is not None:
    engine = intent_obj.get("engine", "rules")
    course = intent_obj.get("course") or "—"
    rp_val = intent_obj.get("rp") if intent_obj.get("rp") is not None else student_rp
    st.markdown(
        f"""
        <div class="intent-bar">
          {ui_theme.pill('🧠 ' + intent_obj['intent'], 'info')}
          <span class="intent-chip">classifier <b>{engine}</b></span>
          <span class="intent-chip">course <b>{course}</b></span>
          <span class="intent-chip">RP <b>{rp_val}</b></span>
        </div>
        """,
        unsafe_allow_html=True,
    )

if live_payload is not None:
    src = "sponsor fallback" if live_payload["used_fallback"] else "live scrape"
    st.markdown(
        f"""
        <div class="intent-bar">
          {ui_theme.pill('🛰️ ' + live_payload['branch'], 'info')}
          <span class="intent-chip">backend <b>Person B agents</b></span>
          <span class="intent-chip">source <b>{src}</b></span>
          <span class="intent-chip">rows <b>{len(live_payload['data'])}</b></span>
        </div>
        """,
        unsafe_allow_html=True,
    )


# ──────────────────────────────────────────────────────────────────────────
# Branch-specific renders
# ──────────────────────────────────────────────────────────────────────────
_EXPLORE_VERDICT_LABEL = {
    "Safe": "✅ Safe",
    "Reach": "🟡 Reach",
    "Out of reach": "⚪ Out of reach",
}


def render_explore(res):
    ui_theme.section(
        f"🔭 Explore — options for RP {res['student_rp']:.1f}",
        f"{res['n_valid']} of {len(res['options'])} programmes within reach "
        "(Safe or Reach) · static 2024/25 cutoffs",
    )
    legend = (
        ui_theme.pill("Safe", "success") + " &nbsp; "
        + ui_theme.pill("Reach", "warn") + " &nbsp; "
        + ui_theme.pill("Out of reach", "neutral")
    )
    st.markdown(legend, unsafe_allow_html=True)
    st.write("")

    table = [
        {
            "Course": o["course"],
            "Institution": o["institution"],
            "IGP Cutoff": o["igp_cutoff"],
            "RP Gap": o["rp_gap"],
            "Verdict": _EXPLORE_VERDICT_LABEL.get(o["verdict"], o["verdict"]),
            "Median Salary": o["median_salary"],
            "Employment": o["employment"],
        }
        for o in res["options"]
    ]
    st.dataframe(
        table,
        use_container_width=True,
        hide_index=True,
        column_config={
            "IGP Cutoff": st.column_config.NumberColumn("IGP Cutoff", format="%.1f"),
            "Median Salary": st.column_config.NumberColumn("Median Salary", format="SGD %d"),
        },
    )


def render_evaluate(res):
    if not res.get("matched"):
        st.warning(res.get("message", "Course not found."))
        if res.get("suggestions"):
            st.caption("Did you mean: " + ", ".join(res["suggestions"]))
        return

    vibe = res["reddit"]["vibe"]
    ui_theme.section(f"📈 Evaluate — {res['institution']} {res['course']}")
    st.markdown(
        "Course outlook &nbsp; " + ui_theme.pill(vibe + " vibe", ui_theme.vibe_kind(vibe)),
        unsafe_allow_html=True,
    )
    st.write("")

    m1, m2, m3 = st.columns(3)
    m1.metric("Median Salary", f"SGD {res['median_salary']:,}")
    m2.metric("Employment", res["employment"])
    m3.metric("IGP Cutoff", f"{res['igp_cutoff']:.1f}")

    reddit = res["reddit"]
    st.markdown("**🗣️ Reddit vibe**")
    v1, v2 = st.columns([1, 2])
    with v1:
        st.metric(reddit["vibe"], f"{reddit['pct_positive']:.0f}% positive")
    with v2:
        st.caption(
            f"👍 {reddit['pos']} positive · 👎 {reddit['neg']} negative · "
            f"😐 {reddit['neu']} neutral  (sentiment score {reddit['sentiment_score']})"
        )

    st.markdown("**📰 Live SG hiring news**")
    if res.get("hiring_news"):
        for bullet in res["hiring_news"]:
            st.markdown(f"- {bullet}")
    else:
        st.caption("No hiring news on file for this course.")


def render_admission(res):
    if not res.get("matched"):
        st.warning(res.get("message", "Course not found."))
        if res.get("suggestions"):
            st.caption("Did you mean: " + ", ".join(res["suggestions"]))
        return

    verdict = res["verdict"]
    ui_theme.section(f"🎯 Admission — {res['institution']} {res['course']}")
    st.markdown(
        ui_theme.pill(verdict, ui_theme.admission_kind(verdict)),
        unsafe_allow_html=True,
    )
    st.write("")

    headline = (
        f"Your RP **{res['student_rp']:.2f}** vs cutoff **{res['igp_cutoff']:.2f}** "
        f"(gap {res['rp_gap']})"
    )
    if verdict == "LIKELY IN":
        st.success("✅ " + headline)
    elif verdict == "BORDERLINE":
        st.warning("⚠️ " + headline)
    else:
        st.error("❌ " + headline)

    st.markdown("**🧮 Pass/fail math sandbox**")
    st.code("\n".join(res["math"]), language=None)


def render_live(payload):
    """Render Person B's live backend results in the bright design language.

    Person B's row contract differs from the Demo contract — keys are read
    defensively with .get() since they vary by data source (Bright Data,
    data.gov.sg GES, Asia news, fallback).
    """
    branch = payload["branch"]
    ui_theme.section(
        f"🛰️ Live — {branch.title()} pipeline",
        "Person B's agentic backend: TokenRouter + Kimi routing · Bright Data · "
        "data.gov.sg GES · Asia news"
        + (" · sponsor fallback data" if payload["used_fallback"] else ""),
    )
    if payload.get("summary"):
        st.markdown(f"**🧠 Summary** — {payload['summary']}")

    rows = payload["data"]
    if not rows:
        st.warning(
            "The live pipeline returned no rows. Tick **Demo Mode** for the cached experience."
        )
        return

    table = [
        {
            "Course": r.get("course", "—"),
            "University": r.get("university", "—"),
            "Status": r.get("status", "—"),
            "Salary": r.get("salary_estimate", "—"),
            "Employment": r.get("employment_rate", "—"),
            "Reddit Vibe": r.get("reddit_vibe", "—"),
            "News Signal": r.get("news_signal") or r.get("techasia_signal") or "—",
        }
        for r in rows
    ]
    st.dataframe(table, use_container_width=True, hide_index=True)


if live_payload is not None and backend_error is None:
    with st.container(border=True):
        render_live(live_payload)
elif result is not None and backend_error is None:
    with st.container(border=True):
        intent = result.get("intent")
        if intent == INTENT_EXPLORE:
            render_explore(result)
        elif intent == INTENT_EVALUATE:
            render_evaluate(result)
        elif intent == INTENT_ADMISSION:
            render_admission(result)


# ──────────────────────────────────────────────────────────────────────────
# Bottom bar — cost breakdown placeholders + data freshness (in a card)
# ──────────────────────────────────────────────────────────────────────────
st.write("")
with st.container(border=True):
    cost_col, data_col = st.columns([2, 1])

    with cost_col:
        st.markdown("**💸 Cost breakdown**  ·  *placeholder, wired once live*")
        st.text("Intent classify (TokenRouter+Kimi): $0.0000")
        st.text("Bright Data scrape:                 $0.0000")
        st.text("Daytona compute:                    $0.0000")
        st.text("────────────────────────────────────────────")
        st.text("Total this run:                     $0.0000")

    with data_col:
        st.markdown("**📡 Data source**")
        badge = ui_theme.pill(data_source, "success" if data_source == "LIVE" else "info")
        st.markdown(f"{badge} &nbsp; scraped **{scraped_age_min} min** ago", unsafe_allow_html=True)
        if demo_mode:
            st.caption("(bundled fallback snapshot)")
