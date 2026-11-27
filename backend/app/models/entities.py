from typing import Optional, List
from sqlmodel import SQLModel, Field, Relationship
from sqlalchemy import UniqueConstraint
from datetime import datetime, timezone
import json

def get_utc_now() -> datetime:
    return datetime.now(timezone.utc)

class Course(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    subject: str = Field(index=True)
    level: str = Field(index=True)
    created_at: datetime = Field(default_factory=get_utc_now)
    is_completed: bool = Field(default=False)
    language: str = Field(default="pt-BR", index=True)
    access_mode: str = Field(default="open") # "open" ou "guided"
    research_dossier: Optional[str] = Field(default=None)
    sources_json: Optional[str] = Field(default=None)
    cover_image_url: Optional[str] = Field(default=None)
    source_type: str = Field(default="web", index=True) # "web" | "document"
    source_book_filename: Optional[str] = Field(default=None)
    source_book_pages: Optional[int] = Field(default=None)

    modules: List['Module'] = Relationship(back_populates='course')

class Module(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    course_id: int = Field(foreign_key='course.id')
    module_number: int
    title: str
    is_unlocked: bool = Field(default=False)
    is_completed: bool = Field(default=False)

    course: Optional[Course] = Relationship(back_populates='modules')
    lessons: List['Lesson'] = Relationship(back_populates='module')

class Lesson(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    module_id: int = Field(foreign_key='module.id')
    lesson_number: int
    title: str
    core_concept: str
    content_markdown: Optional[str] = Field(default=None)
    summary_50_words: Optional[str] = Field(default=None)
    
    # Quiz estruturado em JSON
    quiz_json: Optional[str] = Field(default=None)
    
    # Status e Mastery Learning
    status: str = Field(default='locked') # locked, in_progress, completed
    mcq_score: int = Field(default=0)
    blanks_score: int = Field(default=0)
    discursive_passed: bool = Field(default=False)
    discursive_feedback: Optional[str] = Field(default=None)
    
    # Mini-Simulador Sandbox & Duelo Socrático
    simulation_passed: bool = Field(default=False)
    socratic_passed: bool = Field(default=False)
    socratic_state_json: Optional[str] = Field(default=None)
    
    module: Optional[Module] = Relationship(back_populates='lessons')
    chat_messages: List['LessonChatMessage'] = Relationship(back_populates='lesson')

class LessonChatMessage(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    lesson_id: int = Field(foreign_key='lesson.id', index=True)
    user_id: Optional[int] = Field(default=None, foreign_key='user.id', index=True)
    role: str = Field(index=True) # "user" | "assistant"
    content: str
    created_at: datetime = Field(default_factory=get_utc_now)

    lesson: Optional[Lesson] = Relationship(back_populates='chat_messages')

class GenerationJob(SQLModel, table=True):
    id: str = Field(primary_key=True)
    course_id: Optional[int] = Field(default=None)
    status: str = Field(default='processing') # processing, completed, failed
    progress_pct: int = Field(default=0)
    current_step: str = Field(default='Iniciando...')
    error_message: Optional[str] = Field(default=None)
    created_at: datetime = Field(default_factory=get_utc_now)
    updated_at: datetime = Field(default_factory=get_utc_now)

class LearnerProfile(SQLModel, table=True):
    """Per-user gamification profile.

    ``id=1`` remains the legacy local learner so existing installs keep their
    XP/streak; authenticated users get their own row linked by ``user_id``.
    """
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: Optional[int] = Field(default=None, foreign_key='user.id', index=True, unique=True)
    display_name: str = Field(default="Learner")
    last_active_date: Optional[str] = Field(default=None) # YYYY-MM-DD
    streak_days: int = Field(default=0)
    reviews_completed: int = Field(default=0)
    created_at: datetime = Field(default_factory=get_utc_now)
    updated_at: datetime = Field(default_factory=get_utc_now)

class ReviewItem(SQLModel, table=True):
    """Spaced-repetition queue for individually missed quiz/flashcard items."""
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: Optional[int] = Field(default=None, foreign_key='user.id', index=True)
    lesson_id: int = Field(foreign_key='lesson.id', index=True)
    item_key: Optional[str] = Field(default=None, index=True)  # e.g. "mcq:0", "blank:2"
    kind: Optional[str] = Field(default=None)                  # "mcq" | "blank" | "lesson"
    prompt: Optional[str] = Field(default=None)                # question / cloze text
    expected: Optional[str] = Field(default=None)              # correct answer (review key)
    due_on: str = Field(index=True) # YYYY-MM-DD
    interval_days: int = Field(default=1)
    misses: int = Field(default=0)
    pass_count: int = Field(default=0)
    last_reviewed_on: Optional[str] = Field(default=None)
    created_at: datetime = Field(default_factory=get_utc_now)


# ---------------------------------------------------------------------------
# Multi-user auth + per-user progress
# ---------------------------------------------------------------------------

class User(SQLModel, table=True):
    """A learner account. Passwords use PBKDF2-HMAC-SHA256 (stdlib only)."""
    __table_args__ = (UniqueConstraint("username", name="uq_user_username"),)

    id: Optional[int] = Field(default=None, primary_key=True)
    username: str = Field(index=True)
    email: Optional[str] = Field(default=None, index=True)
    password_hash: str
    display_name: str = Field(default="Learner")
    is_active: bool = Field(default=True)
    created_at: datetime = Field(default_factory=get_utc_now)


class AuthToken(SQLModel, table=True):
    """Opaque bearer token; revocable and expiring without a JWT dependency."""
    token: str = Field(primary_key=True)
    user_id: int = Field(foreign_key='user.id', index=True)
    created_at: datetime = Field(default_factory=get_utc_now)
    expires_at: Optional[datetime] = Field(default=None)
    revoked: bool = Field(default=False)


class LessonProgress(SQLModel, table=True):
    """One learner's mastery-gate state for one lesson.

    The global ``Lesson`` row keeps the shared curriculum (and the legacy
    local learner's state). Every authenticated user's progress lives here,
    so one user's quiz result can never reveal or advance another's path.
    """
    __table_args__ = (UniqueConstraint("user_id", "lesson_id", name="uq_user_lesson"),)

    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key='user.id', index=True)
    lesson_id: int = Field(foreign_key='lesson.id', index=True)
    status: str = Field(default='locked')  # locked | in_progress | completed
    mcq_score: int = Field(default=0)
    blanks_score: int = Field(default=0)
    discursive_passed: bool = Field(default=False)
    discursive_feedback: Optional[str] = Field(default=None)
    simulation_passed: bool = Field(default=False)
    socratic_passed: bool = Field(default=False)
    socratic_state_json: Optional[str] = Field(default=None)
    completed_at: Optional[datetime] = Field(default=None)
    updated_at: datetime = Field(default_factory=get_utc_now)
