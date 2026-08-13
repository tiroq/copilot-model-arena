"""Append-only JSONL store with atomic writes and corruption tolerance."""

import json
import os
from pathlib import Path
from typing import Any, Iterator, Optional


class JSONLStore:
    """Append-only JSONL store with atomic writes, get, put, list operations."""

    def __init__(self, store_path: str):
        """Initialize the store at the given path."""
        self.store_path = Path(store_path)
        self.store_path.parent.mkdir(parents=True, exist_ok=True)

    def put(self, key: str, value: Any) -> None:
        """
        Atomically append a key-value pair to the store.
        Uses atomic write pattern: write to temp file, then rename.
        """
        entry = {key: value}
        line = json.dumps(entry)

        temp_path = self.store_path.with_suffix(self.store_path.suffix + ".tmp")

        # Read existing content and write to temp file
        content = ""
        if self.store_path.exists():
            with open(self.store_path, "r") as f:
                content = f.read()

        # Append new line to temp file
        with open(temp_path, "w") as f:
            if content:
                f.write(content)
            f.write(line + "\n")

        os.replace(temp_path, self.store_path)

    def get(self, key: str) -> Optional[Any]:
        """
        Get the most recent value for a key from the store.
        Returns None if key not found. Tolerates corruption by skipping bad lines.
        """
        if not self.store_path.exists():
            return None

        last_value = None
        found = False

        with open(self.store_path, "r") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue

                try:
                    entry = json.loads(line)
                    if key in entry:
                        last_value = entry[key]
                        found = True
                except (json.JSONDecodeError, ValueError):
                    # Skip corrupted lines
                    continue

        return last_value if found else None

    def list(self, prefix: str = "") -> Iterator[tuple[str, Any]]:
        """
        List all key-value pairs with keys matching the prefix.
        Returns (key, value) tuples with most recent value per key.
        Tolerates corruption by skipping bad lines.
        """
        if not self.store_path.exists():
            return iter([])

        store = {}

        with open(self.store_path, "r") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue

                try:
                    entry = json.loads(line)
                    for k, v in entry.items():
                        if k.startswith(prefix):
                            store[k] = v
                except (json.JSONDecodeError, ValueError):
                    # Skip corrupted lines
                    continue

        return iter(store.items())
