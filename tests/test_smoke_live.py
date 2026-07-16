"""Live end-to-end smoke test against the DEPLOYED service.

Opt-in: every test is skipped unless ``LIVE_BASE_URL`` is set, so this never
runs as part of the normal offline suite (``uv run pytest -q``). In CI it runs
only on the nightly schedule / manual dispatch (see ``.github/workflows/ci.yml``
job ``smoke-live``). A generous timeout absorbs Render free-tier cold starts
(~1 min on the first hit after idle).

Local use::

    LIVE_BASE_URL=https://upsc-agentic-ai.onrender.com uv run pytest tests/test_smoke_live.py -q

Optional demo-login check (read-only, writes nothing to prod)::

    LIVE_BASE_URL=... LIVE_DEMO_EMAIL=demo@upsc.local LIVE_DEMO_PASSWORD=Demo@12345 \
        uv run pytest tests/test_smoke_live.py -q
"""

from __future__ import annotations

import os

import pytest

BASE_URL = os.getenv("LIVE_BASE_URL", "").rstrip("/")
_TIMEOUT = float(os.getenv("LIVE_SMOKE_TIMEOUT", "90"))

pytestmark = pytest.mark.skipif(
    not BASE_URL, reason="LIVE_BASE_URL not set; live smoke test skipped"
)


def test_live_health_ok():
    """The deployed service boots and /health reports healthy."""
    import requests

    r = requests.get(f"{BASE_URL}/health", timeout=_TIMEOUT)
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "healthy"
    assert "version" in body


def test_live_protected_route_requires_auth():
    """Auth guard is live: a protected route rejects an unauthenticated call.

    Writes nothing to prod -- it only proves the 401 gate is wired.
    """
    import requests

    r = requests.post(
        f"{BASE_URL}/api/v1/pyq/parse",
        json={"text": "1. dummy?"},
        timeout=_TIMEOUT,
    )
    assert r.status_code == 401


def test_live_demo_login_optional():
    """If demo creds are supplied, a full login returns a bearer token.

    Read-only: logging in creates no new data. The login route uses an OAuth2
    form body where the ``username`` field carries the email.
    """
    email = os.getenv("LIVE_DEMO_EMAIL")
    password = os.getenv("LIVE_DEMO_PASSWORD")
    if not (email and password):
        pytest.skip("LIVE_DEMO_EMAIL / LIVE_DEMO_PASSWORD not set")

    import requests

    r = requests.post(
        f"{BASE_URL}/api/v1/auth/login",
        data={"username": email, "password": password},
        timeout=_TIMEOUT,
    )
    assert r.status_code == 200
    assert r.json().get("access_token")
