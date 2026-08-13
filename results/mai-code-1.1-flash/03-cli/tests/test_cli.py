from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def run_cli(*args: str, path: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "src.cli", "--path", str(path), *args],
        cwd=str(ROOT),
        text=True,
        capture_output=True,
        check=False,
    )


def test_store_round_trip(tmp_path: Path) -> None:
    store_path = tmp_path / "store.jsonl"

    put = run_cli("put", "alpha", "beta", path=store_path)
    assert put.returncode == 0, put.stderr
    assert json.loads(put.stdout) == {"key": "alpha", "value": "beta"}

    get = run_cli("get", "alpha", path=store_path)
    assert get.returncode == 0, get.stderr
    assert json.loads(get.stdout) == {"key": "alpha", "value": "beta"}

    ls = run_cli("list", path=store_path)
    assert ls.returncode == 0, ls.stderr
    assert json.loads(ls.stdout) == {"keys": ["alpha"]}


def test_json_values_and_missing_key(tmp_path: Path) -> None:
    store_path = tmp_path / "store.jsonl"

    put_number = run_cli("put", "count", "42", path=store_path)
    assert put_number.returncode == 0, put_number.stderr
    assert json.loads(put_number.stdout) == {"key": "count", "value": 42}

    get_number = run_cli("get", "count", path=store_path)
    assert get_number.returncode == 0, get_number.stderr
    assert json.loads(get_number.stdout) == {"key": "count", "value": 42}

    missing = run_cli("get", "missing", path=store_path)
    assert missing.returncode == 3
    payload = json.loads(missing.stdout)
    assert payload["code"] == 3
    assert payload["error"] == "key not found"
    assert payload["key"] == "missing"


def test_list_prefix_filter(tmp_path: Path) -> None:
    store_path = tmp_path / "store.jsonl"

    run_cli("put", "alpha", "1", path=store_path)
    run_cli("put", "beta", "2", path=store_path)
    run_cli("put", "gamma", "3", path=store_path)

    rows = run_cli("list", "a", path=store_path)
    assert rows.returncode == 0, rows.stderr
    assert json.loads(rows.stdout) == {"keys": ["alpha"]}
