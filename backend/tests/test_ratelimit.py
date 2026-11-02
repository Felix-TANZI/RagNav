# backend/tests/test_ratelimit.py
from app.ratelimit import RateLimiter


def test_fenetre_glissante_par_adresse():
    now = [0.0]
    limiter = RateLimiter(limit=2, window_seconds=60, clock=lambda: now[0])
    assert limiter.retry_after("10.0.0.1") is None and limiter.retry_after("10.0.0.1") is None
    assert limiter.retry_after("10.0.0.1") == 61
    assert limiter.retry_after("10.0.0.2") is None
    now[0] = 61
    assert limiter.retry_after("10.0.0.1") is None
