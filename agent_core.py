"""
agent_core.py
=============
Core scoring + orchestration logic for SG UniNavigator.

Contains three public entry points:
  - score_courses(student_rp, scraped_data, weights) -> list[dict]
        Pure, deterministic ranking engine. Logic is FROZEN per the task spec.
  - extract_weights(user_priority) -> dict
        Maps a free-text priority into composite-score weights summing to 1.0.
  - scrape_and_score(student_rp, user_priority) -> generator
        STUB streaming pipeline that Person B will wire to live scrapers.

The scoring engine reads the field contract defined in fallback_data.py:
    course, university, igp_cutoff, ges_median_salary,
    ges_employment_rate, reddit_pos, reddit_neg, reddit_neu
"""


# ──────────────────────────────────────────────────────────────────────────
# TASK 2 — Scoring engine.
# NOTE: This function's logic is a contract. Do NOT change the math, the
# field names, the early-continue threshold, or the output keys. The only
# additions are surrounding docstring/comments.
# ──────────────────────────────────────────────────────────────────────────
def score_courses(student_rp, scraped_data, weights):
    """Rank courses for a student given scraped data and priority weights.

    Args:
        student_rp:   float  -- student's A-level Rank Points (0-90 scale).
        scraped_data: dict   -- must contain key "courses" -> list of course
                                dicts following the fallback_data contract.
        weights:      dict   -- keys rp_safety, job_score, sentiment (sum 1.0),
                                as produced by extract_weights().

    Returns:
        list[dict]: up to the top 5 courses, sorted by composite score
                    descending. Each row uses display-ready keys:
                    course, institution, rp_gap, median_salary,
                    employment, reddit_vibe, score.

    Courses where the student is more than 3 RP below the cutoff are dropped
    (treated as out of reach).
    """
    results = []
    for course in scraped_data["courses"]:
        rp_gap = student_rp - course["igp_cutoff"]
        if rp_gap < -3:
            continue
        rp_score = min(100, 50 + rp_gap * 8)
        salary_norm = min(100, (course["ges_median_salary"] - 2500) / 40)
        job_score = 0.6 * salary_norm + 0.4 * course["ges_employment_rate"]
        total = course["reddit_pos"] + course["reddit_neg"] + course["reddit_neu"]
        sentiment_score = 50 + ((course["reddit_pos"] - course["reddit_neg"]) / max(total, 1)) * 50
        composite = (
            weights["rp_safety"]  * rp_score +
            weights["job_score"]  * job_score +
            weights["sentiment"]  * sentiment_score
        )
        results.append({
            "course":        course["course"],
            "institution":   course["university"],
            "rp_gap":        f"+{rp_gap:.2f}" if rp_gap >= 0 else f"{rp_gap:.2f}",
            "median_salary": course["ges_median_salary"],
            "employment":    f"{course['ges_employment_rate']:.1f}%",
            "reddit_vibe":   "Positive" if sentiment_score > 65 else "Mixed" if sentiment_score > 40 else "Cautious",
            "score":         round(composite, 1)
        })
    return sorted(results, key=lambda x: x["score"], reverse=True)[:5]


# ──────────────────────────────────────────────────────────────────────────
# TASK 2 (cont.) — Weight extraction from free-text priority.
# ──────────────────────────────────────────────────────────────────────────
def extract_weights(user_priority: str) -> dict:
    """Translate a free-text priority into composite-score weights.

    Routing rules (first match wins):
      - mentions money/career      -> weight job_score heavily
        keywords: salary, job, money, career, pay, rich, employ
      - mentions an easy life       -> weight sentiment (student vibe) heavily
        keywords: chill, workload, relax, easy, stress, fun, lifestyle, wlb
      - mentions safety/backup      -> weight rp_safety heavily
        keywords: safe, safety, backup, sure, guarantee, secure
      - anything else / empty       -> balanced

    The three returned weights ALWAYS sum to 1.0 so the composite score in
    score_courses() stays on a stable 0-100ish scale regardless of priority.

    Returns:
        dict with float keys: rp_safety, job_score, sentiment.
    """
    text = (user_priority or "").lower()

    job_keywords = ("salary", "job", "money", "career", "pay", "rich", "employ")
    chill_keywords = ("chill", "workload", "relax", "easy", "stress", "fun",
                      "lifestyle", "wlb", "balance")
    safety_keywords = ("safe", "safety", "backup", "sure", "guarantee", "secure")

    if any(k in text for k in job_keywords):
        # Career-driven: prioritise salary + employment outcomes.
        return {"rp_safety": 0.20, "job_score": 0.60, "sentiment": 0.20}

    if any(k in text for k in chill_keywords):
        # Lifestyle-driven: prioritise student sentiment / vibe.
        return {"rp_safety": 0.20, "job_score": 0.20, "sentiment": 0.60}

    if any(k in text for k in safety_keywords):
        # Risk-averse: prioritise comfortable admission margin.
        return {"rp_safety": 0.60, "job_score": 0.20, "sentiment": 0.20}

    # Default: balanced across all three dimensions (sums to 1.0).
    return {"rp_safety": 0.34, "job_score": 0.33, "sentiment": 0.33}


# ──────────────────────────────────────────────────────────────────────────
# TASK 4 — Streaming pipeline STUB.
# Person B replaces the body with real scraping (Bright Data IGP/GES scrape,
# Reddit sentiment, etc.) but MUST preserve this yield protocol so the
# Streamlit UI keeps working unchanged:
#   {"type": "status", "message": str}  -> progress log line
#   {"type": "result", "data": list}    -> final scored rows from score_courses
# ──────────────────────────────────────────────────────────────────────────
def scrape_and_score(student_rp: float, user_priority: str):
    """STUB live pipeline — yields progress events then a final result.

    This is a generator. The UI iterates it, rendering each "status" event as
    a progress line and unpacking the single "result" event into the table.

    Person B: build the real scrapers here. Convert your scraped courses into
    the fallback_data field contract, then feed them through:
        weights = extract_weights(user_priority)
        rows = score_courses(student_rp, {"courses": scraped}, weights)
        yield {"type": "result", "data": rows}
    """
    # STUB — Person B wires live scraping here
    # Must be a generator that yields dicts:
    # {"type": "status", "message": "..."} for progress logs
    # {"type": "result", "data": [...]} for final scored list
    yield {"type": "status", "message": "Initialising scrapers..."}
    yield {"type": "status", "message": "Fetching IGP data..."}
    yield {"type": "status", "message": "Fetching GES data..."}
    yield {"type": "status", "message": "Scraping Reddit..."}
    yield {"type": "result", "data": []}  # Person B replaces this


# ══════════════════════════════════════════════════════════════════════════
# INTENT-ROUTING LAYER  (refactor to match the architecture diagram)
#
#   User free-text  ->  classify_intent (TokenRouter + Kimi, rules fallback)
#                       ->  Branch 1 EXPLORE   (only RP)
#                       ->  Branch 2 EVALUATE  (named course: vibe + hiring)
#                       ->  Branch 3 ADMISSION (named course: pass/fail math)
#                       ->  route_query() returns (intent_obj, result)
#
# The frozen score_courses()/extract_weights() above remain available as
# secondary helpers; the primary flow is now classify-then-branch.
# ══════════════════════════════════════════════════════════════════════════
import os
import re
import json

from fallback_data import (
    FALLBACK_COURSES,
    COURSE_ALIASES,
    FALLBACK_HIRING_NEWS,
    course_key,
)

INTENT_EXPLORE = "EXPLORE"
INTENT_EVALUATE = "EVALUATE"
INTENT_ADMISSION = "ADMISSION"

# Phrases that signal "can I get IN?" -> ADMISSION (only when a course is named).
_ADMISSION_PHRASES = (
    "can i get", "will i get", "get into", "get in to", "qualify",
    "do i qualify", "chance", "good enough", "enough for", "enough to",
    "admit", "admission", "do i make", "shot at", "able to get",
    "will i make", "can i make", "eligible",
)


def _extract_rp(text):
    """Pull the first plausible RP value (0-90) out of free text, or None."""
    for token in re.findall(r"\d{1,3}(?:\.\d+)?", text or ""):
        value = float(token)
        if 0 <= value <= 90:
            return value
    return None


def match_course(text):
    """Resolve messy free text to a single course dict, or None.

    Returns the course whose LONGEST matching alias appears in `text`.
    Short / single-token aliases (cs, ds, eee, medicine, infosys) are matched
    with word boundaries so they don't fire inside unrelated words.
    """
    if not text:
        return None
    t = text.lower()
    by_key = {course_key(c): c for c in FALLBACK_COURSES}
    best = None  # (alias_length, course)
    for key, aliases in COURSE_ALIASES.items():
        course = by_key.get(key)
        if not course:
            continue
        for alias in aliases:
            a = alias.lower()
            if " " in a:
                hit = a in t  # multi-word phrase: substring is safe
            else:
                # single token: require word boundaries (no surrounding alnum)
                hit = re.search(r"(?<![a-z0-9])" + re.escape(a) + r"(?![a-z0-9])", t) is not None
            if hit and (best is None or len(a) > best[0]):
                best = (len(a), course)
    return best[1] if best else None


def _course_by_key(key):
    """Look up a course dict by its canonical 'Uni Course' key."""
    if not key:
        return None
    for c in FALLBACK_COURSES:
        if course_key(c) == key:
            return c
    return None


# ── Intent classification ────────────────────────────────────────────────
def _classify_intent_rules(text, student_rp=None):
    """Deterministic classifier used in Demo Mode and as the LLM fallback."""
    t = (text or "").lower()
    course = match_course(t)
    rp = _extract_rp(t)
    if rp is None:
        rp = student_rp
    is_admission = any(p in t for p in _ADMISSION_PHRASES)

    if course is not None and is_admission:
        intent = INTENT_ADMISSION
    elif course is not None:
        intent = INTENT_EVALUATE
    else:
        intent = INTENT_EXPLORE

    return {
        "intent": intent,
        "course": course_key(course) if course else None,
        "rp": rp,
        "engine": "rules",
    }


def _get_llm_client():
    """Build a Kimi (Moonshot) client via the OpenAI-compatible SDK, or None.

    Kimi is the brain. Prefers KIMI_API_KEY / MOONSHOT_API_KEY; falls back to
    TokenRouter (also OpenAI-compatible, NOT OpenAI) only if Kimi is unset.
    No OpenAI API key is ever read — the `openai` package is just the
    OpenAI-compatible transport. Returns None when no key is present or the
    package isn't installed, so callers fall back to the rules classifier.
    Keys come from the environment only (.env) — never hardcoded.
    """
    try:
        from openai import OpenAI
    except Exception:
        return None

    # Kimi / Moonshot is the brain — try it first.
    kimi_key = os.getenv("KIMI_API_KEY") or os.getenv("MOONSHOT_API_KEY")
    if kimi_key:
        base = os.getenv("KIMI_BASE_URL", "https://api.moonshot.ai/v1")
        model = os.getenv("KIMI_MODEL", "kimi-k2.6")
        return OpenAI(api_key=kimi_key, base_url=base), model

    # Optional secondary: TokenRouter (OpenAI-compatible router, not OpenAI).
    tr_key = os.getenv("TOKENROUTER_API_KEY")
    if tr_key:
        base = os.getenv("TOKENROUTER_BASE_URL", "https://api.tokenrouter.com/v1")
        model = os.getenv("TOKENROUTER_MODEL", "kimi-k2.6")
        return OpenAI(api_key=tr_key, base_url=base), model

    return None


_CLASSIFIER_SYSTEM = (
    "You are an intent classifier for a Singapore university course advisor. "
    "Classify the user's message into exactly one intent and extract entities.\n"
    "Intents:\n"
    "- EXPLORE: user gives only their RP / grades and wants options.\n"
    "- EVALUATE: user names a specific course and wants its vibe / outlook.\n"
    "- ADMISSION: user asks whether they can get INTO a specific named course.\n"
    'Respond with STRICT JSON only: '
    '{"intent": "EXPLORE|EVALUATE|ADMISSION", "course": "<course name or null>", '
    '"rp": <number or null>}'
)


def _classify_intent_llm(text, student_rp=None):
    """TokenRouter + Kimi classifier. Returns None on any failure."""
    got = _get_llm_client()
    if not got:
        return None
    client, model = got
    try:
        resp = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": _CLASSIFIER_SYSTEM},
                {"role": "user", "content": text or ""},
            ],
            temperature=0,
            max_tokens=200,
        )
        content = (resp.choices[0].message.content or "").strip()
        content = re.sub(r"^```(?:json)?|```$", "", content.strip()).strip()
        data = json.loads(content)

        intent = str(data.get("intent", "")).upper()
        if intent not in (INTENT_EXPLORE, INTENT_EVALUATE, INTENT_ADMISSION):
            return None

        course = match_course(data.get("course") or "") if data.get("course") else None
        rp = data.get("rp")
        try:
            rp = float(rp) if rp is not None else None
        except (TypeError, ValueError):
            rp = None
        if rp is None:
            rp = student_rp

        return {
            "intent": intent,
            "course": course_key(course) if course else None,
            "rp": rp,
            "engine": "llm",
        }
    except Exception:
        return None


def classify_intent(text, student_rp=None, use_llm=False):
    """Classify free text into EXPLORE / EVALUATE / ADMISSION + entities.

    use_llm=True tries the TokenRouter+Kimi classifier first and falls back to
    deterministic rules on ANY failure (no key, network error, bad JSON).
    Demo Mode passes use_llm=False -> always rules, fully offline.
    """
    if use_llm:
        llm = _classify_intent_llm(text, student_rp)
        if llm is not None:
            return llm
    return _classify_intent_rules(text, student_rp)


# ── Branch handlers ──────────────────────────────────────────────────────
def branch_explore(student_rp, courses=None):
    """Branch 1 — EXPLORE: list ALL options vs the static cutoffs for an RP.

    Unlike score_courses() (top-5 weighted ranking), this returns every course
    with a Safe / Reach / Out of reach verdict so the student sees the full
    landscape. Valid options (Safe + Reach) are listed first, most competitive
    on top.
    """
    courses = courses if courses is not None else FALLBACK_COURSES
    rp = float(student_rp)
    rows = []
    for c in courses:
        gap = rp - c["igp_cutoff"]
        if gap >= 0:
            verdict = "Safe"
        elif gap >= -3:
            verdict = "Reach"
        else:
            verdict = "Out of reach"
        rows.append({
            "course": c["course"],
            "institution": c["university"],
            "igp_cutoff": c["igp_cutoff"],
            "rp_gap": f"+{gap:.2f}" if gap >= 0 else f"{gap:.2f}",
            "verdict": verdict,
            "median_salary": c["ges_median_salary"],
            "employment": f"{c['ges_employment_rate']:.1f}%",
            "_gap": gap,
        })
    # Valid (gap >= -3) first, then most competitive (highest cutoff) on top.
    rows.sort(key=lambda r: (r["_gap"] < -3, -r["igp_cutoff"]))
    for r in rows:
        r.pop("_gap", None)
    return {
        "intent": INTENT_EXPLORE,
        "student_rp": rp,
        "options": rows,
        "n_valid": sum(1 for r in rows if r["verdict"] != "Out of reach"),
    }


def _resolve_course(course_query):
    """Accept a course dict, canonical key, or free text -> course dict|None."""
    if isinstance(course_query, dict):
        return course_query
    return _course_by_key(course_query) or match_course(course_query or "")


def branch_evaluate(course_query, demo_mode=True):
    """Branch 2 — EVALUATE: deep-dive one named course (Reddit vibe + hiring)."""
    course = _resolve_course(course_query)
    if course is None:
        return {
            "intent": INTENT_EVALUATE,
            "matched": False,
            "query": course_query,
            "message": "Couldn't identify that course. Try e.g. "
                       "'NUS Computer Science' or 'NTU EEE'.",
            "suggestions": [course_key(c) for c in FALLBACK_COURSES],
        }
    key = course_key(course)
    pos, neg, neu = course["reddit_pos"], course["reddit_neg"], course["reddit_neu"]
    total = max(pos + neg + neu, 1)
    sentiment_score = 50 + ((pos - neg) / total) * 50
    vibe = "Positive" if sentiment_score > 65 else "Mixed" if sentiment_score > 40 else "Cautious"
    return {
        "intent": INTENT_EVALUATE,
        "matched": True,
        "course": course["course"],
        "institution": course["university"],
        "igp_cutoff": course["igp_cutoff"],
        "median_salary": course["ges_median_salary"],
        "employment": f"{course['ges_employment_rate']:.1f}%",
        "reddit": {
            "pos": pos, "neg": neg, "neu": neu,
            "pct_positive": round(100 * pos / total, 1),
            "vibe": vibe,
            "sentiment_score": round(sentiment_score, 1),
        },
        "hiring_news": FALLBACK_HIRING_NEWS.get(key, []),
    }


def branch_admission(course_query, student_rp):
    """Branch 3 — ADMISSION: strict pass/fail of an RP against a course cutoff."""
    course = _resolve_course(course_query)
    if course is None:
        return {
            "intent": INTENT_ADMISSION,
            "matched": False,
            "query": course_query,
            "message": "Tell me which course, e.g. "
                       "'Can I get into NUS Computer Science?'",
            "suggestions": [course_key(c) for c in FALLBACK_COURSES],
        }
    rp = float(student_rp)
    cutoff = course["igp_cutoff"]
    gap = rp - cutoff
    if gap >= 1:
        verdict = "LIKELY IN"
    elif gap >= -1:
        verdict = "BORDERLINE"
    else:
        verdict = "UNLIKELY"
    passed = gap >= 0
    math_steps = [
        f"Your RP:                {rp:.2f}",
        f"{course['university']} {course['course']} cutoff:  {cutoff:.2f}",
        f"Gap (RP - cutoff):      {gap:+.2f}",
        f"Meets cutoff?           {'YES' if passed else 'NO'}  ->  {verdict}",
    ]
    return {
        "intent": INTENT_ADMISSION,
        "matched": True,
        "course": course["course"],
        "institution": course["university"],
        "igp_cutoff": cutoff,
        "student_rp": rp,
        "rp_gap": f"{gap:+.2f}",
        "passed": passed,
        "verdict": verdict,
        "math": math_steps,
    }


def route_query(text, student_rp, demo_mode=True):
    """Top-level dispatcher matching the architecture diagram.

    1. Classify intent (TokenRouter+Kimi in live mode, rules in demo/on failure).
    2. Dispatch to the matching branch handler.

    Returns (intent_obj, result_dict). intent_obj carries the detected intent,
    matched course key, extracted RP, and which engine classified it.
    """
    intent_obj = classify_intent(text, student_rp=student_rp, use_llm=not demo_mode)
    intent = intent_obj["intent"]
    matched_course = intent_obj.get("course")
    rp = intent_obj.get("rp")
    if rp is None:
        rp = student_rp

    if intent == INTENT_EVALUATE:
        result = branch_evaluate(matched_course or text, demo_mode=demo_mode)
    elif intent == INTENT_ADMISSION:
        result = branch_admission(matched_course or text, rp)
    else:
        result = branch_explore(rp)

    return intent_obj, result
