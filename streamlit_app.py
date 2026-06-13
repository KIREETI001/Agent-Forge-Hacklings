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

# Voice input (browser speech-to-text). Optional — degrade gracefully if absent.
try:
    from streamlit_mic_recorder import speech_to_text
except Exception:
    speech_to_text = None

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
    st.caption("Try these 👇 (one tap fills the box)")
    for _i, _ex in enumerate([
        "What courses fit my RP?",
        "Tell me about SMU Information Systems",
        "Can I get into NUS Computer Science?",
    ]):
        if st.button(_ex, key=f"ex_{_i}", use_container_width=True):
            st.session_state["query_text"] = _ex


# ──────────────────────────────────────────────────────────────────────────
# Inputs (inside a bright card)
# ──────────────────────────────────────────────────────────────────────────
with st.container(border=True):
    # Seed the query in session_state so the 🎤 voice button can populate it.
    if "query_text" not in st.session_state:
        st.session_state["query_text"] = "What courses can I do with my RP?"

    q_col, mic_col = st.columns([6, 1])
    with mic_col:
        st.write("")
        st.write("")
        if speech_to_text is not None:
            spoken = speech_to_text(
                language="en", start_prompt="🎤", stop_prompt="⏹️",
                just_once=True, use_container_width=True, key="stt",
            )
            if spoken:
                st.session_state["query_text"] = spoken
        else:
            st.caption("🎤 n/a")
    with q_col:
        query = st.text_input(
            "Ask me anything about SG uni courses — type or 🎤 speak 🌸",
            key="query_text",
            help="e.g. 'Can I get into NTU EEE?', 'Is NUS Business Analytics good?'",
        )

    col_demo, col_btn = st.columns([2, 1])
    with col_demo:
        st.write("")
        demo_mode = st.checkbox("Demo Mode (use cached data)", value=False)
    with col_btn:
        run = st.button("Navigate ▶", type="primary", use_container_width=True)

    # No separate RP box — the question IS the input. Derive an optional RP only
    # if the student typed a number; else a quiet default for Demo Mode math.
    import re as _re
    _m = _re.search(r"\b([0-9]{1,2}(?:\.[0-9])?)\b", query or "")
    student_rp = float(_m.group(1)) if (_m and 0.0 <= float(_m.group(1)) <= 90.0) else 85.0


# ──────────────────────────────────────────────────────────────────────────
# Run the intent router
# ──────────────────────────────────────────────────────────────────────────
intent_obj = None
result = None
live_payload = None          # set in Live Mode from Person B's backend
backend_error = None
data_source = "CACHED" if demo_mode else "LIVE"
scraped_age_min = FALLBACK_SNAPSHOT_AGE_MIN

# Live Mode hits paid sponsor APIs, so only run it on an explicit Navigate
# click. Demo Mode is cheap/local, so it can render on every rerun.
if query.strip() and (demo_mode or run):
    try:
        if demo_mode:
            # Demo Mode: my self-contained intent router over cached data.
            intent_obj, result = route_query(query, student_rp, demo_mode=True)
        else:
            # Live Mode: the REAL agentic pipeline — NO fallback. Streams
            # live_backend.py: Kimi intent -> route plan -> Bright Data + GES +
            # Asia news + Daytona sandbox -> Kimi/TokenRouter synthesis. Errors
            # surface honestly (we never mask a failed sponsor with demo data).
            import live_backend

            # The question IS the input. Kimi reads any RP from the text itself.
            live_query = query.strip()
            run_started = datetime.now()
            final_event = None
            prog = st.progress(0.0, text="Starting live pipeline…")
            with st.status("Live mode: routing + scraping via sponsors…", expanded=True) as box:
                for event in live_backend.route_and_scrape_with_sponsors_streaming(
                    live_query, use_fallback=False
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
                    "route_plan": final_event.get("route_plan") or {},
                    "trace": final_event.get("trace") or {},
                    "used_fallback": False,
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


def _short(text, n=90):
    """Trim long free-text cell values so the table stays scannable."""
    if not isinstance(text, str):
        return text
    text = text.strip()
    return text if len(text) <= n else text[: n - 1].rstrip() + "…"


def _render_sponsor_status(payload):
    """Show which sponsors are configured and which actually ran this branch.

    No fallback masking: a sponsor that's needed but missing its key/collector
    shows as a warning so the real pipeline state is honest.
    """
    import os

    plan = payload.get("route_plan") or {}
    trace = payload.get("trace") or {}

    def cfg(*names):
        return any((os.getenv(n) or "").strip() for n in names)

    bright = cfg("BRIGHTDATA_API_TOKEN", "BRIGHTDATA_API_KEY")
    items = [
        ("🧠 Kimi", cfg("KIMI_API_KEY", "MOONSHOT_API_KEY"), True),
        ("🔀 TokenRouter", cfg("TOKENROUTER_API_KEY"), bool(trace.get("tokenrouter_usage"))),
        ("🏫 BrightData·Uni", bright and cfg("BRIGHTDATA_UNI_COLLECTOR_ID"), bool(plan.get("need_uni"))),
        ("💬 BrightData·Reddit", bright and cfg("BRIGHTDATA_REDDIT_COLLECTOR_ID"), bool(plan.get("need_reddit"))),
        ("📰 BrightData·TechAsia", bright and cfg("BRIGHTDATA_TECHASIA_COLLECTOR_ID"), bool(plan.get("need_techasia"))),
        ("🏛️ data.gov.sg GES", cfg("GOV_DATA_URL"), True),
        ("🗞️ Asia News", True, bool(plan.get("need_news"))),
        ("⚙️ Daytona", cfg("DAYTONA_API_KEY"), bool(plan.get("need_daytona"))),
    ]
    chips = []
    for label, configured, ran in items:
        if ran and configured:
            kind, mark = "success", "✓ ran"
        elif ran and not configured:
            kind, mark = "warn", "needs key"
        elif configured:
            kind, mark = "info", "ready"
        else:
            kind, mark = "neutral", "off"
        chips.append(ui_theme.pill(f"{label} · {mark}", kind))
    st.markdown("**🛰️ Sponsor pipeline**", unsafe_allow_html=True)
    st.markdown(" ".join(chips), unsafe_allow_html=True)
    st.write("")


def _render_daytona(payload):
    """Surface the Daytona sandbox ranking (real in-sandbox compute)."""
    import json as _json

    dy = (payload.get("trace") or {}).get("daytona")
    if not isinstance(dy, dict):
        return
    parsed = None
    result = dy.get("result")
    if isinstance(result, str):
        try:
            parsed = _json.loads(result)
        except Exception:
            parsed = None
    if parsed and parsed.get("ranked"):
        st.markdown("**⚙️ Daytona sandbox ranking** — *fit score computed in an isolated sandbox*")
        st.dataframe(
            [
                {"Course": x.get("course"), "University": x.get("university"), "Fit score": x.get("fit_score")}
                for x in parsed["ranked"]
            ],
            use_container_width=True,
            hide_index=True,
        )
    elif dy.get("status") and dy.get("status") != "ok":
        st.caption(f"⚙️ Daytona: {dy.get('status')} — {dy.get('message', '')}")


def render_live(payload):
    """Render the live backend results: course table first, then summary.

    Person B's row contract differs from the Demo contract — keys are read
    defensively with .get() since they vary by data source (Bright Data,
    data.gov.sg GES, Asia news, fallback).
    """
    branch = payload["branch"]
    ui_theme.section(
        f"🛰️ Live — {branch.title()} pipeline ✨",
        "Real agentic run: Kimi routing · Bright Data · data.gov.sg GES · "
        "Asia news · Daytona sandbox",
    )

    _render_sponsor_status(payload)

    # 1) The list, as a table.
    rows = payload["data"]
    if rows:
        table = [
            {
                "Course": r.get("course", "—"),
                "University": r.get("university", "—"),
                "Status": r.get("status", "—"),
                "Salary": r.get("salary_estimate", "—"),
                "Employment": r.get("employment_rate", "—"),
                "Reddit Vibe": _short(r.get("reddit_vibe", "—"), 36),
                "News Signal": _short(r.get("news_signal") or r.get("techasia_signal") or "—"),
            }
            for r in rows
        ]
        st.dataframe(
            table,
            use_container_width=True,
            hide_index=True,
            column_config={
                "Salary": st.column_config.TextColumn("Salary", width="small"),
                "Employment": st.column_config.TextColumn("Employment", width="small"),
                "Reddit Vibe": st.column_config.TextColumn("Reddit Vibe", width="medium"),
                "News Signal": st.column_config.TextColumn("News Signal", width="large"),
            },
        )
    else:
        st.warning(
            "No structured rows came back — check the sponsor pipeline above "
            "(a key or collector may be missing). The agent's read is below 👇"
        )

    # Daytona-computed ranking (real sandbox compute).
    _render_daytona(payload)

    # 2) Then the summary. Escape $ so salary figures don't render as LaTeX.
    summary = payload.get("summary")
    if summary:
        st.markdown("**🧠 Summary**")
        st.markdown(str(summary).replace("$", "\\$"))


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
