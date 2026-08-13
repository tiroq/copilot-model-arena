from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Any, Sequence

try:
    from .store import Store
except ImportError:  # pragma: no cover - direct script execution fallback.
    from store import Store


def _coerce_value(raw: str) -> Any:
    text = raw.strip()
    if not text:
        return raw
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return raw


def _emit_json(data: Any) -> None:
    print(json.dumps(data, separators=(",", ":"), sort_keys=True, ensure_ascii=False))


def _error(code: int, message: str, **extra: Any) -> int:
    payload = {"error": message, "code": code}
    payload.update(extra)
    _emit_json(payload)
    return code


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="JSONL key-value store CLI")
    parser.add_argument("--path", default=os.environ.get("STORE_PATH", "store.jsonl"), help="path to the JSONL store file")

    subparsers = parser.add_subparsers(dest="command", required=True)

    put_parser = subparsers.add_parser("put", help="store a key/value pair")
    put_parser.add_argument("key")
    put_parser.add_argument("value", nargs="?", help="literal value to store; defaults to --value when provided")
    put_parser.add_argument("--value", dest="value_opt", help="literal value to store")

    get_parser = subparsers.add_parser("get", help="retrieve a value by key")
    get_parser.add_argument("key")

    list_parser = subparsers.add_parser("list", help="list keys with an optional prefix filter")
    list_parser.add_argument("prefix", nargs="?", default="")
    list_parser.add_argument("--prefix", dest="prefix_opt", help="optional key prefix filter")

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        store = Store(args.path)

        if args.command == "put":
            raw_value = args.value_opt if args.value_opt is not None else args.value
            if raw_value is None:
                parser.error("put requires KEY VALUE")
            value = _coerce_value(raw_value)
            store.put(args.key, value)
            _emit_json({"key": args.key, "value": value})
            return 0

        if args.command == "get":
            sentinel = object()
            value = store.get(args.key, sentinel)
            if value is sentinel:
                return _error(3, "key not found", key=args.key)
            _emit_json({"key": args.key, "value": value})
            return 0

        if args.command == "list":
            prefix = args.prefix_opt if args.prefix_opt is not None else args.prefix
            _emit_json({"keys": store.list(prefix)})
            return 0

        parser.error(f"unsupported command: {args.command}")
        return 2
    except Exception as exc:  # pragma: no cover - broad safety net for CLI use.
        return _error(1, str(exc))


if __name__ == "__main__":
    raise SystemExit(main())
