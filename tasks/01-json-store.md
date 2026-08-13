# Task 01: JSON Store

Implement `src/store.py`: an append-only JSONL key-value store.

## Required API

```python
from typing import Any, Iterator

MISSING = object()

class JsonlStore:
    """Append-only JSONL key-value store with atomic writes."""
    
    def __init__(self, store_path: str | pathlib.Path) -> None:
        """Initialize store at the given path."""
        ...
    
    def put(self, key: str, value: Any) -> None:
        """Store a value for the given key.
        
        - Appends exactly one JSONL record to the file (must not rewrite existing records)
        - Must use append-mode or O_APPEND semantics
        - Latest write wins for duplicate keys
        - value may be any JSON-serializable type including None
        """
        ...
    
    def get(self, key: str, default: Any = MISSING) -> Any:
        """Retrieve the value for the given key.
        
        - Returns the value from the most recent put() for this key
        - If key is not found and default is MISSING, raises KeyError
        - If key is not found and default is provided, returns default
        - Must distinguish between stored None and missing key
        """
        ...
    
    def list(self, prefix: str = "") -> Iterator[tuple[str, Any]]:
        """List all key-value pairs whose keys start with prefix.
        
        - Returns an iterator of (key, value) tuples (NOT keys alone)
        - Results must be in deterministic order
        - For duplicate keys, only the latest value is included
        - Empty prefix returns all keys
        """
        ...
```

## Required Behavior

1. **File Format**: JSONL (JSON Lines), one record per line
   - Each line must be valid JSON representing a single key-value pair
   - Suggested format: `{"key": "...", "value": ...}` per line

2. **Append-Only Semantics**:
   - Each `put()` must append to the file, never rewrite existing records
   - Use `open(path, "a")` or equivalent O_APPEND
   - Do NOT read entire file and rewrite it on every put()

3. **Latest Write Wins**:
   - If the same key is written multiple times, `get()` returns the most recent value
   - `list()` includes only the most recent value for each key

4. **None Handling**:
   - `None` is a valid stored value
   - Must distinguish between `get("key")` where key→None vs key not found
   - Use MISSING sentinel to detect missing keys

5. **Corruption Tolerance**:
   - `get()` and `list()` must skip invalid JSON lines without crashing
   - Empty lines must be ignored
   - Log or silently skip malformed records

6. **Durability**:
   - Writes should be durable according to OS guarantees
   - Optional: Use fsync/flush for stronger durability guarantees

## Required Tests

Add comprehensive pytest tests in `tests/test_store.py`:

- Basic put/get round-trip for various value types (str, int, float, bool, None, list, dict)
- Get with default value
- Get missing key raises KeyError when no default
- Put and retrieve None value explicitly
- List with empty prefix returns all keys
- List with prefix filters correctly
- List returns (key, value) tuples, not keys alone
- Latest write wins for duplicate keys
- Corruption tolerance: malformed JSON lines are skipped
- Empty lines are ignored
- Deterministic list ordering
- Empty store behavior

## Scope Restrictions

- Implement only the store in `src/store.py`
- Add or update tests in `tests/test_store.py`
- Do not modify other files unless required for imports
- Do not add CLI or web interface
- Do not add features beyond the specified API
