"""End-to-end Trivium loop: Learn -> Quiz -> Simulate -> Teach-back -> Express -> Unlock.

Drives the real FastAPI app against an isolated DB. LLM graders are stubbed so
the state machine is exercised deterministically (the mini-project grader's
offline heuristic is deliberately left in place).
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
os.environ.setdefault("DATABASE_URL", f"sqlite:///{tempfile.mkdtemp()}/loop.db")

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
from app.schemas.quiz import (  # noqa: E402
    SocraticRound1Evaluation, SocraticRound2Evaluation,
)
from app.services.tutor_service import TutorService  # noqa: E402

SECRETS = ("SECRET-NEXT-TITLE", "SECRET-NEXT-CONCEPT", "SECRET-NEXT-CONTENT")
FUTURE = ("SECRET-LATER-TITLE", "SECRET-LATER-CONCEPT", "SECRET-LATER-CONTENT")


@pytest.fixture(scope="module", autouse=True)
def isolated_db():
    original = db.engine
    path = Path(tempfile.mkdtemp(prefix="trivium-loop-")) / "test.db"
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
        ],
        "fill_in_the_blanks": [{"correct_word": "alpha"}, {"correct_word": "beta"}],
        "simulation": {
            "context": "An operational choice", "initial_indicators": [],
            "turn1_prompt": "Pick a path", "turn1_options": [{
                "id": "t1", "reaction_story": "It worked", "updated_indicators": [],
                "turn2_prompt": "Now what?", "turn2_options": [{
                    "id": "t2", "is_success": True, "verdict_summary": "Good trade-off"}],
            }],
        },
        "socratic_duel": {"question": "Defend it.", "evaluation_rubric": ["uses the core idea"]},
    })


@pytest.fixture
def seeded():
    init_db()
    tag = uuid.uuid4().hex[:8]
    with Session(db.engine) as s:
        course = Course(subject=f"Loop Lab {tag}", level="Básico", language="en-US")
        s.add(course); s.commit(); s.refresh(course)
        mod = Module(course_id=course.id, module_number=1, title="Opening", is_unlocked=True)
        s.add(mod); s.commit(); s.refresh(mod)
        first = Lesson(module_id=mod.id, lesson_number=1, title="Public Current Step",
                       core_concept="compound interest",
                       summary_50_words="PUBLIC HOOK",
                       content_markdown="PUBLIC LESSON about compound interest.",
                       status="in_progress", quiz_json=_quiz())
        second = Lesson(module_id=mod.id, lesson_number=2, title="SECRET-NEXT-TITLE",
                        core_concept="SECRET-NEXT-CONCEPT", status="locked",
                        content_markdown="SECRET-NEXT-CONTENT", quiz_json=_quiz())
        third = Lesson(module_id=mod.id, lesson_number=3, title="SECRET-LATER-TITLE",
                       core_concept="SECRET-LATER-CONCEPT", status="locked",
                       content_markdown="SECRET-LATER-CONTENT", quiz_json=_quiz())
        s.add(first); s.add(second); s.add(third); s.commit()
        s.refresh(first); s.refresh(second); s.refresh(third)
        ids = (course.id, mod.id, first.id, second.id, third.id)
    client = TestClient(app)
    yield client, ids
    with Session(db.engine) as s:
        lids = list(ids[2:])
        s.exec(delete(LessonChatMessage).where(LessonChatMessage.lesson_id.in_(lids)))
        s.exec(delete(ReviewItem).where(ReviewItem.lesson_id.in_(lids)))
        for lid in lids:
            lesson = s.get(Lesson, lid)
            if lesson:
                s.delete(lesson)
        mod = s.get(Module, ids[1])
        if mod:
            s.delete(mod)
        course = s.get(Course, ids[0])
        if course:
            s.delete(course)
        profile = s.get(LearnerProfile, 1)
        if profile:
            profile.streak_days = 0; profile.reviews_completed = 0; profile.last_active_date = None
            s.add(profile)
        s.commit()


def test_full_loop_learn_quiz_simulate_teachback_express_unlock(seeded, monkeypatch):
    client, (cid, mid, l1, l2, l3) = seeded

    # 1. LEARN: only the current step is visible, with its hook and gates.
    step = client.get(f"/api/courses/{cid}/current-step")
    assert step.status_code == 200
    assert step.json()["id"] == l1 and step.json()["stage"] == "quiz"

    # 2. QUIZ: Grammar gate needs MCQ + retrieval practice.
    early = client.post(f"/api/lessons/{l1}/submit-simulation",
                        json={"turn1_id": "t1", "turn2_id": "t2", "is_success": True})
    assert early.status_code == 409
    q = client.post(f"/api/lessons/{l1}/submit-quiz", json={
        "lesson_id": l1, "answers": {"0": "B", "1": "B"},
        "blanks": {"0": "alpha", "1": "beta"},
    })
    assert q.status_code == 200 and q.json()["mcq_passed"] is True
    assert client.get(f"/api/lessons/{l1}/gates").json()["grammar"] is True

    # 3. SIMULATE: Logic gate tracks live decisions and second-order outcomes.
    sim = client.post(f"/api/lessons/{l1}/submit-simulation",
                      json={"turn1_id": "t1", "turn2_id": "t2", "is_success": True})
    assert sim.status_code == 200 and sim.json()["lesson_completed"] is False
    assert client.get(f"/api/courses/{cid}/current-step").json()["stage"] == "teach_back"

    # Express artifact is not reachable before the teach-back duel.
    assert client.post(f"/api/lessons/{l1}/mini-project",
                       json={"submission": "too early to submit"}).status_code == 409

    # 4. TEACH-BACK: two-round Socratic duel with an edge-case attack.
    async def r1(**kwargs):
        return SocraticRound1Evaluation(passed_round1=True, feedback="Good thesis.",
                                        cognitive_knot="What if the rate halves?")
    async def r2(**kwargs):
        return SocraticRound2Evaluation(passed=True, score=9, feedback="Solid rebuttal.")
    monkeypatch.setattr("app.main.GraderAgent.evaluate_socratic_round1", r1)
    monkeypatch.setattr("app.main.GraderAgent.evaluate_socratic_round2", r2)

    d1 = client.post(f"/api/lessons/{l1}/socratic-duel",
                     json={"round": 1, "answer": "compound interest grows capital"})
    assert d1.status_code == 200 and d1.json()["passed_round1"] is True
    d2 = client.post(f"/api/lessons/{l1}/socratic-duel",
                     json={"round": 2, "answer": "I would extend the horizon and reduce risk"})
    assert d2.status_code == 200 and d2.json()["lesson_completed"] is True

    # 5. EXPRESS: lesson-scoped brief, artifact graded, state persisted.
    brief = client.get(f"/api/lessons/{l1}/mini-project").json()
    assert brief["available"] is True and "compound interest" in brief["brief"]["prompt"]
    artifact = (
        "In a savings plan I would start early because compound interest rewards time. "
        "For example, ten years of contributions beats starting five years late. "
        "The trade-off is that I lock money away and lose liquidity for emergencies."
    )
    mp = client.post(f"/api/lessons/{l1}/mini-project", json={"submission": artifact})
    assert mp.status_code == 200 and mp.json()["passed"] is True
    assert mp.json()["score"] >= 8
    saved = client.get(f"/api/lessons/{l1}").json()["mini_project"]
    assert saved["submission"] == artifact and saved["passed"] is True

    # 6. EXPORT: notes booklet + PDF booklet both work and carry the work.
    notes = client.get(f"/api/lessons/{l1}/export-notes")
    assert notes.status_code == 200 and "text/markdown" in notes.headers["content-type"]
    assert "compound interest grows capital" in notes.text
    assert artifact in notes.text
    assert not any(secret in notes.text for secret in SECRETS)
    report = client.get("/api/dashboard/mastery/report")
    assert report.status_code == 200 and "text/markdown" in report.headers["content-type"]
    assert "Public Current Step" in report.text  # earned work only
    assert not any(s in report.text for s in SECRETS + FUTURE)  # no unrevealed/future work
    pdf = client.get(f"/api/lessons/{l1}/download-pdf")
    assert pdf.status_code == 200 and pdf.content.startswith(b"%PDF")

    # 7. UNLOCK: exactly one next step revealed, future still invisible.
    nxt = client.get(f"/api/courses/{cid}/next-step").json()
    assert nxt["current_step"]["id"] == l2
    assert [c["id"] for c in nxt["completed_lessons"]] == [l1]
    revealed = client.get(f"/api/courses/{cid}/current-step").json()
    assert set(revealed) == {"id", "stage", "title", "hook", "content", "gates"}
    assert revealed["id"] == l2 and revealed["title"] == "SECRET-NEXT-TITLE"
    assert revealed["hook"] == "SECRET-NEXT-CONCEPT"
    assert client.get(f"/api/lessons/{l2}").status_code == 200
    assert client.get(f"/api/lessons/{l2}/mini-project").status_code == 200
    # The step AFTER the newly revealed one stays completely blind.
    assert client.get(f"/api/lessons/{l3}").status_code == 403
    for url in (f"/api/courses/{cid}", f"/api/courses/{cid}/next-step", "/api/catalog"):
        blob = json.dumps(client.get(url).json(), ensure_ascii=False)
        assert not any(s in blob for s in SECRETS + FUTURE), url
    assert not any(s in json.dumps(revealed) for s in FUTURE)

    # Tutor stays scoped: its system prompt carries only this lesson's content.
    with Session(db.engine) as s:
        lesson = s.get(Lesson, l1)
        other = s.get(Lesson, l2)
        course = s.get(Course, cid)
    prompt = TutorService.build_system_prompt(
        course, lesson, TutorService.clean_lesson_for_context(lesson.content_markdown))
    assert "compound interest" in prompt
    assert "SECRET-NEXT-CONCEPT" not in prompt and "SECRET-NEXT-CONTENT" not in prompt
    assert "STRICT LESSON SCOPE" in prompt or "ESCOPO RESTRITO" in prompt
    # No cross-lesson chat history: a different lesson's messages are invisible.
    with Session(db.engine) as s:
        s.add(LessonChatMessage(lesson_id=other.id, user_id=1, role="user",
                                content="SECRET-NEXT-QUESTION"))
        s.commit()
    history = client.get(f"/api/lessons/{l1}/chat").json()
    assert all("SECRET-NEXT-QUESTION" not in m["content"] for m in history)
