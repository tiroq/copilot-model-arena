# Audit Report - gpt-5.5

**Auditor model:** gpt-5.5  
**Date:** 2026-08-13  
**Tasks audited:** 01-json-store, 02-retry, 03-cli  
**Models under review:** claude-haiku-4.5, mai-code-1.1-flash

## Summary

| Model | Task | Score | Correctness | Tests | Scope |
| --- | --- | ---: | --- | --- | --- |
| claude-haiku-4.5 | 01-json-store | 78 | Partial | 17/17 passed | Full API, flawed append-only semantics |
| claude-haiku-4.5 | 02-retry | 88 | Full | 4/4 passed | Full |
| claude-haiku-4.5 | 03-cli | 82 | Mostly full | 27/27 passed | Full CLI, null-value defect |
| mai-code-1.1-flash | 01-json-store | 86 | Mostly full | 4/4 passed | Full core API, thin tests |
| mai-code-1.1-flash | 02-retry | 90 | Full | 4/4 passed | Full |
| mai-code-1.1-flash | 03-cli | 85 | Mostly full | 3/3 passed | Full CLI, thin tests |

## Validation performed

I inspected diffs from the empty `seed/` project for every task/model. All six implementations add task-specific source and tests; `mai-code-1.1-flash/02-retry` also changes `pyproject.toml` to declare `pytest-asyncio`.

Own test suites:

```text
results/claude-haiku-4.5/01-json-store: 17 passed
results/claude-haiku-4.5/02-retry:      4 passed
results/claude-haiku-4.5/03-cli:        27 passed
results/mai-code-1.1-flash/01-json-store: 4 passed
results/mai-code-1.1-flash/02-retry:      4 passed
results/mai-code-1.1-flash/03-cli:        3 passed
```

Focused probes also verified CLI direct execution, JSON stability, list output shape, null-value handling, and that both retry implementations/tests are byte-for-byte identical.

## claude-haiku-4.5

### 01-json-store - Score: 78/100

**Correctness:** Implements `put`, `get`, `list(prefix)`, latest-write-wins reads, JSONL persistence, and corruption-tolerant reads. `list(prefix)` returns `(key, value)` pairs and handles prefix filtering correctly.

**Tests:** 17/17 pass. Coverage is broad for values, prefixes, malformed lines, empty lines, and latest-write-wins behavior.

**Scope:** Full requested API is present.

**Defects:**

1. The store is not truly append-only. `put()` reads the whole file, writes old content plus the new record to a temp file, then replaces the original. That gives atomic replacement, but violates the append-only requirement and is O(n) per write.
2. No `fsync` before `os.replace`, so crash durability is weaker than expected for an atomic store.
3. Stored `None` is indistinguishable from missing keys because `get()` returns `None` for both. This becomes a real CLI bug in task 03.

**Evidence:**

```python
# results/claude-haiku-4.5/01-json-store/src/store.py:25-39
temp_path = self.store_path.with_suffix(self.store_path.suffix + ".tmp")
content = ""
if self.store_path.exists():
    with open(self.store_path, "r") as f:
        content = f.read()
with open(temp_path, "w") as f:
    if content:
        f.write(content)
    f.write(line + "\n")
os.replace(temp_path, self.store_path)
```

### 02-retry - Score: 88/100

**Correctness:** Correct async retry decorator with configurable exception filtering, exponential backoff, optional max delay, numeric/callable jitter, and explicit `asyncio.CancelledError` propagation.

**Tests:** 4/4 pass. Tests cover success after retries, non-retryable exceptions, cancellation, and callable jitter. Coverage is thin for validation paths, `attempts=1`, `max_delay`, and numeric jitter.

**Scope:** Full requested implementation is present.

**Defects:**

1. Numeric jitter is additive (`base_delay + random.uniform(...)`), which can sleep up to 2x the base delay for `jitter=1.0`. This may be acceptable, but it is undocumented and not tested.
2. Tests require `pytest-asyncio`, but this result did not declare it in `pyproject.toml`; the local environment happened to have it installed.
3. Provenance/benchmark independence concern: `agent.log` shows this implementation read `results/mai-code-1.1-flash/02-retry/src/retry.py` and its tests before creating its own. The final `retry.py` and `test_retry.py` are byte-for-byte identical to the `mai-code-1.1-flash` result.

**Evidence:**

```python
# results/claude-haiku-4.5/02-retry/src/retry.py:32-40
def _apply_jitter(base_delay: float, jitter: float | Callable[[float], float] | None) -> float:
    ...
    return max(0.0, base_delay + random.uniform(0.0, base_delay * jitter))
```

```text
diff -u results/claude-haiku-4.5/02-retry/src/retry.py \
        results/mai-code-1.1-flash/02-retry/src/retry.py
# no output
```

### 03-cli - Score: 82/100

**Correctness:** Provides argparse `put`, `get`, and `list`, stable JSON output via `sort_keys=True`, configurable store path, and useful basic exit codes. Direct `python -m src.cli` invocations work.

**Tests:** 27/27 pass. Coverage is broad, but mostly unit-level or patched `sys.argv`; there are no subprocess tests of the installed/module CLI path.

**Scope:** Full requested CLI surface is present.

**Defects:**

1. JSON `null` values cannot be retrieved through the CLI: `put n null` succeeds, but `get n` returns `not_found` with exit code 1 because `cmd_get` treats `None` as missing.
2. The bundled store repeats the task-01 rewrite-not-append implementation, so CLI persistence inherits the append-only flaw.
3. Exit code `1` is used for both not-found and operational errors; still useful, but less precise than distinct error codes.

**Evidence:**

```python
# results/claude-haiku-4.5/03-cli/src/cli.py:41-49
value = store.get(key)
if value is None:
    output_json({"status": "not_found", "key": key})
    return 1
```

Focused probe:

```text
python -m src.cli --store /tmp/s.jsonl put n null -> 0 {"key": "n", "status": "ok"}
python -m src.cli --store /tmp/s.jsonl get n      -> 1 {"key": "n", "status": "not_found"}
```

## mai-code-1.1-flash

### 01-json-store - Score: 86/100

**Correctness:** Implements a real append-only JSONL store using `O_APPEND`, handles partial `os.write` risk in task 03 and basic writes in task 01, uses `fsync`, supports latest-write-wins `get`, prefix listing, and skips malformed JSON lines.

**Tests:** 4/4 pass. Tests cover basic round trip, latest value, corrupted tail, and invalid JSON lines, but omit many edge cases covered by the haiku suite.

**Scope:** Core API is present. The exact `list(prefix)` return shape is underspecified in `tasks/01-json-store.md`; this implementation returns sorted keys rather than key/value pairs.

**Defects:**

1. `list(prefix)` returns only keys. If consumers expect listed values, this is an API gap; if `list` means key listing, it is acceptable.
2. Tests are thin: no coverage for empty stores, complex values, `None`, directory creation, or many prefix cases.
3. Extra root-level `store.py` exists beside `src/store.py`, which is an implementation artifact and could confuse manual imports, though tests import `src.store`.

**Evidence:**

```python
# results/mai-code-1.1-flash/01-json-store/src/store.py:49-62
fd = os.open(self.path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
try:
    os.write(fd, encoded)
    os.fsync(fd)
finally:
    os.close(fd)

def list(self, prefix: str = "") -> list[str]:
    state = self._read_state()
    matching = [k for k in state if k.startswith(prefix)]
    return sorted(matching)
```

### 02-retry - Score: 90/100

**Correctness:** Correct async retry decorator with exponential backoff, jitter injection, cancellation propagation, configurable exception filtering, validation, and typed signature preservation.

**Tests:** 4/4 pass. Tests cover the main behavior but not all parameter validation and edge cases.

**Scope:** Full requested implementation is present.

**Defects:**

1. Numeric jitter is additive and undocumented, as in the haiku copy.
2. Test suite is minimal for a retry primitive: no `max_delay`, `attempts=1`, invalid exception specs, negative inputs, or non-async callable misuse coverage.

**Evidence:**

```python
# results/mai-code-1.1-flash/02-retry/src/retry.py:80-97
for attempt in range(1, attempts + 1):
    try:
        return await func(*args, **kwargs)
    except asyncio.CancelledError:
        raise
    except Exception as exc:
        if not isinstance(exc, normalized):
            raise
        if attempt == attempts:
            raise
        wait = delay
        if max_delay is not None:
            wait = min(wait, max_delay)
        wait = _apply_jitter(wait, jitter)
        await _sleep_for(wait, sleep_fn)
```

### 03-cli - Score: 85/100

**Correctness:** Provides working argparse `put`, `get`, and `list`; stable compact JSON; direct subprocess tests; distinct exit code 3 for missing keys; and correct handling of JSON `null` via a sentinel default.

**Tests:** 3/3 pass. They are realistic subprocess tests, but cover only the happy path, JSON number handling, missing key, and one prefix case.

**Scope:** Full requested CLI surface is present.

**Defects:**

1. `list` emits only `{"keys":[...]}`. This is consistent with its store, but less informative if the expected CLI list output is key/value data.
2. `put` has both positional `value` and `--value`; if both are provided, `--value` silently wins. That is surprising CLI behavior.
3. Broad `except Exception` around the whole CLI collapses all operational failures to a JSON error code 1. That is acceptable for a CLI boundary, but it hides error classes and has no tests.
4. Test suite is very small and does not cover environment `STORE_PATH`, duplicate writes, empty list, `--value`, invalid invocations, or corruption tolerance through CLI.

**Evidence:**

```python
# results/mai-code-1.1-flash/03-cli/src/cli.py:42-45, 64-84
put_parser.add_argument("value", nargs="?", help="literal value to store; defaults to --value when provided")
put_parser.add_argument("--value", dest="value_opt", help="literal value to store")
...
raw_value = args.value_opt if args.value_opt is not None else args.value
...
if args.command == "list":
    prefix = args.prefix_opt if args.prefix_opt is not None else args.prefix
    _emit_json({"keys": store.list(prefix)})
```

Focused probe:

```text
python -m src.cli --path /tmp/s.jsonl put n null -> 0 {"key":"n","value":null}
python -m src.cli --path /tmp/s.jsonl get n      -> 0 {"key":"n","value":null}
python -m src.cli --path /tmp/s.jsonl list       -> 0 {"keys":["n"]}
```

## Cross-model observations

1. `claude-haiku-4.5/02-retry` is not independent from `mai-code-1.1-flash/02-retry`: the haiku agent log shows it read the mai implementation/tests, and the final files are identical.
2. Haiku wrote much broader self-tests for tasks 01 and 03, but missed important integration behavior such as CLI `null` retrieval.
3. Mai implemented stronger append durability (`O_APPEND` + `fsync`) and stronger CLI subprocess tests, but its suites are much smaller overall.
4. The task specs are intentionally terse. `list(prefix)` output shape is not explicit, so I penalized key-only listing lightly and framed it as a compatibility risk rather than a definite failure.
