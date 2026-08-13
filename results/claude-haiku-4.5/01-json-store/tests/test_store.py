"""Tests for the JSONL store implementation."""

import json
import tempfile
from pathlib import Path

import pytest

from src.store import JSONLStore


@pytest.fixture
def temp_store():
    """Create a temporary store for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        store_path = Path(tmpdir) / "test.jsonl"
        yield JSONLStore(str(store_path))


def test_put_and_get_basic(temp_store):
    """Test basic put and get operations."""
    temp_store.put("key1", "value1")
    assert temp_store.get("key1") == "value1"


def test_get_nonexistent_key(temp_store):
    """Test getting a non-existent key returns None."""
    assert temp_store.get("nonexistent") is None


def test_get_nonexistent_store(temp_store):
    """Test getting from non-existent store returns None."""
    # Use a store path that doesn't exist yet
    new_store = JSONLStore("/tmp/nonexistent_store_" + str(id(temp_store)) + ".jsonl")
    assert new_store.get("key") is None


def test_put_overwrites_previous_value(temp_store):
    """Test that putting the same key overwrites the previous value."""
    temp_store.put("key1", "value1")
    temp_store.put("key1", "value2")
    assert temp_store.get("key1") == "value2"


def test_put_multiple_keys(temp_store):
    """Test putting multiple different keys."""
    temp_store.put("key1", "value1")
    temp_store.put("key2", "value2")
    temp_store.put("key3", "value3")

    assert temp_store.get("key1") == "value1"
    assert temp_store.get("key2") == "value2"
    assert temp_store.get("key3") == "value3"


def test_put_complex_values(temp_store):
    """Test putting complex values like dicts and lists."""
    data = {"nested": {"key": "value"}, "list": [1, 2, 3]}
    temp_store.put("complex", data)
    assert temp_store.get("complex") == data


def test_list_empty_store(temp_store):
    """Test listing from an empty store."""
    result = list(temp_store.list())
    assert result == []


def test_list_with_prefix(temp_store):
    """Test listing with a prefix filter."""
    temp_store.put("user:1", "Alice")
    temp_store.put("user:2", "Bob")
    temp_store.put("admin:1", "Charlie")

    users = list(temp_store.list("user:"))
    assert len(users) == 2
    assert ("user:1", "Alice") in users
    assert ("user:2", "Bob") in users


def test_list_without_prefix(temp_store):
    """Test listing all keys without prefix."""
    temp_store.put("key1", "value1")
    temp_store.put("key2", "value2")
    temp_store.put("key3", "value3")

    result = list(temp_store.list())
    assert len(result) == 3
    assert ("key1", "value1") in result
    assert ("key2", "value2") in result
    assert ("key3", "value3") in result


def test_list_returns_most_recent_value(temp_store):
    """Test that list returns the most recent value for each key."""
    temp_store.put("key1", "value1")
    temp_store.put("key1", "value2")
    temp_store.put("key1", "value3")

    result = list(temp_store.list())
    assert len(result) == 1
    assert result[0] == ("key1", "value3")


def test_list_prefix_no_matches(temp_store):
    """Test listing with a prefix that matches no keys."""
    temp_store.put("user:1", "Alice")
    result = list(temp_store.list("admin:"))
    assert result == []


def test_corruption_tolerance_get(temp_store):
    """Test that get tolerates corrupted lines in the store."""
    store_path = Path(temp_store.store_path)

    # Write a valid entry, then a corrupted line, then another valid entry
    with open(store_path, "w") as f:
        f.write(json.dumps({"key1": "value1"}) + "\n")
        f.write("this is not valid json\n")
        f.write(json.dumps({"key2": "value2"}) + "\n")

    assert temp_store.get("key1") == "value1"
    assert temp_store.get("key2") == "value2"


def test_corruption_tolerance_list(temp_store):
    """Test that list tolerates corrupted lines in the store."""
    store_path = Path(temp_store.store_path)

    # Write entries with corruption
    with open(store_path, "w") as f:
        f.write(json.dumps({"key1": "value1"}) + "\n")
        f.write("invalid line\n")
        f.write(json.dumps({"key2": "value2"}) + "\n")
        f.write("{incomplete json\n")
        f.write(json.dumps({"key3": "value3"}) + "\n")

    result = list(temp_store.list())
    assert len(result) == 3
    assert ("key1", "value1") in result
    assert ("key2", "value2") in result
    assert ("key3", "value3") in result


def test_atomic_writes(temp_store):
    """Test that puts use atomic writes (temp file + rename)."""
    temp_store.put("key1", "value1")

    # Verify the main file exists and temp file doesn't
    store_path = Path(temp_store.store_path)
    temp_path = store_path.with_suffix(store_path.suffix + ".tmp")

    assert store_path.exists()
    assert not temp_path.exists()


def test_empty_lines_ignored(temp_store):
    """Test that empty lines in the store are handled correctly."""
    store_path = Path(temp_store.store_path)

    with open(store_path, "w") as f:
        f.write(json.dumps({"key1": "value1"}) + "\n")
        f.write("\n")
        f.write("\n")
        f.write(json.dumps({"key2": "value2"}) + "\n")

    result = list(temp_store.list())
    assert len(result) == 2


def test_numbers_and_null_values(temp_store):
    """Test storing various data types."""
    temp_store.put("int", 42)
    temp_store.put("float", 3.14)
    temp_store.put("bool", True)
    temp_store.put("null", None)

    assert temp_store.get("int") == 42
    assert temp_store.get("float") == 3.14
    assert temp_store.get("bool") is True
    assert temp_store.get("null") is None


def test_special_characters_in_keys_and_values(temp_store):
    """Test that special characters are handled correctly."""
    temp_store.put("key/with:special-chars", "value with\nnewlines and \"quotes\"")
    result = temp_store.get("key/with:special-chars")
    assert result == "value with\nnewlines and \"quotes\""
