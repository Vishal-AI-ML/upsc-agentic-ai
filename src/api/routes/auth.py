"""Auth routes - register + login."""
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel
from sqlalchemy.orm import Session

import logging

from src.core.users import (
    authenticate, create_user, get_user_by_email, set_password,
)
from src.core.security import create_access_token
from src.core.reset_tokens import create_reset_token, consume_reset_token
from src.core.verification_tokens import (
    create_verification_token, consume_verification_token,
)
from src.core.email_utils import send_reset_email, send_verification_email, verification_enforced
from src.core.models import User
from src.core.config import settings
from src.core.db import get_db
from src.api.deps import get_current_user

router = APIRouter(prefix="/auth", tags=["Auth"])
logger = logging.getLogger(__name__)


class RegisterRequest(BaseModel):
    email: str
    password: str
    name: str = ""


def _token_for(user) -> dict:
    token = create_access_token(
        {"sub": user.id, "email": user.email, "name": user.name}
    )
    return {"access_token": token, "token_type": "bearer"}


def _frontend_link(param: str, raw_token: str) -> str:
    """Build a frontend URL with one query param (works with bare host or file path)."""
    base = settings.frontend_url.strip().rstrip("/")
    sep = "&" if "?" in base else "?"
    return f"{base}{sep}{param}={raw_token}"


def _send_verification(db: Session, user) -> None:
    """Issue a verification token and email the link (logged to console if SMTP off)."""
    try:
        raw = create_verification_token(db, user.id)
        send_verification_email(user.email, _frontend_link("verify_token", raw))
    except Exception as e:  # noqa: BLE001
        logger.error(f"Verification email failed for {user.email}: {e}")


@router.post("/register", status_code=status.HTTP_201_CREATED)
async def register(body: RegisterRequest, db: Session = Depends(get_db)):
    """Create a new account and email a verification link.

    When REQUIRE_EMAIL_VERIFICATION is on (default), login stays blocked until the
    email is verified, so no JWT is returned here.
    """
    try:
        user = create_user(db, body.email, body.password, body.name)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)
        )
    if verification_enforced():
        _send_verification(db, user)
        return {
            "verification_required": True,
            "email": user.email,
            "message": "Account created. Please check your email and verify your account before signing in.",
        }
    # Verification disabled (dev): mark verified and auto-login.
    user.email_verified = True
    db.commit()
    return _token_for(user)


@router.post("/login")
async def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
):
    """Login with email + password (OAuth2 form field 'username' = email)."""
    user = authenticate(db, form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if verification_enforced() and not user.email_verified:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Email not verified. Check your inbox for the verification link, or request a new one.",
        )
    return _token_for(user)


@router.get("/me")
async def me(current_user: dict = Depends(get_current_user)):
    """Return the currently logged-in user."""
    return current_user


class ForgotPasswordRequest(BaseModel):
    email: str


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str


@router.post("/forgot-password")
async def forgot_password(body: ForgotPasswordRequest, db: Session = Depends(get_db)):
    """Email a password-reset link if the address is registered.

    Always returns a generic message so we don't reveal whether an email exists.
    """
    user = get_user_by_email(db, body.email)
    if user:
        try:
            raw_token = create_reset_token(db, user.id)
            base = settings.frontend_url.strip().rstrip("/")
            sep = "&" if "?" in base else "?"
            link = f"{base}{sep}reset_token={raw_token}"
            send_reset_email(user.email, link)
        except Exception as e:  # noqa: BLE001
            logger.error(f"Password reset email failed for {user.email}: {e}")
    return {"message": "If an account exists for that email, a reset link has been sent."}


@router.post("/reset-password")
async def reset_password(body: ResetPasswordRequest, db: Session = Depends(get_db)):
    """Consume a reset token and set a new password."""
    user_id = consume_reset_token(db, body.token)
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired reset link. Please request a new one.",
        )
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired reset link. Please request a new one.",
        )
    try:
        set_password(db, user, body.new_password)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    return {"message": "Password updated. You can now sign in with your new password."}


class VerifyEmailRequest(BaseModel):
    token: str


class ResendVerificationRequest(BaseModel):
    email: str


@router.post("/verify-email")
async def verify_email(body: VerifyEmailRequest, db: Session = Depends(get_db)):
    """Consume an email-verification token, mark the user verified, and auto-login."""
    user_id = consume_verification_token(db, body.token)
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired verification link. Please request a new one.",
        )
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired verification link. Please request a new one.",
        )
    if not user.email_verified:
        user.email_verified = True
        db.commit()
        db.refresh(user)
    data = _token_for(user)
    data["message"] = "Email verified successfully. You are now signed in."
    return data


@router.post("/resend-verification")
async def resend_verification(body: ResendVerificationRequest, db: Session = Depends(get_db)):
    """Resend the verification email if the account exists and is still unverified.

    Always returns a generic message so we don't reveal whether an email exists.
    """
    user = get_user_by_email(db, body.email)
    if user and not user.email_verified:
        _send_verification(db, user)
    return {"message": "If an unverified account exists for that email, a new verification link has been sent."}
