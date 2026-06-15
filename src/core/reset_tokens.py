"""Password reset tokens: hashed, single-use, time-limited.

The raw token is returned only once (emailed in the reset link). Only its
SHA-256 hash is stored, so a DB leak cannot be used to reset passwords.
"""
import hashlib
import secrets
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.core.config import settings
from src.core.models import PasswordResetToken


def _hash_token(raw: str) -> str:
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def create_reset_token(db: Session, user_id: str) -> str:
    """Invalidate the user's old unused tokens, then issue a new raw token."""
    now = datetime.now(timezone.utc)
    old = db.scalars(
        select(PasswordResetToken).where(
            PasswordResetToken.user_id == user_id,
            PasswordResetToken.used_at.is_(None),
        )
    ).all()
    for row in old:
        row.used_at = now

    raw = secrets.token_urlsafe(32)
    token = PasswordResetToken(
        user_id=user_id,
        token_hash=_hash_token(raw),
        expires_at=now + timedelta(minutes=settings.reset_token_expire_minutes),
    )
    db.add(token)
    db.commit()
    return raw


def consume_reset_token(db: Session, raw_token: str) -> str | None:
    """Return user_id if token is valid, unused and unexpired (and mark it used). Else None."""
    if not raw_token:
        return None
    row = db.scalar(
        select(PasswordResetToken).where(
            PasswordResetToken.token_hash == _hash_token(raw_token)
        )
    )
    if not row or row.used_at is not None:
        return None

    expires_at = row.expires_at
    if expires_at.tzinfo is None:  # SQLite may return naive datetimes
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if expires_at < datetime.now(timezone.utc):
        return None

    row.used_at = datetime.now(timezone.utc)
    db.commit()
    return row.user_id
