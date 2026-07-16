"""Offline tests for the rate limiter (in-memory + Redis + fallback)."""

from src.api.rate_limit_core import RateLimiter


class FakeRedis:
    def __init__(self, enabled=True, fail=False):
        self.enabled = enabled
        self.fail = fail
        self.store = {}
        self.calls = []

    def command(self, command):
        self.calls.append(command)
        if self.fail:
            return None
        op = command[0]
        if op == "INCR":
            k = command[1]
            self.store[k] = self.store.get(k, 0) + 1
            return self.store[k]
        if op == "EXPIRE":
            return 1
        return None


def test_in_memory_window():
    lim = RateLimiter(3, 60, redis=FakeRedis(enabled=False))
    t = 1000.0
    assert lim.check("ip", mono=t)[0]
    assert lim.check("ip", mono=t)[0]
    assert lim.check("ip", mono=t)[0]
    allowed, retry = lim.check("ip", mono=t)
    assert not allowed and retry > 0
    assert lim.check("other", mono=t)[0]
    assert lim.check("ip", mono=t + 61)[0]


def test_redis_fixed_window():
    fake = FakeRedis(enabled=True)
    lim = RateLimiter(3, 60, redis=fake)
    for _ in range(3):
        assert lim.check("ip", wall=100.0)[0]
    allowed, retry = lim.check("ip", wall=100.0)
    assert not allowed and retry > 0
    assert sum(1 for c in fake.calls if c[0] == "EXPIRE") == 1


def test_redis_unavailable_falls_back():
    fake = FakeRedis(enabled=True, fail=True)
    lim = RateLimiter(2, 60, redis=fake)
    assert lim.check("ip", wall=100.0, mono=1.0)[0]
    assert lim.check("ip", wall=100.0, mono=1.0)[0]
    assert not lim.check("ip", wall=100.0, mono=1.0)[0]
