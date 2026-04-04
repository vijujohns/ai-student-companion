"""
Progress Analytics Tests — analytics module (unit) + API routes (integration).

Covers:
  - Unit: log_activity persists correctly
  - Unit: update_mastery rolling formula
  - Unit: get_mastery_stats grouping and ordering
  - Unit: _calc_streak consecutive-day logic
  - Unit: get_dashboard aggregate shape
  - API: GET /progress/dashboard — authenticated shape, unauthenticated 401
  - API: GET /progress/mastery  — authenticated list, unauthenticated 401
  - API: POST /progress/activity — valid payload, invalid type, out-of-range duration
"""

import sys
import os
import pytest
import uuid
from datetime import datetime, timezone, timedelta
from types import SimpleNamespace
from unittest.mock import patch, MagicMock

# ─── path bootstrap ──────────────────────────────────────────────────────────
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "backend")))


# ─── DB setup helper ─────────────────────────────────────────────────────────
def _setup_db():
    from app.modules.db import init_db
    init_db()


# =============================================================================
# Unit tests — analytics module
# =============================================================================

class TestLogActivity:
    @classmethod
    def setup_class(cls):
        _setup_db()

    def test_returns_positive_row_id(self):
        from app.modules.analytics import log_activity
        row_id = log_activity("unit_user", "quiz", "Math", "Algebra", 120)
        assert isinstance(row_id, int)
        assert row_id > 0

    def test_persists_record_in_db(self):
        from app.modules.analytics import log_activity
        from app.modules.db import get_connection
        log_activity("persist_user", "lesson", "Physics", "Optics", 300)
        conn = get_connection()
        try:
            cur = conn.cursor()
            cur.execute(
                "SELECT activity_type, subject, chapter, duration_seconds "
                "FROM learning_time_log WHERE user_id='persist_user' ORDER BY id DESC LIMIT 1"
            )
            row = cur.fetchone()
        finally:
            conn.close()
        assert row is not None
        assert row[0] == "lesson"
        assert row[1] == "Physics"
        assert row[2] == "Optics"
        assert row[3] == 300

    def test_invalid_activity_type_stored_as_other(self):
        from app.modules.analytics import log_activity
        from app.modules.db import get_connection
        log_activity("type_user", "invalid_type_xyz", "Chem", "Acids", 60)
        conn = get_connection()
        try:
            cur = conn.cursor()
            cur.execute(
                "SELECT activity_type FROM learning_time_log "
                "WHERE user_id='type_user' ORDER BY id DESC LIMIT 1"
            )
            row = cur.fetchone()
        finally:
            conn.close()
        assert row is not None
        assert row[0] == "other"

    def test_negative_duration_clamped_to_zero(self):
        from app.modules.analytics import log_activity
        from app.modules.db import get_connection
        log_activity("dur_user", "chat", "", "", -50)
        conn = get_connection()
        try:
            cur = conn.cursor()
            cur.execute(
                "SELECT duration_seconds FROM learning_time_log "
                "WHERE user_id='dur_user' ORDER BY id DESC LIMIT 1"
            )
            row = cur.fetchone()
        finally:
            conn.close()
        assert row is not None
        assert row[0] == 0


class TestUpdateMastery:
    @classmethod
    def setup_class(cls):
        _setup_db()

    def test_first_attempt_equals_score(self):
        from app.modules.analytics import update_mastery
        pct = update_mastery("mastery_u1", "Math", "Ch1", correct=8, total=10)
        assert pct == 80.0

    def test_rolling_formula(self):
        from app.modules.analytics import update_mastery
        uid = f"mastery_roll_{uuid.uuid4().hex}"
        # first attempt: 80%
        update_mastery(uid, "Science", "Ch2", correct=8, total=10)
        # second attempt: 100% → 80*0.6 + 100*0.4 = 48 + 40 = 88
        pct = update_mastery(uid, "Science", "Ch2", correct=10, total=10)
        assert pct == 88.0

    def test_zero_total_returns_zero(self):
        from app.modules.analytics import update_mastery
        pct = update_mastery("mastery_zero", "Math", "ChZ", correct=0, total=0)
        assert pct == 0.0

    def test_multiple_users_isolated(self):
        from app.modules.analytics import update_mastery
        p1 = update_mastery("iso_u1", "Bio", "Cells", correct=5, total=10)
        p2 = update_mastery("iso_u2", "Bio", "Cells", correct=9, total=10)
        assert p1 == 50.0
        assert p2 == 90.0

    def test_returns_float(self):
        from app.modules.analytics import update_mastery
        result = update_mastery("float_u", "Geo", "Maps", correct=3, total=7)
        assert isinstance(result, float)


class TestGetMasteryStats:
    @classmethod
    def setup_class(cls):
        _setup_db()

    def test_returns_list(self):
        from app.modules.analytics import get_mastery_stats
        result = get_mastery_stats("no_activity_ever_xyz")
        assert isinstance(result, list)

    def test_contains_expected_fields(self):
        from app.modules.analytics import update_mastery, get_mastery_stats
        update_mastery("fields_u", "History", "WWII", correct=6, total=10)
        stats = get_mastery_stats("fields_u")
        assert len(stats) >= 1
        entry = next(s for s in stats if s["subject"] == "History" and s["chapter"] == "WWII")
        assert "subject" in entry
        assert "chapter" in entry
        assert "mastery_pct" in entry
        assert "quizzes_taken" in entry
        assert "last_updated" in entry

    def test_ordered_by_subject_then_mastery_desc(self):
        from app.modules.analytics import update_mastery, get_mastery_stats
        uid = "order_u"
        update_mastery(uid, "Alpha", "ChA", correct=3, total=10)   # 30%
        update_mastery(uid, "Alpha", "ChB", correct=9, total=10)   # 90%
        stats = get_mastery_stats(uid)
        alpha = [s for s in stats if s["subject"] == "Alpha"]
        assert len(alpha) == 2
        assert alpha[0]["mastery_pct"] >= alpha[1]["mastery_pct"]


class TestCalcStreak:
    def test_empty_dates_returns_zero(self):
        from app.modules.analytics import _calc_streak
        assert _calc_streak([]) == 0

    def test_single_today_returns_one(self):
        from app.modules.analytics import _calc_streak
        today = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")
        assert _calc_streak([today]) == 1

    def test_two_consecutive_days(self):
        from app.modules.analytics import _calc_streak
        today = datetime.now(timezone.utc)
        yesterday = today - timedelta(days=1)
        dates = [today.strftime("%Y-%m-%dT%H:%M:%S"), yesterday.strftime("%Y-%m-%dT%H:%M:%S")]
        assert _calc_streak(dates) == 2

    def test_gap_in_dates_breaks_streak(self):
        from app.modules.analytics import _calc_streak
        today = datetime.now(timezone.utc)
        two_days_ago = today - timedelta(days=2)
        # only today and two_days_ago — no yesterday → streak = 1
        dates = [today.strftime("%Y-%m-%dT%H:%M:%S"), two_days_ago.strftime("%Y-%m-%dT%H:%M:%S")]
        streak = _calc_streak(dates)
        # streak should be 1 (today only, gap at -2d)
        assert streak == 1

    def test_only_yesterday_returns_one(self):
        from app.modules.analytics import _calc_streak
        yesterday = datetime.now(timezone.utc) - timedelta(days=1)
        # no activity today but yesterday → streak continues from yesterday
        assert _calc_streak([yesterday.strftime("%Y-%m-%dT%H:%M:%S")]) == 1


class TestGetDashboard:
    @classmethod
    def setup_class(cls):
        _setup_db()

    def test_returns_required_keys(self):
        from app.modules.analytics import get_dashboard
        dash = get_dashboard("dash_test_u")
        for key in ("total_study_seconds", "streak_days", "totals", "top_subjects",
                    "recent_activity", "mastery_summary"):
            assert key in dash, f"Missing key: {key}"

    def test_totals_has_expected_subkeys(self):
        from app.modules.analytics import get_dashboard
        dash = get_dashboard("dash_totals_u")
        for k in ("quizzes", "lessons", "assessments"):
            assert k in dash["totals"], f"Missing totals key: {k}"

    def test_new_user_has_zero_study_time(self):
        from app.modules.analytics import get_dashboard
        dash = get_dashboard("brand_new_user_never_logged_anything")
        assert dash["total_study_seconds"] == 0
        assert dash["streak_days"] == 0

    def test_study_time_accumulates(self):
        from app.modules.analytics import log_activity, get_dashboard
        uid = "accum_dash_u"
        log_activity(uid, "quiz", "Math", "Algebra", 200)
        log_activity(uid, "lesson", "Science", "Physics", 100)
        dash = get_dashboard(uid)
        assert dash["total_study_seconds"] >= 300

    def test_top_subjects_is_list(self):
        from app.modules.analytics import get_dashboard
        dash = get_dashboard("top_subj_u")
        assert isinstance(dash["top_subjects"], list)

    def test_mastery_summary_is_list(self):
        from app.modules.analytics import get_dashboard
        dash = get_dashboard("mastery_sum_u")
        assert isinstance(dash["mastery_summary"], list)


class TestGetProgressInsights:
    @classmethod
    def setup_class(cls):
        _setup_db()

    def test_returns_expected_keys(self):
        from app.modules.analytics import get_progress_insights
        payload = get_progress_insights("insights_test_u")
        assert set(payload.keys()) == {"headline", "recommendations", "badges", "notifications"}
        assert isinstance(payload["headline"], str)
        assert isinstance(payload["recommendations"], list)
        assert isinstance(payload["badges"], list)

    def test_recommends_low_mastery_subject_review(self):
        from app.modules.analytics import get_progress_insights, update_mastery
        uid = f"insights_low_{uuid.uuid4().hex}"
        update_mastery(uid, "Math", "Algebra", correct=2, total=10)
        payload = get_progress_insights(uid)
        assert any(
            "Math" in rec.get("title", "") or "Math" in rec.get("description", "")
            for rec in payload["recommendations"]
        )

    def test_recommendations_include_action_metadata(self):
        from app.modules.analytics import get_progress_insights, update_mastery
        uid = f"insights_meta_{uuid.uuid4().hex}"
        update_mastery(uid, "Science", "Optics", correct=3, total=10)
        payload = get_progress_insights(uid)
        assert len(payload["recommendations"]) > 0
        assert all(
            "action_tab" in rec
            and "cta_label" in rec
            and "chapter_hint" in rec
            and "context_hint" in rec
            for rec in payload["recommendations"]
        )

    def test_recommends_assessment_retry_when_scores_are_low(self):
        from app.modules import analytics

        with patch.object(
            analytics,
            "get_dashboard",
            return_value={
                "total_study_seconds": 1800,
                "streak_days": 1,
                "totals": {"quizzes": 2, "lessons": 2, "assessments": 2},
                "mastery_summary": [{"subject": "Science", "avg_mastery_pct": 72}],
                "top_subjects": [{"subject": "Science", "study_seconds": 1200}],
                "assessment_summary": {
                    "attempt_count": 2,
                    "average_score_pct": 58,
                    "latest_score_pct": 52,
                    "latest_subject": "Science",
                },
            },
        ):
            payload = analytics.get_progress_insights("insights_assessment_retry")

        assessment_rec = next((rec for rec in payload["recommendations"] if rec.get("action_tab") == "assessment"), None)
        assert assessment_rec is not None
        assert assessment_rec["cta_label"] == "Retry Assessment"
        assert assessment_rec["chapter_hint"] == "Science"

    def test_recommends_starting_assessment_when_none_attempted_yet(self):
        from app.modules import analytics

        with patch.object(
            analytics,
            "get_dashboard",
            return_value={
                "total_study_seconds": 2400,
                "streak_days": 2,
                "totals": {"quizzes": 2, "lessons": 3, "assessments": 0},
                "mastery_summary": [{"subject": "Science", "avg_mastery_pct": 78}],
                "top_subjects": [{"subject": "Science", "study_seconds": 1500}],
                "assessment_summary": {
                    "attempt_count": 0,
                    "average_score_pct": 0,
                    "latest_score_pct": 0,
                    "latest_subject": "Science",
                },
            },
        ):
            payload = analytics.get_progress_insights("insights_assessment_start")

        assessment_rec = next((rec for rec in payload["recommendations"] if rec.get("action_tab") == "assessment"), None)
        assert assessment_rec is not None
        assert assessment_rec["cta_label"] == "Start Assessment"
        assert assessment_rec["chapter_hint"] == "Science"


class TestGetStudyPlan:
    @classmethod
    def setup_class(cls):
        _setup_db()

    def test_returns_expected_keys(self):
        from app.modules.analytics import get_study_plan
        payload = get_study_plan("study_plan_test_u")
        assert set(payload.keys()) == {"headline", "focus_subject", "schedule", "goal_summary", "targets", "history"}
        assert isinstance(payload["headline"], str)
        assert isinstance(payload["focus_subject"], str)
        assert isinstance(payload["schedule"], list)
        assert isinstance(payload["goal_summary"], dict)
        assert isinstance(payload["targets"], list)

    def test_schedule_prioritizes_low_mastery_subject(self):
        from app.modules.analytics import get_study_plan, update_mastery, log_activity
        uid = f"study_plan_{uuid.uuid4().hex}"
        update_mastery(uid, "Science", "Optics", correct=3, total=10)
        log_activity(uid, "lesson", "Science", "Optics", 900)
        payload = get_study_plan(uid)
        assert payload["focus_subject"] == "Science"
        assert any("Science" in step.get("title", "") or "Science" in step.get("description", "") for step in payload["schedule"])

    def test_schedule_steps_include_action_metadata(self):
        from app.modules.analytics import get_study_plan
        payload = get_study_plan("study_plan_actions_u")
        assert len(payload["schedule"]) > 0
        assert all(
            "action_tab" in step
            and "cta_label" in step
            and "chapter_hint" in step
            and "context_hint" in step
            and "status" in step
            and "completed" in step
            for step in payload["schedule"]
        )

    def test_schedule_steps_mark_next_focus_based_on_progress(self):
        from app.modules import analytics

        with patch.object(
            analytics,
            "get_dashboard",
            return_value={
                "total_study_seconds": 1800,
                "streak_days": 1,
                "totals": {"lessons": 2, "quizzes": 0, "assessments": 0},
                "top_subjects": [{"subject": "Science", "study_seconds": 1200}],
                "mastery_summary": [{"subject": "Science", "avg_mastery_pct": 52.0, "chapters": []}],
                "recent_activity": [],
            },
        ), patch.object(
            analytics,
            "get_progress_insights",
            return_value={"headline": "", "recommendations": [{"description": "Focus on Science revision."}], "badges": []},
        ):
            payload = analytics.get_study_plan("study_plan_status_u")

        assert payload["focus_subject"] == "Science"
        assert payload["schedule"][0]["status"] == "done"
        assert payload["schedule"][0]["completed"] is True
        assert payload["schedule"][1]["status"] == "next"
        assert payload["schedule"][1]["completed"] is False

    def test_study_plan_includes_weekly_goal_targets(self):
        from app.modules import analytics

        with patch.object(
            analytics,
            "get_dashboard",
            return_value={
                "total_study_seconds": 1200,
                "streak_days": 2,
                "totals": {"lessons": 1, "quizzes": 1, "assessments": 0},
                "top_subjects": [{"subject": "Science", "study_seconds": 1200}],
                "mastery_summary": [{"subject": "Science", "avg_mastery_pct": 68.0, "chapters": []}],
                "recent_activity": [{"activity_type": "lesson"}, {"activity_type": "quiz"}],
            },
        ), patch.object(
            analytics,
            "get_progress_insights",
            return_value={"headline": "", "recommendations": [{"description": "Focus on Science revision."}], "badges": []},
        ):
            payload = analytics.get_study_plan("study_plan_goals_u")

        assert payload["goal_summary"]["completed"] == 2
        assert payload["goal_summary"]["total"] == 3
        assert payload["history"]["current_week"]["goal_total"] == 3
        assert any(target["id"] == "study-minutes" and target["current"] == 20 and target["target"] == 30 for target in payload["targets"])
        assert any(
            target["id"] == "weekly-quiz"
            and target["completed"] is True
            and target.get("action_tab") == "quiz"
            and target.get("cta_label") == "Practice Quiz Goal"
            and target.get("chapter_hint") == "Science"
            for target in payload["targets"]
        )

    def test_study_plan_history_tracks_previous_week_snapshot(self):
        from app.modules import analytics

        with patch.object(analytics, "_get_week_key", side_effect=["2026-W13", "2026-W14"]):
            with patch.object(
                analytics,
                "get_dashboard",
                return_value={
                    "total_study_seconds": 900,
                    "streak_days": 1,
                    "totals": {"lessons": 0, "quizzes": 0, "assessments": 0},
                    "top_subjects": [{"subject": "Science", "study_seconds": 900}],
                    "mastery_summary": [{"subject": "Science", "avg_mastery_pct": 58.0, "chapters": []}],
                    "recent_activity": [],
                    "assessment_summary": {},
                },
            ), patch.object(
                analytics,
                "get_progress_insights",
                return_value={"headline": "", "recommendations": [{"description": "Focus on Science revision."}], "badges": [], "notifications": []},
            ):
                analytics.get_study_plan("study_plan_history_u")

            with patch.object(
                analytics,
                "get_dashboard",
                return_value={
                    "total_study_seconds": 1800,
                    "streak_days": 3,
                    "totals": {"lessons": 1, "quizzes": 1, "assessments": 0},
                    "top_subjects": [{"subject": "Science", "study_seconds": 1800}],
                    "mastery_summary": [{"subject": "Science", "avg_mastery_pct": 74.0, "chapters": []}],
                    "recent_activity": [{"activity_type": "lesson"}, {"activity_type": "quiz"}],
                    "assessment_summary": {},
                },
            ), patch.object(
                analytics,
                "get_progress_insights",
                return_value={"headline": "", "recommendations": [{"description": "Keep pushing Science."}], "badges": [], "notifications": []},
            ):
                payload = analytics.get_study_plan("study_plan_history_u")

        assert payload["history"]["previous_week"]["week_key"] == "2026-W13"
        assert payload["history"]["comparison"]["goal_delta"] >= 0

    def test_study_plan_can_recommend_assessment_retry_for_low_scores(self):
        from app.modules import analytics

        with patch.object(
            analytics,
            "get_dashboard",
            return_value={
                "total_study_seconds": 1800,
                "streak_days": 2,
                "totals": {"lessons": 1, "quizzes": 1, "assessments": 2},
                "top_subjects": [{"subject": "Science", "study_seconds": 1200}],
                "mastery_summary": [{"subject": "Science", "avg_mastery_pct": 68.0, "chapters": []}],
                "recent_activity": [{"activity_type": "lesson"}, {"activity_type": "assessment"}],
                "assessment_summary": {
                    "attempt_count": 3,
                    "average_score_pct": 52,
                    "best_score_pct": 80,
                    "latest_score_pct": 45,
                    "recent_scores": [45, 60, 80],
                },
            },
        ), patch.object(
            analytics,
            "get_progress_insights",
            return_value={"headline": "", "recommendations": [{"description": "Focus on Science revision."}], "badges": [], "notifications": []},
        ):
            payload = analytics.get_study_plan("study_plan_assessment_retry_u")

        assessment_step = next((step for step in payload["schedule"] if step.get("action_tab") == "assessment"), None)
        assert assessment_step is not None
        assert assessment_step["cta_label"] == "Retry Assessment"
        assert assessment_step["activity_type"] == "assessment"
        assert assessment_step["auto_run"] is True
        assert "Science" in assessment_step["title"]


# =============================================================================
# API integration tests — /progress/* routes
# =============================================================================

@pytest.fixture(scope="module")
def client():
    """TestClient with heavy deps mocked."""
    _heavy = [
        "sentence_transformers", "faiss", "numpy", "numpy.core",
        "tqdm", "tqdm.auto", "pypdf", "deep_translator",
        "llama_cpp", "openai", "docx", "python_docx",
    ]
    _injected = {}
    for pkg in _heavy:
        if pkg not in sys.modules:
            sys.modules[pkg] = MagicMock()
            _injected[pkg] = True

    st_mock = sys.modules["sentence_transformers"]
    st_mock.SentenceTransformer = MagicMock(return_value=MagicMock())

    try:
        import app.main as main_module
        from fastapi.testclient import TestClient

        with (
            patch.object(main_module, "load_index", return_value=None),
            patch.object(main_module, "load_knowledge_base", return_value=None),
            patch.object(main_module, "init_db", return_value=None),
            patch("threading.Thread"),
        ):
            from app.modules.db import init_db
            init_db()
            with TestClient(main_module.app, raise_server_exceptions=True) as c:
                yield c
    finally:
        for pkg in _injected:
            del sys.modules[pkg]


@pytest.fixture(autouse=True)
def clear_cookies(client):
    client.cookies.clear()


def _login(client, email="student@example.com", password="student123"):
    resp = client.post("/login", json={"email": email, "password": password})
    assert resp.status_code == 200, f"Login failed: {resp.text}"
    return resp.json()["access_token"]


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


class TestProgressDashboardRoute:

    def test_dashboard_unauthenticated_returns_401(self, client):
        client.cookies.clear()
        resp = client.get("/progress/dashboard")
        assert resp.status_code in (401, 403)
    
        def test_dashboard_route_uses_progress_service_registry(self, client):
            import app.api.routes as routes_module
        
            token = _login(client)
            stub_progress = SimpleNamespace(
                get_dashboard=lambda user_id: {
                    "total_study_seconds": 321,
                    "streak_days": 4,
                    "totals": {"quizzes": 7, "lessons": 8, "assessments": 1},
                    "top_subjects": [],
                    "recent_activity": [],
                    "mastery_summary": [],
                    "service_user": user_id,
                },
                get_mastery_stats=lambda user_id: [],
                log_activity=lambda **kwargs: 999,
                update_mastery=lambda *args, **kwargs: 88.0,
                get_student_progress=lambda student_user_id: ({}, []),
            )
        
            with patch.object(routes_module, "services", SimpleNamespace(progress=stub_progress, relationships=MagicMock())):
                resp = client.get("/progress/dashboard", headers=_auth(token))
        
            assert resp.status_code == 200
            body = resp.json()
            assert body["total_study_seconds"] == 321
            assert body["service_user"] == "student"

    def test_dashboard_authenticated_returns_200(self, client):
        token = _login(client)
        resp = client.get("/progress/dashboard", headers=_auth(token))
        assert resp.status_code == 200

    def test_dashboard_response_shape(self, client):
        token = _login(client)
        resp = client.get("/progress/dashboard", headers=_auth(token))
        body = resp.json()
        for key in ("total_study_seconds", "streak_days", "totals",
                    "top_subjects", "recent_activity", "mastery_summary"):
            assert key in body, f"Missing key in dashboard response: {key}"

    def test_dashboard_totals_shape(self, client):
        token = _login(client)
        resp = client.get("/progress/dashboard", headers=_auth(token))
        totals = resp.json()["totals"]
        for k in ("quizzes", "lessons", "assessments"):
            assert k in totals

    def test_dashboard_numeric_fields_non_negative(self, client):
        token = _login(client)
        resp = client.get("/progress/dashboard", headers=_auth(token))
        body = resp.json()
        assert body["total_study_seconds"] >= 0
        assert body["streak_days"] >= 0


class TestProgressMasteryRoute:

    def test_mastery_unauthenticated_returns_401(self, client):
        client.cookies.clear()
        resp = client.get("/progress/mastery")
        assert resp.status_code in (401, 403)

    def test_mastery_authenticated_returns_200(self, client):
        token = _login(client)
        resp = client.get("/progress/mastery", headers=_auth(token))
        assert resp.status_code == 200

    def test_mastery_response_is_list(self, client):
        token = _login(client)
        resp = client.get("/progress/mastery", headers=_auth(token))
        body = resp.json()
        # envelope wraps data: {mastery: [...], message: {...}}
        assert "mastery" in body
        assert isinstance(body["mastery"], list)

    def test_mastery_entries_have_required_fields(self, client):
        from app.modules.analytics import update_mastery
        from app.modules.db import init_db
        init_db()
        # Pre-seed mastery row for student user
        update_mastery("student@example.com", "TestSubj", "TestChap", correct=7, total=10)

        token = _login(client)
        resp = client.get("/progress/mastery", headers=_auth(token))
        body = resp.json()
        mastery_list = body["mastery"]
        if len(mastery_list) > 0:
            entry = mastery_list[0]
            for field in ("subject", "chapter", "mastery_pct", "quizzes_taken"):
                assert field in entry, f"Missing field: {field}"


class TestProgressInsightsRoute:

    def test_insights_unauthenticated_returns_401(self, client):
        client.cookies.clear()
        resp = client.get("/progress/insights")
        assert resp.status_code in (401, 403)

    def test_insights_authenticated_returns_200(self, client):
        token = _login(client)
        resp = client.get("/progress/insights", headers=_auth(token))
        assert resp.status_code == 200

    def test_insights_response_shape(self, client):
        token = _login(client)
        resp = client.get("/progress/insights", headers=_auth(token))
        body = resp.json()
        assert set(body.keys()) == {"headline", "recommendations", "badges", "notifications", "message"}
        assert isinstance(body["headline"], str)
        assert isinstance(body["recommendations"], list)
        assert isinstance(body["badges"], list)
        assert isinstance(body["notifications"], list)

    def test_insights_route_uses_progress_service_registry(self, client):
        import app.api.routes as routes_module

        token = _login(client)
        stub_progress = SimpleNamespace(
            get_insights=lambda user_id: {
                "headline": f"On track, {user_id}",
                "recommendations": [{"id": "focus", "title": "Focus", "description": "Do one quiz"}],
                "badges": [{"id": "starter", "label": "Starter", "earned": True, "progress_pct": 100}],
                "notifications": [{"id": "reminder", "title": "Stay on track", "message": "Finish one more quiz."}],
            },
        )

        with patch.object(routes_module, "services", SimpleNamespace(progress=stub_progress, relationships=MagicMock())):
            resp = client.get("/progress/insights", headers=_auth(token))

        assert resp.status_code == 200
        body = resp.json()
        assert body["headline"] == "On track, student"
        assert body["recommendations"][0]["id"] == "focus"


class TestProgressStudyPlanRoute:

    def test_study_plan_unauthenticated_returns_401(self, client):
        client.cookies.clear()
        resp = client.get("/progress/study-plan")
        assert resp.status_code in (401, 403)

    def test_study_plan_authenticated_returns_200(self, client):
        token = _login(client)
        resp = client.get("/progress/study-plan", headers=_auth(token))
        assert resp.status_code == 200

    def test_study_plan_response_shape(self, client):
        token = _login(client)
        resp = client.get("/progress/study-plan", headers=_auth(token))
        body = resp.json()
        assert set(body.keys()) == {"headline", "focus_subject", "schedule", "goal_summary", "targets", "history", "message"}
        assert isinstance(body["headline"], str)
        assert isinstance(body["focus_subject"], str)
        assert isinstance(body["schedule"], list)
        assert isinstance(body["goal_summary"], dict)
        assert isinstance(body["targets"], list)
        assert isinstance(body["history"], dict)

    def test_study_plan_route_uses_progress_service_registry(self, client):
        import app.api.routes as routes_module

        token = _login(client)
        stub_progress = SimpleNamespace(
            get_study_plan=lambda user_id: {
                "headline": f"Focus week for {user_id}",
                "focus_subject": "Math",
                "schedule": [{"id": "s1", "title": "Review Math", "description": "Do one quiz"}],
                "goal_summary": {"completed": 0, "total": 0},
                "targets": [],
                "history": {"current_week": {"week_key": "2026-W14"}, "previous_week": None, "comparison": {"summary": "No history yet."}},
            },
        )

        with patch.object(routes_module, "services", SimpleNamespace(progress=stub_progress, relationships=MagicMock())):
            resp = client.get("/progress/study-plan", headers=_auth(token))

        assert resp.status_code == 200
        body = resp.json()
        assert body["focus_subject"] == "Math"
        assert body["schedule"][0]["id"] == "s1"

    def test_study_plan_item_completion_can_be_saved(self, client):
        email = f"goal-save-{uuid.uuid4().hex[:8]}@example.com"
        register = client.post(
            "/register",
            json={
                "first_name": "Goal",
                "last_name": "Saver",
                "email": email,
                "dob": "2010-01-01",
                "password": "pass1234",
                "role": "student",
            },
        )
        assert register.status_code == 200

        token = _login(client, email, "pass1234")
        save_resp = client.post(
            "/progress/study-plan/items/weekly-quiz",
            headers=_auth(token),
            json={"item_type": "goal", "completed": True},
        )
        assert save_resp.status_code == 200
        assert save_resp.json()["completed"] is True

        refreshed = client.get("/progress/study-plan", headers=_auth(token))
        assert refreshed.status_code == 200
        assert any(target["id"] == "weekly-quiz" and target["completed"] is True for target in refreshed.json()["targets"])

    def test_learning_actions_feed_weekly_plan_completion(self, client):
        import app.api.routes as routes_module

        email = f"progress-plan-{uuid.uuid4().hex[:8]}@example.com"
        register = client.post(
            "/register",
            json={
                "first_name": "Plan",
                "last_name": "Student",
                "email": email,
                "dob": "2010-01-01",
                "password": "pass1234",
                "role": "student",
            },
        )
        assert register.status_code == 200

        token = _login(client, email, "pass1234")

        initial_plan = client.get("/progress/study-plan", headers=_auth(token))
        assert initial_plan.status_code == 200
        assert initial_plan.json()["schedule"][0]["completed"] is False

        with patch.object(
            routes_module,
            "generate_lesson_plan",
            return_value={
                "lesson_plan_id": 1,
                "session_id": "lesson-progress-session",
                "chapter": "Science",
                "steps": [{"id": 1, "title": "Review notes"}],
            },
        ):
            lesson_resp = client.post(
                "/lesson-plan/create",
                headers=_auth(token),
                json={
                    "session_id": "lesson-progress-session",
                    "chapter": "Science",
                    "lesson_context": "Review the key optics ideas.",
                },
            )
        assert lesson_resp.status_code == 200

        after_lesson = client.get("/progress/study-plan", headers=_auth(token))
        assert after_lesson.status_code == 200
        assert after_lesson.json()["schedule"][0]["completed"] is True

        with patch.object(
            routes_module,
            "generate_quiz",
            return_value={
                "quiz_id": "quiz-progress-1",
                "questions": [
                    {
                        "id": "q1",
                        "question": "What is refraction?",
                        "options": ["A", "B", "C", "D"],
                        "correct_option": "A",
                    }
                ],
            },
        ):
            quiz_resp = client.post(
                "/quiz/generate",
                headers=_auth(token),
                json={
                    "session_id": "quiz-progress-session",
                    "chapter": "Science",
                    "quiz_context": "Check recall on optics.",
                },
            )
        assert quiz_resp.status_code == 200

        after_quiz = client.get("/progress/study-plan", headers=_auth(token))
        assert after_quiz.status_code == 200
        assert after_quiz.json()["schedule"][1]["completed"] is True

        dashboard = client.get("/progress/dashboard", headers=_auth(token))
        assert dashboard.status_code == 200
        activity_types = [item["activity_type"] for item in dashboard.json()["recent_activity"]]
        assert "lesson" in activity_types
        assert "quiz" in activity_types

    def test_assessment_generation_appears_in_recent_activity(self, client):
        import app.api.routes as routes_module

        email = f"progress-assessment-{uuid.uuid4().hex[:8]}@example.com"
        register = client.post(
            "/register",
            json={
                "first_name": "Assessment",
                "last_name": "Student",
                "email": email,
                "dob": "2010-01-01",
                "password": "pass1234",
                "role": "student",
            },
        )
        assert register.status_code == 200

        token = _login(client, email, "pass1234")

        with patch.object(
            routes_module,
            "generate_subject_quiz",
            return_value={
                "paper_id": 77,
                "paper_type": "SUBJECT_QUIZ",
                "subject": "Science",
                "class_name": "Class 8",
                "mode": "practice",
                "difficulty": "mixed",
                "questions": [],
            },
        ):
            response = client.post(
                "/assessment/subject-quiz",
                headers=_auth(token),
                json={
                    "subject": "Science",
                    "class_name": "Class 8",
                    "num_questions": 5,
                    "difficulty": "mixed",
                    "mode": "practice",
                },
            )
        assert response.status_code == 200

        dashboard = client.get("/progress/dashboard", headers=_auth(token))
        assert dashboard.status_code == 200
        activity_types = [item["activity_type"] for item in dashboard.json()["recent_activity"]]
        assert "assessment" in activity_types


class TestLogActivityRoute:

    def test_activity_unauthenticated_returns_401(self, client):
        client.cookies.clear()
        resp = client.post("/progress/activity", json={
            "activity_type": "quiz", "subject": "Math", "chapter": "Algebra", "duration_seconds": 60
        })
        assert resp.status_code in (401, 403)
    
        def test_activity_route_uses_progress_service_registry(self, client):
            import app.api.routes as routes_module
        
            token = _login(client)
            stub_progress = SimpleNamespace(
                get_dashboard=lambda user_id: {},
                get_mastery_stats=lambda user_id: [],
                log_activity=lambda **kwargs: 4321,
                update_mastery=lambda *args, **kwargs: 91.0,
                get_student_progress=lambda student_user_id: ({}, []),
            )
        
            with patch.object(routes_module, "services", SimpleNamespace(progress=stub_progress, relationships=MagicMock())):
                resp = client.post("/progress/activity", headers=_auth(token), json={
                    "activity_type": "quiz",
                    "subject": "Science",
                    "chapter": "Optics",
                    "duration_seconds": 120,
                })
        
            assert resp.status_code == 200
            body = resp.json()
            assert body.get("logged") is True
            assert body["activity_id"] == 4321

    def test_activity_valid_payload_returns_200(self, client):
        token = _login(client)
        resp = client.post("/progress/activity", headers=_auth(token), json={
            "activity_type": "quiz",
            "subject": "Science",
            "chapter": "Optics",
            "duration_seconds": 120,
        })
        assert resp.status_code == 200

    def test_activity_response_contains_logged_flag(self, client):
        token = _login(client)
        resp = client.post("/progress/activity", headers=_auth(token), json={
            "activity_type": "lesson",
            "subject": "History",
            "chapter": "WWII",
            "duration_seconds": 90,
        })
        body = resp.json()
        # envelope wraps: {logged: True, activity_id: int, message: {...}}
        assert body.get("logged") is True
        assert "activity_id" in body
        assert isinstance(body["activity_id"], int)

    def test_activity_invalid_type_rejected_with_422(self, client):
        token = _login(client)
        resp = client.post("/progress/activity", headers=_auth(token), json={
            "activity_type": "INVALID_TYPE_XYZ",
            "subject": "Math",
            "chapter": "Algbra",
            "duration_seconds": 60,
        })
        assert resp.status_code == 422

    def test_activity_negative_duration_rejected_with_422(self, client):
        token = _login(client)
        resp = client.post("/progress/activity", headers=_auth(token), json={
            "activity_type": "quiz",
            "subject": "Math",
            "chapter": "Geometry",
            "duration_seconds": -10,
        })
        assert resp.status_code == 422

    def test_activity_duration_exceeding_86400_rejected_with_422(self, client):
        token = _login(client)
        resp = client.post("/progress/activity", headers=_auth(token), json={
            "activity_type": "chat",
            "subject": "",
            "chapter": "",
            "duration_seconds": 999999,
        })
        assert resp.status_code == 422

    def test_activity_all_valid_types_accepted(self, client):
        token = _login(client)
        for act_type in ("chat", "lesson", "quiz", "flashcard", "assessment"):
            resp = client.post("/progress/activity", headers=_auth(token), json={
                "activity_type": act_type,
                "subject": "Test",
                "chapter": "Test",
                "duration_seconds": 10,
            })
            assert resp.status_code == 200, f"Type '{act_type}' should be accepted, got {resp.status_code}"

    def test_activity_zero_duration_accepted(self, client):
        token = _login(client)
        resp = client.post("/progress/activity", headers=_auth(token), json={
            "activity_type": "chat",
            "duration_seconds": 0,
        })
        assert resp.status_code == 200


class TestQuizMasteryRoute:

    def test_quiz_submit_route_uses_progress_service_registry(self, client):
        import app.api.routes as routes_module

        token = _login(client)
        stub_progress = SimpleNamespace(
            get_dashboard=lambda user_id: {},
            get_mastery_stats=lambda user_id: [],
            log_activity=lambda **kwargs: 0,
            update_mastery=lambda *args, **kwargs: 77.7,
            get_student_progress=lambda student_user_id: ({}, []),
        )

        with (
            patch.object(routes_module, "services", SimpleNamespace(progress=stub_progress, relationships=MagicMock())),
            patch.object(routes_module, "submit_quiz_answer", return_value={
                "q1": {"is_correct": True},
                "q2": {"is_correct": False},
            }),
            patch.object(routes_module, "_infer_subject_chapter", return_value=("Science", "Optics")),
        ):
            resp = client.post(
                "/quiz/quiz-123/submit",
                headers=_auth(token),
                json={
                    "session_id": "session-123",
                    "answers": {"q1": "A", "q2": "B"},
                },
            )

        assert resp.status_code == 200
        body = resp.json()
        assert body["_mastery_pct"] == 77.7
