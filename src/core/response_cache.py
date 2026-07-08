"""Response cache backed by Upstash Redis (REST).

Skips re-running the full agent graph when the SAME question is asked again in
the same conversation, cutting both latency and LLM cost for repeats/retries.

Design goals
------------
* **Zero new dependency** - talks to Upstash's REST endpoint with ``httpx``
  (already a project dependency). No local Redis server, so it is safe on a
  small (8 GB) box and on free-tier hosting.
* **Fail-open** - any cache error (network, timeout, bad payload) is swallowed
  and treated as a miss, so the cache can never break a chat request.
* **No-op when unconfigured** - if ``RESPONSE_CACHE_ENABLED`` is false or the
  Upstash creds are empty, every call is a cheap no-op and behaviour is
  identical to before (so existing tests / deployments are unaffected).
* **Correctness-first scoping** - the cache key includes the conversation
  scope (thread by default), so a cached answer is only ever reused for the
  exact same question in the exact same context. This avoids serving one
  user's personalised answer to another, or leaking context across
  conversations.

Scope options (``RESPONSE_CACHE_SCOPE``):
    "thread" (default) - key per (thread, question); safest, reuses on retries
    "user"             - key per (user, question); reuse across a user's threads
    "global"           - key per question; max hit-rate, use only for a purely
                         static-knowledge deployment (no personalisation)
"""
from __future__ import annotations

import hashlib
import json
import logging
import re
from typing import Any, Optional

logger = logging.getLogger(__name__)

_WS_RE = re.compile(r"\s+")
# Trailing chars stripped during normalisation (ASCII punctuation + Devanagari danda).
_TRAILING = " ?!.\u0964"


def _normalize(question: str) -> str:
    """Normalise a question so trivial variants map to one cache key.

    Lowercases, collapses runs of whitespace, and strips trailing punctuation
    so "What is Article 21?" and "  what is article 21 " collide.
    """
    q = (question or "").strip().lower()
    q = _WS_RE.sub(" ", q)
    return q.rstrip(_TRAILING)


def _cache_key(scope: str, user_id: str, thread_id: str, question: str) -> str:
    """Build a stable, collision-resistant cache key for the given scope."""
    digest = hashlib.sha256(_normalize(question).encode("utf-8")).hexdigest()
    if scope == "user":
        scope_part = f"u:{user_id}"
    elif scope == "global":
        scope_part = "g"
    else:  # "thread" (default / fallback)
        scope_part = f"t:{thread_id}"
    return f"respcache:v1:{scope_part}:{digest}"


class ResponseCache:
    """Thin Upstash-Redis-REST cache for final agent answers."""

    def __init__(
        self,
        *,
        enabled: bool,
        rest_url: str,
        rest_token: str,
        ttl_seconds: int = 86400,
        scope: str = "thread",
        timeout: float = 2.0,
    ) -> None:
        self.rest_url = (rest_url or "").rstrip("/")
        self.rest_token = rest_token or ""
        # Only truly enabled when switched on AND fully configured.
        self.enabled = bool(enabled and self.rest_url and self.rest_token)
        self.ttl_seconds = ttl_seconds
        self.scope = scope if scope in ("thread", "user", "global") else "thread"
        self.timeout = timeout

    # -- public API -------------------------------------------------------
    def get(self, *, user_id: str, thread_id: str, question: str) -> Optional[dict]:
        """Return the cached ``{"answer", "route"}`` dict, or None on miss."""
        if not self.enabled:
            return None
        key = _cache_key(self.scope, user_id, thread_id, question)
        try:
            raw = self._redis_command(["GET", key])
        except Exception:  # fail-open: any error == miss
            logger.debug("response cache GET failed", exc_info=True)
            return None
        if not raw:
            return None
        try:
            data = json.loads(raw)
        except (TypeError, ValueError):
            return None
        if isinstance(data, dict) and data.get("answer"):
            return data
        return None

    def set(
        self,
        *,
        user_id: str,
        thread_id: str,
        question: str,
        answer: str,
        route: Optional[str] = None,
    ) -> None:
        """Store a final answer under the (scope, question) key with a TTL."""
        if not self.enabled or not answer:
            return
        key = _cache_key(self.scope, user_id, thread_id, question)
        payload = json.dumps({"answer": answer, "route": route})
        try:
            self._redis_command(["SET", key, payload, "EX", str(self.ttl_seconds)])
        except Exception:  # fail-open: never break the request path
            logger.debug("response cache SET failed", exc_info=True)

    # -- transport --------------------------------------------------------
    def _redis_command(self, command: list) -> Any:
        """Execute one Redis command via the Upstash REST endpoint.

        Upstash accepts a command as a JSON array in the POST body and replies
        with ``{"result": ...}``. httpx is imported lazily so this module stays
        import-safe (and unit-testable) without the dependency loaded.
        """
        import httpx

        resp = httpx.post(
            self.rest_url,
            json=command,
            headers={"Authorization": f"Bearer {self.rest_token}"},
            timeout=self.timeout,
        )
        resp.raise_for_status()
        return resp.json().get("result")


_cache_singleton: Optional[ResponseCache] = None


def get_response_cache() -> ResponseCache:
    """Return the process-wide cache singleton (built from settings)."""
    global _cache_singleton
    if _cache_singleton is None:
        from src.core.config import settings

        _cache_singleton = ResponseCache(
            enabled=settings.response_cache_enabled,
            rest_url=settings.upstash_redis_rest_url,
            rest_token=settings.upstash_redis_rest_token,
            ttl_seconds=settings.response_cache_ttl_seconds,
            scope=settings.response_cache_scope,
        )
        if _cache_singleton.enabled:
            logger.info(
                "Response cache ON (scope=%s, ttl=%ss)",
                _cache_singleton.scope,
                _cache_singleton.ttl_seconds,
            )
    return _cache_singleton


def reset_response_cache() -> None:
    """Drop the singleton so the next call rebuilds it from settings."""
    global _cache_singleton
    _cache_singleton = None
