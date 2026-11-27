"""Catalog categories, XP and gamification rules for the Learn-Anything layer.

Design contract (Fog-of-War):
- The catalog is *discovery*: category / difficulty / topic only.
- Nothing in this module ever exposes a course's total lesson/module count,
  a percentage towards a total, or any future lesson/module title.
- XP, streaks, badges and levels are computed exclusively from work the
  learner has already completed (lessons with status == "completed").
"""
from __future__ import annotations

import math
import unicodedata
from typing import Any, Dict, List

XP_PER_COMPLETED_LESSON = 25
XP_PER_REVIEW_COMPLETED = 10

CATEGORIES: List[Dict[str, Any]] = [
    {"id": "code", "label_en": "Code", "label_pt": "Código",
     "keywords": ["python", "javascript", "typescript", "code", "coding", "program", "software",
                  "web", "api", "database", "sql", "git", "linux", "devops", "ai agent", "machine learning",
                  "data science", "engenharia de software", "programacao", "programação", "código", "codigo"]},
    {"id": "music", "label_en": "Music", "label_pt": "Música",
     "keywords": ["music", "musica", "música", "piano", "guitar", "viola", "sing", "canto", "harmony",
                  "harmonia", "melody", "melodia", "song", "rhythm", "ritmo", "beat", "production", "mixing"]},
    {"id": "money", "label_en": "Money", "label_pt": "Dinheiro",
     "keywords": ["money", "dinheiro", "invest", "investimento", "trading", "stock", "bolsa", "finance",
                  "financa", "finanças", "crypto", "bitcoin", "eth", "bank", "banco", "tax", "imposto",
                  "budget", "orcamento", "orçamento", "risk", "risco"]},
    {"id": "business", "label_en": "Business", "label_pt": "Negócios",
     "keywords": ["business", "negocio", "negócio", "startup", "marketing", "sales", "vendas", "management",
                  "gestao", "gestão", "leadership", "lideranca", "liderança", "entrepreneur", "empreendedor",
                  "product", "produto", "brand", "marca"]},
    {"id": "mind", "label_en": "Mind & Logic", "label_pt": "Mente & Lógica",
     "keywords": ["logic", "logica", "lógica", "philosophy", "filosofia", "psychology", "psicologia",
                  "mental", "mente", "thinking", "pensamento", "decision", "decisao", "decisão",
                  "neuroscience", "neurociencia", "neurociência", "cognitive", "cognitivo", "critical thinking"]},
    {"id": "design", "label_en": "Design", "label_pt": "Design",
     "keywords": ["design", "typography", "tipografia", "editorial", "ux", "ui", "figma", "graphic",
                  "grafico", "gráfico", "visual", "color", "cor", "architecture", "arquitetura",
                  "interior", "fashion", "moda", "drawing", "desenho", "illustration", "ilustracao", "ilustração"]},
    {"id": "language", "label_en": "Language", "label_pt": "Idiomas",
     "keywords": ["english", "ingles", "inglês", "portuguese", "portugues", "português", "spanish",
                  "espanhol", "french", "frances", "francês", "german", "alemao", "alemão", "language",
                  "lingua", "língua", "grammar", "gramatica", "gramática", "vocabulary", "vocabulario",
                  "vocabulário", "rhyme", "rimar", "poetry", "poesia"]},
    {"id": "craft", "label_en": "Craft", "label_pt": "Artesanato",
     "keywords": ["craft", "artesanato", "wood", "madeira", "carpentry", "marcenaria", "sewing", "costura",
                  "knitting", "crochet", "tricot", "cooking", "culinaria", "culinária", "baking", "padaria",
                  "pottery", "ceramica", "cerâmica", "photography", "fotografia", "gardening", "jardinagem"]},
    {"id": "science", "label_en": "Science", "label_pt": "Ciência",
     "keywords": ["science", "ciencia", "ciência", "biology", "biologia", "chemistry", "quimica", "química",
                  "physics", "fisica", "física", "math", "matematica", "matemática", "astronomy", "astronomia",
                  "medicine", "medicina", "health", "saude", "saúde", "history", "historia", "história",
                  "geography", "geografia", "civil engineering", "engenharia civil", "molecular"]},
    {"id": "life", "label_en": "Life & Productivity", "label_pt": "Vida & Produtividade",
     "keywords": ["productivity", "produtividade", "habit", "habito", "hábito", "focus", "foco",
                  "time", "tempo", "learning", "aprendizagem", "memory", "memoria", "memória",
                  "note", "anotacao", "anotação", "writing", "escrita", "communication", "comunicacao", "comunicação"]},
]


def _norm(text: str) -> str:
    text = unicodedata.normalize("NFKD", (text or "").lower())
    return "".join(c for c in text if not unicodedata.combining(c))


def classify_category(subject: str) -> str:
    """Deterministic keyword classifier. Falls back to 'science'."""
    hay = _norm(subject)
    best_id, best_score = "science", 0
    for cat in CATEGORIES:
        score = sum(1 for kw in cat["keywords"] if _norm(kw) in hay)
        if score > best_score:
            best_id, best_score = cat["id"], score
    return best_id


def category_label(category_id: str, language: str = "en-US") -> str:
    for cat in CATEGORIES:
        if cat["id"] == category_id:
            return cat["label_pt"] if language.lower().startswith("pt") else cat["label_en"]
    return category_id


def level_for_xp(xp: int) -> int:
    """Level ring: 1 at 0 XP, +1 every ~50 XP band (sqrt curve, never decreases)."""
    return 1 + int(math.sqrt(max(0, xp) / 50.0))


def xp_for_completed(completed_lessons: int, reviews_completed: int = 0) -> int:
    return completed_lessons * XP_PER_COMPLETED_LESSON + reviews_completed * XP_PER_REVIEW_COMPLETED


def badges_for(completed_lessons: int, streak_days: int) -> List[str]:
    badges: List[str] = []
    if completed_lessons >= 1:
        badges.append("first-step")
    if completed_lessons >= 5:
        badges.append("scholar")
    if completed_lessons >= 10:
        badges.append("master")
    if streak_days >= 3:
        badges.append("on-fire")
    if streak_days >= 7:
        badges.append("unstoppable")
    return badges


# ---------------------------------------------------------------------------
# AI generation tiers (Basic / Working / Mastery)
# ---------------------------------------------------------------------------
# Canonical levels are the keys used by CourseOrchestrator.LEVEL_SPECS.
TIERS: List[Dict[str, Any]] = [
    {"id": "basic",   "label_en": "Basic",   "label_pt": "Básico",     "level_en": "Foundational", "level_pt": "Básico",        "modules": 4,  "lessons_per_module": 3, "words": 650},
    {"id": "working", "label_en": "Working", "label_pt": "Prático",    "level_en": "Intermediate", "level_pt": "Intermediário", "modules": 8,  "lessons_per_module": 4, "words": 850},
    {"id": "mastery", "label_en": "Mastery", "label_pt": "Maestria",   "level_en": "Advanced",     "level_pt": "Avançado",      "modules": 12, "lessons_per_module": 5, "words": 1100},
]


def tiers_payload() -> List[Dict[str, Any]]:
    """Public tier metadata (no internal level strings, just what the UI needs)."""
    return [
        {"id": t["id"], "label_en": t["label_en"], "label_pt": t["label_pt"],
         "modules": t["modules"], "lessons_per_module": t["lessons_per_module"],
         "total_lessons": t["modules"] * t["lessons_per_module"]}
        for t in TIERS
    ]


def resolve_level(value: str, language: str = "pt-BR") -> str:
    """Map a tier id or any level alias to the canonical orchestrator level.

    This is the single source of truth that makes Basic=4x3, Working=8x4 and
    Mastery=12x5 work regardless of the language or spelling the client sends.
    """
    norm = _norm(value or "")
    is_en = language.lower().startswith("en")
    if norm in {"basic", "basico", "foundational", "fundamental", "básico"}:
        return "Foundational" if is_en else "Básico"
    if norm in {"working", "intermediate", "intermediario", "intermediário", "médio", "medio"}:
        return "Intermediate" if is_en else "Intermediário"
    if norm in {"mastery", "advanced", "avancado", "avançado", "expert"}:
        return "Advanced" if is_en else "Avançado"
    if norm == "test":
        return "Test" if is_en else "Teste"
    return value


def tier_for_level(level: str) -> Dict[str, Any]:
    """Which generation tier produced a course at this canonical level."""
    for t in TIERS:
        if level in (t["level_pt"], t["level_en"]):
            return t
    return TIERS[0]


def level_matches_difficulty(level: str, difficulty: str) -> bool:
    """Catalog difficulty filter accepts tier ids and localized level names."""
    norm_diff = _norm(difficulty)
    if not norm_diff or norm_diff == "all":
        return True
    level_norm = _norm(level)
    for t in TIERS:
        aliases = {t["id"], _norm(t["label_en"]), _norm(t["label_pt"]),
                   _norm(t["level_en"]), _norm(t["level_pt"])}
        if norm_diff in aliases:
            return level_norm in aliases
    return norm_diff in level_norm


def document_citations(chapter_chunks: List[Dict[str, Any]], book_filename: str) -> List[Dict[str, Any]]:
    """Turn uploaded-material chapters into traceable course citations.

    Each entry points back to a chapter and page range of the learner's own
    PDF/EPUB, so the source panel can show *where* a lesson came from.
    """
    out: List[Dict[str, Any]] = [{
        "title": book_filename or "Material enviado",
        "url": "",
        "domain": "Arquivo Local (PDF/EPUB)",
        "description": f"Obra original com {len(chapter_chunks)} capítulos/seções indexados integralmente.",
        "type": "book",
        "citation": False,
    }]
    for idx, ch in enumerate(chapter_chunks, start=1):
        title = ch.get("title") or f"Capítulo {idx}"
        page_start = ch.get("page_start") or "?"
        page_end = ch.get("page_end") or page_start
        out.append({
            "title": f"Cap. {idx} — {title}",
            "url": "",
            "domain": f"p. {page_start}–{page_end}",
            "description": f"Citação do material enviado: {title}.",
            "type": "book",
            "chapter_index": idx,
            "citation": True,
        })
    return out
