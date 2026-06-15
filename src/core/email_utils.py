"""Password-reset email sending via SMTP (stdlib only).

If SMTP settings are not configured, the reset link is logged to the server
console instead of being emailed (useful for local development / testing).
"""
import logging
import smtplib
from email.message import EmailMessage

from src.core.config import settings

logger = logging.getLogger(__name__)


def smtp_configured() -> bool:
    return bool(settings.smtp_host and settings.smtp_user and settings.smtp_password)


def verification_enforced() -> bool:
    """
    Email verification is enforced ONLY when it is both requested AND SMTP is
    configured. This prevents a lockout state: if verification were required but
    no email could be sent, users would never receive the link and login would
    be permanently blocked. When SMTP is off, verification auto-disables.
    """
    return bool(settings.require_email_verification and smtp_configured())


def send_reset_email(to_email: str, reset_link: str) -> None:
    """Send a password-reset email. Falls back to logging the link if SMTP is off."""
    minutes = settings.reset_token_expire_minutes
    subject = "Reset your UPSC AI password"
    text_body = (
        "We received a request to reset your UPSC AI password.\n\n"
        f"Reset it using the link below (valid for {minutes} minutes):\n"
        f"{reset_link}\n\n"
        "If you didn't request this, you can safely ignore this email."
    )
    html_body = (
        "<div style='font-family:Arial,sans-serif;color:#1a1a2e;line-height:1.6;'>"
        "<h2 style='color:#4361ee;margin:0 0 12px;'>Reset your UPSC AI password</h2>"
        f"<p>We received a request to reset your password. This link is valid for "
        f"<b>{minutes} minutes</b>.</p>"
        f"<p><a href='{reset_link}' style='display:inline-block;padding:12px 22px;"
        "background:#4361ee;color:#fff;border-radius:8px;text-decoration:none;font-weight:600;'>"
        "Reset Password</a></p>"
        "<p style='color:#6b7490;font-size:13px;'>Or paste this link into your browser:<br>"
        f"{reset_link}</p>"
        "<p style='color:#6b7490;font-size:13px;'>If you didn't request this, you can ignore this email.</p>"
        "</div>"
    )

    if not smtp_configured():
        logger.warning(
            "SMTP not configured - password reset link (DEV ONLY, not emailed): %s",
            reset_link,
        )
        return

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = settings.smtp_from or settings.smtp_user
    msg["To"] = to_email
    msg.set_content(text_body)
    msg.add_alternative(html_body, subtype="html")

    with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=20) as server:
        if settings.smtp_use_tls:
            server.starttls()
        server.login(settings.smtp_user, settings.smtp_password)
        server.send_message(msg)
    logger.info("Password reset email sent to %s", to_email)


def send_verification_email(to_email: str, verify_link: str) -> None:
    """Send an email-verification link. Falls back to logging the link if SMTP is off."""
    minutes = settings.verification_token_expire_minutes
    hours = max(1, minutes // 60)
    subject = "Verify your UPSC AI email"
    text_body = (
        "Welcome to UPSC AI! Please verify your email to activate your account.\n\n"
        f"Verify using the link below (valid for {hours} hour(s)):\n"
        f"{verify_link}\n\n"
        "If you didn't create this account, you can safely ignore this email."
    )
    html_body = (
        "<div style='font-family:Arial,sans-serif;color:#1a1a2e;line-height:1.6;'>"
        "<h2 style='color:#4361ee;margin:0 0 12px;'>Verify your UPSC AI email</h2>"
        "<p>Welcome! Please verify your email to activate your account. This link is valid for "
        f"<b>{hours} hour(s)</b>.</p>"
        f"<p><a href='{verify_link}' style='display:inline-block;padding:12px 22px;"
        "background:#4361ee;color:#fff;border-radius:8px;text-decoration:none;font-weight:600;'>"
        "Verify Email</a></p>"
        "<p style='color:#6b7490;font-size:13px;'>Or paste this link into your browser:<br>"
        f"{verify_link}</p>"
        "<p style='color:#6b7490;font-size:13px;'>If you didn't create this account, you can ignore this email.</p>"
        "</div>"
    )

    if not smtp_configured():
        logger.warning(
            "SMTP not configured - email verification link (DEV ONLY, not emailed): %s",
            verify_link,
        )
        return

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = settings.smtp_from or settings.smtp_user
    msg["To"] = to_email
    msg.set_content(text_body)
    msg.add_alternative(html_body, subtype="html")

    with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=20) as server:
        if settings.smtp_use_tls:
            server.starttls()
        server.login(settings.smtp_user, settings.smtp_password)
        server.send_message(msg)
    logger.info("Verification email sent to %s", to_email)
