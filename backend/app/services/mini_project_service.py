"""Rhetoric 'Express' output: the build/present mini-project.

The Socratic teach-back duel proves the learner can defend an idea under an
edge-case attack. This service adds the second half of Rhetoric: turning that
understanding into a small, concrete artifact (a write-up, recipe, checklist
or tiny snippet) and giving formative feedback on it.

No schema change is needed: the artifact is stored inside the lesson's
``socratic_state_json`` under ``mini_project``, so it inherits the existing
per-user isolation. Grading uses the LLM when available and falls back to a
deterministic heuristic so the loop works offline (and in tests).
"""
from __future__ import annotations

import re
from typing import Any, Dict, List

from pydantic import BaseModel, Field

from app.services.llm_gateway import LLMGateway


class MiniProjectEvaluation(BaseModel):
    passed: bool = False
    score: int = Field(default=5, ge=0, le=10)
    feedback: str = ""


def _is_en(language: str) -> bool:
    return (language or "pt-BR").lower().startswith("en")


def build_brief(lesson: Any, course: Any, language: str) -> Dict[str, Any]:
    """Deterministic, lesson-scoped brief (no network, no future content)."""
    core = (getattr(lesson, "core_concept", "") or "").strip()
    title = (getattr(lesson, "title", "") or "").strip()
    if _is_en(language):
        return {
            "title": "Build & Present",
            "lesson_title": title,
            "prompt": (
                f"Turn what you mastered about {core or 'this lesson'} into a small, "
                "usable artifact: a 4-6 sentence write-up, a short checklist, a recipe, "
                "or a tiny code snippet. State the situation, the decision you would "
                "make, and the trade-off you accept."
            ),
            "checklist": [
                "Uses the lesson's core idea in your own words",
                "Shows one concrete, real-world example",
                "Names a trade-off, limitation or failure mode",
            ],
            "deliverable_hint": "Aim for at least 30 words. Plain language beats jargon.",
        }
    return {
        "title": "Construa e Apresente",
        "lesson_title": title,
        "prompt": (
            f"Transforme o que você dominou sobre {core or 'esta aula'} em um artefato "
            "pequeno e útil: um texto de 4 a 6 frases, um checklist, um passo a passo ou "
            "um trecho de código. Apresente a situação, a decisão que você tomaria e o "
            "trade-off que aceita."
        ),
        "checklist": [
            "Usa a ideia central da aula com as suas próprias palavras",
            "Mostra um exemplo concreto do cotidiano",
            "Aponta um trade-off, limite ou modo de falha",
        ],
        "deliverable_hint": "Escreva pelo menos 30 palavras. Linguagem simples vale mais que jargão.",
    }


def _keywords(text: str) -> List[str]:
    stop = {
        "the", "and", "for", "with", "that", "this", "from", "your", "you", "are",
        "but", "not", "has", "have", "uma", "um", "que", "com", "para", "por", "mais",
        "como", "sua", "seu", "the", "de", "da", "do", "em", "e", "a", "o",
    }
    return [w for w in re.findall(r"[a-zA-ZÀ-ÿ]{4,}", text.lower()) if w not in stop]


async def grade(
    submission: str,
    brief: Dict[str, Any],
    core_concept: str,
    language: str,
) -> Dict[str, Any]:
    """Formative grading with an offline-deterministic fallback."""
    is_en = _is_en(language)
    clean = (submission or "").strip()
    words = re.findall(r"\b[\wÀ-ÿ]+\b", clean)
    threshold = 30 if is_en else 25

    # Try the LLM first; any failure (offline install, missing key, bad JSON)
    # degrades gracefully to the rubric heuristic below.
    try:
        system_prompt = (
            "You are the Trivium Rhetoric mentor. Grade ONE learner's mini-project "
            "against the lesson brief. Be generous and formative: reward a concrete "
            "artifact in the learner's own words, a real example and an honest "
            "trade-off. Never mention content outside this lesson. Reply with JSON "
            "only: passed (bool), score (0-10 int), feedback (string, 2 sentences)."
            if is_en else
            "Você é o mentor de Retórica da Trivium. Avalie o mini-projeto do aluno "
            "contra o briefing da aula. Seja generoso e formativo: valorize um artefato "
            "concreto, nas palavras do aluno, com exemplo real e trade-off honesto. "
            "Nunca cite conteúdo fora desta aula. Responda só em JSON: passed (bool), "
            "score (int 0-10), feedback (string, 2 frases)."
        )
        user_prompt = (
            f"Lesson core concept: {core_concept}\n"
            f"Brief: {brief.get('prompt', '')}\n"
            f"Checklist: {'; '.join(brief.get('checklist') or [])}\n"
            f"Learner artifact:\n{clean}"
        )
        result = await LLMGateway.generate_structured(
            system_prompt, user_prompt, MiniProjectEvaluation, max_tokens=300, timeout=25
        )
        if result is not None and (result.feedback or "").strip():
            return {
                "passed": bool(result.passed),
                "score": int(result.score),
                "feedback": (result.feedback or "").strip(),
            }
    except Exception:
        pass

    core_words = set(_keywords(core_concept))
    body_words = set(_keywords(clean))
    on_topic = bool(core_words & body_words) or len(words) >= threshold * 2
    structured = bool(re.search(
        r"\b(because|trade-?off|example|for instance|however|limitation|failure)\b"
        r"|\b(porque|trade-?off|exemplo|contudo|limitação|limitacao|falha)\b"
        r"|[•\-\n]\s", clean, re.IGNORECASE,
    ))
    enough = len(words) >= threshold
    passed = enough and on_topic and structured
    score = 10 if passed and len(words) >= threshold * 1.5 else (8 if passed else (5 if enough else 3))
    if is_en:
        feedback = (
            "Your artifact turns the lesson's core idea into something usable and names "
            "a real trade-off. This is Rhetoric: you can now express and defend the concept."
            if passed else
            "Good start. To pass, write a fuller artifact (at least 30 words) in your own "
            "words, include one concrete example from the lesson, and name the trade-off "
            "or failure mode you accept."
        )
    else:
        feedback = (
            "Seu artefato transforma a ideia central da aula em algo utilizável e aponta "
            "um trade-off real. Isso é Retórica: você já consegue expressar e defender o conceito."
            if passed else
            "Bom começo. Para aprovar, escreva um artefato mais completo (pelo menos 30 "
            "palavras), com um exemplo concreto da aula e o trade-off ou modo de falha que você aceita."
        )
    return {"passed": passed, "score": score, "feedback": feedback}


class MiniProjectService:
    """Stable class API used by the routes (kept separate from the engine)."""

    build_brief = staticmethod(build_brief)
    grade = staticmethod(grade)
