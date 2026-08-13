# Task 03: CLI for JSON Store

Implement `src/cli.py`: a command-line interface around the JSON store from Task 01.

## Required Commands

The CLI must support three subcommands: `put`, `get`, and `list`.

```bash
python -m src.cli put <key> <value> [--store PATH]
python -m src.cli get <key> [--default VALUE] [--store PATH]
python -m src.cli list [--prefix PREFIX] [--store PATH]
```

## Exact Behavior

### `put` command

```bash
python -m src.cli put <key> <value> [--store PATH]
```

- Stores `<value>` under `<key>` in the store
- `<value>` is parsed as JSON if valid, otherwise stored as a plain string
- Output: JSON object with status
  ```json
  {"status": "ok", "key": "...", "value": ...}
  ```
- Exit code: `0` on success, `1` on error
- Store path: `--store` argument or environment variable `STORE_PATH` or default `store.jsonl`

### `get` command

```bash
python -m src.cli get <key> [--default VALUE] [--store PATH]
```

- Retrieves value for `<key>` from the store
- If key exists, output:
  ```json
  {"status": "ok", "key": "...", "value": ...}
  ```
  Exit code: `0`
- If key does not exist:
  - With `--default VALUE`: output `{"status": "ok", "key": "...", "value": ...}` with default value, exit code `0`
  - Without `--default`: output `{"status": "error", "message": "Key not found: ..."}`, exit code `2`
- Store path: same precedence as `put`

### `list` command

```bash
python -m src.cli list [--prefix PREFIX] [--store PATH]
```

- Lists all keys (and values) whose keys start with `prefix`
- If `--prefix` is omitted, list all keys
- Output: JSON object with list of key-value pairs
  ```json
  {"status": "ok", "items": [{"key": "...", "value": ...}, ...]}
  ```
- Exit code: `0` on success, `1` on error
- Store path: same precedence as `put`

## JSON Output Requirements

- All output must be valid JSON
- Use `json.dumps()` with `sort_keys=True` for stability
- No pretty-printing (single-line JSON)
- Include newline after JSON object

## Exit Codes

- `0`: Success
- `1`: General error (invalid arguments, I/O error, etc.)
- `2`: Key not found (only for `get` without `--default`)

## Store Path Precedence

1. `--store PATH` command-line argument (highest priority)
2. `STORE_PATH` environment variable
3. Default: `store.jsonl` in current directory

## Argument Parsing

- Use `argparse` for CLI parsing
- Each subcommand should have its own subparser
- Use clear help messages
- Invalid arguments should print usage and exit with code `1`

## Value Parsing

For `put <value>`:
- Try `json.loads(value)` first
- If JSON parsing succeeds, store the parsed value (preserving type)
- If JSON parsing fails, store `value` as a plain string
- Examples:
  - `put key "123"` → stores integer `123`
  - `put key "hello"` → stores string `"hello"`
  - `put key "true"` → stores boolean `true`
  - `put key '{"a":1}'` → stores dict `{"a": 1}`
  - `put key null` → stores `None`

For `get --default VALUE`:
- Same JSON parsing logic as `put`

## Required Tests

Add comprehensive tests in `tests/test_cli.py`:

- All three commands with various inputs
- JSON output validation (valid JSON, correct schema)
- Exit code verification for each command
- Key not found without default (exit 2)
- Key not found with default (exit 0)
- Store path from `--store` argument
- Store path from environment variable
- Value type preservation (int, bool, None, dict, list, string)
- List with prefix filtering
- List with empty prefix (all keys)
- Invalid arguments (exit 1)

Tests should use subprocess to invoke the CLI as an external command:

```python
import subprocess
import json

result = subprocess.run(
    ["python", "-m", "src.cli", "put", "key", "value"],
    capture_output=True,
    text=True,
)
assert result.returncode == 0
output = json.loads(result.stdout)
assert output["status"] == "ok"
```

## Scope Restrictions

- Implement only the CLI in `src/cli.py`
- Reuse `src/store.py` from Task 01 (do not modify it)
- Add or update tests in `tests/test_cli.py`
- Do not add features beyond the specified commands
- Do not add interactive mode, TUI, or web interface
- Do not modify other files unless required for imports
