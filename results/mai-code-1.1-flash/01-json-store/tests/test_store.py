import json
from pathlib import Path

import pytest

from src.store import Store


@pytest.fixture
def store_path(tmp_path: Path) -> Path:
    return tmp_path / "store.jsonl"


def test_put_get_and_list(store_path: Path) -> None:
    store = Store(store_path)

    store.put("alpha", {"x": 1})
    store.put("beta", [1, 2, 3])
    store.put("alphabet", "value")

    assert store.get("alpha") == {"x": 1}
    assert store.get("beta") == [1, 2, 3]
    assert store.get("missing") is None
    assert store.list("a") == ["alpha", "alphabet"]
    assert store.list("") == ["alpha", "alphabet", "beta"]


def test_latest_value_wins(store_path: Path) -> None:
    store = Store(store_path)

    store.put("counter", 1)
    store.put("counter", 2)
    store.put("counter", 3)

    assert store.get("counter") == 3
    assert store.list("") == ["counter"]


def test_ignores_corrupted_tail(store_path: Path) -> None:
    store = Store(store_path)
    store.put("good", "value")

    with store_path.open("ab") as handle:
        handle.write(b'{"key": "broken"')

    assert store.get("good") == "value"
    assert store.list("") == ["good"]


def test_ignores_invalid_json_lines(store_path: Path) -> None:
    store = Store(store_path)
    with store_path.open("w", encoding="utf-8") as handle:
        handle.write(json.dumps({"key": "first", "value": 1}) + "\n")
        handle.write("not valid json\n")
        handle.write(json.dumps({"key": "second", "value": 2}) + "\n")
        handle.write("{\"key\": \"oops\"\n")

    assert store.get("first") == 1
    assert store.get("second") == 2
    assert store.list("") == ["first", "second"]
