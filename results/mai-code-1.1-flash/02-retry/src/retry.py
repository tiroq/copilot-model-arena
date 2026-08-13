from __future__ import annotations

import asyncio
import functools
import inspect
import random
from collections.abc import Awaitable, Callable
from typing import Any, ParamSpec, TypeVar, cast

P = ParamSpec("P")
T = TypeVar("T")

Retryable = type[Exception] | tuple[type[Exception], ...]


def _normalize_exceptions(exceptions: Retryable | None) -> tuple[type[Exception], ...]:
    if exceptions is None:
        return (Exception,)
    if isinstance(exceptions, tuple):
        normalized = exceptions
        if not normalized:
            raise ValueError("exceptions must not be empty")
        for exc in normalized:
            if not isinstance(exc, type) or not issubclass(exc, Exception):
                raise TypeError("Retry exceptions must be exception classes")
        return normalized
    if not isinstance(exceptions, type) or not issubclass(exceptions, Exception):
        raise TypeError("Retry exceptions must be exception classes")
    return (exceptions,)


def _apply_jitter(base_delay: float, jitter: float | Callable[[float], float] | None) -> float:
    if jitter is None:
        return base_delay
    if callable(jitter):
        value = float(jitter(base_delay))
        return max(0.0, value)
    if jitter < 0:
        raise ValueError("jitter must be non-negative")
    return max(0.0, base_delay + random.uniform(0.0, base_delay * jitter))


async def _sleep_for(delay: float, sleep_fn: Callable[[float], Awaitable[None] | None]) -> None:
    result = sleep_fn(delay)
    if inspect.isawaitable(result):
        await result


def retry(
    exceptions: Retryable | None = None,
    *,
    attempts: int = 3,
    base_delay: float = 0.1,
    factor: float = 2.0,
    max_delay: float | None = None,
    jitter: float | Callable[[float], float] | None = None,
    sleep: Callable[[float], Awaitable[None] | None] | None = None,
) -> Callable[[Callable[P, Awaitable[T]]], Callable[P, Awaitable[T]]]:
    """Retry async callables with exponential backoff.

    The decorator retries only on the selected exception types. Cancellation is
    propagated immediately and never swallowed.
    """
    if attempts < 1:
        raise ValueError("attempts must be at least 1")
    if base_delay < 0:
        raise ValueError("base_delay must be non-negative")
    if factor < 1:
        raise ValueError("factor must be >= 1")
    if max_delay is not None and max_delay < 0:
        raise ValueError("max_delay must be non-negative")

    normalized = _normalize_exceptions(exceptions)
    sleep_fn = sleep or asyncio.sleep

    def decorator(func: Callable[P, Awaitable[T]]) -> Callable[P, Awaitable[T]]:
        @functools.wraps(func)
        async def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
            delay = float(base_delay)
            for attempt in range(1, attempts + 1):
                try:
                    return await func(*args, **kwargs)
                except asyncio.CancelledError:
                    raise
                except Exception as exc:  # pragma: no branch - guard below
                    if not isinstance(exc, normalized):
                        raise
                    if attempt == attempts:
                        raise
                    wait = delay
                    if max_delay is not None:
                        wait = min(wait, max_delay)
                    wait = _apply_jitter(wait, jitter)
                    await _sleep_for(wait, sleep_fn)
                    delay *= factor
                    if max_delay is not None:
                        delay = min(delay, max_delay)

            raise RuntimeError("retry loop exited without returning or raising")

        return cast(Callable[..., Awaitable[T]], wrapper)

    return decorator


__all__ = ["retry"]
