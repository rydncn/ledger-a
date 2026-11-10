"""The command line as a user meets it.

Most tests call ``main`` in-process, so mutation testing sees them; one goes
through a real subprocess, so the installed entry point is proved too.
"""

from __future__ import annotations

import subprocess
import sys

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
    result = subprocess.run(
        [sys.executable, "-m", "tally.cli", "--version"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0
    assert result.stdout.strip() == f"tally {__version__}"
