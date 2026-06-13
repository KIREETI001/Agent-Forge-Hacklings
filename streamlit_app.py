from __future__ import annotations

import requests
import streamlit as st

from agent_core import extract_intent_with_kimi, route_and_scrape_with_sponsors_streaming, scrape_and_score_with_sponsors_streaming, scrape_streaming

st.set_page_config(page_title="Person B Scraper Console", layout="wide")

st.markdown(
    """
    <style>
    .block-container {
        padding-top: 1.25rem;
        padding-bottom: 2rem;
    }
    .hero {
        padding: 1.25rem 1.5rem;
        border-radius: 1.2rem;
        background: linear-gradient(135deg, #0f172a 0%, #1e293b 55%, #334155 100%);
        color: white;
        margin-bottom: 1rem;
    }
    .hero h1 { margin-bottom: 0.35rem; }
    .hero p { margin-bottom: 0; opacity: 0.88; }
    </style>
    """,
    unsafe_allow_html=True,
)

st.markdown(
    """
    <div class="hero">
        <h1>Person B Scraper Console</h1>
        <p>TokenRouter + Kimi classify the request first, then only the needed scrapers run for the chosen branch.</p>
    </div>
    """,
    unsafe_allow_html=True,
)

st.markdown(
    """
## Agentic Routing Architecture

```text
User Unstructured Input
        │
        ▼
TokenRouter + Kimi AI Intent Classifier
        │
        ├── EXPLORE   -> Static RP cutoffs + minimal live lookups
        ├── EVALUATE  -> Reddit + TechAsia + employment links + news
        └── ADMISSION -> Uni IGP + Reddit + TechAsia + employment links + news + Daytona
        │
        ▼
Streamlit Dashboard
```
"""
)

with st.sidebar:
    st.header("Controls")
    raw_prompt = st.text_area(
        "Freeform student prompt",
        value="I got 78.75 RP, I want a chill environment but good banking prospects, computing track",
        height=100,
    )
    parse_button = st.button("Interpret with Kimi")
    parsed_intent = st.session_state.get("parsed_intent")
    if parse_button:
        parsed_intent = extract_intent_with_kimi(raw_prompt)
        st.session_state["parsed_intent"] = parsed_intent
    query = st.text_input("Query", value=str((parsed_intent or {}).get("normalized_query", raw_prompt)))
    rank_points = st.slider(
        "Rank Points",
        min_value=40,
        max_value=90,
        value=int(float((parsed_intent or {}).get("student_rp", 75))),
        step=1,
    )
    interest_fields = st.multiselect(
        "Fields of interest",
        ["course", "university", "status", "salary_estimate", "reddit_vibe", "news_signal"],
        default=["course", "status", "salary_estimate", "reddit_vibe", "news_signal"],
    )
    demo_mode = st.checkbox("Demo mode / fallback", value=True)
    call_backend = st.checkbox("Use packaged API endpoint instead of direct core call", value=False)
    run_button = st.button("Run pipeline", type="primary")

left, right = st.columns([1.35, 1])

with left:
    st.subheader("Live output")
    log_box = st.empty()
    table_box = st.empty()

with right:
    st.subheader("Run details")
    st.write({"query": query, "rank_points": rank_points, "demo_mode": demo_mode, "call_backend": call_backend})
    if parsed_intent:
        st.caption(f"Kimi parsed: {parsed_intent}")

if run_button:
    events: list[dict[str, object]] = []
    final_result: dict[str, object] | None = None

    if call_backend:
        try:
            response = requests.post(
                "http://127.0.0.1:8000/orchestrate",
                json={"raw_text": raw_prompt, "use_fallback": demo_mode},
                timeout=600,
            )
            response.raise_for_status()
            final_result = response.json()
            events = list(final_result.get("events", []))
        except Exception as exc:
            st.error(f"Packaged API call failed: {exc}")
    else:
        pipeline = route_and_scrape_with_sponsors_streaming(raw_prompt if raw_prompt else query, use_fallback=demo_mode)
        for event in pipeline:
            events.append(event)
            log_box.info(f"{event.get('status')}: {event.get('message')}")
            if event.get("status") == "done":
                final_result = event
            if event.get("status") == "complete":
                final_result = event

    if final_result is None:
        st.error("The pipeline did not return a final result.")
    else:
        trace = final_result.get("trace", {}) if isinstance(final_result, dict) else {}
        rows = final_result.get("data", [])
        if isinstance(rows, list):
            filtered_rows = []
            for row in rows:
                if not isinstance(row, dict):
                    continue
                filtered_rows.append({field: row.get(field) for field in interest_fields})
            table_box.dataframe(filtered_rows, use_container_width=True, hide_index=True)
        else:
            st.warning("The final result did not include a list of rows.")

        if final_result.get("summary"):
            st.success(str(final_result["summary"]))

        cost_value = None
        if isinstance(trace, dict):
            cost_value = trace.get("cost")
        if cost_value is not None:
            st.caption(f"Cost: ${float(cost_value):.3f}")

        with st.expander("Raw events", expanded=False):
            st.json(events)
