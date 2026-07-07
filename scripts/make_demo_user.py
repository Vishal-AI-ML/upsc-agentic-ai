"""Create (or reset) a VERIFIED demo user for local smoke testing.

Run:  uv run python scripts/make_demo_user.py

Idempotent: safe to run repeatedly. Force-sets ``email_verified=True`` so the
demo account can log in even when REQUIRE_EMAIL_VERIFICATION + SMTP are enabled.
Runs against whatever DB your .env points to (Supabase Postgres or local SQLite).
"""
import os
import sys

# Make the project root importable when run directly (python scripts/...),
# since Python only puts the script's own folder on sys.path by default.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.core.db import init_db, SessionLocal
from src.core.users import get_user_by_email, create_user, set_password

DEMO_EMAIL = "demo@upsc.local"
DEMO_PASSWORD = "Demo@12345"
DEMO_NAME = "Demo User"


def main() -> None:
    init_db()
    db = SessionLocal()
    try:
        user = get_user_by_email(db, DEMO_EMAIL)
        if user is None:
            user = create_user(db, DEMO_EMAIL, DEMO_PASSWORD, DEMO_NAME)
            print(f"Created demo user: {DEMO_EMAIL}")
        else:
            set_password(db, user, DEMO_PASSWORD)
            print(f"Demo user already existed -> password reset: {DEMO_EMAIL}")

        # Force-verify so login works regardless of email-verification settings.
        if not user.email_verified:
            user.email_verified = True
            db.commit()
            print("email_verified -> True")

        print("")
        print("=== DEMO LOGIN ===")
        print(f"email:    {DEMO_EMAIL}")
        print(f"password: {DEMO_PASSWORD}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
