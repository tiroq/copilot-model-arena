# CLI Implementation Summary

## Task
Implement `src/cli.py`: argparse CLI around the store with put/get/list commands, stable JSON output, useful exit codes, and tests.

## Files Created

1. **src/store.py** - JSONLStore implementation (append-only JSONL store with atomic writes)
2. **src/cli.py** - CLI interface with argparse
3. **tests/test_cli.py** - Comprehensive test suite
4. **src/__init__.py** - Package initialization
5. **tests/__init__.py** - Test package initialization

## Implementation Details

### CLI Features
- **Commands**: `put`, `get`, `list`
- **Options**:
  - `--store PATH` - Specify store file location (default: `.store.jsonl`)
  - `--prefix PATTERN` - Filter keys by prefix (list command only)
- **Output**: Stable JSON with sorted keys
- **Exit Codes**:
  - `0` - Success
  - `1` - Failure (key not found, errors, etc.)

### Store API
- **put(key, value)** - Add/update key-value pair
- **get(key)** - Retrieve most recent value for key
- **list(prefix)** - List all key-value pairs, optionally filtered by prefix

## Test Results

```
============================= test session starts ==============================
platform darwin -- Python 3.14.6, pytest-9.1.1, pluggy-1.6.0
rootdir: /Users/mysterx/dev/copilot-model-arena/results/claude-haiku-4.5/03-cli
configfile: pyproject.toml

tests/test_cli.py::TestJSONLStore::test_put_and_get PASSED               [  3%]
tests/test_cli.py::TestJSONLStore::test_get_nonexistent_key PASSED       [  7%]
tests/test_cli.py::TestJSONLStore::test_put_overwrites_latest PASSED     [ 11%]
tests/test_cli.py::TestJSONLStore::test_put_json_values PASSED           [ 14%]
tests/test_cli.py::TestJSONLStore::test_list_empty_store PASSED          [ 18%]
tests/test_cli.py::TestJSONLStore::test_list_all_items PASSED            [ 22%]
tests/test_cli.py::TestJSONLStore::test_list_with_prefix PASSED          [ 25%]
tests/test_cli.py::TestJSONLStore::test_corruption_tolerance PASSED      [ 29%]
tests/test_cli.py::TestLoadJsonValue::test_load_json_string PASSED       [ 33%]
tests/test_cli.py::TestLoadJsonValue::test_load_json_number PASSED       [ 37%]
tests/test_cli.py::TestLoadJsonValue::test_load_json_object PASSED       [ 40%]
tests/test_cli.py::TestLoadJsonValue::test_load_json_array PASSED        [ 44%]
tests/test_cli.py::TestLoadJsonValue::test_load_plain_string PASSED      [ 48%]
tests/test_cli.py::TestLoadJsonValue::test_load_bool PASSED              [ 51%]
tests/test_cli.py::TestCLICommands::test_cmd_put_string PASSED           [ 55%]
tests/test_cli.py::TestCLICommands::test_cmd_put_json PASSED             [ 59%]
tests/test_cli.py::TestCLICommands::test_cmd_get_exists PASSED           [ 62%]
tests/test_cli.py::TestCLICommands::test_cmd_get_not_found PASSED        [ 66%]
tests/test_cli.py::TestCLICommands::test_cmd_list_empty PASSED           [ 70%]
tests/test_cli.py::TestCLICommands::test_cmd_list_all PASSED             [ 74%]
tests/test_cli.py::TestCLICommands::test_cmd_list_with_prefix PASSED     [ 77%]
tests/test_cli.py::TestCLIMain::test_put_via_cli PASSED                  [ 81%]
tests/test_cli.py::TestCLIMain::test_get_via_cli PASSED                  [ 85%]
tests/test_cli.py::TestCLIMain::test_get_nonexistent_via_cli PASSED      [ 88%]
tests/test_cli.py::TestCLIMain::test_list_via_cli PASSED                 [ 92%]
tests/test_cli.py::TestCLIMain::test_list_with_prefix_via_cli PASSED     [ 96%]
tests/test_cli.py::TestCLIMain::test_default_store_path PASSED           [100%]

============================== 27 passed in 0.05s ==============================
```

## CLI Usage Examples

### Put Command
```bash
$ python -m src.cli --store /tmp/test_store.jsonl put user:alice '{"name": "Alice", "age": 30}'
{"key": "user:alice", "status": "ok"}
```

### Get Command
```bash
$ python -m src.cli --store /tmp/test_store.jsonl get user:alice
{"key": "user:alice", "status": "ok", "value": {"age": 30, "name": "Alice"}}
```

### List All Items
```bash
$ python -m src.cli --store /tmp/test_store.jsonl list
{"items": {"config:timeout": 30, "user:alice": {"age": 30, "name": "Alice"}, "user:bob": {"age": 25, "name": "Bob"}}, "status": "ok"}
```

### List with Prefix Filter
```bash
$ python -m src.cli --store /tmp/test_store.jsonl list --prefix user:
{"items": {"user:alice": {"age": 30, "name": "Alice"}, "user:bob": {"age": 25, "name": "Bob"}}, "status": "ok"}
```

### Exit Codes
```bash
$ python -m src.cli --store /tmp/test_store.jsonl get nonexistent
{"key": "nonexistent", "status": "not_found"}
$ echo $?
1
```

## Test Coverage

- **Store Operations**: put, get, list, prefix filtering, corruption tolerance
- **Value Types**: strings, numbers, objects, arrays, booleans
- **CLI Commands**: put, get, list with all options
- **Exit Codes**: success (0) and failure cases (1)
- **JSON Output**: stable/sorted keys
- **Error Handling**: not found, invalid input

## Key Features

✅ Append-only JSONL store with atomic writes  
✅ Put/get/list operations  
✅ Prefix filtering for list command  
✅ Flexible JSON input (JSON values or plain strings)  
✅ Stable JSON output (sorted keys)  
✅ Useful exit codes  
✅ Corruption tolerance (skips bad lines)  
✅ Comprehensive test suite (27 tests, 100% pass rate)
