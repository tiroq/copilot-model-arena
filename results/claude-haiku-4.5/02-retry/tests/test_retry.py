from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from typing import Any

import pytest

from src.retry import retry


@pytest.mark.asyncio
async def test_retries_until_success() -> None:
    attempts: list[str] = []
    seen: list[float] = []

    async def fake_sleep(delay: float) -> None:
        seen.append(delay)

    @retry(exceptions=ValueError, attempts=4, base_delay=1.0, factor=2.0, jitter=0.0, sleep=fake_sleep)
    async def flaky() -> int:
        attempts.append("call")
        if len(attempts) < 3:
            raise ValueError("transient")
        return 42

    assert await flaky() == 42
    assert len(attempts) == 3
    assert seen == [1.0, 2.0]


@pytest.mark.asyncio
async def test_raises_non_retryable_exception_immediately() -> None:
    attempts = 0

    @retry(exceptions=ValueError, attempts=5, base_delay=0.01)
    async def boom() -> None:
        nonlocal attempts
        attempts += 1
        raise TypeError("no retry")

    with pytest.raises(TypeError, match="no retry"):
        await boom()
    assert attempts == 1


@pytest.mark.asyncio
async def test_cancellation_propagates() -> None:
    loop = asyncio.get_running_loop()
    started = asyncio.Event()
    cancelled = False

    @retry(exceptions=ValueError, attempts=5, base_delay=0.1, sleep=lambda delay: asyncio.sleep(0))
    async def flaky() -> None:
        nonlocal cancelled
        started.set()
        await asyncio.sleep(0)
        cancelled = True
        raise ValueError("retry me")

    task = asyncio.create_task(flaky())
    await started.wait()
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert cancelled is False


@pytest.mark.asyncio
async def test_jitter_is_applied() -> None:
    payloads: list[float] = []

    def jitter(value: float) -> float:
        payloads.append(value)
        return value * 0.5

    async def fake_sleep(delay: float) -> None:
        pass

    @retry(exceptions=ValueError, attempts=3, base_delay=2.0, factor=2.0, jitter=jitter, sleep=fake_sleep)
    async def flaky() -> int:
        raise ValueError("still bad")

    with pytest.raises(ValueError):
        await flaky()
    assert payloads == [2.0, 4.0]
