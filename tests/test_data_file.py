"""AC6 to AC8: the data file is the user's alone, and two copies never collide."""

from __future__ import annotations

import sqlite3
import stat
import subprocess
import sys
import time
from pathlib import Path

import pytest

from tally.cli import main
from tally.store import Store


def mode(path: Path) -> int:
    return stat.S_IMODE(path.stat().st_mode)


def test_ac06_a_fresh_data_directory_and_file_are_the_users_alone(tmp_path: Path) -> None:
    data_dir = tmp_path / "deep" / "data"
    with Store.open(data_dir) as store:
        assert store.tightened is False
    assert mode(data_dir) == 0o700
    assert mode(data_dir / "tally.sqlite") == 0o600
    connection = sqlite3.connect(data_dir / "tally.sqlite")
    assert connection.execute("PRAGMA journal_mode").fetchone()[0] == "wal"
    connection.close()


def test_ac06_a_wider_data_file_is_tightened_and_reported(tmp_path: Path) -> None:
    data_file = tmp_path / "tally.sqlite"
    with Store.open(tmp_path):
        pass
    data_file.chmod(0o644)
    with Store.open(tmp_path) as store:
        assert store.tightened is True
    assert mode(data_file) == 0o600
    with Store.open(tmp_path) as store:
        assert store.tightened is False


def test_the_schema_holds_accounts_imports_and_transactions_once_per_account(
    tmp_path: Path,
) -> None:
    with Store.open(tmp_path), Store.open(tmp_path):
        pass  # opening twice applies the schema once
    connection = sqlite3.connect(tmp_path / "tally.sqlite")
    assert connection.execute("PRAGMA user_version").fetchone()[0] == 1
    tables = {
        row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")
    }
    assert {"accounts", "imports", "transactions"} <= tables
    connection.execute("INSERT INTO accounts VALUES (1, 'a', 'GBP', 2, '2026-11-10T00:00:00Z')")
    connection.execute("INSERT INTO accounts VALUES (2, 'b', 'GBP', 2, '2026-11-10T00:00:00Z')")
    connection.execute(
        "INSERT INTO imports VALUES (1, 1, 'f.csv', '2026-11-10T00:00:00Z', 1, 0, 0)"
    )
    row = (
        "INSERT INTO transactions"
        " (account_id, import_id, date, description, amount_minor, fingerprint)"
        " VALUES (?, 1, '2026-10-01', 'x', -4217, 'csv:1')"
    )
    connection.execute(row, (1,))
    connection.execute(row, (2,))
    with pytest.raises(sqlite3.IntegrityError):
        connection.execute(row, (1,))
    connection.close()


def console_script() -> Path:
    tally = Path(sys.executable).with_name("tally")
    assert tally.exists(), "install the project first: uv sync"
    return tally


def test_ac06_the_variable_places_the_data_file_and_a_wider_one_is_tightened(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    data_dir = tmp_path / "from-variable"
    monkeypatch.setenv("TALLY_DATA_DIR", str(data_dir))
    assert main(["account", "add", "current", "--currency", "GBP"]) == 0
    assert mode(data_dir) == 0o700
    assert mode(data_dir / "tally.sqlite") == 0o600
    (data_dir / "tally.sqlite").chmod(0o644)
    assert main(["account", "list"]) == 0
    captured = capsys.readouterr()
    assert captured.out == "current GBP\n"
    assert captured.err == "tightened the data file's permissions to 0600\n"
    assert mode(data_dir / "tally.sqlite") == 0o600
    # The installed command, with the variable inherited from this process.
    result = subprocess.run(
        [str(console_script()), "account", "add", "savings", "--currency", "GBP"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert (result.returncode, result.stdout, result.stderr) == (0, "", "")
    assert mode(data_dir / "tally.sqlite") == 0o600


def test_ac07_two_copies_at_once_each_write_once_and_the_file_stays_whole(tmp_path: Path) -> None:
    tally = str(console_script())
    data_dir = tmp_path / "data"
    both = [
        subprocess.Popen(
            [tally, "account", "add", name, "--currency", "GBP", "--data-dir", str(data_dir)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        for name in ("current", "savings")
    ]
    outcomes = [(p.wait(), *p.communicate()) for p in both]
    assert outcomes == [(0, "", ""), (0, "", "")]
    listed = subprocess.run(
        [tally, "account", "list", "--data-dir", str(data_dir)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert listed.stdout == "current GBP\nsavings GBP\n"
    connection = sqlite3.connect(data_dir / "tally.sqlite")
    assert connection.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
    connection.close()


def test_ac07_a_copy_waits_for_a_lock_that_is_released_in_time(tmp_path: Path) -> None:
    assert (
        main(["account", "add", "current", "--currency", "GBP", "--data-dir", str(tmp_path)]) == 0
    )
    holder = sqlite3.connect(tmp_path / "tally.sqlite", autocommit=True)
    holder.execute("BEGIN IMMEDIATE")
    started = time.monotonic()
    waiting = subprocess.Popen(
        [
            str(console_script()),
            "account",
            "add",
            "savings",
            "--currency",
            "GBP",
            "--data-dir",
            str(tmp_path),
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    time.sleep(2)
    holder.execute("COMMIT")
    out, err = waiting.communicate()
    assert (waiting.returncode, out, err) == (0, "", "")
    assert time.monotonic() - started >= 2
    assert [row[0] for row in holder.execute("SELECT name FROM accounts ORDER BY name")] == [
        "current",
        "savings",
    ]
    holder.close()


def test_ac08_a_copy_that_cannot_get_the_file_in_time_says_so_and_writes_nothing(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert (
        main(["account", "add", "current", "--currency", "GBP", "--data-dir", str(tmp_path)]) == 0
    )
    capsys.readouterr()
    holder = sqlite3.connect(tmp_path / "tally.sqlite", autocommit=True)
    holder.execute("BEGIN IMMEDIATE")
    started = time.monotonic()
    # Waits the whole busy timeout (ADR 0005: 10 seconds), on purpose.
    code = main(["account", "add", "savings", "--currency", "GBP", "--data-dir", str(tmp_path)])
    waited = time.monotonic() - started
    captured = capsys.readouterr()
    assert (code, captured.out, captured.err) == (
        3,
        "",
        "another copy of tally is using the data file\n",
    )
    assert waited >= 9
    holder.execute("COMMIT")
    assert [row[0] for row in holder.execute("SELECT name FROM accounts")] == ["current"]
    holder.close()
