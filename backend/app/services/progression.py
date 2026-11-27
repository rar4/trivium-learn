"""Fog-of-War response shaping and the Trivium mastery gate state machine.

The database keeps the *whole* curriculum. This module is the single place
that decides what may cross the API boundary and when a step may unlock.

Design contract
---------------
* ``strip_counts`` removes every field that reveals how much content exists
  (totals, percentages, ordinals). It is applied by default to all list and
  catalog endpoints via the ``suppress_counts`` query flag.
* ``gate_state`` is the single source of truth for the Learn -> Quiz ->
  Simulate -> Teach-back -> Unlock chain (Grammar / Logic / Rhetoric).
* ``current_step_payload`` exposes exactly one step: title, hook, content and
  gates. Past steps are reviewable through the lesson endpoint; future steps
  are never part of any payload built here.
"""
from __future__ import annotations

import json
import math
from typing import Any, Dict, List, Optional

GATE_STAGES = ("learn", "quiz", "simulate", "teach_back", "unlock")

# Fields that disclose the size of the curriculum or a step's position in it.
# "Lesson X of Y" leaks either the ordinal or the total, so both are removed.
_COUNT_KEYS = frozenset({
    "total_modules", "total_lessons", "total_items", "total", "total_count",
    "count", "lesson_count", "module_count", "lessons_total", "modules_total",
    "remaining", "remaining_lessons", "remaining_modules",
    "progress_percent", "percent_complete", "percent", "progress",
    "lesson_number", "module_number", "completed_count",
})


def strip_counts(payload: Any, enabled: bool = True) -> Any:
    """Recursively drop count/ordinal/percent fields from an API payload.

    ``completed_lessons`` is intentionally kept when it is a *list* of already
    mastered steps (Fog-of-War allows reviewing the past); it is dropped when
    it is a numeric count.
    """
    if not enabled:
        return payload
    if isinstance(payload, dict):
        cleaned: Dict[str, Any] = {}
        for key, value in payload.items():
            if key in _COUNT_KEYS:
                continue
            if key == "completed_lessons" and isinstance(value, (int, float)) and not isinstance(value, bool):
                continue
            cleaned[key] = strip_counts(value, True)
        return cleaned
    if isinstance(payload, list):
        return [strip_counts(item, True) for item in payload]
    return payload


def quiz_data(lesson: Any) -> Dict[str, Any]:
    try:
        data = json.loads(lesson.quiz_json) if lesson.quiz_json else {}
    except (TypeError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def socratic_data(lesson: Any) -> Dict[str, Any]:
    try:
        data = json.loads(lesson.socratic_state_json) if lesson.socratic_state_json else {}
    except (TypeError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def mcq_target(quiz: Dict[str, Any]) -> int:
    total = len(quiz.get("mcq") or [])
    return 2 if total <= 3 else 3


def flashcard_target(quiz: Dict[str, Any]) -> int:
    """Need at least half of the fill-in-the-blank / flashcard items."""
    blanks = quiz.get("fill_in_the_blanks") or []
    return max(1, math.ceil(len(blanks) / 2)) if blanks else 0


def grammar_passed(lesson: Any) -> bool:
    quiz = quiz_data(lesson)
    return ((lesson.mcq_score or 0) >= mcq_target(quiz)
            and (lesson.blanks_score or 0) >= flashcard_target(quiz))


def gate_state(lesson: Any) -> Dict[str, Any]:
    """Compute gate booleans, current stage and the ordered stage ladder.

    Grammar = MCQ mastery + flashcard retrieval.
    Logic   = decision simulation (preferred) or discursive grading.
    Rhetoric = the two-round Socratic teach-back duel (legacy: discursive).
    """
    quiz = quiz_data(lesson)
    has_sim = bool(quiz.get("simulation"))
    has_disc = bool(quiz.get("discursive"))
    has_soc = bool(quiz.get("socratic_duel"))

    grammar = grammar_passed(lesson)
    logic = bool(lesson.simulation_passed) if has_sim else bool(lesson.discursive_passed)
    rhetoric = bool(lesson.socratic_passed) if has_soc else bool(lesson.discursive_passed)

    completed = lesson.status == "completed"
    if completed:
        stage = "unlock"
    elif not grammar:
        stage = "quiz"
    elif not logic:
        stage = "simulate"
    elif not rhetoric:
        stage = "teach_back"
    else:
        stage = "unlock"

    soc_state = socratic_data(lesson)
    stages: List[Dict[str, Any]] = [
        {"id": "learn", "passed": True, "available": True},
        {"id": "quiz", "passed": grammar, "available": True},
        {"id": "simulate", "passed": logic, "available": grammar},
        {"id": "teach_back", "passed": rhetoric, "available": grammar and logic},
        {"id": "unlock", "passed": completed, "available": grammar and logic and rhetoric},
    ]
    return {
        "lesson_id": lesson.id,
        "grammar": bool(grammar),
        "logic": bool(logic),
        "rhetoric": bool(rhetoric),
        "lesson_completed": completed,
        "current_stage": stage,
        "stages": stages,
        # Compatibility booleans kept from the original gate endpoint.
        "has_simulation": has_sim,
        "has_discursive": has_disc,
        "has_socratic_duel": has_soc,
        "mcq": {"score": lesson.mcq_score or 0, "target": mcq_target(quiz)},
        "flashcards": {"score": lesson.blanks_score or 0, "target": flashcard_target(quiz)},
        "socratic_round": int(soc_state.get("current_round") or 0),
    }


def can_attempt(state: Dict[str, Any], stage: str) -> bool:
    """Enforce stage order: a later gate cannot be attempted early."""
    if stage in ("learn", "quiz"):
        return True
    if stage == "simulate":
        return bool(state["grammar"])
    if stage == "teach_back":
        return bool(state["grammar"] and state["logic"])
    if stage == "unlock":
        return bool(state["grammar"] and state["logic"] and state["rhetoric"])
    return False


def stage_error(stage: str) -> str:
    return {
        "simulate": "Complete the Grammar gate (Quiz + flashcards) before the Logic gate.",
        "teach_back": "Complete the Logic gate (simulation / discursive) before the teach-back duel.",
        "unlock": "Complete every gate before unlocking the next step.",
    }.get(stage, "This stage is not available yet.")


def current_step_payload(lesson: Optional[Any]) -> Dict[str, Any]:
    """Exactly one revealed step: id, stage, title, hook, content and gates."""
    if lesson is None:
        return {
            "id": None, "stage": "unlock", "title": None,
            "hook": None, "content": None, "gates": None,
        }
    gates = gate_state(lesson)
    return {
        "id": lesson.id,
        "stage": gates["current_stage"],
        "title": lesson.title,
        # The 50-word synopsis is the Netflix-style dramatic hook; fall back
        # to the curated core concept when the writer did not supply one.
        "hook": lesson.summary_50_words or lesson.core_concept,
        "content": lesson.content_markdown,
        "gates": gates,
    }


def catalog_card(course: Any, category: str) -> Dict[str, Any]:
    """Discovery card: category / difficulty / topic, never counts."""
    return {
        "id": course.id,
        "topic": course.subject,
        "category": category,
        "difficulty": course.level,
        # Legacy aliases kept so the existing catalog UI keeps working.
        "subject": course.subject,
        "level": course.level,
        "language": getattr(course, "language", "pt-BR") or "pt-BR",
        "cover_image_url": course.cover_image_url,
        "source_type": getattr(course, "source_type", "web") or "web",
    }
