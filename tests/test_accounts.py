"""AC1 to AC5, AC34 and AC35: ``tally account add|list|forget``."""

from __future__ import annotations

import json
import sqlite3
import stat
import subprocess
import sys
from pathlib import Path

import pytest

from tally.cli import main


def run(argv: list[str], capsys: pytest.CaptureFixture[str]) -> tuple[int, str, str]:
    code = main(argv)
    captured = capsys.readouterr()
    return code, captured.out, captured.err


def add(data_dir: Path, name: str, currency: str, capsys: pytest.CaptureFixture[str]) -> None:
    assert run(
        ["account", "add", name, "--currency", currency, "--data-dir", str(data_dir)], capsys
    ) == (
        0,
        "",
        "",
    )


def insert_rows(data_dir: Path, account: str, count: int) -> None:
    """Rows in the real data file, standing in for an import until slice 2."""
    connection = sqlite3.connect(data_dir / "tally.sqlite")
    (account_id,) = connection.execute(
        "SELECT id FROM accounts WHERE name = ?", (account,)
    ).fetchone()
    import_id = connection.execute(
        "INSERT INTO imports (account_id, file, imported_at, added, duplicates, unreadable)"
        " VALUES (?, 'f.csv', '2026-11-10T00:00:00Z', ?, 0, 0)",
        (account_id, count),
    ).lastrowid
    for n in range(count):
        connection.execute(
            "INSERT INTO transactions"
            " (account_id, import_id, date, description, amount_minor, fingerprint)"
            " VALUES (?, ?, '2026-10-01', 'x', -100, ?)",
            (account_id, import_id, f"csv:{account}:{n}"),
        )
    connection.commit()
    connection.close()


def counts(data_dir: Path) -> dict[str, tuple[int, int]]:
    """Per account name: (transactions, import records)."""
    connection = sqlite3.connect(data_dir / "tally.sqlite")
    rows = connection.execute(
        "SELECT a.name,"
        " (SELECT count(*) FROM transactions t WHERE t.account_id = a.id),"
        " (SELECT count(*) FROM imports i WHERE i.account_id = a.id)"
        " FROM accounts a"
    ).fetchall()
    connection.close()
    return {name: (transactions, imports) for name, transactions, imports in rows}


class Terminal:
    """A standard input that says it is a terminal and answers one line."""

    def __init__(self, answer: str) -> None:
        self.answer = answer

    def isatty(self) -> bool:
        return True

    def readline(self) -> str:
        return self.answer


def test_ac01_add_an_account(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    data_dir = tmp_path / "data"
    add(data_dir, "current", "GBP", capsys)
    assert run(["account", "list", "--data-dir", str(data_dir)], capsys) == (0, "current GBP\n", "")
    assert stat.S_IMODE(data_dir.stat().st_mode) == 0o700
    assert stat.S_IMODE((data_dir / "tally.sqlite").stat().st_mode) == 0o600


def test_ac01_list_is_empty_before_any_account(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert run(["account", "list", "--data-dir", str(tmp_path)], capsys) == (0, "", "")
    assert run(["account", "list", "--data-dir", str(tmp_path), "--format", "json"], capsys) == (
        0,
        "[]\n",
        "",
    )


def test_ac02_a_name_is_taken_once(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    add(tmp_path, "current", "GBP", capsys)
    code, out, err = run(
        ["account", "add", "current", "--currency", "EUR", "--data-dir", str(tmp_path)], capsys
    )
    assert (code, out, err) == (1, "", 'account "current" already exists\n')
    assert run(["account", "list", "--data-dir", str(tmp_path)], capsys)[1] == "current GBP\n"


def test_ac03_forget_deletes_the_account_and_everything_imported_into_it(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    add(tmp_path, "current", "GBP", capsys)
    add(tmp_path, "savings", "GBP", capsys)
    insert_rows(tmp_path, "current", 3)
    insert_rows(tmp_path, "savings", 2)
    code, out, err = run(
        ["account", "forget", "current", "--yes", "--data-dir", str(tmp_path)], capsys
    )
    assert (code, out, err) == (0, "", 'forgot account "current" and its 3 transactions\n')
    assert run(["account", "list", "--data-dir", str(tmp_path)], capsys) == (0, "savings GBP\n", "")
    assert counts(tmp_path) == {"savings": (2, 1)}


def test_ac03_without_yes_off_a_terminal_is_a_usage_error(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    add(tmp_path, "current", "GBP", capsys)
    insert_rows(tmp_path, "current", 3)
    code, out, err = run(["account", "forget", "current", "--data-dir", str(tmp_path)], capsys)
    assert (code, out) == (2, "")
    assert err == 'forgetting "current" needs --yes when standard input is not a terminal\n'
    assert counts(tmp_path) == {"current": (3, 1)}


def test_ac03_on_a_terminal_the_prompt_names_the_account_and_the_count(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    add(tmp_path, "current", "GBP", capsys)
    insert_rows(tmp_path, "current", 3)
    prompt = 'Forget account "current" and its 3 transactions? Type yes to continue: '
    for answer in ("no\n", "y\n", "YES\n", "\n"):
        monkeypatch.setattr("sys.stdin", Terminal(answer))
        code, out, err = run(["account", "forget", "current", "--data-dir", str(tmp_path)], capsys)
        assert (code, out, err) == (1, "", prompt + "nothing forgotten\n")
        assert counts(tmp_path) == {"current": (3, 1)}
    monkeypatch.setattr("sys.stdin", Terminal("yes\n"))
    code, out, err = run(["account", "forget", "current", "--data-dir", str(tmp_path)], capsys)
    assert (code, out, err) == (0, "", prompt + 'forgot account "current" and its 3 transactions\n')
    assert counts(tmp_path) == {}


def test_ac04_forgetting_an_unknown_account_is_refused(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    add(tmp_path, "current", "GBP", capsys)
    code, out, err = run(["account", "forget", "old", "--yes", "--data-dir", str(tmp_path)], capsys)
    assert (code, out, err) == (1, "", 'no account named "old"\n')
    assert counts(tmp_path) == {"current": (0, 0)}


@pytest.mark.parametrize(
    ("argv", "named"),
    [
        (["account", "add", "current", "--currency", "pounds"], "--currency"),
        (["account", "add", "current", "--currency", "gb1"], "--currency"),
        (["account", "add", "current"], "--currency"),
        (["account", "add", " ", "--currency", "GBP"], "name"),
        (["account", "list", "--format", "xml"], "--format"),
        (["account"], "usage"),
        (["account", "forget"], "name"),
    ],
)
def test_ac34_usage_errors_go_to_stderr_with_exit_2_and_touch_nothing(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], argv: list[str], named: str
) -> None:
    with pytest.raises(SystemExit) as raised:
        main([*argv, "--data-dir", str(tmp_path)])
    captured = capsys.readouterr()
    assert raised.value.code == 2
    assert captured.out == ""
    assert named in captured.err
    assert not (tmp_path / "tally.sqlite").exists()


def test_ac34_a_configuration_error_is_exit_2_before_the_data_file_opens(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    config = tmp_path / "tally.toml"
    config.write_text("data_dir = 1\n", encoding="utf-8")
    argv = [
        "account",
        "add",
        "current",
        "--currency",
        "GBP",
        "--config",
        str(config),
        "--data-dir",
        str(tmp_path),
    ]
    assert run(argv, capsys) == (2, "", f"{config}: data_dir must be a string\n")
    assert not (tmp_path / "tally.sqlite").exists()


def test_ac34_a_data_directory_that_cannot_be_created_is_exit_1(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    blocker = tmp_path / "file"
    blocker.write_text("not a directory", encoding="utf-8")
    code, out, err = run(["account", "list", "--data-dir", str(blocker / "data")], capsys)
    assert (code, out) == (1, "")
    assert err.startswith("cannot open the data file: ")
    assert err.endswith("\n")
    assert err.count("\n") == 1


def test_ac35_account_list_has_a_json_form(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    add(tmp_path, "savings", "GBP", capsys)
    add(tmp_path, "card", "EUR", capsys)
    add(tmp_path, "yen", "jpy", capsys)
    code, out, err = run(
        ["account", "list", "--data-dir", str(tmp_path), "--format", "json"], capsys
    )
    assert (code, err) == (0, "")
    assert json.loads(out) == [
        {"name": "card", "currency": "EUR"},
        {"name": "savings", "currency": "GBP"},
        {"name": "yen", "currency": "JPY"},
    ]
    assert out.endswith("\n")
    assert out.count("\n") == 1
    assert (
        run(["account", "list", "--data-dir", str(tmp_path)], capsys)[1]
        == "card EUR\nsavings GBP\nyen JPY\n"
    )


def test_the_installed_command_adds_lists_and_forgets(tmp_path: Path) -> None:
    tally = Path(sys.executable).with_name("tally")
    assert tally.exists(), "install the project first: uv sync"

    def tally_run(*args: str, stdin: int = subprocess.DEVNULL) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [str(tally), "account", *args, "--data-dir", str(tmp_path)],
            capture_output=True,
            text=True,
            check=False,
            stdin=stdin,
        )

    added = tally_run("add", "current", "--currency", "GBP")
    assert (added.returncode, added.stdout, added.stderr) == (0, "", "")
    taken = tally_run("add", "current", "--currency", "EUR")
    assert (taken.returncode, taken.stdout, taken.stderr) == (
        1,
        "",
        'account "current" already exists\n',
    )
    listed = tally_run("list", "--format", "json")
    assert (listed.returncode, listed.stderr) == (0, "")
    assert json.loads(listed.stdout) == [{"name": "current", "currency": "GBP"}]
    no_terminal = tally_run("forget", "current")
    assert (no_terminal.returncode, no_terminal.stdout) == (2, "")
    assert "needs --yes" in no_terminal.stderr
    forgotten = tally_run("forget", "current", "--yes")
    assert (forgotten.returncode, forgotten.stdout) == (0, "")
    assert tally_run("list").stdout == ""
