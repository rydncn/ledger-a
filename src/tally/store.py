"""The SQLite data file (ADR 0005).

One file, ``tally.sqlite``, in a directory created ``0700``, itself created
``0600``. Every write runs in one ``BEGIN IMMEDIATE`` transaction with a busy
timeout, so two copies of Tally never corrupt it or count a transaction
twice; a copy that cannot get the file in time raises ``LockedError``. Journal
mode is WAL, so a report can read while an import writes. The schema and its
migrations live here and nowhere else. This module never prints.
"""

from __future__ import annotations

import os
import sqlite3
import stat
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from types import TracebackType
from typing import Self

from tally.money import scale_of

DATA_FILE = "tally.sqlite"
BUSY_TIMEOUT_SECONDS = 10
LOCKED_MESSAGE = "another copy of tally is using the data file"

# Each entry is one schema version, applied in order inside one transaction;
# PRAGMA user_version records how many have been applied. SQL text carries
# "pragma: no mutate": SQLite reads keywords and names in any case, so a
# case-swapped statement is the same statement, not a mutant.
MIGRATIONS: list[list[str]] = [
    [
        """CREATE TABLE accounts (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL UNIQUE,
            currency TEXT NOT NULL,
            scale INTEGER NOT NULL,
            created_at TEXT NOT NULL
        )""",
        """CREATE TABLE imports (
            id INTEGER PRIMARY KEY,
            account_id INTEGER NOT NULL REFERENCES accounts(id),
            file TEXT NOT NULL,
            imported_at TEXT NOT NULL,
            added INTEGER NOT NULL,
            duplicates INTEGER NOT NULL,
            unreadable INTEGER NOT NULL
        )""",
        """CREATE TABLE transactions (
            id INTEGER PRIMARY KEY,
            account_id INTEGER NOT NULL REFERENCES accounts(id),
            import_id INTEGER NOT NULL REFERENCES imports(id),
            date TEXT NOT NULL,
            description TEXT NOT NULL,
            amount_minor INTEGER NOT NULL,
            fingerprint TEXT NOT NULL,
            UNIQUE (account_id, fingerprint)
        )""",
    ],
]


class RefusedError(Exception):
    """The data said no (an unknown account, a name already taken): exit code 1."""


class LockedError(Exception):
    """Another copy holds the data file past the busy timeout: exit code 3."""


@dataclass(frozen=True)
class Account:
    id: int
    name: str
    currency: str
    scale: int


@contextmanager
def _busy_is_locked() -> Iterator[None]:
    try:
        yield
    except sqlite3.OperationalError as error:
        if error.sqlite_errorcode == sqlite3.SQLITE_BUSY:
            raise LockedError(LOCKED_MESSAGE) from error
        raise


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


class Store:
    """An open data file. ``tightened`` says a wider permission was corrected on open."""

    def __init__(self, connection: sqlite3.Connection, *, tightened: bool) -> None:
        self._connection = connection
        self.tightened = tightened

    @classmethod
    def open(cls, data_dir: Path) -> Self:
        """Open the data file under ``data_dir``, creating both privately, and migrate."""
        data_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
        path = data_dir / DATA_FILE
        tightened = False
        if path.exists():
            if stat.S_IMODE(path.stat().st_mode) & 0o077:
                path.chmod(0o600)
                tightened = True
        else:
            os.close(os.open(path, os.O_CREAT | os.O_WRONLY, 0o600))
        connection = sqlite3.connect(
            path, timeout=BUSY_TIMEOUT_SECONDS, autocommit=True
        )  # pragma: no mutate
        store = cls(connection, tightened=tightened)
        try:
            with _busy_is_locked():
                connection.execute("PRAGMA journal_mode=WAL")  # pragma: no mutate
                connection.execute("PRAGMA foreign_keys=ON")  # pragma: no mutate
                store._migrate()
        except sqlite3.DatabaseError as error:
            connection.close()
            raise RefusedError(f"cannot open the data file: {error}") from error
        except BaseException:
            connection.close()
            raise
        return store

    def close(self) -> None:
        self._connection.close()

    def __enter__(self) -> Self:
        return self

    def __exit__(
        self,
        kind: type[BaseException] | None,
        value: BaseException | None,
        trace: TracebackType | None,
    ) -> None:
        self.close()

    @contextmanager
    def write(self) -> Iterator[sqlite3.Connection]:
        """One ``BEGIN IMMEDIATE`` transaction: committed on success, rolled back on any error."""
        with _busy_is_locked():
            self._connection.execute("BEGIN IMMEDIATE")  # pragma: no mutate
        try:
            yield self._connection
        except BaseException:
            self._connection.execute("ROLLBACK")  # pragma: no mutate
            raise
        self._connection.execute("COMMIT")  # pragma: no mutate

    def _applied(self) -> int:
        version: int = self._connection.execute("PRAGMA user_version").fetchone()[
            0
        ]  # pragma: no mutate
        if version > len(MIGRATIONS):
            raise RefusedError("the data file was written by a newer version of tally")
        return version

    def _migrate(self) -> None:
        if self._applied() == len(MIGRATIONS):
            return  # a reader never takes the write lock (ADR 0005)
        with self.write() as connection:
            applied = self._applied()  # again, under the lock: another copy may have migrated
            for version, statements in enumerate(MIGRATIONS[applied:], start=applied + 1):
                for statement in statements:
                    connection.execute(statement)
                connection.execute(f"PRAGMA user_version = {version}")  # pragma: no mutate

    def add_account(self, name: str, currency: str) -> Account:
        """Create an account; the UNIQUE name decides a race between two copies (AC2)."""
        scale = scale_of(currency)
        with self.write() as connection:
            try:
                cursor = connection.execute(
                    "INSERT INTO accounts (name, currency, scale, created_at)"  # pragma: no mutate
                    " VALUES (?, ?, ?, ?)",  # pragma: no mutate
                    (name, currency, scale, _now()),
                )
            except sqlite3.IntegrityError as error:
                raise RefusedError(f'account "{name}" already exists') from error
        return Account(cursor.lastrowid or 0, name, currency, scale)

    def accounts(self) -> list[Account]:
        rows = self._connection.execute(
            "SELECT id, name, currency, scale FROM accounts ORDER BY name"  # pragma: no mutate
        ).fetchall()
        return [Account(*row) for row in rows]

    def account(self, name: str) -> Account | None:
        """Whether the account is present: the one query that reads accounts by name."""
        row = self._connection.execute(
            "SELECT id, name, currency, scale FROM accounts WHERE name = ?",
            (name,),  # pragma: no mutate
        ).fetchone()
        return Account(*row) if row else None

    def transaction_count(self, account: Account) -> int:
        row = self._connection.execute(
            "SELECT count(*) FROM transactions WHERE account_id = ?",
            (account.id,),  # pragma: no mutate
        ).fetchone()
        return int(row[0])

    def forget_account(self, account: Account) -> None:
        """Delete the account, its transactions and its import records, all or nothing (AC3)."""
        with self.write() as connection:
            connection.execute(
                "DELETE FROM transactions WHERE account_id = ?", (account.id,)
            )  # pragma: no mutate
            connection.execute(
                "DELETE FROM imports WHERE account_id = ?", (account.id,)
            )  # pragma: no mutate
            gone = connection.execute(
                "DELETE FROM accounts WHERE id = ?", (account.id,)
            ).rowcount  # pragma: no mutate
            if gone == 0:
                raise RefusedError(f'no account named "{account.name}"')
