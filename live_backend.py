from __future__ import annotations

import json
import os
import re
import xml.etree.ElementTree as ET
import time
from dataclasses import dataclass
from typing import Any, Iterable

import requests
from dotenv import load_dotenv
from openai import OpenAI

BRIGHTDATA_BASE_URL = "https://api.brightdata.com"
TOKENROUTER_BASE_URL = "https://api.tokenrouter.com/v1"
DEFAULT_TIMEOUT_SECONDS = 900
DEFAULT_POLL_SECONDS = 5
GES_DATASET_ID = "d_3c55210de27fcccda2ed0c63fdd2b352"
NEWS_RSS_BASE_URL = "https://news.google.com/rss/search"

FALLBACK_DATA: dict[str, list[dict[str, Any]]] = {
    "Engineering": [
        {
            "course": "Mechanical Engineering",
            "university": "NUS",
            "status": "Strong prospects",
            "salary_estimate": "$4,900",
            "employment_rate": "92.1%",
            "reddit_vibe": "Mixed",
            "news_signal": "Asia manufacturing and robotics hiring remains steady",
        },
        {
            "course": "Electrical Engineering",
            "university": "NTU",
            "status": "Strong prospects",
            "salary_estimate": "$4,700",
            "employment_rate": "91.4%",
            "reddit_vibe": "Mixed",
            "news_signal": "Semiconductor and systems roles continue to hire across Asia",
        },
        {
            "course": "Civil Engineering",
            "university": "SMU",
            "status": "Stable prospects",
            "salary_estimate": "$4,500",
            "employment_rate": "90.0%",
            "reddit_vibe": "Neutral",
            "news_signal": "Infrastructure and urban development demand stays resilient",
        },
    ],
    "Computing": [
        {
            "course": "Information Systems",
            "university": "SMU",
            "status": "Safe (+3.75 RP)",
            "salary_estimate": "$4,300",
            "employment_rate": "93.8%",
            "reddit_vibe": "Positive",
            "news_signal": "Asia tech hiring remains active",
        },
        {
            "course": "Data Science & AI",
            "university": "NTU",
            "status": "Safe (+0.75 RP)",
            "salary_estimate": "$4,800",
            "employment_rate": "95.2%",
            "reddit_vibe": "Positive",
            "news_signal": "AI roles continue expanding across Asia",
        },
        {
            "course": "Computer Science",
            "university": "NUS",
            "status": "Risky (-1.25 RP)",
            "salary_estimate": "$5,200",
            "employment_rate": "94.7%",
            "reddit_vibe": "Mixed",
            "news_signal": "Regional product and platform roles stay competitive",
        },
    ]
}


@dataclass(frozen=True)
class PipelineSettings:
    brightdata_api_token: str
    uni_collector_id: str
    reddit_collector_id: str
    techasia_collector_id: str
    gov_data_url: str
    tokenrouter_api_key: str | None
    tokenrouter_model: str
    tokenrouter_base_url: str
    kimi_api_key: str | None
    kimi_base_url: str
    kimi_model: str
    daytona_api_key: str | None
    daytona_base_url: str
    uni_inputs_json: str | None
    reddit_inputs_json: str | None
    techasia_inputs_json: str | None

    @classmethod
    def from_env(cls) -> "PipelineSettings":
        load_dotenv()
        return cls(
            brightdata_api_token=os.getenv("BRIGHTDATA_API_TOKEN", "").strip(),
            uni_collector_id=os.getenv("BRIGHTDATA_UNI_COLLECTOR_ID", "").strip(),
            reddit_collector_id=os.getenv("BRIGHTDATA_REDDIT_COLLECTOR_ID", "").strip(),
            techasia_collector_id=os.getenv("BRIGHTDATA_TECHASIA_COLLECTOR_ID", "").strip(),
            gov_data_url=os.getenv("GOV_DATA_URL", "").strip(),
            tokenrouter_api_key=os.getenv("TOKENROUTER_API_KEY", "").strip() or None,
            tokenrouter_model=os.getenv("TOKENROUTER_MODEL", "gpt-4o-mini").strip(),
            tokenrouter_base_url=os.getenv("TOKENROUTER_BASE_URL", TOKENROUTER_BASE_URL).strip(),
            kimi_api_key=(os.getenv("KIMI_API_KEY", "").strip() or os.getenv("MOONSHOT_API_KEY", "").strip()) or None,
            kimi_base_url=os.getenv("KIMI_BASE_URL", "https://api.moonshot.ai/v1").strip(),
            kimi_model=os.getenv("KIMI_MODEL", "kimi-k2.6").strip(),
            daytona_api_key=os.getenv("DAYTONA_API_KEY", "").strip() or None,
            daytona_base_url=os.getenv("DAYTONA_BASE_URL", "https://api.daytona.io/v1").strip(),
            uni_inputs_json=os.getenv("BRIGHTDATA_UNI_INPUTS_JSON"),
            reddit_inputs_json=os.getenv("BRIGHTDATA_REDDIT_INPUTS_JSON"),
            techasia_inputs_json=os.getenv("BRIGHTDATA_TECHASIA_INPUTS_JSON"),
        )


def _clean_text(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        stripped = value.strip()
        return stripped or None
    return str(value).strip() or None


def _safe_float(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        digits = []
        has_decimal = False
        for character in value:
            if character.isdigit():
                digits.append(character)
            elif character == "." and not has_decimal:
                digits.append(character)
                has_decimal = True
            elif digits:
                break
        if not digits:
            return None
        try:
            return float("".join(digits))
        except ValueError:
            return None
    return None


def _maybe_monthly_amount(field_name: str, value: float) -> float:
    lowered = field_name.lower()
    if any(marker in lowered for marker in ("annual", "year", "yearly", "per_annum")):
        return value / 12.0
    return value


def _extract_rows(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [row for row in payload if isinstance(row, dict)]
    if isinstance(payload, dict):
        for key in ("data", "results", "items", "rows", "records"):
            value = payload.get(key)
            if isinstance(value, list):
                return [row for row in value if isinstance(row, dict)]
    return []


def _first_present(row: dict[str, Any], *keys: str) -> str | None:
    for key in keys:
        value = row.get(key)
        text = _clean_text(value)
        if text:
            return text
    for candidate_key, candidate_value in row.items():
        lowered = candidate_key.lower()
        if any(key in lowered for key in keys):
            text = _clean_text(candidate_value)
            if text:
                return text
    return None


def _load_inputs(raw_inputs_json: str | None, fallback_inputs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if raw_inputs_json:
        try:
            parsed = json.loads(raw_inputs_json)
            if isinstance(parsed, list) and all(isinstance(item, dict) for item in parsed):
                return parsed
        except json.JSONDecodeError:
            pass
    return fallback_inputs


def _normalize_data_gov_url(url: str) -> str:
    stripped = url.strip()
    if not stripped:
        return ""
    if "api/action/datastore_search" in stripped:
        return stripped
    if "data.gov.sg/datasets" in stripped or "resultId=" in stripped:
        return f"https://data.gov.sg/api/action/datastore_search?resource_id={GES_DATASET_ID}"
    return stripped


def _normalize_news_query(interest: str) -> str:
    cleaned = interest.strip()
    if not cleaned:
        return "Asia careers"
    return f'{cleaned} jobs hiring OR salaries OR internships Asia'


def _route_from_intent(student_rp: float | None, interest: str, priority_weights: dict[str, Any] | None = None) -> str:
    interest_lower = interest.lower().strip()
    if not interest_lower:
        return "EXPLORE"
    if student_rp and student_rp < 70 and any(token in interest_lower for token in ("course", "fit", "can i get", "admission", "cutoff")):
        return "EXPLORE"
    if any(token in interest_lower for token in ("can i get", "chance", "admission", "admit", "cutoff", "igp")):
        return "ADMISSION"
    if any(token in interest_lower for token in ("salary", "bank", "industry", "prospect", "vibe", "workload", "chill")):
        return "EVALUATE"
    if priority_weights and isinstance(priority_weights, dict):
        salary_weight = float(priority_weights.get("salary", 0) or 0)
        workload_weight = float(priority_weights.get("workload", 0) or 0)
        if salary_weight > workload_weight:
            return "EVALUATE"
    return "EVALUATE"


def _heuristic_intent_from_text(raw_text: str) -> dict[str, Any]:
    lowered = raw_text.lower()
    rp_match = re.search(r"(\d{2}(?:\.\d{1,2})?)\s*rp", lowered)
    student_rp = float(rp_match.group(1)) if rp_match else None
    if any(token in lowered for token in ("engineer", "engineering", "engineering courses", "mechanical", "electrical", "civil")):
        interest = "Engineering"
    elif any(token in lowered for token in ("computing", "computer", "software", "data", "ai", "cs")):
        interest = "Computing"
    elif any(token in lowered for token in ("business", "bank", "finance", "account", "econom", "marketing")):
        interest = "Business"
    elif any(token in lowered for token in ("law", "legal", "advocate")):
        interest = "Law"
    elif any(token in lowered for token in ("engineering", "mech", "electrical", "civil", "robot")):
        interest = "Engineering"
    elif any(token in lowered for token in ("science", "bio", "chem", "physics")):
        interest = "Science"
    else:
        interest = "Computing"
    priority_weights = {
        "salary": 0.4 if any(token in lowered for token in ("bank", "salary", "pay", "industry")) else 0.25,
        "workload": 0.35 if any(token in lowered for token in ("chill", "workload", "stress", "manageable")) else 0.2,
        "fit": 0.35,
    }
    branch = _route_from_intent(student_rp, interest, priority_weights)
    if any(token in lowered for token in ("future options", "future path", "options", "what can i do", "next step", "next steps")):
        branch = "EXPLORE"
    return {
        "student_rp": student_rp,
        "interest": interest,
        "priority_weights": priority_weights,
        "normalized_query": raw_text.strip(),
        "branch": branch,
        "confidence": 0.55,
        "source": "heuristic",
    }


def _response_usage(response: Any) -> dict[str, Any]:
    usage = getattr(response, "usage", None)
    if usage is None:
        return {}
    if hasattr(usage, "model_dump"):
        return usage.model_dump()
    if hasattr(usage, "dict"):
        return usage.dict()
    return {"prompt_tokens": getattr(usage, "prompt_tokens", None), "completion_tokens": getattr(usage, "completion_tokens", None), "total_tokens": getattr(usage, "total_tokens", None)}


def _build_headers(api_token: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {api_token}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }


def trigger_collector(
    session: requests.Session,
    api_token: str,
    collector_id: str,
    inputs: list[dict[str, Any]],
) -> str:
    if not collector_id:
        raise ValueError("Missing Bright Data collector ID")
    response = session.post(
        f"{BRIGHTDATA_BASE_URL}/dca/trigger",
        params={"collector": collector_id, "queue_next": 1},
        headers=_build_headers(api_token),
        json=inputs,
        timeout=60,
    )
    response.raise_for_status()
    payload = response.json()
    snapshot_id = payload.get("collection_id") or payload.get("snapshot_id")
    if not snapshot_id:
        raise ValueError(f"Bright Data trigger response did not include a collection_id: {payload}")
    return str(snapshot_id)


def poll_snapshot(
    session: requests.Session,
    api_token: str,
    snapshot_id: str,
    timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
    poll_seconds: int = DEFAULT_POLL_SECONDS,
) -> list[dict[str, Any]]:
    deadline = time.monotonic() + timeout_seconds
    while True:
        response = session.get(
            f"{BRIGHTDATA_BASE_URL}/dca/dataset",
            params={"id": snapshot_id},
            headers={"Authorization": f"Bearer {api_token}"},
            timeout=60,
        )
        response.raise_for_status()
        payload = response.json()
        if isinstance(payload, list):
            return [row for row in payload if isinstance(row, dict)]
        if isinstance(payload, dict):
            status = str(payload.get("status", "")).lower()
            if status in {"building", "queued", "running", "pending"}:
                if time.monotonic() >= deadline:
                    raise TimeoutError(f"Timed out waiting for snapshot {snapshot_id}")
                time.sleep(poll_seconds)
                continue
            if "error" in payload:
                raise RuntimeError(f"Bright Data snapshot error: {payload}")
        if time.monotonic() >= deadline:
            raise TimeoutError(f"Timed out waiting for snapshot {snapshot_id}")
        time.sleep(poll_seconds)


def fetch_government_data(session: requests.Session, url: str) -> list[dict[str, Any]]:
    if not url:
        return []
    response = session.get(_normalize_data_gov_url(url), timeout=60)
    response.raise_for_status()
    payload = response.json()
    return _extract_rows(payload)


def fetch_asia_news(session: requests.Session, interest: str) -> list[dict[str, Any]]:
    query = _normalize_news_query(interest)
    response = session.get(
        NEWS_RSS_BASE_URL,
        params={"q": query, "hl": "en-US", "gl": "US", "ceid": "US:en"},
        timeout=60,
    )
    response.raise_for_status()
    root = ET.fromstring(response.text)
    items: list[dict[str, Any]] = []
    for item in root.findall("./channel/item")[:8]:
        title = _clean_text(item.findtext("title")) or ""
        link = _clean_text(item.findtext("link")) or ""
        description = _clean_text(item.findtext("description")) or ""
        pub_date = _clean_text(item.findtext("pubDate")) or ""
        items.append(
            {
                "title": title,
                "link": link,
                "description": description,
                "pub_date": pub_date,
            }
        )
    return items


def _salary_from_gov_rows(rows: list[dict[str, Any]]) -> str:
    samples: list[float] = []
    for row in rows:
        for key, value in row.items():
            lowered = key.lower()
            if not any(marker in lowered for marker in ("salary", "pay", "income", "wage", "monthly", "annual")):
                continue
            numeric_value = _safe_float(value)
            if numeric_value is None:
                continue
            samples.append(_maybe_monthly_amount(lowered, numeric_value))
    if not samples:
        return "No salary signal yet"
    average = sum(samples) / len(samples)
    return f"S${average:,.0f}/month"


def _reddit_vibe_from_rows(rows: list[dict[str, Any]]) -> str:
    texts: list[str] = []
    for row in rows[:20]:
        text = _first_present(row, "title", "post_title", "text", "body", "content", "summary")
        if text:
            texts.append(text)
    if not texts:
        return "No Reddit signal yet"
    positive = sum(token in " ".join(texts).lower() for token in ("good", "great", "helpful", "chill", "manageable", "solid"))
    negative = sum(token in " ".join(texts).lower() for token in ("stress", "bad", "hard", "terrible", "toxic", "panic"))
    if positive > negative:
        label = "Positive"
    elif negative > positive:
        label = "Tense"
    else:
        label = "Mixed"
    highlights = "; ".join(texts[:3])
    return f"{label} vibe - {highlights}"


def _news_signal_from_items(items: list[dict[str, Any]]) -> str:
    if not items:
        return "No Asia news signal yet"
    titles = [item.get("title", "") for item in items[:3] if item.get("title")]
    joined = " | ".join(titles)
    lowered = joined.lower()
    positive_markers = sum(marker in lowered for marker in ("hiring", "growth", "expands", "boom", "rise", "surge"))
    negative_markers = sum(marker in lowered for marker in ("layoff", "slowdown", "weak", "cut", "freeze", "decline"))
    if positive_markers > negative_markers:
        prefix = "Positive Asia trend"
    elif negative_markers > positive_markers:
        prefix = "Cooling Asia trend"
    else:
        prefix = "Mixed Asia trend"
    return f"{prefix} - {joined}"


def merge_results(
    uni_rows: list[dict[str, Any]],
    reddit_rows: list[dict[str, Any]],
    gov_rows: list[dict[str, Any]],
    news_items: list[dict[str, Any]],
    query: str,
) -> list[dict[str, Any]]:
    if not uni_rows:
        uni_rows = [{"course": query or "Unknown course", "university": "Unknown university", "status": "No uni data"}]

    salary_estimate = _salary_from_gov_rows(gov_rows)
    reddit_vibe = _reddit_vibe_from_rows(reddit_rows)
    news_signal = _news_signal_from_items(news_items)

    merged_rows: list[dict[str, Any]] = []
    for row in uni_rows:
        merged_rows.append(
            {
                "course": _first_present(row, "course", "programme", "program", "title", "name") or query or "Unknown course",
                "university": _first_present(row, "university", "school", "institution", "campus") or "Unknown university",
                "status": _first_present(row, "status", "cutoff_status", "admission_status") or "available",
                "salary_estimate": _first_present(row, "salary_estimate") or salary_estimate,
                "reddit_vibe": _first_present(row, "reddit_vibe") or reddit_vibe,
                "news_signal": _first_present(row, "news_signal") or news_signal,
            }
        )
    return merged_rows


def build_tokenrouter_client(settings: PipelineSettings) -> OpenAI | None:
    if not settings.tokenrouter_api_key:
        return None
    return OpenAI(api_key=settings.tokenrouter_api_key, base_url=settings.tokenrouter_base_url)


def build_kimi_client(settings: PipelineSettings) -> OpenAI | None:
    kimi_key = os.getenv("MOONSHOT_API_KEY", "").strip() or settings.kimi_api_key
    if not kimi_key:
        return None
    return OpenAI(api_key=kimi_key, base_url=settings.kimi_base_url)


def extract_intent_with_kimi(raw_text: str) -> dict[str, Any]:
    settings = PipelineSettings.from_env()
    client = build_kimi_client(settings)
    if client is None:
        return _heuristic_intent_from_text(raw_text)
    try:
        response = client.chat.completions.create(
            model=settings.kimi_model,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "Extract student admissions intent from freeform text. Return STRICT JSON only with keys: "
                        "student_rp (number or null if not mentioned), interest (string), priority_weights (object with salary/workload/fit numbers), "
                        "normalized_query (string), branch (one of EXPLORE, EVALUATE, ADMISSION), confidence (number)."
                    ),
                },
                {"role": "user", "content": raw_text},
            ],
            temperature=0.0,
        )
        content = response.choices[0].message.content or ""
        parsed = json.loads(content)
        if not isinstance(parsed, dict):
            return _heuristic_intent_from_text(raw_text)
        parsed.setdefault("source", "kimi")
        parsed.setdefault("branch", _route_from_intent(float(parsed.get("student_rp", 0) or 0), str(parsed.get("interest", "")), parsed.get("priority_weights")))
        return parsed
    except Exception:
        return _heuristic_intent_from_text(raw_text)


def summarize_with_tokenrouter(
    client: OpenAI | None,
    merged_rows: list[dict[str, Any]],
    query: str,
    model: str,
) -> str | None:
    if client is None:
        return None
    try:
        response = client.chat.completions.create(
            model=model,
            messages=[
                {
                    "role": "system",
                    "content": "Summarize Singapore university admissions and student sentiment in one short paragraph.",
                },
                {
                    "role": "user",
                    "content": json.dumps(
                        {
                            "query": query,
                            "rows": merged_rows,
                        },
                        ensure_ascii=True,
                    ),
                },
            ],
            temperature=0.2,
        )
        return response.choices[0].message.content
    except Exception:
        return None


def summarize_with_kimi(
    client: OpenAI | None,
    merged_rows: list[dict[str, Any]],
    query: str,
) -> dict[str, Any] | None:
    if client is None:
        return None
    try:
        response = client.chat.completions.create(
            model="moonshot-v1-8k",
            messages=[
                {
                    "role": "system",
                    "content": "Summarize Singapore university admissions, Reddit student sentiment, and Asia career news in one short paragraph.",
                },
                {
                    "role": "user",
                    "content": json.dumps(
                        {
                            "query": query,
                            "rows": merged_rows,
                        },
                        ensure_ascii=True,
                    ),
                },
            ],
            temperature=0.2,
        )
        return {
            "provider": "kimi",
            "text": response.choices[0].message.content,
            "usage": _response_usage(response),
        }
    except Exception:
        return None


def polish_summary_with_tokenrouter(
    client: OpenAI | None,
    draft_summary: str | None,
    merged_rows: list[dict[str, Any]],
    query: str,
    model: str,
) -> dict[str, Any] | None:
    local_fallback_text = draft_summary or _local_summary_from_rows(merged_rows, query)
    if client is None:
        return {
            "provider": "tokenrouter",
            "text": local_fallback_text,
            "usage": {},
            "fallback": True,
        }
    try:
        response = client.chat.completions.create(
            model=model,
            messages=[
                {
                    "role": "system",
                    "content": "Refine the draft into a concise, investor-ready summary for a Singapore admissions and careers dashboard.",
                },
                {
                    "role": "user",
                    "content": json.dumps(
                        {
                            "query": query,
                            "draft_summary": draft_summary,
                            "rows": merged_rows,
                        },
                        ensure_ascii=True,
                    ),
                },
            ],
            temperature=0.2,
        )
        return {
            "provider": "tokenrouter",
            "text": response.choices[0].message.content,
            "usage": _response_usage(response),
        }
    except Exception:
        return {
            "provider": "tokenrouter",
            "text": local_fallback_text,
            "usage": {},
            "fallback": True,
        }


def _summary_text(summary_result: dict[str, Any] | None) -> str | None:
    if summary_result is None:
        return None
    text = summary_result.get("text")
    return str(text) if text is not None else None


def _summary_usage(summary_result: dict[str, Any] | None) -> dict[str, Any]:
    if not summary_result:
        return {}
    usage = summary_result.get("usage")
    return usage if isinstance(usage, dict) else {}


def _fallback_rows_for_interest(interest: str) -> list[dict[str, Any]]:
    normalized = interest.strip().title()
    return FALLBACK_DATA.get(normalized, FALLBACK_DATA.get("Engineering", FALLBACK_DATA["Computing"]))


def _local_summary_from_rows(rows: list[dict[str, Any]], query: str) -> str:
    if not rows:
        return f"No live data yet for {query}."
    top = rows[0]
    course = _first_present(top, "course", "program", "programme", "title") or query
    university = _first_present(top, "university", "school", "institution") or "the main universities"
    status = _first_present(top, "status") or "available"
    salary = _first_present(top, "salary_estimate") or "salary data pending"
    vibe = _first_present(top, "reddit_vibe") or "community sentiment pending"
    news = _first_present(top, "news_signal") or "news signal pending"
    return f"{course} at {university} is currently {status}. Salary outlook: {salary}. Reddit vibe: {vibe}. News pulse: {news}."


def _collector_inputs_for_query(settings: PipelineSettings, query: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    uni_defaults = [{"query": query}]
    reddit_defaults = [{"query": query}]
    return (
        _load_inputs(settings.uni_inputs_json, uni_defaults),
        _load_inputs(settings.reddit_inputs_json, reddit_defaults),
    )


def _source_inputs_for_query(raw_inputs_json: str | None, query: str) -> list[dict[str, Any]]:
    return _load_inputs(raw_inputs_json, [{"query": query}])


def _run_collector(session: requests.Session, settings: PipelineSettings, collector_id: str, inputs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    try:
        snapshot_id = trigger_collector(session, settings.brightdata_api_token, collector_id, inputs)
        return poll_snapshot(session, settings.brightdata_api_token, snapshot_id)
    except Exception:
        return []


def run_bright_data_reddit_scraper(settings: PipelineSettings, interest: str) -> str:
    session = requests.Session()
    inputs = _source_inputs_for_query(settings.reddit_inputs_json, interest)
    rows = _run_collector(session, settings, settings.reddit_collector_id, inputs)
    return _reddit_vibe_from_rows(rows)


def run_bright_data_uni_scraper(settings: PipelineSettings, interest: str) -> str:
    session = requests.Session()
    inputs = _source_inputs_for_query(settings.uni_inputs_json, interest)
    rows = _run_collector(session, settings, settings.uni_collector_id, inputs)
    if not rows:
        return f"No admissions rows for {interest}"
    first_row = rows[0]
    course = _first_present(first_row, "course", "programme", "program", "title", "name") or interest
    university = _first_present(first_row, "university", "school", "institution", "campus") or "Unknown university"
    cutoff = _first_present(first_row, "rank", "rp", "cutoff", "igp", "score") or "unknown RP"
    return f"{university} {course}: {cutoff}"


def run_bright_data_techasia_scraper(settings: PipelineSettings, query: str) -> list[dict[str, Any]]:
    session = requests.Session()
    if not settings.techasia_collector_id:
        return []
    inputs = _source_inputs_for_query(settings.techasia_inputs_json, query)
    return _run_collector(session, settings, settings.techasia_collector_id, inputs)


def _intent_classifier_prompt(raw_text: str) -> str:
    return (
        "Classify this student query for a routing architecture. Return STRICT JSON with keys: "
        "student_rp, interest, branch, priority_weights, normalized_query, confidence, route_note. "
        "Branch must be one of EXPLORE, EVALUATE, ADMISSION. Query: "
        f"{raw_text}"
    )


def refine_intent_with_tokenrouter(intent: dict[str, Any], raw_text: str) -> dict[str, Any]:
    settings = PipelineSettings.from_env()
    client = build_tokenrouter_client(settings)
    if client is None:
        return intent
    try:
        response = client.chat.completions.create(
            model=settings.tokenrouter_model,
            messages=[
                {"role": "system", "content": "Refine route classification for a Singapore university admissions dashboard. Return STRICT JSON only."},
                {
                    "role": "user",
                    "content": json.dumps({"raw_text": raw_text, "intent": intent}, ensure_ascii=True),
                },
            ],
            temperature=0.0,
        )
        content = response.choices[0].message.content or ""
        parsed = json.loads(content)
        if isinstance(parsed, dict):
            parsed.setdefault("source", "tokenrouter")
            return parsed
    except Exception:
        pass
    return intent


def classify_route(raw_text: str) -> dict[str, Any]:
    kimi_intent = extract_intent_with_kimi(raw_text)
    return refine_intent_with_tokenrouter(kimi_intent, raw_text)


def _route_plan(intent: dict[str, Any]) -> dict[str, bool]:
    branch = str(intent.get("branch") or "EVALUATE").upper()
    if branch == "EXPLORE":
        return {"need_uni": False, "need_reddit": False, "need_techasia": True, "need_news": True, "need_daytona": False}
    if branch == "ADMISSION":
        return {"need_uni": True, "need_reddit": True, "need_techasia": True, "need_news": True, "need_daytona": True}
    return {"need_uni": False, "need_reddit": True, "need_techasia": True, "need_news": True, "need_daytona": False}


def _safe_row_list(rows_or_text: Any, key: str) -> list[dict[str, Any]]:
    if isinstance(rows_or_text, list):
        if rows_or_text and isinstance(rows_or_text[0], dict):
            return rows_or_text
        if rows_or_text and isinstance(rows_or_text[0], str):
            return [{key: item} for item in rows_or_text]
    if isinstance(rows_or_text, str):
        return [{key: rows_or_text}]
    return []


def route_and_scrape_with_sponsors_streaming(raw_text: str, use_fallback: bool = False) -> Iterable[dict[str, Any]]:
    intent = classify_route(raw_text)
    branch = str(intent.get("branch", "EVALUATE")).upper()
    plan = _route_plan(intent)

    if use_fallback:
        fallback_rows = FALLBACK_DATA.get(str(intent.get("interest", "Computing")), FALLBACK_DATA["Computing"])
        yield {
            "status": "fallback_mode",
            "message": f"Routing branch {branch} is using pre-seeded local data.",
            "progress": 0.2,
            "branch": branch,
            "intent": intent,
            "route_plan": plan,
        }
        yield {
            "status": "complete",
            "data": fallback_rows,
            "trace": {"branch": branch, "cost": 0.0, "scraped_at": "Fallback routing path"},
            "progress": 1.0,
            "branch": branch,
        }
        return

    settings = PipelineSettings.from_env()
    session = requests.Session()
    branch_label = branch if branch in {"EXPLORE", "EVALUATE", "ADMISSION"} else "EVALUATE"
    yield {"status": "starting", "message": f"Intent classified as {branch_label}", "progress": 0.05, "branch": branch_label, "intent": intent, "route_plan": plan}

    gov_rows = fetch_government_data(session, settings.gov_data_url)
    news_items = fetch_asia_news(session, str(intent.get("interest", raw_text))) if plan["need_news"] else []

    uni_rows: list[dict[str, Any]] = []
    reddit_rows: list[dict[str, Any]] = []
    techasia_rows: list[dict[str, Any]] = []

    if plan["need_uni"]:
        yield {"status": "scraping", "message": "Running Bright Data university admissions collector", "progress": 0.25, "branch": branch_label}
        session_uni = requests.Session()
        uni_inputs = _source_inputs_for_query(settings.uni_inputs_json, raw_text)
        uni_rows = _run_collector(session_uni, settings, settings.uni_collector_id, uni_inputs)

    if plan["need_reddit"]:
        yield {"status": "scraping", "message": "Running Bright Data Reddit collector", "progress": 0.40, "branch": branch_label}
        session_reddit = requests.Session()
        reddit_inputs = _source_inputs_for_query(settings.reddit_inputs_json, raw_text)
        reddit_rows = _run_collector(session_reddit, settings, settings.reddit_collector_id, reddit_inputs)

    if plan["need_techasia"]:
        yield {"status": "scraping", "message": "Running Bright Data TechAsia collector", "progress": 0.68, "branch": branch_label}
        techasia_rows = run_bright_data_techasia_scraper(settings, raw_text)

    daytona_result: dict[str, Any] | None = None
    if plan["need_daytona"]:
        yield {"status": "computing", "message": "Building Daytona sandbox script", "progress": 0.82, "branch": branch_label}
        daytona_script = json.dumps(
            {
                "raw_text": raw_text,
                "intent": intent,
                "branch": branch_label,
                "news_items": news_items,
            },
            ensure_ascii=True,
        )
        daytona_result = run_daytona_code(f"print({daytona_script!r})")

    summary_seed_rows = _safe_row_list(uni_rows, "title") + _safe_row_list(reddit_rows, "title") + _safe_row_list(techasia_rows, "title")
    fallback_rows = _fallback_rows_for_interest(str(intent.get("interest", "Computing")))
    kimi_client = build_kimi_client(settings)
    kimi_summary_result = summarize_with_kimi(kimi_client, summary_seed_rows or fallback_rows, raw_text)
    tokenrouter_client = build_tokenrouter_client(settings)
    tokenrouter_summary_result = polish_summary_with_tokenrouter(
        tokenrouter_client,
        _summary_text(kimi_summary_result),
        summary_seed_rows or fallback_rows,
        raw_text,
        settings.tokenrouter_model,
    )

    merged_rows = merge_results(
        uni_rows,
        reddit_rows or _safe_row_list([_summary_text(kimi_summary_result) or "No Reddit signal yet"], "title"),
        gov_rows,
        news_items,
        str(intent.get("interest", raw_text)),
    )
    if techasia_rows:
        merged_rows = [
            {
                **row,
                "techasia_signal": _first_present(techasia_rows[0], "title", "summary", "description") or _first_present(techasia_rows[0], "post_title", "company", "link") or "Live TechAsia ready",
            }
            for row in merged_rows
        ]

    tokenrouter_text = _summary_text(tokenrouter_summary_result)
    tokenrouter_usage = _summary_usage(tokenrouter_summary_result)
    tokenrouter_cost = tokenrouter_usage.get("cost") or tokenrouter_usage.get("total_cost")
    final_summary = tokenrouter_text or _summary_text(kimi_summary_result) or _local_summary_from_rows(merged_rows, str(intent.get("interest", raw_text)))

    yield {
        "status": "complete",
        "branch": branch_label,
        "intent": intent,
        "route_plan": plan,
        "data": merged_rows,
        "summary": final_summary,
        "trace": {
            "branch": branch_label,
            "cost": tokenrouter_cost,
            "kimi_summary": kimi_summary_result,
            "tokenrouter_summary": tokenrouter_summary_result,
            "kimi_usage": _summary_usage(kimi_summary_result),
            "tokenrouter_usage": tokenrouter_usage,
            "daytona": daytona_result,
            "scraped_at": "Agentic routing pipeline",
        },
        "progress": 1.0,
    }


def fetch_gov_salaries(interest: str) -> dict[str, Any]:
    session = requests.Session()
    settings = PipelineSettings.from_env()
    rows = fetch_government_data(session, settings.gov_data_url)
    if rows:
        return rows[0]
    return {"gross_monthly_median": "4500", "employment_rate_ft_perm": "93%", "interest": interest}


def run_daytona_code(daytona_script: str) -> dict[str, Any]:
    try:
        import importlib

        daytona_module = importlib.import_module("daytona")
        Daytona = getattr(daytona_module, "Daytona")
        DaytonaConfig = getattr(daytona_module, "DaytonaConfig")
    except ImportError as exc:
        return {
            "status": "unavailable",
            "message": "Install the daytona package to enable sandbox execution.",
            "error": str(exc),
            "script": daytona_script,
        }

    settings = PipelineSettings.from_env()
    if not settings.daytona_api_key:
        return {
            "status": "skipped",
            "message": "DAYTONA_API_KEY is missing, so sandbox execution was skipped.",
            "script": daytona_script,
        }

    try:
        config = DaytonaConfig(api_key=settings.daytona_api_key, api_url=settings.daytona_base_url)
        daytona = Daytona(config)
        sandbox = daytona.create()
        try:
            response = sandbox.process.code_run(daytona_script)
            return {
                "status": "ok",
                "exit_code": getattr(response, "exit_code", None),
                "result": getattr(response, "result", None),
                "script": daytona_script,
            }
        finally:
            try:
                sandbox.delete()
            except Exception:
                pass
    except Exception as exc:
        return {
            "status": "error",
            "message": "Daytona execution failed.",
            "error": str(exc),
            "script": daytona_script,
        }


def scrape_streaming(query: str, use_fallback: bool = True) -> Iterable[dict[str, Any]]:
    settings = PipelineSettings.from_env()
    if not settings.brightdata_api_token:
        raise ValueError("Missing BRIGHTDATA_API_TOKEN in the environment")

    session = requests.Session()
    uni_inputs, reddit_inputs = _collector_inputs_for_query(settings, query)
    events: list[dict[str, Any]] = []

    def emit(status: str, message: str, **extra: Any) -> dict[str, Any]:
        event = {"status": status, "message": message, **extra}
        events.append(event)
        return event

    yield emit("scraping", "Starting collector 1 for university data")
    uni_snapshot_id = trigger_collector(session, settings.brightdata_api_token, settings.uni_collector_id, uni_inputs)
    yield emit("scraping", f"Collector 1 triggered: {uni_snapshot_id}", snapshot_id=uni_snapshot_id)
    uni_rows = poll_snapshot(session, settings.brightdata_api_token, uni_snapshot_id)
    yield emit("scraping", f"Collector 1 ready with {len(uni_rows)} rows", row_count=len(uni_rows))

    yield emit("scraping", "Starting collector 2 for Reddit student vibe data")
    reddit_snapshot_id = trigger_collector(session, settings.brightdata_api_token, settings.reddit_collector_id, reddit_inputs)
    yield emit("scraping", f"Collector 2 triggered: {reddit_snapshot_id}", snapshot_id=reddit_snapshot_id)
    reddit_rows = poll_snapshot(session, settings.brightdata_api_token, reddit_snapshot_id)
    yield emit("scraping", f"Collector 2 ready with {len(reddit_rows)} rows", row_count=len(reddit_rows))

    yield emit("scraping", "Calling government dataset API")
    gov_rows = fetch_government_data(session, settings.gov_data_url)
    yield emit("scraping", f"Government API returned {len(gov_rows)} rows", row_count=len(gov_rows))

    yield emit("merging", "Merging scraped rows into the contract shape")
    merged_rows = merge_results(uni_rows, reddit_rows, gov_rows, query)

    summary: str | None = None
    if not use_fallback:
        yield emit("summarizing", "Sending merged rows through Kimi")
        kimi_client = build_kimi_client(settings)
        summary = summarize_with_kimi(kimi_client, merged_rows, query)
        if summary is None:
            yield emit("summarizing", "Kimi unavailable, falling back to TokenRouter")
            tokenrouter_client = build_tokenrouter_client(settings)
            summary = summarize_with_tokenrouter(tokenrouter_client, merged_rows, query, settings.tokenrouter_model)
        if summary:
            yield emit("summarizing", "Summary ready", summary=summary)

    yield {
        "status": "done",
        "message": "Pipeline complete",
        "query": query,
        "data": merged_rows,
        "summary": summary,
        "events": events,
    }


def scrape_and_score_with_sponsors_streaming(student_rp: float, interest: str, use_fallback: bool = False) -> Iterable[dict[str, Any]]:
    if use_fallback:
        fallback_rows = FALLBACK_DATA.get(interest, FALLBACK_DATA["Computing"])
        yield {
            "status": "fallback_mode",
            "message": "Demo mode activated. Using pre-seeded local dataset.",
            "progress": 0.2,
        }
        yield {
            "status": "complete",
            "data": fallback_rows,
            "trace": {"cost": 0.0, "scraped_at": "Cached Local Disk Framework"},
            "progress": 1.0,
        }
        return

    settings = PipelineSettings.from_env()
    if not settings.brightdata_api_token:
        raise ValueError("Missing BRIGHTDATA_API_TOKEN in the environment")

    session = requests.Session()
    yield {"status": "starting", "message": "Launching sponsor pipeline", "progress": 0.1}

    yield {"status": "scraping", "message": f"Running Reddit collector for {interest}", "progress": 0.25}
    reddit_vibe = run_bright_data_reddit_scraper(settings, interest)

    yield {"status": "scraping", "message": f"Running university IGP collector for {interest}", "progress": 0.45}
    uni_context = run_bright_data_uni_scraper(settings, interest)

    yield {"status": "scraping", "message": "Calling data.gov.sg salary dataset", "progress": 0.65}
    gov_data = fetch_gov_salaries(interest)

    yield {"status": "scraping", "message": "Pulling real-time Asia news headlines", "progress": 0.73}
    news_items = fetch_asia_news(session, interest)

    yield {"status": "computing", "message": "Building Daytona script", "progress": 0.8}
    daytona_script = f"""
student_rp = {student_rp}
interest = {interest!r}
reddit_context = {reddit_vibe!r}
uni_context = {uni_context!r}
gov_data = {json.dumps(gov_data, ensure_ascii=True)}
news_items = {json.dumps(news_items, ensure_ascii=True)}
print('Daytona processing metrics successfully...')
"""
    daytona_result = run_daytona_code(daytona_script)

    kimi_client = build_kimi_client(settings)
    kimi_summary = summarize_with_kimi(
        kimi_client,
        [{"course": interest, "university": "SMU", "status": uni_context, "salary_estimate": gov_data.get("gross_monthly_median", ""), "reddit_vibe": reddit_vibe, "news_signal": _news_signal_from_items(news_items)}],
        interest,
    )
    tokenrouter_client = build_tokenrouter_client(settings)
    tokenrouter_summary = polish_summary_with_tokenrouter(
        tokenrouter_client,
        kimi_summary,
        [{"course": interest, "university": "SMU", "status": uni_context, "salary_estimate": gov_data.get("gross_monthly_median", ""), "reddit_vibe": reddit_vibe, "news_signal": _news_signal_from_items(news_items)}],
        interest,
        settings.tokenrouter_model,
    )

    final_rows = merge_results(
        [{"course": interest, "university": "SMU", "status": uni_context}],
        [{"title": reddit_vibe}],
        [gov_data],
        news_items,
        interest,
    )
    yield {
        "status": "complete",
        "data": final_rows,
        "trace": {
            "cost": 0.044,
            "kimi_summary": kimi_summary,
            "tokenrouter_summary": tokenrouter_summary,
            "daytona": daytona_result,
            "scraped_at": "Multi-Scraper Pipeline Unified (Live)",
        },
        "progress": 1.0,
    }


def run_pipeline(query: str, use_fallback: bool = True) -> dict[str, Any]:
    last_event: dict[str, Any] | None = None
    for event in scrape_streaming(query, use_fallback=use_fallback):
        last_event = event
    if last_event is None:
        raise RuntimeError("Pipeline produced no events")
    return last_event
