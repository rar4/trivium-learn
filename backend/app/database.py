from sqlmodel import SQLModel, create_engine, Session
import os

from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DB_PATH = BASE_DIR / "trivium.db"

DATABASE_URL = os.getenv('DATABASE_URL', f'sqlite:///{DB_PATH.as_posix()}')
engine = create_engine(DATABASE_URL, echo=False, connect_args={'check_same_thread': False, 'timeout': 30.0})

def init_db():
    from app.models.entities import (
        Course, Module, Lesson, GenerationJob, LearnerProfile, ReviewItem,
        LessonChatMessage, User, AuthToken, LessonProgress,
    )
    
    with engine.connect() as conn:
        from sqlalchemy import text
        try:
            conn.execute(text("PRAGMA journal_mode=WAL;"))
            conn.execute(text("PRAGMA synchronous=NORMAL;"))
            conn.commit()
        except Exception:
            pass

    SQLModel.metadata.create_all(engine)
    
    # Migração segura para colunas novas em bases SQLite já existentes
    with engine.connect() as conn:
        from sqlalchemy import text
        for col, col_type in [
            ("simulation_passed", "BOOLEAN DEFAULT 0"),
            ("socratic_passed", "BOOLEAN DEFAULT 0"),
            ("socratic_state_json", "TEXT DEFAULT NULL"),
        ]:
            try:
                conn.execute(text(f"ALTER TABLE lesson ADD COLUMN {col} {col_type}"))
                conn.commit()
            except Exception:
                pass

        for col, col_type in [
            ("research_dossier", "TEXT DEFAULT NULL"),
            ("sources_json", "TEXT DEFAULT NULL"),
            ("cover_image_url", "TEXT DEFAULT NULL"),
            ("language", "VARCHAR DEFAULT 'pt-BR'"),
            ("access_mode", "VARCHAR DEFAULT 'open'"),
            ("source_type", "VARCHAR DEFAULT 'web'"),
            ("source_book_filename", "TEXT DEFAULT NULL"),
            ("source_book_pages", "INTEGER DEFAULT NULL"),
        ]:
            try:
                conn.execute(text(f"ALTER TABLE course ADD COLUMN {col} {col_type}"))
                conn.commit()
            except Exception:
                pass

        # Multi-user columns on pre-existing tables (ALTER is idempotent here:
        # SQLite raises on duplicate column and we swallow it).
        for table, cols in [
            ("learnerprofile", [("user_id", "INTEGER DEFAULT NULL")]),
            ("reviewitem", [
                ("user_id", "INTEGER DEFAULT NULL"),
                ("item_key", "TEXT DEFAULT NULL"),
                ("kind", "TEXT DEFAULT NULL"),
                ("prompt", "TEXT DEFAULT NULL"),
                ("expected", "TEXT DEFAULT NULL"),
                ("pass_count", "INTEGER DEFAULT 0"),
                ("last_reviewed_on", "TEXT DEFAULT NULL"),
            ]),
            ("lessonchatmessage", [("user_id", "INTEGER DEFAULT NULL")]),
        ]:
            for col, col_type in cols:
                try:
                    conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {col} {col_type}"))
                    conn.commit()
                except Exception:
                    pass

    # The legacy local learner is a real User row (id=1). Requests without a
    # bearer token resolve to it, so existing installs and clients keep working.
    from sqlmodel import Session as _Session, select as _select
    with _Session(engine) as _s:
        if _s.exec(_select(User).where(User.username == "local")).first() is None:
            _s.add(User(id=1, username="local", email=None,
                        password_hash="!disabled-local-account!",
                        display_name="Local Learner"))
            _s.commit()

def get_session():
    with Session(engine) as session:
        yield session
