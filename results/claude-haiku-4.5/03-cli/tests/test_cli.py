"""Tests for CLI and JSONLStore."""

import json
import os
import pytest
import tempfile
from pathlib import Path
from unittest.mock import patch

from src.cli import (
    cmd_put,
    cmd_get,
    cmd_list,
    load_json_value,
    output_json,
    main,
)
from src.store import JSONLStore


class TestJSONLStore:
    """Tests for JSONLStore class."""

    def test_put_and_get(self):
        """Test putting and getting a key-value pair."""
        with tempfile.TemporaryDirectory() as tmpdir:
            store_path = os.path.join(tmpdir, "test.jsonl")
            store = JSONLStore(store_path)
            
            store.put("key1", "value1")
            assert store.get("key1") == "value1"

    def test_get_nonexistent_key(self):
        """Test getting a key that doesn't exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            store_path = os.path.join(tmpdir, "test.jsonl")
            store = JSONLStore(store_path)
            
            assert store.get("nonexistent") is None

    def test_put_overwrites_latest(self):
        """Test that put overwrites the latest value of a key."""
        with tempfile.TemporaryDirectory() as tmpdir:
            store_path = os.path.join(tmpdir, "test.jsonl")
            store = JSONLStore(store_path)
            
            store.put("key1", "value1")
            store.put("key1", "value2")
            assert store.get("key1") == "value2"

    def test_put_json_values(self):
        """Test storing JSON objects and arrays."""
        with tempfile.TemporaryDirectory() as tmpdir:
            store_path = os.path.join(tmpdir, "test.jsonl")
            store = JSONLStore(store_path)
            
            obj = {"a": 1, "b": 2}
            arr = [1, 2, 3]
            
            store.put("obj", obj)
            store.put("arr", arr)
            
            assert store.get("obj") == obj
            assert store.get("arr") == arr

    def test_list_empty_store(self):
        """Test listing from an empty store."""
        with tempfile.TemporaryDirectory() as tmpdir:
            store_path = os.path.join(tmpdir, "test.jsonl")
            store = JSONLStore(store_path)
            
            items = list(store.list())
            assert items == []

    def test_list_all_items(self):
        """Test listing all items from store."""
        with tempfile.TemporaryDirectory() as tmpdir:
            store_path = os.path.join(tmpdir, "test.jsonl")
            store = JSONLStore(store_path)
            
            store.put("key1", "value1")
            store.put("key2", "value2")
            store.put("key3", "value3")
            
            items = sorted(store.list())
            assert len(items) == 3
            assert items[0] == ("key1", "value1")
            assert items[1] == ("key2", "value2")
            assert items[2] == ("key3", "value3")

    def test_list_with_prefix(self):
        """Test listing items filtered by prefix."""
        with tempfile.TemporaryDirectory() as tmpdir:
            store_path = os.path.join(tmpdir, "test.jsonl")
            store = JSONLStore(store_path)
            
            store.put("user:alice", "data1")
            store.put("user:bob", "data2")
            store.put("config:timeout", 30)
            
            items = sorted(store.list("user:"))
            assert len(items) == 2
            assert ("user:alice", "data1") in items
            assert ("user:bob", "data2") in items

    def test_corruption_tolerance(self):
        """Test that store tolerates corrupted lines."""
        with tempfile.TemporaryDirectory() as tmpdir:
            store_path = os.path.join(tmpdir, "test.jsonl")
            store = JSONLStore(store_path)
            
            store.put("key1", "value1")
            
            # Add a corrupted line manually
            with open(store_path, "a") as f:
                f.write("{ INVALID JSON }\n")
            
            store.put("key2", "value2")
            
            # Should still get valid entries
            assert store.get("key1") == "value1"
            assert store.get("key2") == "value2"


class TestLoadJsonValue:
    """Tests for load_json_value function."""

    def test_load_json_string(self):
        """Test loading valid JSON string."""
        assert load_json_value('"hello"') == "hello"

    def test_load_json_number(self):
        """Test loading valid JSON number."""
        assert load_json_value('42') == 42

    def test_load_json_object(self):
        """Test loading valid JSON object."""
        assert load_json_value('{"a": 1}') == {"a": 1}

    def test_load_json_array(self):
        """Test loading valid JSON array."""
        assert load_json_value('[1, 2, 3]') == [1, 2, 3]

    def test_load_plain_string(self):
        """Test that plain strings are returned as-is."""
        assert load_json_value('hello') == "hello"

    def test_load_bool(self):
        """Test loading boolean values."""
        assert load_json_value('true') is True
        assert load_json_value('false') is False


class TestCLICommands:
    """Tests for CLI commands."""

    def test_cmd_put_string(self, capsys):
        """Test put command with string value."""
        with tempfile.TemporaryDirectory() as tmpdir:
            store_path = os.path.join(tmpdir, "test.jsonl")
            store = JSONLStore(store_path)
            
            result = cmd_put(store, "key1", "value1")
            assert result == 0
            
            captured = capsys.readouterr()
            output = json.loads(captured.out)
            assert output["status"] == "ok"
            assert output["key"] == "key1"

    def test_cmd_put_json(self, capsys):
        """Test put command with JSON value."""
        with tempfile.TemporaryDirectory() as tmpdir:
            store_path = os.path.join(tmpdir, "test.jsonl")
            store = JSONLStore(store_path)
            
            result = cmd_put(store, "key1", '{"a": 1}')
            assert result == 0
            
            captured = capsys.readouterr()
            output = json.loads(captured.out)
            assert output["status"] == "ok"

    def test_cmd_get_exists(self, capsys):
        """Test get command for existing key."""
        with tempfile.TemporaryDirectory() as tmpdir:
            store_path = os.path.join(tmpdir, "test.jsonl")
            store = JSONLStore(store_path)
            store.put("key1", "value1")
            
            result = cmd_get(store, "key1")
            assert result == 0
            
            captured = capsys.readouterr()
            output = json.loads(captured.out)
            assert output["status"] == "ok"
            assert output["key"] == "key1"
            assert output["value"] == "value1"

    def test_cmd_get_not_found(self, capsys):
        """Test get command for non-existent key."""
        with tempfile.TemporaryDirectory() as tmpdir:
            store_path = os.path.join(tmpdir, "test.jsonl")
            store = JSONLStore(store_path)
            
            result = cmd_get(store, "nonexistent")
            assert result == 1
            
            captured = capsys.readouterr()
            output = json.loads(captured.out)
            assert output["status"] == "not_found"

    def test_cmd_list_empty(self, capsys):
        """Test list command on empty store."""
        with tempfile.TemporaryDirectory() as tmpdir:
            store_path = os.path.join(tmpdir, "test.jsonl")
            store = JSONLStore(store_path)
            
            result = cmd_list(store)
            assert result == 0
            
            captured = capsys.readouterr()
            output = json.loads(captured.out)
            assert output["status"] == "ok"
            assert output["items"] == {}

    def test_cmd_list_all(self, capsys):
        """Test list command returns all items."""
        with tempfile.TemporaryDirectory() as tmpdir:
            store_path = os.path.join(tmpdir, "test.jsonl")
            store = JSONLStore(store_path)
            store.put("key1", "value1")
            store.put("key2", "value2")
            
            result = cmd_list(store)
            assert result == 0
            
            captured = capsys.readouterr()
            output = json.loads(captured.out)
            assert output["status"] == "ok"
            assert output["items"]["key1"] == "value1"
            assert output["items"]["key2"] == "value2"

    def test_cmd_list_with_prefix(self, capsys):
        """Test list command with prefix filter."""
        with tempfile.TemporaryDirectory() as tmpdir:
            store_path = os.path.join(tmpdir, "test.jsonl")
            store = JSONLStore(store_path)
            store.put("user:alice", "data1")
            store.put("user:bob", "data2")
            store.put("config:timeout", 30)
            
            result = cmd_list(store, "user:")
            assert result == 0
            
            captured = capsys.readouterr()
            output = json.loads(captured.out)
            assert output["status"] == "ok"
            assert len(output["items"]) == 2
            assert "user:alice" in output["items"]
            assert "user:bob" in output["items"]


class TestCLIMain:
    """Tests for main CLI entry point."""

    def test_put_via_cli(self):
        """Test put command via main CLI."""
        with tempfile.TemporaryDirectory() as tmpdir:
            store_path = os.path.join(tmpdir, "test.jsonl")
            
            with patch("sys.argv", ["cli", "--store", store_path, "put", "key1", "value1"]):
                result = main()
                assert result == 0
            
            store = JSONLStore(store_path)
            assert store.get("key1") == "value1"

    def test_get_via_cli(self):
        """Test get command via main CLI."""
        with tempfile.TemporaryDirectory() as tmpdir:
            store_path = os.path.join(tmpdir, "test.jsonl")
            store = JSONLStore(store_path)
            store.put("key1", "value1")
            
            with patch("sys.argv", ["cli", "--store", store_path, "get", "key1"]):
                result = main()
                assert result == 0

    def test_get_nonexistent_via_cli(self):
        """Test get command for non-existent key via main CLI."""
        with tempfile.TemporaryDirectory() as tmpdir:
            store_path = os.path.join(tmpdir, "test.jsonl")
            
            with patch("sys.argv", ["cli", "--store", store_path, "get", "nonexistent"]):
                result = main()
                assert result == 1

    def test_list_via_cli(self):
        """Test list command via main CLI."""
        with tempfile.TemporaryDirectory() as tmpdir:
            store_path = os.path.join(tmpdir, "test.jsonl")
            store = JSONLStore(store_path)
            store.put("key1", "value1")
            
            with patch("sys.argv", ["cli", "--store", store_path, "list"]):
                result = main()
                assert result == 0

    def test_list_with_prefix_via_cli(self):
        """Test list command with prefix via main CLI."""
        with tempfile.TemporaryDirectory() as tmpdir:
            store_path = os.path.join(tmpdir, "test.jsonl")
            store = JSONLStore(store_path)
            store.put("user:alice", "data1")
            store.put("config:timeout", 30)
            
            with patch("sys.argv", ["cli", "--store", store_path, "list", "--prefix", "user:"]):
                result = main()
                assert result == 0

    def test_default_store_path(self):
        """Test that default store path is used."""
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("src.cli.JSONLStore") as mock_store_class:
                mock_store = mock_store_class.return_value
                mock_store.get.return_value = None
                
                with patch("sys.argv", ["cli", "get", "key1"]):
                    try:
                        main()
                    except SystemExit:
                        pass
                
                # Verify default path was used
                mock_store_class.assert_called_once_with(".store.jsonl")
