# Task 02: Async Retry Decorator

Implement `src/retry.py`: an async retry decorator with exponential backoff.

## Required API

```python
from typing import Callable, TypeVar, ParamSpec, Awaitable

P = ParamSpec("P")
T = TypeVar("T")

def retry(
    *,
    attempts: int = 3,
    backoff_factor: float = 2.0,
    initial_delay: float = 1.0,
    max_delay: float | None = None,
    jitter: float | Callable[[float], float] | None = None,
    retry_on: type[Exception] | tuple[type[Exception], ...] = Exception,
) -> Callable[[Callable[P, Awaitable[T]]], Callable[P, Awaitable[T]]]:
    """Decorator to retry async functions with exponential backoff.
    
    Args:
        attempts: Total number of attempts (must be >= 1). First call plus (attempts-1) retries.
        backoff_factor: Exponential backoff multiplier (must be >= 1.0)
        initial_delay: Initial delay in seconds before first retry (must be >= 0)
        max_delay: Maximum delay cap in seconds, or None for unlimited
        jitter: Jitter strategy:
            - None: no jitter
            - float in [0.0, 1.0]: add uniform random jitter in [0, delay * jitter]
            - Callable: function (delay: float) -> actual_delay
        retry_on: Exception type(s) to retry. Other exceptions propagate immediately.
    
    Returns:
        Decorated async function
        
    Raises:
        ValueError: if arguments are invalid
    """
    ...
```

## Required Behavior

1. **Retry Semantics**:
   - `attempts=3` means: 1 initial call + 2 retries (3 total attempts)
   - `attempts=1` means: no retries, just one call
   - If all attempts fail, raise the last exception
   - If any attempt succeeds, return immediately (no further retries)

2. **Exponential Backoff**:
   - Delay after attempt N (N=1 for first retry): `initial_delay * (backoff_factor ** (N-1))`
   - Example: `initial_delay=1.0, backoff_factor=2.0` → delays: 1.0, 2.0, 4.0, 8.0, ...

3. **Max Delay**:
   - If `max_delay` is set, cap each delay: `min(computed_delay, max_delay)`
   - If `max_delay=None`, no cap

4. **Jitter**:
   - Numeric jitter (float): add `random.uniform(0, delay * jitter)` to computed delay
     - `jitter=0.0` means no jitter
     - `jitter=0.5` means add up to 50% of delay as random jitter
   - Callable jitter: call `jitter(delay)` to compute final delay
   - Jitter is applied AFTER max_delay capping

5. **Exception Filtering**:
   - Only retry if exception is instance of `retry_on`
   - All other exceptions propagate immediately without retry

6. **Cancellation Propagation**:
   - If `asyncio.CancelledError` is raised, it must propagate immediately (no retry)
   - Even if `retry_on=Exception`, CancelledError must not be caught

7. **Argument Validation**:
   - Raise `ValueError` if `attempts < 1`
   - Raise `ValueError` if `backoff_factor < 1.0`
   - Raise `ValueError` if `initial_delay < 0`
   - Raise `ValueError` if `max_delay` is not None and `max_delay < 0`

8. **Type Hints**:
   - Use `ParamSpec` and `TypeVar` to preserve function signatures
   - Decorated function must accept same args/kwargs as original

## Required Tests

Add comprehensive pytest tests in `tests/test_retry.py`:

- Success on first attempt (no retries)
- Success after N retries
- All attempts fail (raise last exception)
- Non-retryable exception (propagates immediately)
- Cancellation propagation (`asyncio.CancelledError`)
- Exponential backoff timing verification
- Max delay capping
- Numeric jitter (verify delay is in expected range)
- Callable jitter
- Zero jitter
- attempts=1 (no retries)
- Invalid arguments raise ValueError
- Decorated function signature is preserved

Use `pytest-asyncio` for async tests. Declare `pytest-asyncio` in `pyproject.toml`:

```toml
[project]
name = "bench"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = ["pytest-asyncio>=0.21.0"]

[tool.pytest.ini_options]
testpaths = ["tests"]
asyncio_mode = "auto"
```

## Scope Restrictions

- Implement only the retry decorator in `src/retry.py`
- Add or update tests in `tests/test_retry.py`
- Update `pyproject.toml` to add pytest-asyncio dependency
- Do not modify other files unless required for imports
- Do not add CLI or web interface
- Do not add features beyond the specified API
