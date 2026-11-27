"""Acceptance tests: Fog-of-War filtering + Trivium mastery gates.

Proves, against the real FastAPI app:
  * future lesson/module titles, content and counts never cross the API;
  * ``suppress_counts`` removes totals/percent/ordinals from list/catalog
    responses by default;
  * the current-step endpoint exposes exactly one step (title/hook/content/
    gates);
  * the Learn -> Quiz -> Simulate -> Teach-back -> Unlock chain blocks early
    attempts and only unlocks the next step after every gate passes;
  * past steps stay reviewable while the locked ones 403 on every route.
"""
import json
import os
import sys
import tempfile
import uuid
from pathlib import Path
from types import SimpleNamespace

BACKEND = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND))
os.environ.setdefault("DATABASE_URL", f"sqlite:///{tempfile.mkdtemp()}/fog_gates.db")

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine  # noqa: E402
from sqlmodel import Session, delete, select  # noqa: E402

import app.database as db  # noqa: E402
from app.database import init_db  # noqa: E402
from app.main import app  # noqa: E402
from app.models.entities import (  # noqa: E402
    Course, Lesson, LessonChatMessage, LearnerProfile, Module, ReviewItem,
)
from app.schemas.quiz import SocraticRound1Evaluation, SocraticRound2Evaluation  # noqa: E402

SECRETS = (
    "SECRET-FUTURE-LESSON-BRAVO",
    "SECRET-FUTURE-LESSON-CHARLIE",
    "SECRET-FUTURE-MODULE-DELTA",
    "SECRET-FUTURE-CONTENT",
    "SECRET-FUTURE-CONCEPT",
)
COUNT_KEYS = {
    "total_modules", "total_lessons", "total", "count", "lesson_count",
    "module_count", "remaining", "progress_percent", "percent_complete",
    "lesson_number", "module_number",
}


@pytest.fixture(scope="module", autouse=True)
def isolated_db():
    """Bind this module to a private DB: app.database is imported once per suite."""
    original = db.engine
    path = Path(tempfile.mkdtemp(prefix="trivium-fog-")) / "test.db"
    db.engine = create_engine(f"sqlite:///{path}", connect_args={"check_same_thread": False})
    init_db()
    yield
    db.engine = original


def _quiz():
    return json.dumps({
        "mcq": [
            {"question": "Q1?", "options": [
                {"label": "A", "text": "wrong", "is_correct": False},
                {"label": "B", "text": "right", "is_correct": True}], "explanation": "e"},
            {"question": "Q2?", "options": [
                {"label": "A", "text": "wrong", "is_correct": False},
                {"label": "B", "text": "right", "is_correct": True}], "explanation": "e"},
            {"question": "Q3?", "options": [
                {"label": "A", "text": "wrong", "is_correct": False},
                {"label": "B", "text": "right", "is_correct": True}], "explanation": "e"},
        ],
        "fill_in_the_blanks": [
            {"correct_word": "alpha"}, {"correct_word": "beta"}, {"correct_word": "gamma"},
        ],
        "discursive": {"question": "Explain.", "evaluation_rubric": ["r"]},
        "simulation": {"context": "ctx", "initial_indicators": [],
                       "turn1_prompt": "p", "turn1_options": []},
        "socratic_duel": {"question": "Defend it.", "evaluation_rubric": ["r"]},
    })


def _keys(obj):
    keys = set()
    if isinstance(obj, dict):
        for k, v in obj.items():
            keys.add(k)
            keys |= _keys(v)
    elif isinstance(obj, list):
        for v in obj:
            keys |= _keys(v)
    return keys


def _ids(obj):
    """Ids carried in a payload — recursive, restricted to id-like keys.

    Scores/targets are legitimate integers (e.g. mcq target 2), so a blanket
    integer scan would falsely report an unrevealed lesson with id 2.
    """
    ids = set()
    if isinstance(obj, dict):
        for k, v in obj.items():
            if (k == "id" or k.endswith("_id")) and isinstance(v, int) and not isinstance(v, bool):
                ids.add(v)
            ids |= _ids(v)
    elif isinstance(obj, list):
        for v in obj:
            ids |= _ids(v)
    return ids


def _no_leak(payload, label):
    blob = json.dumps(payload, ensure_ascii=False)
    for secret in SECRETS:
        assert secret not in blob, f"{label}: leaked {secret!r}"


@pytest.fixture
def seeded():
    init_db()
    tag = uuid.uuid4().hex[:8]
    subject = f"FogGate Lab {tag}"
    with Session(db.engine) as s:
        course = Course(subject=subject, level="Básico", language="en-US")
        s.add(course); s.commit(); s.refresh(course)
        m1 = Module(course_id=course.id, module_number=1, title="Visible Module",
                    is_unlocked=True)
        m2 = Module(course_id=course.id, module_number=2,
                    title="SECRET-FUTURE-MODULE-DELTA", is_unlocked=False)
        s.add(m1); s.add(m2); s.commit(); s.refresh(m1); s.refresh(m2)
        l1 = Lesson(module_id=m1.id, lesson_number=1, title="Public Current Alpha",
                    core_concept="public concept", status="in_progress",
                    summary_50_words="PUBLIC HOOK ALPHA",
                    content_markdown="PUBLIC CONTENT ALPHA", quiz_json=_quiz())
        l2 = Lesson(module_id=m1.id, lesson_number=2, title="SECRET-FUTURE-LESSON-BRAVO",
                    core_concept="SECRET-FUTURE-CONCEPT", status="locked",
                    content_markdown="SECRET-FUTURE-CONTENT", quiz_json=_quiz())
        l3 = Lesson(module_id=m2.id, lesson_number=1, title="SECRET-FUTURE-LESSON-CHARLIE",
                    core_concept="SECRET-FUTURE-CONCEPT", status="locked",
                    content_markdown="SECRET-FUTURE-CONTENT", quiz_json=_quiz())
        s.add(l1); s.add(l2); s.add(l3); s.commit()
        for obj in (l1, l2, l3):
            s.refresh(obj)
        ids = (course.id, l1.id, l2.id, l3.id)
    client = TestClient(app)
    yield client, ids, subject
    # Keep the shared test DB clean for sibling tests.
    with Session(db.engine) as s:
        lesson_ids = list(ids[1:])
        s.exec(delete(LessonChatMessage).where(LessonChatMessage.lesson_id.in_(lesson_ids)))
        s.exec(delete(ReviewItem).where(ReviewItem.lesson_id.in_(lesson_ids)))
        for lid in lesson_ids:
            lesson = s.get(Lesson, lid)
            if lesson:
                s.delete(lesson)
        for mod in s.exec(select(Module).where(Module.course_id == ids[0])).all():
            s.delete(mod)
        course = s.get(Course, ids[0])
        if course:
            s.delete(course)
        profile = s.get(LearnerProfile, 1)
        if profile:
            profile.streak_days = 0
            profile.reviews_completed = 0
            profile.last_active_date = None
            s.add(profile)
        s.commit()


def _pass_quiz(client, lid, blanks=("alpha", "beta", "gamma")):
    return client.post(f"/api/lessons/{lid}/submit-quiz", json={
        "lesson_id": lid,
        "answers": {"0": "B", "1": "B", "2": "B"},
        "blanks": {str(i): word for i, word in enumerate(blanks)},
    })


def test_current_step_is_the_only_step_returned(seeded):
    client, (cid, l1, l2, l3), subject = seeded
    r = client.get(f"/api/courses/{cid}/current-step")
    assert r.status_code == 200, r.text
    body = r.json()
    assert set(body) == {"id", "stage", "title", "hook", "content", "gates"}
    assert body["id"] == l1
    assert body["title"] == "Public Current Alpha"
    assert body["hook"] == "PUBLIC HOOK ALPHA"
    assert body["content"] == "PUBLIC CONTENT ALPHA"
    assert body["stage"] == "quiz"
    assert set(body["gates"]) >= {"grammar", "logic", "rhetoric", "current_stage", "stages"}
    assert [s["id"] for s in body["gates"]["stages"]] == [
        "learn", "quiz", "simulate", "teach_back", "unlock"]
    _no_leak(body, "current-step")
    # IDs of unrevealed steps must not appear anywhere in the payload.
    assert l2 not in _ids(body) and l3 not in _ids(body)


def test_no_future_titles_or_counts_leak_anywhere(seeded):
    client, (cid, l1, l2, l3), subject = seeded
    endpoints = [
        "/api/courses", f"/api/courses/{cid}", f"/api/courses/{cid}/next-step",
        f"/api/courses/{cid}/current-step", "/api/catalog",
        "/api/catalog?category=code", f"/api/catalog?q={subject}",
        "/api/profile/stats", "/api/reviews/due", f"/api/lessons/{l1}",
    ]
    for url in endpoints:
        r = client.get(url)
        assert r.status_code == 200, (url, r.text)
        _no_leak(r.json(), url)
        assert not (COUNT_KEYS & _keys(r.json())), (url, COUNT_KEYS & _keys(r.json()))

    # Locked lessons reveal nothing on ANY route, including submissions and PDF.
    for method, url, payload in [
        ("get", f"/api/lessons/{l2}", None),
        ("get", f"/api/lessons/{l2}/gates", None),
        ("get", f"/api/lessons/{l2}/download-pdf", None),
        ("get", f"/api/lessons/{l2}/chat", None),
        ("post", f"/api/lessons/{l2}/submit-quiz",
         {"lesson_id": l2, "answers": {}, "blanks": {}}),
        ("post", f"/api/lessons/{l2}/submit-simulation",
         {"turn1_id": "t", "turn2_id": "t", "is_success": True}),
        ("post", f"/api/lessons/{l2}/socratic-duel", {"round": 1, "answer": "a"}),
    ]:
        r = getattr(client, method)(url, json=payload) if payload else getattr(client, method)(url)
        assert r.status_code == 403, (method, url, r.status_code, r.text)
        _no_leak(r.json(), f"{method} {url}")


def test_suppress_counts_flag_defaults_on_for_lists_and_catalog(seeded):
    client, (cid, l1, l2, l3), subject = seeded
    cards = client.get("/api/catalog").json()
    mine = [c for c in cards if c["id"] == cid]
    assert len(mine) == 1
    card = mine[0]
    assert {"topic", "category", "difficulty"} <= set(card)
    assert card["topic"] == subject and card["difficulty"] == "Básico"
    assert not (COUNT_KEYS & set(card)), set(card) & COUNT_KEYS
    assert set(card) <= {"id", "topic", "category", "difficulty", "subject", "level",
                         "language", "cover_image_url", "source_type"}

    for url in ("/api/courses", "/api/catalog", f"/api/courses/{cid}/next-step",
                "/api/courses?suppress_counts=true", "/api/catalog?suppress_counts=true"):
        payload = client.get(url).json()
        assert not (COUNT_KEYS & _keys(payload)), (url, COUNT_KEYS & _keys(payload))
        if isinstance(payload, list):
            assert all(not isinstance(item.get("completed_lessons"), int) for item in payload)
        elif "completed_lessons" in payload:
            assert isinstance(payload["completed_lessons"], list)  # past steps, reviewable

    # Explicit opt-out shows the flag actually controls the shaping.
    raw = client.get("/api/courses?suppress_counts=false").json()
    assert any(isinstance(item.get("completed_lessons"), int) for item in raw)


def test_mastery_gate_blocks_until_passed(seeded, monkeypatch):
    client, (cid, l1, l2, l3), subject = seeded

    # Logic and Rhetoric cannot be attempted before Grammar passes.
    assert client.post(f"/api/lessons/{l1}/submit-simulation", json={
        "turn1_id": "t1", "turn2_id": "t2", "is_success": True}).status_code == 409
    assert client.post(f"/api/lessons/{l1}/socratic-duel", json={
        "round": 1, "answer": "thesis"}).status_code == 409

    # MCQ alone is not enough: flashcards are part of the Grammar gate.
    r = _pass_quiz(client, l1, blanks=("alpha", "", ""))
    assert r.status_code == 200 and r.json()["mcq_passed"] is True
    gates = client.get(f"/api/lessons/{l1}/gates").json()
    assert gates["grammar"] is False and gates["lesson_completed"] is False
    assert client.post(f"/api/lessons/{l1}/submit-simulation", json={
        "turn1_id": "t1", "turn2_id": "t2", "is_success": True}).status_code == 409

    # Full Grammar pass unlocks the Logic stage.
    r = _pass_quiz(client, l1)
    assert r.json()["mcq_passed"] is True
    gates = client.get(f"/api/lessons/{l1}/gates").json()
    assert gates["grammar"] is True and gates["logic"] is False
    assert client.get(f"/api/courses/{cid}/current-step").json()["stage"] == "simulate"

    # Decision simulation passes Logic; Rhetoric still blocks unlock.
    r = client.post(f"/api/lessons/{l1}/submit-simulation", json={
        "turn1_id": "t1", "turn2_id": "t2", "is_success": True})
    assert r.status_code == 200 and r.json()["lesson_completed"] is False
    assert client.get(f"/api/courses/{cid}/current-step").json()["stage"] == "teach_back"

    # Round 2 requires round 1 to have passed.
    assert client.post(f"/api/lessons/{l1}/socratic-duel", json={
        "round": 2, "answer": "rebuttal"}).status_code == 409

    async def _fake_round1(**kwargs):
        assert kwargs["student_answer"] == "thesis"
        return SocraticRound1Evaluation(
            passed_round1=True, feedback="Good thesis.",
            cognitive_knot="What if the input doubles?")

    async def _fake_round2(**kwargs):
        assert kwargs["student_answer_round1"] == "thesis"
        assert kwargs["cognitive_knot"] == "What if the input doubles?"
        return SocraticRound2Evaluation(passed=True, score=9, feedback="Solid rebuttal.")

    monkeypatch.setattr("app.main.GraderAgent.evaluate_socratic_round1", _fake_round1)
    monkeypatch.setattr("app.main.GraderAgent.evaluate_socratic_round2", _fake_round2)

    r1 = client.post(f"/api/lessons/{l1}/socratic-duel", json={
        "round": 1, "answer": "thesis"})
    assert r1.status_code == 200 and r1.json()["passed_round1"] is True
    assert r1.json()["socratic_passed"] is False and not r1.json()["lesson_completed"]

    r2 = client.post(f"/api/lessons/{l1}/socratic-duel", json={
        "round": 2, "answer": "rebuttal"})
    assert r2.status_code == 200 and r2.json()["passed"] is True
    assert r2.json()["lesson_completed"] is True

    # Exactly one next step is revealed; the one after it stays invisible.
    ns = client.get(f"/api/courses/{cid}/next-step").json()
    assert ns["current_step"]["id"] == l2
    assert [c["id"] for c in ns["completed_lessons"]] == [l1]
    _no_leak(ns, "next-step after unlock")

    # Past step remains reviewable; the newly revealed step is readable.
    past = client.get(f"/api/lessons/{l1}").json()
    assert past["title"] == "Public Current Alpha"
    assert client.get(f"/api/lessons/{l2}").status_code == 200
    assert client.get(f"/api/lessons/{l3}").status_code == 403

    stats = client.get("/api/profile/stats").json()
    assert stats["completed_lessons"] >= 1 and stats["xp"] >= 25


def test_discursive_grading_is_the_logic_gate_without_simulation(seeded, monkeypatch):
    """Logic can also be earned by discursive grading, never before Grammar."""
    client, (cid, l1, l2, l3), subject = seeded

    # Force the discursive variant: remove the decision simulation from the quiz.
    with Session(db.engine) as s:
        lesson = s.get(Lesson, l1)
        quiz = json.loads(lesson.quiz_json)
        quiz.pop("simulation", None)
        lesson.quiz_json = json.dumps(quiz)
        s.add(lesson)
        s.commit()

    def _submit(answer="my explanation"):
        return client.post(f"/api/lessons/{l1}/submit-discursive",
                           json={"lesson_id": l1, "answer": answer})

    # Early Logic attempt is blocked by the Grammar gate.
    assert _submit().status_code == 409

    _pass_quiz(client, l1)
    gates = client.get(f"/api/lessons/{l1}/gates").json()
    assert gates["grammar"] is True and gates["logic"] is False

    async def _fake_discursive(**kwargs):
        assert kwargs["student_answer"] == "my explanation"
        return SimpleNamespace(passed=True, score=9, feedback="Solid explanation.")

    monkeypatch.setattr("app.main.GraderAgent.evaluate_discursive", _fake_discursive)

    r = _submit()
    assert r.status_code == 200 and r.json()["passed"] is True
    gates = client.get(f"/api/lessons/{l1}/gates").json()
    assert gates["logic"] is True and gates["rhetoric"] is False
    assert gates["lesson_completed"] is False
    assert client.get(f"/api/courses/{cid}/current-step").json()["stage"] == "teach_back"
    # Teach-back still blocks unlock after Logic alone.
    assert client.get(f"/api/courses/{cid}/next-step").json()["current_step"]["id"] == l1
