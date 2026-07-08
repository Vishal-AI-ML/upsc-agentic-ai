"""Unit tests for the Upstash-backed response cache (src.core.response_cache).

Network is never touched: ResponseCache._redis_command is replaced with an
in-memory dict, so these run fully offline and deterministically.
"""
from __future__ import annotations

from src.core.response_cache import ResponseCache, _cache_key, _normalize


def _mem_cache(scope: str = "thread") -> ResponseCache:
    cache = ResponseCache(
        enabled=True,
        rest_url="https://fake.upstash.io",
        rest_token="token",
        ttl_seconds=100,
        scope=scope,
    )
    store: dict[str, str] = {}

    def fake_cmd(command):
        op = command[0].upper()
        if op == "SET":
            store[command[1]] = command[2]
            return "OK"
        if op == "GET":
            return store.get(command[1])
        return None

    cache._redis_command = fake_cmd  # type: ignore[assignment]
    cache._store = store  # type: ignore[attr-defined]  # for assertions
    return cache


def test_normalize_collapses_variants():
    base = _normalize("What is Article 21?")
    assert base == _normalize("  what   is   article 21   ")
    assert base == _normalize("WHAT IS ARTICLE 21???")


def test_cache_key_scoping():
    t = _cache_key("thread", "u1", "th1", "Q?")
    assert t == _cache_key("thread", "u1", "th1", "q")  # normalized-equal
    assert t != _cache_key("thread", "u1", "th2", "Q?")  # different thread
    assert _cache_key("user", "u1", "t", "Q") != _cache_key("user", "u2", "t", "Q")
    assert _cache_key("global", "u1", "t1", "Q") == _cache_key("global", "u2", "t2", "Q")


def test_set_then_get_roundtrip():
    cache = _mem_cache()
    assert cache.get(user_id="u1", thread_id="t1", question="Article 21?") is None
    cache.set(
        user_id="u1", thread_id="t1", question="Article 21?",
        answer="Right to life", route="mentor",
    )
    hit = cache.get(user_id="u1", thread_id="t1", question="  article 21  ")
    assert hit is not None
    assert hit["answer"] == "Right to life"
    assert hit["route"] == "mentor"


def test_scope_isolates_threads():
    cache = _mem_cache()
    cache.set(user_id="u1", thread_id="t1", question="Q", answer="A")
    assert cache.get(user_id="u1", thread_id="t2", question="Q") is None


def test_disabled_cache_is_noop():
    cache = ResponseCache(enabled=False, rest_url="", rest_token="")
    cache.set(user_id="u1", thread_id="t1", question="Q", answer="A")
    assert cache.get(user_id="u1", thread_id="t1", question="Q") is None


def test_empty_answer_not_cached():
    cache = _mem_cache()
    cache.set(user_id="u1", thread_id="t1", question="Q", answer="")
    assert cache._store == {}  # type: ignore[attr-defined]
    assert cache.get(user_id="u1", thread_id="t1", question="Q") is None
