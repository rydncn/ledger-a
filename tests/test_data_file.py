"""AC6 to AC8: the data file is the user's alone, and two copies never collide."""

from __future__ import annotations

import sqlite3
import stat
from pathlib import Path

import pytest

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
