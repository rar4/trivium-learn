"""Per-user mastery progress, spaced repetition and the post-hoc dashboard.

The shared ``Lesson`` row is the curriculum and keeps the legacy local
learner's state. Authenticated learners read and write their own
``LessonProgress`` row through :class:`UserLessonView`, which exposes exactly
the attribute names :mod:`app.services.progression` consumes. Nothing in this
module ever returns a future lesson, a curriculum total or a remaining count.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

from sqlmodel import Session, select

from app.models.entities import (
    Course, LearnerProfile, Lesson, LessonChatMessage, LessonProgress,
    Module, ReviewItem, User,
)
from app.services import progression as _progression
from app.services.auth import LOCAL_USERNAME

PROGRESS_FIELDS = frozenset({
    "status", "mcq_score", "blanks_score", "discursive_passed",
    "discursive_feedback", "simulation_passed", "socratic_passed",
    "socratic_state_json", "completed_at",
})


def is_local(user: User) -> bool:
    return getattr(user, "username", None) == LOCAL_USERNAME or getattr(user, "id", None) == 1


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _today() -> str:
    return date.today().isoformat()


class UserLessonView:
    """One learner's effective state for one lesson.

    Falls back to the global lesson only for the legacy local learner; every
    other account starts with the first lesson of a course revealed and all
    other lessons locked.
    """

    def __init__(self, lesson: Lesson, progress: Optional[LessonProgress],
                 local: bool, first: bool = False):
        self._lesson = lesson
        self._progress = progress
        self._local = local
        self._first = first
        # Immutable curriculum fields: identical for every learner.
        self.id = lesson.id
        self.module_id = lesson.module_id
        self.lesson_number = lesson.lesson_number
        self.title = lesson.title
        self.core_concept = lesson.core_concept
        self.summary_50_words = lesson.summary_50_words
        self.content_markdown = lesson.content_markdown
        self.quiz_json = lesson.quiz_json

    def _value(self, field: str, default: Any) -> Any:
        if self._progress is not None:
            return getattr(self._progress, field, default)
        if self._local:
            return getattr(self._lesson, field, default)
        return default

    @property
    def status(self) -> str:
        if self._progress is not None:
            return self._progress.status
        if self._local:
            return self._lesson.status
        return "in_progress" if self._first else "locked"

    @property
    def mcq_score(self) -> int:
        return self._value("mcq_score", 0)

    @property
    def blanks_score(self) -> int:
        return self._value("blanks_score", 0)

    @property
    def discursive_passed(self) -> bool:
        return bool(self._value("discursive_passed", False))

    @property
    def discursive_feedback(self) -> Optional[str]:
        return self._value("discursive_feedback", None)

    @property
    def simulation_passed(self) -> bool:
        return bool(self._value("simulation_passed", False))

    @property
    def socratic_passed(self) -> bool:
        return bool(self._value("socratic_passed", False))

    @property
    def socratic_state_json(self) -> Optional[str]:
        return self._value("socratic_state_json", None)

    @property
    def completed_at(self) -> Optional[datetime]:
        return self._value("completed_at", None)


def _progress_row(session: Session, user_id: int, lesson_id: int) -> Optional[LessonProgress]:
    return session.exec(
        select(LessonProgress).where(
            LessonProgress.user_id == user_id, LessonProgress.lesson_id == lesson_id
        )
    ).first()


def _first_lesson_ids(session: Session) -> set:
    """The entry lesson of every course (revealed for a brand-new account)."""
    first_ids: set = set()
    for course in session.exec(select(Course)).all():
        first: Optional[Lesson] = None
        modules = session.exec(
            select(Module).where(Module.course_id == course.id)
        ).all()
        for mod in modules:
            candidate = session.exec(
                select(Lesson).where(Lesson.module_id == mod.id).order_by(Lesson.lesson_number)
            ).first()
            if candidate is not None and (
                first is None or candidate.lesson_number < first.lesson_number
            ):
                first = candidate
        if first is not None and first.id is not None:
            first_ids.add(first.id)
    return first_ids


def view(session: Session, user: User, lesson: Optional[Lesson]) -> Optional[UserLessonView]:
    if lesson is None:
        return None
    local = is_local(user)
    # The legacy local learner's state stays in the global Lesson rows. Keeping
    # it there preserves existing installs, clients and tests that mutate those
    # rows directly; every other account is fully isolated in LessonProgress.
    progress = None if local else (
        _progress_row(session, user.id, lesson.id) if user.id is not None else None
    )
    first = False if local else lesson.id in _first_lesson_ids(session)
    return UserLessonView(lesson, progress, local, first)


def ordered(session: Session, course_id: int, user: User) -> List[Tuple[Module, UserLessonView]]:
    """(module, effective lesson) pairs in curriculum order for one learner."""
    out: List[Tuple[Module, UserLessonView]] = []
    modules = session.exec(
        select(Module).where(Module.course_id == course_id).order_by(Module.module_number)
    ).all()
    for mod in modules:
        lessons = session.exec(
            select(Lesson).where(Lesson.module_id == mod.id).order_by(Lesson.lesson_number)
        ).all()
        for lesson in lessons:
            out.append((mod, view(session, user, lesson)))  # type: ignore[arg-type]
    return out


def current(session: Session, course_id: int, user: User) -> Optional[UserLessonView]:
    """The single revealed step: first non-completed, non-locked lesson."""
    for _mod, lesson in ordered(session, course_id, user):
        if lesson.status not in ("completed", "locked"):
            return lesson
    return None


def completed_lessons(session: Session, course_id: int, user: User) -> List[UserLessonView]:
    return [lesson for _mod, lesson in ordered(session, course_id, user)
            if lesson.status == "completed"]


def apply(session: Session, user: User, lesson: Lesson, **updates: Any) -> LessonProgress:
    """Persist one learner's progress (and mirror legacy local state)."""
    row = _progress_row(session, user.id, lesson.id)
    if row is None:
        local = is_local(user)
        row = LessonProgress(
            user_id=user.id,
            lesson_id=lesson.id,
            status=lesson.status if local else (
                "in_progress" if lesson.id in _first_lesson_ids(session) else "locked"
            ),
            mcq_score=lesson.mcq_score if local else 0,
            blanks_score=lesson.blanks_score if local else 0,
            discursive_passed=bool(lesson.discursive_passed) if local else False,
            discursive_feedback=lesson.discursive_feedback if local else None,
            simulation_passed=bool(lesson.simulation_passed) if local else False,
            socratic_passed=bool(lesson.socratic_passed) if local else False,
            socratic_state_json=lesson.socratic_state_json if local else None,
        )
        session.add(row)
    for key, value in updates.items():
        if key in PROGRESS_FIELDS:
            setattr(row, key, value)
        if is_local(user) and hasattr(lesson, key):
            setattr(lesson, key, value)
    row.updated_at = _now()
    session.add(row)
    if is_local(user):
        session.add(lesson)
    return row


def unlock(session: Session, user: User, lesson: Lesson) -> bool:
    """Run the mastery gate for one learner; reveal exactly one next step."""
    effective = view(session, user, lesson)
    state = _progression.gate_state(effective)  # type: ignore[arg-type]
    if not (state["grammar"] and state["logic"] and state["rhetoric"]):
        return False
    if effective is not None and effective.status == "completed":  # type: ignore[union-attr]
        return True

    apply(session, user, lesson, status="completed", completed_at=_now())

    nxt = session.exec(
        select(Lesson).where(
            Lesson.module_id == lesson.module_id,
            Lesson.lesson_number == (lesson.lesson_number or 0) + 1,
        )
    ).first()
    if nxt is not None:
        if view(session, user, nxt).status == "locked":  # type: ignore[union-attr]
            apply(session, user, nxt, status="in_progress")
    else:
        cur_mod = session.get(Module, lesson.module_id)
        if cur_mod is not None:
            next_mod = session.exec(
                select(Module).where(
                    Module.course_id == cur_mod.course_id,
                    Module.module_number == (cur_mod.module_number or 0) + 1,
                )
            ).first()
            if next_mod is not None:
                first = session.exec(
                    select(Lesson).where(Lesson.module_id == next_mod.id, Lesson.lesson_number == 1)
                ).first()
                if first is not None and view(session, user, first).status == "locked":  # type: ignore[union-attr]
                    apply(session, user, first, status="in_progress")
            if is_local(user):
                cur_mod.is_completed = True
                session.add(cur_mod)
                if next_mod is not None:
                    next_mod.is_unlocked = True
                    session.add(next_mod)
    return True


def completed_count(session: Session, user: User) -> int:
    """Count only this learner's mastered lessons (post-hoc)."""
    return sum(
        1 for lesson in session.exec(select(Lesson)).all()
        if (v := view(session, user, lesson)) is not None and v.status == "completed"
    )


def profile_for(session: Session, user: User) -> LearnerProfile:
    row = session.exec(select(LearnerProfile).where(LearnerProfile.user_id == user.id)).first()
    if row is None and is_local(user) and user.id == 1:
        row = session.get(LearnerProfile, 1)
    if row is None:
        row = LearnerProfile(user_id=user.id, display_name=user.display_name)
        session.add(row)
        session.commit()
        session.refresh(row)
    return row


def touch_activity(session: Session, user: User) -> LearnerProfile:
    row = profile_for(session, user)
    today = _today()
    if row.last_active_date == today:
        return row
    yesterday = (date.today() - timedelta(days=1)).isoformat()
    row.streak_days = (row.streak_days or 0) + 1 if row.last_active_date == yesterday else 1
    row.last_active_date = today
    row.updated_at = _now()
    session.add(row)
    return row


def _owned_reviews(session: Session, user: User, *, due_only: bool = False) -> List[ReviewItem]:
    stmt = select(ReviewItem)
    if due_only:
        stmt = stmt.where(ReviewItem.due_on <= _today())
    rows = session.exec(stmt.order_by(ReviewItem.due_on)).all()
    return [
        r for r in rows
        if r.user_id == user.id or (r.user_id is None and is_local(user))
    ]


def due_reviews(session: Session, user: User) -> List[ReviewItem]:
    return _owned_reviews(session, user, due_only=True)


def all_reviews(session: Session, user: User) -> List[ReviewItem]:
    return _owned_reviews(session, user)


def record_misses(
    session: Session,
    user: User,
    lesson: Lesson,
    quiz: Dict[str, Any],
    mcq_correct: int,
    blanks_correct: int,
    correct_mcq_indices: Optional[set] = None,
    correct_blank_indices: Optional[set] = None,
) -> None:
    """Queue each missed MCQ / flashcard for spaced repetition."""
    tomorrow = (date.today() + timedelta(days=1)).isoformat()
    passed_mcq = correct_mcq_indices if correct_mcq_indices is not None else set(range(mcq_correct))
    passed_blanks = correct_blank_indices if correct_blank_indices is not None else set(range(blanks_correct))
    missed: List[Tuple[str, str, str, str]] = []
    for idx, question in enumerate(quiz.get("mcq") or []):
        if idx in passed_mcq:
            continue
        correct = next(
            (o for o in (question.get("options") or []) if o.get("is_correct")), {}
        )
        missed.append((
            f"mcq:{idx}", "mcq", str(question.get("question") or ""),
            str(correct.get("text") or correct.get("label") or ""),
        ))
    for idx, blank in enumerate(quiz.get("fill_in_the_blanks") or []):
        if idx in passed_blanks:
            continue
        missed.append((
            f"blank:{idx}", "blank", str(blank.get("sentence") or blank.get("question") or ""),
            str(blank.get("correct_word") or ""),
        ))
    if not missed:
        missed.append(("lesson:0", "lesson", lesson.title or "", lesson.core_concept or ""))

    for key, kind, prompt, expected in missed:
        row = session.exec(
            select(ReviewItem).where(
                ReviewItem.user_id == user.id,
                ReviewItem.lesson_id == lesson.id,
                ReviewItem.item_key == key,
            )
        ).first()
        if row is None:
            row = ReviewItem(
                user_id=user.id, lesson_id=lesson.id, item_key=key, kind=kind,
                prompt=prompt, expected=expected, interval_days=1, misses=0,
            )
        row.misses = (row.misses or 0) + 1
        row.interval_days = 1
        row.due_on = tomorrow
        session.add(row)


def complete_review(session: Session, user: User, item: ReviewItem, passed: bool = True) -> str:
    """SM-2-ish scheduling: pass doubles the gap, miss resets it to one day."""
    if passed:
        item.interval_days = max(1, (item.interval_days or 1) * 2)
        item.pass_count = (item.pass_count or 0) + 1
    else:
        item.interval_days = 1
        item.misses = (item.misses or 0) + 1
    item.last_reviewed_on = _today()
    item.due_on = (date.today() + timedelta(days=item.interval_days)).isoformat()
    session.add(item)
    row = profile_for(session, user)
    row.reviews_completed = (row.reviews_completed or 0) + 1
    row.updated_at = _now()
    session.add(row)
    return item.due_on


def mastery_dashboard(session: Session, user: User) -> Dict[str, Any]:
    """Post-hoc mastery view: only mastered past work and reviewable items.

    Deliberately contains no totals, percentages, ordinals, future titles or
    remaining-work counts. Every item listed has already been completed.
    """
    skills: Dict[str, List[Dict[str, Any]]] = {}
    for lesson in session.exec(select(Lesson)).all():
        effective = view(session, user, lesson)
        if effective is None or effective.status != "completed":
            continue
        mod = session.get(Module, lesson.module_id)
        course = session.get(Course, mod.course_id) if mod else None
        category = _catalog_category(course.subject) if course else "general"
        completed_on = effective.completed_at
        if completed_on is None:
            stored = _progress_row(session, user.id, lesson.id)
            completed_on = stored.completed_at if stored is not None else None
        skills.setdefault(category, []).append({
            "id": lesson.id,
            "title": lesson.title,
            "core_concept": lesson.core_concept,
            "course": course.subject if course else None,
            "completed_on": completed_on.date().isoformat()
            if completed_on and hasattr(completed_on, "date") else None,
        })

    reviews = [{
        "id": item.id,
        "lesson_id": item.lesson_id,
        "item_key": item.item_key,
        "kind": item.kind,
        "prompt": item.prompt,
        "expected": item.expected,
        "due_on": item.due_on,
        "interval_days": item.interval_days,
        "misses": item.misses,
    } for item in due_reviews(session, user)]

    profile = profile_for(session, user)
    xp = _catalog_xp(completed_count(session, user), profile.reviews_completed or 0)
    payload = {
        "display_name": profile.display_name,
        "xp": xp,
        "level": _catalog_level(xp),
        "reviewable_items": reviews,
        "mastered_by_skill": [
            {"category": category, "mastered_items": items}
            for category, items in sorted(skills.items())
        ],
    }
    return _progression.strip_counts(payload, True)


def _catalog_category(subject: str) -> str:
    from app.services import catalog
    return catalog.classify_category(subject)


def _catalog_xp(completed: int, reviews: int) -> int:
    from app.services import catalog
    return catalog.xp_for_completed(completed, reviews)


def _catalog_level(xp: int) -> int:
    from app.services import catalog
    return catalog.level_for_xp(xp)
