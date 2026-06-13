"""
tests/test_core.py
==================
Deterministic, fully OFFLINE unit tests for SG UniNavigator.

No network calls, no API keys, no env dependencies. Every test exercises the
code exactly as written in agent_core.py / fallback_data.py / live_backend.py
and asserts only behaviour that is guaranteed by that code.

Run with:  pytest tests/test_core.py
"""

import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pytest

from fallback_data import FALLBACK_COURSES
import agent_core
import live_backend


BALANCED_WEIGHTS = {"rp_safety": 0.34, "job_score": 0.33, "sentiment": 0.33}


# ──────────────────────────────────────────────────────────────────────────
# agent_core.score_courses
# ──────────────────────────────────────────────────────────────────────────
class TestScoreCourses:
    def _rows(self):
        return agent_core.score_courses(
            85.0, {"courses": FALLBACK_COURSES}, BALANCED_WEIGHTS
        )

    def test_returns_list_of_at_most_five(self):
        rows = self._rows()
        assert isinstance(rows, list)
        assert len(rows) <= 5

    def test_sorted_by_score_descending(self):
        rows = self._rows()
        scores = [r["score"] for r in rows]
        assert scores == sorted(scores, reverse=True)

    def test_row_has_exact_contract_keys(self):
        rows = self._rows()
        assert rows, "expected at least one scored course at RP 85"
        expected = {
            "course",
            "institution",
            "rp_gap",
            "median_salary",
            "employment",
            "reddit_vibe",
            "score",
        }
        for row in rows:
            assert set(row.keys()) == expected

    def test_rp_gap_is_signed_string(self):
        rows = self._rows()
        for row in rows:
            assert isinstance(row["rp_gap"], str)
            assert row["rp_gap"][0] in "+-"
            # e.g. "+2.50" / "-1.25" -> two decimal places.
            assert "." in row["rp_gap"]
            float(row["rp_gap"])  # parses as a number

    def test_score_is_numeric(self):
        rows = self._rows()
        for row in rows:
            assert isinstance(row["score"], (int, float))


# ──────────────────────────────────────────────────────────────────────────
# agent_core.extract_weights
# ──────────────────────────────────────────────────────────────────────────
class TestExtractWeights:
    def test_salary_priority_weights_job_highest(self):
        w = agent_core.extract_weights("salary")
        assert w["job_score"] == max(w.values())
        assert w["job_score"] > w["rp_safety"]
        assert w["job_score"] > w["sentiment"]

    def test_job_keyword_weights_job_highest(self):
        w = agent_core.extract_weights("job")
        assert w["job_score"] == max(w.values())

    def test_chill_priority_weights_sentiment_highest(self):
        w = agent_core.extract_weights("chill")
        assert w["sentiment"] == max(w.values())
        assert w["sentiment"] > w["rp_safety"]
        assert w["sentiment"] > w["job_score"]

    def test_relax_keyword_weights_sentiment_highest(self):
        w = agent_core.extract_weights("relax")
        assert w["sentiment"] == max(w.values())

    def test_safe_priority_weights_rp_safety_highest(self):
        w = agent_core.extract_weights("safe")
        assert w["rp_safety"] == max(w.values())
        assert w["rp_safety"] > w["job_score"]
        assert w["rp_safety"] > w["sentiment"]

    def test_backup_keyword_weights_rp_safety_highest(self):
        w = agent_core.extract_weights("backup")
        assert w["rp_safety"] == max(w.values())

    def test_empty_is_balanced(self):
        w = agent_core.extract_weights("")
        assert w == BALANCED_WEIGHTS

    @pytest.mark.parametrize("text", ["salary", "chill", "safe", ""])
    def test_weights_sum_to_about_one(self, text):
        w = agent_core.extract_weights(text)
        assert sum(w.values()) == pytest.approx(1.0, abs=0.02)


# ──────────────────────────────────────────────────────────────────────────
# agent_core.match_course
# ──────────────────────────────────────────────────────────────────────────
class TestMatchCourse:
    def test_nus_cs(self):
        course = agent_core.match_course("nus cs")
        assert course is not None
        assert course["university"] == "NUS"
        assert course["course"] == "Computer Science"

    def test_ntu_eee(self):
        course = agent_core.match_course("ntu eee")
        assert course is not None
        assert course["university"] == "NTU"
        assert course["course"] == "Electrical & Electronic Engineering"

    def test_data_science(self):
        course = agent_core.match_course("data science")
        assert course is not None
        assert course["university"] == "NTU"
        assert course["course"] == "Data Science & AI"

    def test_nonsense_returns_none(self):
        assert agent_core.match_course("zzz nonsense") is None


# ──────────────────────────────────────────────────────────────────────────
# agent_core.route_query
# ──────────────────────────────────────────────────────────────────────────
class TestRouteQuery:
    def test_explore_intent(self):
        intent_obj, result = agent_core.route_query(
            "What courses can I do with my RP?", 85.0, demo_mode=True
        )
        assert intent_obj["intent"] == agent_core.INTENT_EXPLORE
        assert result["intent"] == agent_core.INTENT_EXPLORE

    def test_evaluate_intent(self):
        intent_obj, result = agent_core.route_query(
            "Tell me about NUS Computer Science", 85.0, demo_mode=True
        )
        assert intent_obj["intent"] == agent_core.INTENT_EVALUATE
        assert result["intent"] == agent_core.INTENT_EVALUATE

    def test_admission_intent(self):
        intent_obj, result = agent_core.route_query(
            "Can I get into NUS Computer Science?", 85.0, demo_mode=True
        )
        assert intent_obj["intent"] == agent_core.INTENT_ADMISSION
        assert result["intent"] == agent_core.INTENT_ADMISSION


# ──────────────────────────────────────────────────────────────────────────
# agent_core branch handlers
# ──────────────────────────────────────────────────────────────────────────
class TestBranchHandlers:
    def test_admission_nus_medicine_unlikely_at_85(self):
        # NUS Medicine cutoff is 88.0; at RP 85 the gap is -3.0 -> UNLIKELY.
        result = agent_core.branch_admission("NUS Medicine", 85.0)
        assert result["matched"] is True
        assert result["verdict"] == "UNLIKELY"

    def test_evaluate_known_course_matches_with_reddit_and_news(self):
        result = agent_core.branch_evaluate("NUS Computer Science")
        assert result["matched"] is True
        assert "reddit" in result
        assert "hiring_news" in result

    def test_explore_lists_options_with_valid_verdicts(self):
        result = agent_core.branch_explore(85.0)
        assert "options" in result
        assert result["options"], "expected at least one option"
        allowed = {"Safe", "Reach", "Out of reach"}
        for option in result["options"]:
            assert option["verdict"] in allowed


# ──────────────────────────────────────────────────────────────────────────
# live_backend._extract_rows
# ──────────────────────────────────────────────────────────────────────────
class TestExtractRows:
    def test_datastore_search_shape(self):
        payload = {"success": True, "result": {"records": [{"a": 1}]}}
        rows = live_backend._extract_rows(payload)
        assert rows == [{"a": 1}]


# ──────────────────────────────────────────────────────────────────────────
# live_backend gov-row extractors
# ──────────────────────────────────────────────────────────────────────────
class TestGovRowExtractors:
    def test_salary_from_gov_rows(self):
        rows = [{"gross_monthly_median": "6000"}]
        result = live_backend._salary_from_gov_rows(rows)
        assert isinstance(result, str)
        assert "6,000" in result

    def test_salary_from_gov_rows_no_signal(self):
        result = live_backend._salary_from_gov_rows([{"course": "X"}])
        assert result == "No salary signal yet"

    def test_employment_from_gov_rows_appends_percent(self):
        rows = [{"employment_rate_overall": "94"}]
        result = live_backend._employment_from_gov_rows(rows)
        assert result == "94%"

    def test_employment_from_gov_rows_no_signal(self):
        result = live_backend._employment_from_gov_rows([{"course": "X"}])
        assert result == "No employment signal yet"


# ──────────────────────────────────────────────────────────────────────────
# live_backend.merge_results
# ──────────────────────────────────────────────────────────────────────────
class TestMergeResults:
    def test_merged_row_has_employment_rate(self):
        merged = live_backend.merge_results(
            uni_rows=[{"course": "X", "university": "NUS"}],
            reddit_rows=[],
            gov_rows=[
                {"gross_monthly_median": "6000", "employment_rate_overall": "94"}
            ],
            news_items=[{"title": "hiring"}],
            query="X",
        )
        assert merged
        assert "employment_rate" in merged[0]


# ──────────────────────────────────────────────────────────────────────────
# live_backend._expand_query_inputs
# ──────────────────────────────────────────────────────────────────────────
class TestExpandQueryInputs:
    def test_expands_to_multiple_query_dicts(self):
        inputs = live_backend._expand_query_inputs("NUS Computer Science")
        assert len(inputs) > 1
        for item in inputs:
            assert isinstance(item, dict)
            assert "query" in item


# ──────────────────────────────────────────────────────────────────────────
# live_backend.route_and_scrape_with_sponsors_streaming (offline fallback)
# ──────────────────────────────────────────────────────────────────────────
class TestRouteAndScrapeStreamingFallback:
    def test_last_event_is_complete_with_data_list(self):
        events = list(
            live_backend.route_and_scrape_with_sponsors_streaming(
                "Tell me about NUS Computer Science", use_fallback=True
            )
        )
        assert events
        last = events[-1]
        assert last["status"] == "complete"
        assert isinstance(last["data"], list)
