"""The ``tally`` command line.

Every subcommand is added in its own slice; this module only parses arguments
and routes them. Errors go to standard error with a non-zero exit code.
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence

from tally import __version__

EXIT_OK = 0
EXIT_USAGE = 2


def build_parser() -> argparse.ArgumentParser:
    """The top-level parser, with one subparser per command."""
    parser = argparse.ArgumentParser(
        prog="tally",
        description="See where your money goes, from your bank's statement files.",
    )
    parser.add_argument("--version", action="version", version=f"tally {__version__}")
    parser.add_subparsers(dest="command", metavar="<command>")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Run the command line and return the exit code."""
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command is None:
        parser.print_usage(sys.stderr)
        return EXIT_USAGE
    return EXIT_OK


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
