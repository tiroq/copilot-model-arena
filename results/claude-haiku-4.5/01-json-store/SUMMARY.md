# JSON Store Implementation Summary

## Task
Implement `src/store.py`: an append-only JSONL store with atomic writes, `put`, `get`, `list(prefix)` operations and corruption-tolerant reads. Add pytest tests.

## Implementation

### Files Created

1. **src/store.py** - Core JSONL store implementation
   - `JSONLStore` class with the following methods:
     - `put(key, value)`: Atomically append key-value pairs to the store using temp file + rename pattern
     - `get(key)`: Retrieve the most recent value for a key, returns None if not found
     - `list(prefix)`: List all key-value pairs with keys matching a prefix, returns most recent value per key
   - Features:
     - Append-only architecture
     - Atomic writes using temporary files
     - Corruption tolerance: skips malformed JSON lines while reading
     - Handles empty lines gracefully
     - Supports complex data types (dicts, lists, numbers, None, etc.)

2. **tests/test_store.py** - Comprehensive test suite with 17 tests covering:
   - Basic put/get operations
   - Multiple keys handling
   - Non-existent key/store handling
   - Complex value types
   - Prefix filtering with list()
   - Corruption tolerance (malformed JSON lines)
   - Atomic write verification
   - Empty line handling
   - Special characters in keys and values

## Test Results

### Command
```bash
python -m pytest tests/test_store.py -v
```

### Results
```
============================= test session starts ==============================
platform darwin -- Python 3.14.6, pytest-9.1.1, pluggy-1.6.0
collecting ... collected 17 items

tests/test_store.py::test_put_and_get_basic PASSED                       [  5%]
tests/test_store.py::test_get_nonexistent_key PASSED                     [ 11%]
tests/test_store.py::test_get_nonexistent_store PASSED                   [ 17%]
tests/test_store.py::test_put_overwrites_previous_value PASSED           [ 23%]
tests/test_store.py::test_put_multiple_keys PASSED                       [ 29%]
tests/test_store.py::test_put_complex_values PASSED                      [ 35%]
tests/test_store.py::test_list_empty_store PASSED                        [ 41%]
tests/test_store.py::test_list_with_prefix PASSED                        [ 47%]
tests/test_store.py::test_list_without_prefix PASSED                     [ 52%]
tests/test_store.py::test_list_returns_most_recent_value PASSED          [ 58%]
tests/test_store.py::test_list_prefix_no_matches PASSED                  [ 64%]
tests/test_store.py::test_corruption_tolerance_get PASSED                [ 70%]
tests/test_store.py::test_corruption_tolerance_list PASSED               [ 76%]
tests/test_store.py::test_atomic_writes PASSED                           [ 82%]
tests/test_store.py::test_empty_lines_ignored PASSED                     [ 88%]
tests/test_store.py::test_numbers_and_null_values PASSED                 [ 94%]
tests/test_store.py::test_special_characters_in_keys_and_values PASSED   [100%]

============================== 17 passed in 0.03s ==============================
```

## Status
✅ **COMPLETE** - All 17 tests passing
