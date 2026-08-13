# Audit Report — claude-sonnet-4.6

**Auditor model:** claude-sonnet-4.6  
**Date:** 2026-08-13  
**Tasks audited:** 01-json-store, 02-retry, 03-cli  
**Models under review:** claude-haiku-4.5, mai-code-1.1-flash

---

## Summary Table

| Model              | Task           | Score | Tests        | Correctness | Scope |
|--------------------|----------------|-------|--------------|-------------|-------|
| claude-haiku-4.5   | 01-json-store  | 78    | 17/17 ✅     | Partial     | Full  |
| claude-haiku-4.5   | 02-retry       | 90    | 4/4 ✅       | Full        | Full  |
| claude-haiku-4.5   | 03-cli         | 85    | 27/27 ✅     | Full        | Full  |
| mai-code-1.1-flash | 01-json-store  | 72    | 4/4 ✅       | Partial     | Partial |
| mai-code-1.1-flash | 02-retry       | 85    | 4/4 ✅       | Full        | Full  |
| mai-code-1.1-flash | 03-cli         | 80    | 3/3 ✅       | Full        | Partial |

---

## claude-haiku-4.5

### Task 01 — json-store

**Score: 78 / 100**

**Tests:** 17/17 passed (`pytest tests/ -v`)

**Correctness:**  
All operations (`put`, `get`, `list(prefix)`) work correctly. Values round-trip cleanly including complex objects, None, booleans, and special characters. Corruption-tolerant reads skip invalid lines. The JSONL format uses `{key: value}` objects (one per line), which is valid.

**Defects / Concerns:**
- `put()` **is not truly append-only**. Each write reads the entire existing file into memory and rewrites it to a temp file before renaming. For an "append-only JSONL store" this is semantically wrong and O(n) per write. Correct approach would use `O_APPEND` or `open("a")`.
- The atomic-write pattern (temp file + `os.replace`) is implemented correctly in isolation, but it's unnecessary overhead since the rewrite strategy breaks the append-only contract.
- No `fsync` before rename, so data loss is possible on crash.
- `list()` correctly returns `Iterator[tuple[str, Any]]` matching the spec.
- Tests verify the temp file is cleaned up post-write (good).

**Scope:** All three required operations implemented plus corruption tolerance.

**Evidence:**
```python
# src/store.py:28-39 — rewrite-not-append pattern
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

---

### Task 02 — retry

**Score: 90 / 100**

**Tests:** 4/4 passed (`pytest tests/ -v`)

**Correctness:**  
Full correct implementation. Exponential backoff with configurable factor, jitter (numeric or callable), max_delay cap, `CancelledError` propagation, non-retryable exception pass-through, typed with `ParamSpec`/`TypeVar`. The `_sleep_for` helper handles both sync and async sleep callbacks.

**Defects / Concerns:**
- Jitter with numeric value uses `random.uniform(0.0, base_delay * jitter)` which means `jitter=0.0` yields zero jitter ✅, but `jitter=1.0` yields up to 2× base_delay (additive, not replacement). This is a non-standard convention — most libraries replace delay with jitter, not add. Documented nowhere.
- The fallthrough `raise RuntimeError("retry loop exited...")` is defensive but unreachable — minor dead code.
- Test suite is minimal (4 tests). No tests for `max_delay`, `attempts=1`, invalid-argument validation, or numeric jitter semantics.

**Scope:** All required features covered.

---

### Task 03 — cli

**Score: 85 / 100**

**Tests:** 27/27 passed (`pytest tests/ -v`)

**Correctness:**  
`put`, `get`, `list` commands all work. Stable JSON output with `sort_keys=True`. Exit codes: 0 on success, 1 on not-found for `get`. Values are coerced from JSON when valid, else treated as plain strings. `--store` path flag works.

**Defects / Concerns:**
- `get` returning exit code `1` for "not found" is reasonable but conflates "not found" with "error". Using a distinct code (e.g. `3`) would be cleaner, as `mai-code-1.1-flash` demonstrates.
- Test suite is **entirely unit-level** using mocks and direct function calls. No subprocess/integration tests verifying the actual CLI entry point behaves correctly end-to-end.
- `list` returns `{"status":"ok","items":{...}}` (a dict of key→value). This differs from `mai-code-1.1-flash` which returns `{"keys":[...]}`, but haiku's output is richer and more useful.
- The `output_json` helper includes an unused `pretty` parameter.

**Scope:** All three commands, exit codes, JSON output.

---

## mai-code-1.1-flash

### Task 01 — json-store

**Score: 72 / 100**

**Tests:** 4/4 passed (`pytest tests/ -v`)

**Correctness:**  
`put`, `get`, corruption tolerance all correct. Uses `{"key": k, "value": v}` record format (more explicit than haiku's). Truly append-only via `os.O_WRONLY | os.O_CREAT | os.O_APPEND` with `fsync` — correct durability semantics. 

**Defects / Concerns:**
- **`list(prefix)` returns `list[str]` (keys only)**, not `(key, value)` tuples. The task spec says "list(prefix)" should return key-value pairs. This is a spec deviation.
- A stray `store.py` file exists at the package root (`results/mai-code-1.1-flash/01-json-store/store.py`) alongside the correct `src/store.py`. Suggests an editing artifact.
- Test suite is **thin** — only 4 tests covering basic round-trip, update, and corruption. No tests for empty-prefix listing, multiple prefixes, or edge cases like None values.
- `get()` signature has `default=None` parameter which is a reasonable extension but undocumented and not in the task spec.

**Scope:** Core operations implemented; `list` return type deviates from spec.

**Evidence:**
```python
# src/store.py:59-62 — returns keys only, not (key, value) tuples
def list(self, prefix: str = "") -> list[str]:
    state = self._read_state()
    matching = [k for k in state if k.startswith(prefix)]
    return sorted(matching)
```

---

### Task 02 — retry

**Score: 85 / 100**

**Tests:** 4/4 passed (`pytest tests/ -v`)

**Correctness:** Correct implementation. Same quality as claude-haiku-4.5.

**Defects / Concerns:**
- **The `retry.py` implementation is byte-for-byte identical to `claude-haiku-4.5/02-retry/src/retry.py`** (verified with `diff`). This strongly suggests code was shared, copied, or both agents converged on the exact same solution including all identically-named private helpers and comments. The test files are also identical. This reduces the independent-validation value of the benchmark for this task.
- All concerns from haiku's retry audit apply: jitter convention, minimal tests, unreachable RuntimeError.

---

### Task 03 — cli

**Score: 80 / 100**

**Tests:** 3/3 passed (`pytest tests/ -v`)

**Correctness:**  
All three commands work correctly. Integration tests use subprocess (`python -m src.cli`) — this is a stronger test strategy than haiku's unit tests. JSON output is stable (sorted keys, compact separators). `get` on missing key returns exit code `3` with structured `{"code":3,"error":"key not found","key":"..."}` — clear and distinct from error code `1`.

**Defects / Concerns:**
- `list` command output is `{"keys": [...]}` — returns only key names, no values. Less useful than haiku's key-value map output, and inconsistent with the richer store that does track values.
- `put` command accepts value via both positional and `--value` flag, creating a confusing dual-input path; if both are provided, `--value` wins silently.
- Test suite has only 3 tests — minimal coverage. No tests for: empty store listing, `--path` env var override (`STORE_PATH`), duplicate puts/overwrite, or error paths.
- A stray `store.py` at root level (artifact from 01-json-store) is not present here, but `src/store.py` is re-implemented (duplicated from task 01 context), which is expected.

**Scope:** All three commands, exit codes, JSON output. List output less informative than spec implies.

---

## Cross-Cutting Observations

1. **Identical retry.py**: Both models produced byte-for-byte identical `retry.py` and `test_retry.py`. This is unusual and warrants investigation into whether the benchmark seed provided a template or if models shared intermediate artifacts.

2. **Test depth**: claude-haiku-4.5 wrote significantly more tests (48 total across all tasks vs 11 for mai-code-1.1-flash). Haiku's tests cover more edge cases but are unit-level; mai's tests for 03-cli are subprocess-based and more realistic.

3. **Append semantics**: Only mai-code-1.1-flash implemented truly append-only writes. Haiku's "append-only" store rewrites the file on each put.

4. **Spec adherence**: haiku-4.5 adhered more closely to the `list(prefix)` → `(key, value)` iterator contract. mai-code-1.1-flash's `list()` returns keys only.
