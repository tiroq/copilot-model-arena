from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Iterator


class Store:
    """Persistently store JSON-serializable key/value pairs in a JSONL file."""

    def __init__(self, path: str | os.PathLike[str] = "store.jsonl") -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            self.path.touch(mode=0o600)

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
                    if key is None:
                        continue
                    yield str(key), record.get("value")
        except FileNotFoundError:
            return

    def _read_state(self) -> dict[str, Any]:
        state: dict[str, Any] = {}
        for key, value in self._iter_records():
            state[key] = value
        return state

    def put(self, key: str, value: Any) -> None:
        payload = json.dumps({"key": str(key), "value": value}, separators=(",", ":"), sort_keys=True)
        encoded = (payload + "\n").encode("utf-8")

        fd = os.open(self.path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
        try:
            view = memoryview(encoded)
            while view:
                written = os.write(fd, view)
                if written == 0:
                    raise OSError("short write while appending to store")
                view = view[written:]
            os.fsync(fd)
        finally:
            os.close(fd)

    def get(self, key: str, default: Any = None) -> Any:
        return self._read_state().get(str(key), default)

    def list(self, prefix: str = "") -> list[str]:
        state = self._read_state()
        matches = [k for k in state if k.startswith(prefix)]
        return sorted(matches)


__all__ = ["Store"]
