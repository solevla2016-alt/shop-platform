"""Tests for the in-memory rate limiter."""
from collections import deque

import pytest

from app.core.exceptions import TooManyRequestsError
from app.core.rate_limit import RateLimiter


def _make_request(
    headers=None,
    client=None,
):
    class _Client:
        pass

    class _Request:
        def __init__(self):
            self.headers = headers or {}
            self.client = client

    return _Request()


def test_rate_limiter_get_client_ip_forwarded_for():
    limiter = RateLimiter(max_requests=5, window_seconds=60)

    request = _make_request(
        headers={
            "x-forwarded-for": "203.0.113.5, 70.41.3.18"
        }
    )

    assert limiter.get_client_ip(request) == "203.0.113.5"

    request = _make_request(
        headers={"x-forwarded-for": " 203.0.113.9 "}
    )

    assert limiter.get_client_ip(request) == "203.0.113.9"


def test_rate_limiter_get_client_ip_from_client_host():
    limiter = RateLimiter(max_requests=5, window_seconds=60)

    client = type("Client", (), {"host": "127.0.0.1"})()
    request = _make_request(client=client)

    assert limiter.get_client_ip(request) == "127.0.0.1"


def test_rate_limiter_get_client_ip_unknown():
    limiter = RateLimiter(max_requests=5, window_seconds=60)

    request = _make_request(client=None)

    assert limiter.get_client_ip(request) == "unknown"


@pytest.mark.asyncio
async def test_rate_limiter_allows_requests_under_limit():
    limiter = RateLimiter(max_requests=3, window_seconds=60)

    request = _make_request(
        headers={"x-forwarded-for": "10.0.0.1"}
    )

    await limiter(request)
    await limiter(request)
    await limiter(request)


@pytest.mark.asyncio
async def test_rate_limiter_raises_over_limit():
    limiter = RateLimiter(max_requests=2, window_seconds=60)

    request = _make_request(
        headers={"x-forwarded-for": "10.0.0.2"}
    )

    await limiter(request)
    await limiter(request)

    with pytest.raises(TooManyRequestsError):
        await limiter(request)


@pytest.mark.asyncio
async def test_rate_limiter_window_expiry(monkeypatch):
    limiter = RateLimiter(max_requests=1, window_seconds=10)

    request = _make_request(
        headers={"x-forwarded-for": "10.0.0.3"}
    )

    current_time = [1000.0]

    monkeypatch.setattr(
        "app.core.rate_limit.monotonic",
        lambda: current_time[0],
    )

    await limiter(request)

    with pytest.raises(TooManyRequestsError):
        await limiter(request)

    # Время ушло вперёд за пределы окна — запрос снова разрешён.
    current_time[0] = 1000.0 + 11.0

    await limiter(request)


@pytest.mark.asyncio
async def test_rate_limiter_cleans_empty_keys(monkeypatch):
    limiter = RateLimiter(max_requests=1, window_seconds=1)

    request = _make_request(
        headers={"x-forwarded-for": "10.0.0.4"}
    )

    current_time = [1000.0]

    monkeypatch.setattr(
        "app.core.rate_limit.monotonic",
        lambda: current_time[0],
    )

    await limiter(request)

    # Искусственно превышаем порог, чтобы активировать очистку.
    for i in range(10001):
        limiter.requests[f"spam-{i}"] = deque()
    limiter.requests["empty"] = deque()

    # Сдвигаем время, чтобы запись клиента истекла, и вызываем:
    # запись удалится, добавится новая, len > 10000 -> ветка очистки.
    current_time[0] = 1001.0

    await limiter(request)

    assert "empty" not in limiter.requests
