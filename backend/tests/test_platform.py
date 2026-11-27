"""Fog-of-War + catalog + gamification acceptance tests.

Seeds a course with secret future titles, then asserts the API never leaks
them (nor any total / percent), gates work, and XP only counts completed work.
"""
import json
import os
import sys
import tempfile
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND))
os.environ["DATABASE_URL"] = f"sqlite:///{tempfile.mkdtemp()}/test.db"

from fastapi.testclient import TestClient  # noqa: E402
from sqlmodel import Session, select  # noqa: E402

from app.database import engine, init_db  # noqa: E402
from app.models.entities import Course, Module, Lesson  # noqa: E402
from app.main import app  # noqa: E402

SECRET_FUTURE = ["SECRET Future Lesson Alpha", "SECRET Future Lesson Beta",
                 "SECRET Future Module Zeta"]
FORBIDDEN_KEYS = {"total_modules", "total_lessons", "progress_percent",
                  "total", "remaining", "lesson_number"}


def _quiz():
    return json.dumps({
        "mcq": [{"question": "Q1?", "options": [
            {"label": "A", "text": "wrong", "is_correct": False},
            {"label": "B", "text": "right", "is_correct": True}], "explanation": "e"},
            {"question": "Q2?", "options": [
            {"label": "A", "text": "wrong", "is_correct": False},
            {"label": "B", "text": "right", "is_correct": True}], "explanation": "e"},
            {"question": "Q3?", "options": [
            {"label": "A", "text": "wrong", "is_correct": False},
            {"label": "B", "text": "right", "is_correct": True}], "explanation": "e"}],
        "fill_in_the_blanks": [],
        "simulation": {"context": "ctx", "initial_indicators": [],
                       "turn1_prompt": "p", "turn1_options": []},
        "socratic_duel": {"question": "Explain it.", "evaluation_rubric": ["r"]},
    })


def _seed():
    init_db()
    with Session(engine) as s:
        c = Course(subject="Python & Sistemas Distribuidos", level="Básico", language="pt-BR")
        s.add(c); s.commit(); s.refresh(c)
        m1 = Module(course_id=c.id, module_number=1, title="Visible First Module", is_unlocked=True)
        m2 = Module(course_id=c.id, module_number=2, title=SECRET_FUTURE[2], is_unlocked=False)
        s.add(m1); s.add(m2); s.commit(); s.refresh(m1); s.refresh(m2)
        l1 = Lesson(module_id=m1.id, lesson_number=1, title="Visible First Lesson",
                    core_concept="concept one", status="in_progress", quiz_json=_quiz())
        l2 = Lesson(module_id=m1.id, lesson_number=2, title=SECRET_FUTURE[0],
                    core_concept="secret concept", status="locked", quiz_json=_quiz())
        l3 = Lesson(module_id=m2.id, lesson_number=1, title=SECRET_FUTURE[1],
                    core_concept="secret concept", status="locked", quiz_json=_quiz())
        s.add(l1); s.add(l2); s.add(l3); s.commit()
        for l in (l1, l2, l3):
            s.refresh(l)
        return c.id, l1.id, l2.id


def _assert_no_leak(payload, label):
    blob = json.dumps(payload, ensure_ascii=False)
    for secret in SECRET_FUTURE:
        assert secret not in blob, f"{label}: leaked future title {secret!r}"
    assert "secret concept" not in blob, f"{label}: leaked future concept"


def _keys_deep(obj):
    keys = set()
    if isinstance(obj, dict):
        keys |= set(obj.keys())
        for v in obj.values():
            keys |= _keys_deep(v)
    elif isinstance(obj, list):
        for v in obj:
            keys |= _keys_deep(v)
    return keys


def test_fog_of_war():
    course_id, l1, l2 = _seed()
    client = TestClient(app)

    # Course detail: only current step, no future, no totals
    r = client.get(f"/api/courses/{course_id}")
    assert r.status_code == 200, r.text
    body = r.json()
    _assert_no_leak(body, "course detail")
    assert not (FORBIDDEN_KEYS & _keys_deep(body) - {"lesson_number"}), _keys_deep(body) & FORBIDDEN_KEYS
    assert body["next_step"]["id"] == l1
    assert body["fog_of_war"] is True

    # Next-step endpoint mirrors it
    r = client.get(f"/api/courses/{course_id}/next-step")
    assert r.status_code == 200
    _assert_no_leak(r.json(), "next-step")
    assert r.json()["current_step"]["id"] == l1

    # List + catalog: no totals / percent anywhere
    for url in ("/api/courses", "/api/catalog", "/api/catalog?category=code",
                "/api/catalog?q=python", "/api/catalog?category=music"):
        r = client.get(url)
        assert r.status_code == 200, (url, r.text)
        assert not ({"total_modules", "total_lessons", "progress_percent"} & _keys_deep(r.json())), url
    cats = client.get("/api/catalog/categories").json()
    assert {c["id"] for c in cats} >= {"code", "music", "money", "design", "language"}
    assert client.get("/api/catalog?category=code").json()[0]["category"] == "code"
    assert client.get("/api/catalog?category=music").json() == []

    # Locked lesson: 403 and no title leak
    r = client.get(f"/api/lessons/{l2}")
    assert r.status_code == 403, r.text
    _assert_no_leak(r.json(), "locked lesson")
    r = client.get(f"/api/lessons/{l2}/gates")
    assert r.status_code == 403

    # Gates on current lesson: all False initially
    g = client.get(f"/api/lessons/{l1}/gates").json()
    assert g == {"lesson_id": l1, "grammar": False, "logic": False,
                 "rhetoric": False, "lesson_completed": False}, g

    # Failing quiz: no unlock, review queued, no XP
    r = client.post(f"/api/lessons/{l1}/submit-quiz",
                    json={"lesson_id": l1, "answers": {"0": "A", "1": "A", "2": "A"}, "blanks": {}})
    assert r.json()["mcq_passed"] is False
    stats = client.get("/api/profile/stats").json()
    assert stats["xp"] == 0 and stats["completed_lessons"] == 0, stats

    # Passing quiz: Grammar gate only; lesson NOT completed (Logic+Rhetoric pending)
    r = client.post(f"/api/lessons/{l1}/submit-quiz",
                    json={"lesson_id": l1, "answers": {"0": "B", "1": "B", "2": "B"}, "blanks": {}})
    assert r.json()["mcq_passed"] is True
    assert r.json()["lesson_completed"] is False
    g = client.get(f"/api/lessons/{l1}/gates").json()
    assert g["grammar"] is True and g["logic"] is False and g["rhetoric"] is False

    # Simulation (Logic) + Socratic (Rhetoric) complete the gate chain -> unlock next
    r = client.post(f"/api/lessons/{l1}/submit-simulation",
                    json={"turn1_id": "t1", "turn2_id": "t2", "is_success": True})
    assert r.json()["simulation_passed"] is True
    # Socratic needs the LLM grader; simulate its outcome directly in the DB is
    # out of scope for the API test, so verify gate state instead:
    g = client.get(f"/api/lessons/{l1}/gates").json()
    assert g["logic"] is True and g["rhetoric"] is False and g["lesson_completed"] is False

    # XP still 0: no lesson completed yet (only completed work counts)
    stats = client.get("/api/profile/stats").json()
    assert stats["xp"] == 0, stats

    # Manually mark completion path: set socratic_passed and drive unlock logic
    with Session(engine) as s:
        lesson = s.get(Lesson, l1)
        lesson.socratic_passed = True
        s.add(lesson); s.commit()
    # Re-submit a passing quiz to trigger check_and_unlock with all gates green
    r = client.post(f"/api/lessons/{l1}/submit-quiz",
                    json={"lesson_id": l1, "answers": {"0": "B", "1": "B", "2": "B"}, "blanks": {}})
    assert r.json()["lesson_completed"] is True, r.text

    # Now the next step is revealed — exactly one
    ns = client.get(f"/api/courses/{course_id}/next-step").json()
    assert ns["current_step"]["id"] == l2
    assert [c["id"] for c in ns["completed_lessons"]] == [l1]
    _assert_no_leak({k: v for k, v in ns.items() if k != "current_step"}, "next-step after unlock")
    assert SECRET_FUTURE[1] not in json.dumps(ns) and SECRET_FUTURE[2] not in json.dumps(ns)

    # XP now reflects exactly one completed lesson
    stats = client.get("/api/profile/stats").json()
    assert stats["completed_lessons"] == 1 and stats["xp"] == 25, stats
    assert stats["level"] >= 1 and "first-step" in stats["badges"]
    assert stats["streak_days"] >= 1

    # Certificate blocked until everything is done
    assert client.get(f"/api/courses/{course_id}/certificate").status_code == 403
