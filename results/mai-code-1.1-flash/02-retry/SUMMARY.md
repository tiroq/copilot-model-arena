# Summary

Commands run:

- `python -m pip install pytest-asyncio`
  - Result: installed successfully (`pytest-asyncio-1.4.0`)
- `python -m pytest -q`
  - Result: `4 passed in 0.01s`

Implementation notes:

- Added `src/retry.py` with an async retry decorator using exponential backoff.
- Supports retryable exception filtering, optional jitter, configurable delay/factor, and cancellation propagation.
- Added typed async tests in `tests/test_retry.py`.
