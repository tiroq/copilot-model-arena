"""CLI for JSONLStore with argparse and stable JSON output."""

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Optional

from .store import JSONLStore


def load_json_value(value_str: str) -> Any:
    """Parse a JSON value from string, or treat as plain string if not JSON."""
    try:
        return json.loads(value_str)
    except json.JSONDecodeError:
        # If it's not valid JSON, treat it as a plain string
        return value_str


def output_json(data: Any, pretty: bool = False) -> None:
    """Output data as stable JSON (sorted keys)."""
    if pretty:
        print(json.dumps(data, indent=2, sort_keys=True))
    else:
        print(json.dumps(data, sort_keys=True))


def cmd_put(store: JSONLStore, key: str, value_str: str) -> int:
    """Put command: add key-value pair to store."""
    try:
        value = load_json_value(value_str)
        store.put(key, value)
        output_json({"status": "ok", "key": key})
        return 0
    except Exception as e:
        output_json({"status": "error", "message": str(e)})
        return 1


def cmd_get(store: JSONLStore, key: str) -> int:
    """Get command: retrieve value for key from store."""
    try:
        value = store.get(key)
        if value is None:
            output_json({"status": "not_found", "key": key})
            return 1
        output_json({"status": "ok", "key": key, "value": value})
        return 0
    except Exception as e:
        output_json({"status": "error", "message": str(e)})
        return 1


def cmd_list(store: JSONLStore, prefix: str = "") -> int:
    """List command: retrieve all key-value pairs with optional prefix filter."""
    try:
        items = {}
        for key, value in store.list(prefix):
            items[key] = value
        output_json({"status": "ok", "items": items})
        return 0
    except Exception as e:
        output_json({"status": "error", "message": str(e)})
        return 1


def main():
    """Main entry point for CLI."""
    parser = argparse.ArgumentParser(
        description="CLI for append-only JSONL store",
        prog="store-cli"
    )
    
    parser.add_argument(
        "--store",
        type=str,
        default=".store.jsonl",
        help="Path to the JSONL store file (default: .store.jsonl)"
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Command to execute")
    subparsers.required = True
    
    # Put command
    put_parser = subparsers.add_parser("put", help="Add key-value pair to store")
    put_parser.add_argument("key", help="Key to store")
    put_parser.add_argument("value", help="Value to store (JSON or plain string)")
    
    # Get command
    get_parser = subparsers.add_parser("get", help="Retrieve value by key")
    get_parser.add_argument("key", help="Key to retrieve")
    
    # List command
    list_parser = subparsers.add_parser("list", help="List all key-value pairs")
    list_parser.add_argument(
        "--prefix",
        type=str,
        default="",
        help="Filter keys by prefix (default: empty, returns all)"
    )
    
    args = parser.parse_args()
    
    store = JSONLStore(args.store)
    
    if args.command == "put":
        return cmd_put(store, args.key, args.value)
    elif args.command == "get":
        return cmd_get(store, args.key)
    elif args.command == "list":
        return cmd_list(store, args.prefix)
    
    return 1


if __name__ == "__main__":
    sys.exit(main())
