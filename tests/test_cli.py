"""The command line as a user meets it.

Most tests call ``main`` in-process, so mutation testing sees them; one goes
through a real subprocess, so the installed entry point is proved too.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

from tally import __version__
from tally.cli import main


def test_version_is_printed(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as raised:
        main(["--version"])
    assert raised.value.code == 0
    assert capsys.readouterr().out.strip() == f"tally {__version__}"


def test_no_command_is_a_usage_error_on_stderr(capsys: pytest.CaptureFixture[str]) -> None:
    code = main([])
    captured = capsys.readouterr()
    assert code == 2
    assert captured.out == ""
    assert "usage:" in captured.err


def test_the_installed_command_runs() -> None:
    tally = Path(sys.executable).with_name("tally")  # the console script beside this interpreter
    assert tally.exists(), "install the project first: uv sync"
    result = subprocess.run(
        [str(tally), "--version"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0
    assert result.stdout.strip() == f"tally {__version__}"


TOP_HELP = """\
usage: tally [-h] [--version] <command> ...

See where your money goes, from your bank's statement files.

positional arguments:
  <command>
    account   add, list and forget accounts

options:
  -h, --help  show this help message and exit
  --version   show program's version number and exit
"""


def test_help_names_the_command_and_what_it_is_for(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as raised:
        main(["--help"])
    assert raised.value.code == 0
    assert capsys.readouterr().out == TOP_HELP


ACCOUNT_HELP = """\
usage: tally account [-h] <action> ...

positional arguments:
  <action>
    add       add an account
    list      list the accounts
    forget    delete an account and everything imported into it

options:
  -h, --help  show this help message and exit
"""

ADD_HELP = """\
usage: tally account add [-h] [--config FILE] [--data-dir DIR]
                         --currency CURRENCY
                         name

positional arguments:
  name

options:
  -h, --help           show this help message and exit
  --config FILE        the tally.toml to read
  --data-dir DIR       where the data file lives
  --currency CURRENCY  three letters, e.g. GBP
"""

LIST_HELP = """\
usage: tally account list [-h] [--config FILE] [--data-dir DIR]
                          [--format {table,json}]

options:
  -h, --help            show this help message and exit
  --config FILE         the tally.toml to read
  --data-dir DIR        where the data file lives
  --format {table,json}
"""

FORGET_HELP = """\
usage: tally account forget [-h] [--config FILE] [--data-dir DIR] [--yes] name

positional arguments:
  name

options:
  -h, --help      show this help message and exit
  --config FILE   the tally.toml to read
  --data-dir DIR  where the data file lives
  --yes           do not ask first
"""


@pytest.mark.parametrize(
    ("argv", "expected"),
    [
        (["account"], ACCOUNT_HELP),
        (["account", "add"], ADD_HELP),
        (["account", "list"], LIST_HELP),
        (["account", "forget"], FORGET_HELP),
    ],
)
def test_each_account_help_screen_is_whole(
    capsys: pytest.CaptureFixture[str], argv: list[str], expected: str
) -> None:
    with pytest.raises(SystemExit) as raised:
        main([*argv, "--help"])
    assert raised.value.code == 0
    assert capsys.readouterr().out == expected
