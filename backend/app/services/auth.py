"""Learner accounts and bearer-token authentication.

Passwords are hashed with PBKDF2-HMAC-SHA256 from the standard library, and
sessions are opaque revocable tokens -- no new runtime dependency is needed.

A request without an ``Authorization`` header resolves to the seeded local
learner (``id=1``). That keeps the original single-user install, the existing
frontend and the acceptance suites working while authenticated requests get a
fully isolated account.
"""
from __future__ import annotations

import hashlib
import hmac
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import Depends, Header, HTTPException, status
from sqlmodel import Session, select

from app.database import get_session
from app.models.entities import AuthToken, User

LOCAL_USERNAME = "local"
ITERATIONS = 120_000
TOKEN_TTL_DAYS = 30


def hash_password(password: str, *, salt: Optional[bytes] = None) -> str:
    salt = salt if salt is not None else secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, ITERATIONS)
    return f"pbkdf2_sha256${ITERATIONS}${salt.hex()}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        algo, iterations, salt_hex, digest_hex = stored.split("$")
        if algo != "pbkdf2_sha256":
            return False
        actual = hashlib.pbkdf2_hmac(
            "sha256", password.encode("utf-8"), bytes.fromhex(salt_hex), int(iterations)
        )
        return hmac.compare_digest(actual.hex(), digest_hex)
    except (ValueError, AttributeError, TypeError):
        return False


def create_token(session: Session, user_id: int) -> str:
    token = secrets.token_urlsafe(32)
    expires = datetime.now(timezone.utc) + timedelta(days=TOKEN_TTL_DAYS)
    session.add(AuthToken(token=token, user_id=user_id, expires_at=expires))
    session.commit()
    return token


def _parse_bearer(authorization: Optional[str]) -> Optional[str]:
    if not authorization:
        return None
    parts = authorization.strip().split(None, 1)
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise HTTPException(status_code=401, detail="Invalid Authorization header. Use 'Bearer <token>'.")
    return parts[1].strip() or None


def resolve_user(session: Session, authorization: Optional[str]) -> User:
    raw = _parse_bearer(authorization)
    if raw:
        token = session.get(AuthToken, raw)
        if token is None or token.revoked:
            raise HTTPException(status_code=401, detail="Invalid or revoked token.")
        if token.expires_at is not None:
            expires = token.expires_at
            if expires.tzinfo is None:  # SQLite returns naive datetimes
                expires = expires.replace(tzinfo=timezone.utc)
            if expires < datetime.now(timezone.utc):
                raise HTTPException(status_code=401, detail="Token expired.")
        user = session.get(User, token.user_id)
        if user is None or not user.is_active:
            raise HTTPException(status_code=401, detail="Account unavailable.")
        return user

    user = session.exec(select(User).where(User.username == LOCAL_USERNAME)).first()
    if user is None:  # defensive: init_db seeds this, but keep imports safe
        user = User(id=1, username=LOCAL_USERNAME, password_hash="!disabled-local-account!",
                    display_name="Local Learner")
        session.add(user)
        session.commit()
        session.refresh(user)
    return user


def current_user(
    authorization: Optional[str] = Header(default=None),
    session: Session = Depends(get_session),
) -> User:
    """Optional auth: a missing header means the legacy local learner."""
    return resolve_user(session, authorization)


def require_user(
    authorization: Optional[str] = Header(default=None),
    session: Session = Depends(get_session),
) -> User:
    """Strict auth for account-only routes (register/login excluded)."""
    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required. Provide 'Bearer <token>'.",
        )
    return resolve_user(session, authorization)


def public_user(user: User) -> dict:
    return {
        "id": user.id,
        "username": user.username,
        "display_name": user.display_name,
        "email": user.email,
    }
