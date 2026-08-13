from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Iterator


class Store:
    """Append-only JSONL key-value store with corruption-tolerant reads."""

    def __init__(self, path: str | os.PathLike[str] = "store.jsonl") -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            self.path.touch()

    def _iter_records(self) -> Iterator[tuple[str, Any]]:
        try:
            with self.path.open("r", encoding="utf-8") as handle:
                for raw_line in handle:
                    line = raw_line.strip()
                    if not line:
                        continue
                    try:
                        record = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    if not isinstance(record, dict):
                        continue
                    key = record.get("key")
                    value = record.get("value")
                    if key is None:
                        continue
                    yield str(key), value
        except FileNotFoundError:
            return

    def _read_state(self) -> dict[str, Any]:
        state: dict[str, Any] = {}
        for key, value in self._iter_records():
            state[key] = value
        return state

    def put(self, key: str, value: Any) -> None:
        payload = json.dumps({"key": key, "value": value}, separators=(",", ":"), sort_keys=True)
        encoded = (payload + "\n").encode("utf-8")

        fd = os.open(self.path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
        try:
            os.write(fd, encoded)
            os.fsync(fd)
        finally:
            os.close(fd)

    def get(self, key: str, default: Any = None) -> Any:
        return self._read_state().get(str(key), default)

    def list(self, prefix: str = "") -> list[str]:
        state = self._read_state()
        matching = [k for k in state if k.startswith(prefix)]
        return sorted(matching)


__all__ = ["Store"]
