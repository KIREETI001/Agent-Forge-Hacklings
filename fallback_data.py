"""
fallback_data.py
=================
Hardcoded "cached" dataset for SG UniNavigator (Demo Mode).

This module is the single source of truth for the offline/demo experience.
The field names below are a CONTRACT shared with the scoring engine in
agent_core.score_courses() and the live scraper (agent_core.scrape_and_score()).
DO NOT rename fields — the scoring engine indexes them by exact key.

Field contract (per course):
    course               : str    -- programme name
    university           : str    -- institution (NUS / NTU / SMU)
    igp_cutoff           : float  -- Indicative Grade Profile cutoff, expressed
                                     as A-level University Admission Rank Points
                                     (0-90 scale; higher = more competitive)
    ges_median_salary    : int    -- Graduate Employment Survey gross monthly
                                     median starting salary (SGD)
    ges_employment_rate  : float  -- GES overall employment rate (0-100, %)
    reddit_pos           : int    -- count of positive Reddit mentions
    reddit_neg           : int    -- count of negative Reddit mentions
    reddit_neu           : int    -- count of neutral Reddit mentions

Data notes / decisions (documented per task instructions):
- Figures are realistic, hand-curated approximations modelled on publicly
  reported 2023/2024 GES and IGP ranges for these programmes. They are
  illustrative demo values, NOT official statistics.
- igp_cutoff uses the A-level Rank Points scale (max 90), so a student enters
  an RP score on the same scale and the gap is meaningful.
- Reddit counts are synthetic but tuned to produce a spread of
  Positive / Mixed / Cautious vibes through the sentiment formula.
"""

# The list is intentionally ordered roughly by competitiveness for readability.
FALLBACK_COURSES = [
    {
        "course": "Medicine",
        "university": "NUS",
        "igp_cutoff": 88.0,
        "ges_median_salary": 5750,
        "ges_employment_rate": 100.0,
        "reddit_pos": 140,
        "reddit_neg": 55,
        "reddit_neu": 70,
    },
    {
        "course": "Computer Science",
        "university": "NUS",
        "igp_cutoff": 84.5,
        "ges_median_salary": 6000,
        "ges_employment_rate": 96.0,
        "reddit_pos": 180,
        "reddit_neg": 40,
        "reddit_neu": 90,
    },
    {
        "course": "Computing & Law",
        "university": "SMU",
        "igp_cutoff": 83.0,
        "ges_median_salary": 6200,
        "ges_employment_rate": 97.0,
        "reddit_pos": 60,
        "reddit_neg": 30,
        "reddit_neu": 40,
    },
    {
        "course": "Business Analytics",
        "university": "NUS",
        "igp_cutoff": 82.5,
        "ges_median_salary": 5800,
        "ges_employment_rate": 95.0,
        "reddit_pos": 90,
        "reddit_neg": 35,
        "reddit_neu": 70,
    },
    {
        "course": "Data Science & AI",
        "university": "NTU",
        "igp_cutoff": 81.5,
        "ges_median_salary": 5500,
        "ges_employment_rate": 94.0,
        "reddit_pos": 75,
        "reddit_neg": 30,
        "reddit_neu": 60,
    },
    {
        "course": "Accountancy",
        "university": "NTU",
        "igp_cutoff": 80.0,
        "ges_median_salary": 3800,
        "ges_employment_rate": 93.0,
        "reddit_pos": 45,
        "reddit_neg": 60,
        "reddit_neu": 90,
    },
    {
        "course": "Information Systems",
        "university": "SMU",
        "igp_cutoff": 78.5,
        "ges_median_salary": 5500,
        "ges_employment_rate": 95.5,
        "reddit_pos": 85,
        "reddit_neg": 25,
        "reddit_neu": 55,
    },
    {
        "course": "Electrical & Electronic Engineering",
        "university": "NTU",
        "igp_cutoff": 76.0,
        "ges_median_salary": 4200,
        "ges_employment_rate": 92.0,
        "reddit_pos": 50,
        "reddit_neg": 70,
        "reddit_neu": 80,
    },
]

# Timestamp (in minutes) describing how stale this bundled snapshot is, used by
# the UI's "Scraped: X min ago" indicator when running in Demo / CACHED mode.
FALLBACK_SNAPSHOT_AGE_MIN = 47


# ──────────────────────────────────────────────────────────────────────────
# Intent-routing support data (added for the EXPLORE/EVALUATE/ADMISSION flow).
# These are SUPPLEMENTARY to the frozen FALLBACK_COURSES contract above —
# they do not modify any course dict.
# ──────────────────────────────────────────────────────────────────────────

def course_key(course: dict) -> str:
    """Canonical id for a course dict, e.g. 'NUS Computer Science'.

    Used as the join key between FALLBACK_COURSES, COURSE_ALIASES and
    FALLBACK_HIRING_NEWS so the three structures stay decoupled.
    """
    return f"{course['university']} {course['course']}"


# Free-text aliases -> canonical course key. The course matcher in
# agent_core.match_course() uses these to resolve messy user input
# ("nus cs", "comp sci", "ntu eee") to a specific programme.
# Short/ambiguous aliases (cs, ds, eee, med, accy, bza) are matched with
# word boundaries in agent_core; multi-word aliases match as substrings.
COURSE_ALIASES = {
    "NUS Medicine": [
        "nus medicine", "medicine", "med", "mbbs", "medical school", "doctor",
    ],
    "NUS Computer Science": [
        "nus computer science", "computer science", "comp sci", "compsci",
        "nus cs", "cs",
    ],
    "SMU Computing & Law": [
        "smu computing and law", "computing and law", "computing & law",
        "computing law", "cclaw", "law and computing",
    ],
    "NUS Business Analytics": [
        "nus business analytics", "business analytics", "biz analytics",
        "bza",
    ],
    "NTU Data Science & AI": [
        "ntu data science and ai", "data science and ai", "data science & ai",
        "data science", "dsai", "ds&ai", "ds",
    ],
    "NTU Accountancy": [
        "ntu accountancy", "accountancy", "accounting", "accy",
    ],
    "SMU Information Systems": [
        "smu information systems", "information systems", "info systems",
        "infosys", "smu is",
    ],
    "NTU Electrical & Electronic Engineering": [
        "ntu electrical and electronic engineering",
        "electrical and electronic engineering", "electrical & electronic",
        "electronic engineering", "electrical engineering", "eee",
    ],
}

# Illustrative "live SG hiring news" used by Branch 2 (EVALUATE) in Demo Mode.
# Synthetic, hand-written bullets standing in for the live news scrape that
# Person B will wire through agent_core.scrape_and_score(). NOT real headlines.
FALLBACK_HIRING_NEWS = {
    "NUS Medicine": [
        "MOH Holdings confirms full housemanship placement for 2024 cohort.",
        "Public healthcare clusters (NUHS, SingHealth) expanding resident slots.",
    ],
    "NUS Computer Science": [
        "Big Tech (Google, Meta, TikTok) actively hiring SWE interns in SG.",
        "DBS & UOB expanding graduate tech programmes; AI roles up ~20% YoY.",
    ],
    "SMU Computing & Law": [
        "Top law firms piloting legal-tech analyst tracks for dual-skilled grads.",
        "GovTech and regulators recruiting for tech-policy and compliance roles.",
    ],
    "NUS Business Analytics": [
        "Consulting (Accenture, Deloitte) hiring analytics associates steadily.",
        "E-commerce (Shopee, Lazada) demand for data/BA roles remains strong.",
    ],
    "NTU Data Science & AI": [
        "AI Singapore and startups recruiting ML engineers off campus.",
        "Banks scaling data-science teams; junior DS postings trending up.",
    ],
    "NTU Accountancy": [
        "Big Four (PwC, EY, KPMG, Deloitte) audit intake stable; ACA tracks open.",
        "Demand softening slightly vs tech roles; salaries flat YoY.",
    ],
    "SMU Information Systems": [
        "Strong placement into bank tech and consulting business-analyst roles.",
        "Product/IT analyst openings healthy across SG enterprises.",
    ],
    "NTU Electrical & Electronic Engineering": [
        "Semiconductor push (GlobalFoundries, Micron) hiring hardware engineers.",
        "Fewer pure-EEE grad roles than software; many pivot into tech.",
    ],
}
