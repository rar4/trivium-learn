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
