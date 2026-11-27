"""Acceptance tests: multi-user auth, isolated progress, spaced repetition and
the post-hoc mastery dashboard.

Proves against the real FastAPI app that two accounts cannot see or advance
each other's progress, that missed MCQ/flashcard items resurface on schedule,
and that the dashboard exposes only already-mastered work.
"""
import json
import tempfile
import uuid
from pathlib import Path
from types import SimpleNamespace

import pytest

BACKEND = Path(__file__).resolve().parent.parent
import sys  # noqa: E402
sys.path.insert(0, str(BACKEND))

from sqlalchemy import create_engine  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlmodel import Session  # noqa: E402

import app.database as db  # noqa: E402
from app.database import init_db  # noqa: E402
from app.main import app  # noqa: E402
from app.agents.pipeline import GraderAgent  # noqa: E402
from app.models.entities import Course, Lesson, Module, ReviewItem  # noqa: E402

SECRETS = ("SECRET-FUTURE-LESSON-BRAVO", "SECRET-FUTURE-LESSON-CHARLIE",
           "SECRET-FUTURE-MODULE-DELTA", "SECRET-FUTURE-CONTENT")
FORBIDDEN_KEYS = {"total", "count", "total_modules", "total_lessons", "remaining",
                  "progress", "progress_percent", "percent", "lesson_number",
                  "module_number", "completed_count", "lessons_total", "modules_total"}


@pytest.fixture(scope="module", autouse=True)
def isolated_db():
    """Give this module its own DB regardless of other test modules' imports."""
    original = db.engine
    path = Path(tempfile.mkdtemp(prefix="trivium-auth-")) / "auth_progress.db"
    db.engine = create_engine(f"sqlite:///{path}", connect_args={"check_same_thread": False})
    init_db()
    yield
    db.engine = original


def _quiz():
    return json.dumps({
        "mcq": [
            {"question": f"Q{i}?", "options": [
                {"label": "A", "text": "wrong", "is_correct": False},
                {"label": "B", "text": "right", "is_correct": True}], "explanation": "e"}
            for i in range(3)
        ],
        "fill_in_the_blanks": [],
        "simulation": {"context": "ctx", "initial_indicators": [],
                       "turn1_prompt": "p", "turn1_options": []},
        "socratic_duel": {"question": "Defend it.", "evaluation_rubric": ["r"]},
    })


def _seed():
    init_db()
    with Session(db.engine) as s:
        course = Course(subject=f"Auth Lab {uuid.uuid4().hex[:6]}",
                        level="Básico", language="en-US")
        s.add(course); s.commit(); s.refresh(course)
        m1 = Module(course_id=course.id, module_number=1, title="Visible Module",
                    is_unlocked=True)
        m2 = Module(course_id=course.id, module_number=2,
                    title="SECRET-FUTURE-MODULE-DELTA", is_unlocked=False)
        s.add(m1); s.add(m2); s.commit(); s.refresh(m1); s.refresh(m2)
        l1 = Lesson(module_id=m1.id, lesson_number=1, title="PUBLIC First Lesson",
                    core_concept="public concept", status="in_progress",
                    summary_50_words="PUBLIC HOOK", content_markdown="PUBLIC CONTENT",
                    quiz_json=_quiz())
        l2 = Lesson(module_id=m1.id, lesson_number=2,
                    title="SECRET-FUTURE-LESSON-BRAVO", core_concept="secret concept",
                    status="locked", quiz_json=_quiz())
        l3 = Lesson(module_id=m2.id, lesson_number=1,
                    title="SECRET-FUTURE-LESSON-CHARLIE", core_concept="secret concept",
                    content_markdown="SECRET-FUTURE-CONTENT", status="locked", quiz_json=_quiz())
        s.add(l1); s.add(l2); s.add(l3); s.commit(); s.refresh(l1); s.refresh(l2)
        return course.id, l1.id, l2.id


def _register(client, username):
    r = client.post("/api/auth/register",
                    json={"username": username, "password": "supersecret1"})
    assert r.status_code == 201, r.text
    return {"Authorization": f"Bearer {r.json()['token']}"}


def _keys(obj):
    found = set()
    if isinstance(obj, dict):
        for k, v in obj.items():
            found.add(k)
            found |= _keys(v)
    elif isinstance(obj, list):
        for item in obj:
            found |= _keys(item)
    return found


def _no_future(payload, label):
    blob = json.dumps(payload, ensure_ascii=False)
    for secret in SECRETS:
        assert secret not in blob, f"{label}: leaked {secret!r}"


def test_auth_mechanics():
    init_db()
    client = TestClient(app)
    name = f"mechanics{uuid.uuid4().hex[:6]}"
    h = _register(client, name)

    assert client.post("/api/auth/register",
                       json={"username": name, "password": "supersecret1"}).status_code == 409
    assert client.post("/api/auth/login",
                       json={"username": name, "password": "wrong-password"}).status_code == 401
    assert client.get("/api/auth/me").status_code == 401
    assert client.get("/api/auth/me", headers={"Authorization": "Bearer bogus"}).status_code == 401
    me = client.get("/api/auth/me", headers=h)
    assert me.status_code == 200 and me.json()["username"] == name
    assert client.post("/api/auth/logout", headers=h).status_code == 200
    assert client.get("/api/auth/me", headers=h).status_code == 401
    relogin = client.post("/api/auth/login",
                          json={"username": name, "password": "supersecret1"})
    assert relogin.status_code == 200 and relogin.json()["token"]


def test_isolated_progress_and_fog_of_war(monkeypatch):
    course_id, l1, l2 = _seed()
    client = TestClient(app)
    alice = _register(client, f"alice{uuid.uuid4().hex[:6]}")
    bob = _register(client, f"bob{uuid.uuid4().hex[:6]}")

    # Both start at the same revealed step, but no future titles or counts.
    for headers in (alice, bob):
        step = client.get(f"/api/courses/{course_id}/current-step", headers=headers).json()
        assert step["id"] == l1 and step["title"] == "PUBLIC First Lesson"
        _no_future(step, "current-step")

    # Alice fails the quiz; Bob's gates stay untouched.
    fail = client.post(f"/api/lessons/{l1}/submit-quiz", headers=alice,
                       json={"lesson_id": l1, "answers": {"0": "A", "1": "A", "2": "A"}, "blanks": {}})
    assert fail.status_code == 200, fail.text
    assert fail.json()["mcq_passed"] is False
    assert client.get(f"/api/lessons/{l1}/gates", headers=bob).json()["grammar"] is False
    assert client.get(f"/api/lessons/{l1}/gates", headers=alice).json()["grammar"] is False

    # Alice passes Grammar; Bob still has not.
    ok = client.post(f"/api/lessons/{l1}/submit-quiz", headers=alice,
                     json={"lesson_id": l1, "answers": {"0": "B", "1": "B", "2": "B"}, "blanks": {}})
    assert ok.json()["mcq_passed"] is True and ok.json()["lesson_completed"] is False
    assert client.get(f"/api/lessons/{l1}/gates", headers=alice).json()["grammar"] is True
    assert client.get(f"/api/lessons/{l1}/gates", headers=bob).json()["grammar"] is False
    assert client.get("/api/profile/stats", headers=bob).json()["completed_lessons"] == 0

    # Early Logic attempt is blocked for both learners.
    assert client.post(f"/api/lessons/{l1}/submit-simulation", headers=bob,
                       json={"turn1_id": "t", "turn2_id": "t", "is_success": True}).status_code == 409

    # Alice completes Logic + Rhetoric (LLM grader stubbed, no network call).
    async def r1(**kwargs):
        return SimpleNamespace(passed_round1=True, feedback="ok", cognitive_knot="edge")
    async def r2(**kwargs):
        return SimpleNamespace(passed=True, score=9, feedback="ok")
    monkeypatch.setattr(GraderAgent, "evaluate_socratic_round1", staticmethod(r1))
    monkeypatch.setattr(GraderAgent, "evaluate_socratic_round2", staticmethod(r2))

    sim = client.post(f"/api/lessons/{l1}/submit-simulation", headers=alice,
                      json={"turn1_id": "t", "turn2_id": "t", "is_success": True})
    assert sim.json()["simulation_passed"] is True
    assert client.post(f"/api/lessons/{l1}/socratic-duel", headers=alice,
                       json={"round": 1, "answer": "thesis"}).json()["passed_round1"] is True
    duel = client.post(f"/api/lessons/{l1}/socratic-duel", headers=alice,
                       json={"round": 2, "answer": "rebuttal"})
    assert duel.json()["lesson_completed"] is True, duel.text

    # Exactly one next step is revealed for Alice. Bob is unmoved, and the
    # shared curriculum row is not mutated by Alice's progress.
    assert client.get(f"/api/courses/{course_id}/current-step", headers=alice).json()["id"] == l2
    assert client.get(f"/api/courses/{course_id}/current-step", headers=bob).json()["id"] == l1
    with Session(db.engine) as s:
        assert s.get(Lesson, l2).status == "locked"

    # Locked lessons still 403 (no title leak) and future titles never appear.
    locked = client.get(f"/api/lessons/{l2}", headers=bob)
    assert locked.status_code == 403
    _no_future(locked.json(), "locked lesson")
    next_step = client.get(f"/api/courses/{course_id}/next-step", headers=alice).json()
    _no_future(next_step, "next-step")
    assert [c["id"] for c in next_step["completed_lessons"]] == [l1]

    # Post-hoc dashboard: only Alice's mastered work; no totals or future work.
    dash = client.get("/api/dashboard/mastery", headers=alice).json()
    _no_future(dash, "dashboard")
    assert not (FORBIDDEN_KEYS & _keys(dash)), FORBIDDEN_KEYS & _keys(dash)
    mastered = [item["title"] for skill in dash["mastered_by_skill"]
                for item in skill["mastered_items"]]
    assert mastered == ["PUBLIC First Lesson"], mastered
    bob_dash = client.get("/api/dashboard/mastery", headers=bob).json()
    assert bob_dash["mastered_by_skill"] == [], bob_dash
    _no_future(bob_dash, "bob dashboard")


def test_spaced_repetition_schedule():
    course_id, l1, _l2 = _seed()
    client = TestClient(app)
    carol = _register(client, f"carol{uuid.uuid4().hex[:6]}")
    dave = _register(client, f"dave{uuid.uuid4().hex[:6]}")

    resp = client.post(f"/api/lessons/{l1}/submit-quiz", headers=carol,
                       json={"lesson_id": l1, "answers": {"0": "A", "1": "A", "2": "A"}, "blanks": {}})
    assert resp.status_code == 200, resp.text
    import datetime
    tomorrow = (datetime.date.today() + datetime.timedelta(days=1)).isoformat()
    with Session(db.engine) as s:
        queued = s.exec(__import__("sqlmodel").select(ReviewItem)).all()
    mine = [item for item in queued if item.lesson_id == l1]
    assert {item.item_key for item in mine} == {"mcq:0", "mcq:1", "mcq:2"}
    assert all(item.kind == "mcq" and item.prompt and item.expected for item in mine)
    assert all(item.misses == 1 and item.interval_days == 1 and item.due_on == tomorrow
               for item in mine)
    # Scheduled for tomorrow: nothing is due today yet.
    assert client.get("/api/reviews/due", headers=carol).json() == []
    assert client.get("/api/reviews/due", headers=dave).json() == []

    # Advance the clock on one item to check resurfacing without sleeping.
    target = mine[0].id
    with Session(db.engine) as s:
        s.get(ReviewItem, target).due_on = datetime.date.today().isoformat()
        s.commit()

    today_due = client.get("/api/reviews/due", headers=carol).json()
    assert [item["id"] for item in today_due] == [target]
    assert client.get("/api/reviews/due", headers=dave).json() == []
    # Another learner cannot complete someone else's review item.
    assert client.post(f"/api/reviews/{target}/complete", headers=dave, json={}).status_code == 404

    passed = client.post(f"/api/reviews/{target}/complete", headers=carol,
                         json={"passed": True}).json()
    assert passed["next_due_on"] > __import__("datetime").date.today().isoformat()
    assert client.get("/api/reviews/due", headers=carol).json() == []
    with Session(db.engine) as s:
        item = s.get(ReviewItem, target)
        assert item.interval_days == 2 and item.pass_count == 1

    # A failed review resets the interval to one day and resurfaces tomorrow.
    failed = client.post(f"/api/reviews/{target}/complete", headers=carol,
                         json={"passed": False}).json()
    assert failed["next_due_on"] == (
        __import__("datetime").date.today() + __import__("datetime").timedelta(days=1)
    ).isoformat()
    with Session(db.engine) as s:
        assert s.get(ReviewItem, target).misses == 2