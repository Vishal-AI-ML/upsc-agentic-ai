"""Refresh tokens: hashed, rotating, revocable long-lived session tokens.

Access tokens (JWT) stay short-lived and stateless. A refresh token is an
opaque random string; only its SHA-256 hash is stored, so a DB leak cannot be
replayed. Each successful refresh ROTATES the token (the presented one is
revoked and a new one issued), which lets us detect reuse of a stolen token,
and /auth/logout revokes it so a session can be killed server-side -- something
a bare stateless JWT cannot do.
"""
import hashlib
import secrets
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.core.config import settings
from src.core.models import RefreshToken


def _hash_token(raw: str) -> str:
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _row_for(db: Session, raw_token: str) -> RefreshToken | None:
    if not raw_token:
        return None
    return db.scalar(
        select(RefreshToken).where(
            RefreshToken.token_hash == _hash_token(raw_token)
        )
    )


def _is_active(row: RefreshToken | None) -> bool:
    if row is None or row.revoked_at is not None:
        return False
    expires_at = row.expires_at
    if expires_at.tzinfo is None:  # SQLite may return naive datetimes
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    return expires_at >= datetime.now(timezone.utc)


def issue_refresh_token(db: Session, user_id: str) -> str:
    """Create and persist a new refresh token; return the raw (un-hashed) value."""
    now = datetime.now(timezone.utc)
    raw = secrets.token_urlsafe(48)
    token = RefreshToken(
        user_id=user_id,
        token_hash=_hash_token(raw),
        expires_at=now + timedelta(minutes=settings.refresh_token_expire_minutes),
    )
    db.add(token)
    db.commit()
    return raw


def rotate_refresh_token(db: Session, raw_token: str) -> tuple[str, str] | None:
    """Validate + rotate a refresh token.

    Returns ``(user_id, new_raw_token)`` on success (revoking the presented
    token), or ``None`` if it is unknown, revoked or expired.
    """
    row = _row_for(db, raw_token)
    if not _is_active(row):
        return None
    row.revoked_at = datetime.now(timezone.utc)
    db.commit()
    new_raw = issue_refresh_token(db, row.user_id)
    return row.user_id, new_raw


def revoke_refresh_token(db: Session, raw_token: str) -> bool:
    """Revoke a single refresh token (logout). Returns True if one was revoked."""
    row = _row_for(db, raw_token)
    if row is None or row.revoked_at is not None:
        return False
    row.revoked_at = datetime.now(timezone.utc)
    db.commit()
    return True


def revoke_all_for_user(db: Session, user_id: str) -> int:
    """Revoke every active refresh token for a user (global logout). Returns count."""
    now = datetime.now(timezone.utc)
    rows = db.scalars(
        select(RefreshToken).where(
            RefreshToken.user_id == user_id,
            RefreshToken.revoked_at.is_(None),
        )
    ).all()
    for row in rows:
        row.revoked_at = now
    if rows:
        db.commit()
    return len(rows)
