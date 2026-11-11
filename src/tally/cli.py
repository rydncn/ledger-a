"""The ``tally`` command line.

The only module that prints. Standard output carries data, standard error
carries messages; every refusal is one line on standard error and a non-zero
exit code: 1 when the data said no, 2 for a usage or configuration error, 3
when another copy of Tally holds the data file.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sqlite3
import sys
import unicodedata
from collections.abc import Sequence
from pathlib import Path

from tally import __version__
from tally.config import Config, ConfigError, data_dir_for, load_config
from tally.importers import NotAStatementError, kind, ofx
from tally.importers.csv_layout import Layout, read
from tally.store import LockedError, RefusedError, Store

UNREADABLE_LINES_SHOWN = 50

EXIT_OK = 0
EXIT_REFUSED = 1
EXIT_USAGE = 2
EXIT_LOCKED = 3


def account_name(text: str) -> str:
    name = text.strip()
    if not name:
        raise argparse.ArgumentTypeError("must not be empty")
    if any(unicodedata.category(c).startswith("C") for c in name):
        raise argparse.ArgumentTypeError("must not contain control characters or line breaks")
    return name


def currency_code(text: str) -> str:
    if len(text) != 3 or not text.isascii() or not text.isalpha():
        raise argparse.ArgumentTypeError(f"{text!r} is not a three-letter currency code")
    return text.upper()


def build_parser() -> argparse.ArgumentParser:
    """The top-level parser, with one subparser per command."""
    parser = argparse.ArgumentParser(
        prog="tally",
        description="See where your money goes, from your bank's statement files.",
        allow_abbrev=False,  # every accepted prefix would be part of the command line
    )
    parser.add_argument("--version", action="version", version=f"tally {__version__}")
    commands = parser.add_subparsers(dest="command", metavar="<command>")

    common = argparse.ArgumentParser(add_help=False)  # pragma: no mutate (None is False here)
    common.add_argument("--config", metavar="FILE", help="the tally.toml to read")
    common.add_argument("--data-dir", metavar="DIR", help="where the data file lives")

    account = commands.add_parser(
        "account", allow_abbrev=False, help="add, list and forget accounts"
    )
    actions = account.add_subparsers(metavar="<action>", required=True)
    add = actions.add_parser("add", parents=[common], allow_abbrev=False, help="add an account")
    add.add_argument("name", type=account_name)
    add.add_argument(
        "--currency", required=True, type=currency_code, help="three letters, e.g. GBP"
    )
    add.set_defaults(run=account_add)
    listing = actions.add_parser(
        "list", parents=[common], allow_abbrev=False, help="list the accounts"
    )
    listing.add_argument("--format", choices=["table", "json"], default="table")
    listing.set_defaults(run=account_list)
    forget = actions.add_parser(
        "forget",
        parents=[common],
        allow_abbrev=False,
        help="delete an account and everything imported into it",
    )
    forget.add_argument("name", type=account_name)
    forget.add_argument("--yes", action="store_true", help="do not ask first")
    forget.set_defaults(run=account_forget)

    importing = commands.add_parser(
        "import",
        parents=[common],
        allow_abbrev=False,
        help="import a statement file into an account",
    )
    importing.add_argument("file", help="a CSV or OFX statement")
    importing.add_argument(
        "--account", required=True, type=account_name, help="the account the statement belongs to"
    )
    importing.add_argument(
        "--layout", metavar="NAME", help="the [layouts.NAME] table that describes the CSV"
    )
    importing.add_argument("--format", choices=["table", "json"], default="table")
    importing.add_argument(
        "--verbose", action="store_true", help="say what is being read, on standard error"
    )
    importing.set_defaults(run=import_run)
    return parser


def open_store(args: argparse.Namespace, config: Config) -> Store:
    """Open the data file where the flag, the variable or the configuration puts it."""
    store = Store.open(data_dir_for(args.data_dir, config))
    if store.tightened:
        print("tightened the data file's permissions to 0600", file=sys.stderr)
    return store


def account_add(args: argparse.Namespace, config: Config) -> int:
    with open_store(args, config) as store:
        store.add_account(args.name, args.currency)
    return EXIT_OK


def account_list(args: argparse.Namespace, config: Config) -> int:
    with open_store(args, config) as store:
        accounts = store.accounts()
    if args.format == "table":
        for a in accounts:
            print(f"{a.name} {a.currency}")
    else:
        print(json.dumps([{"name": a.name, "currency": a.currency} for a in accounts]))
    return EXIT_OK


def account_forget(args: argparse.Namespace, config: Config) -> int:
    with open_store(args, config) as store:
        return _forget(args, store)


def _forget(args: argparse.Namespace, store: Store) -> int:
    account = store.account(args.name)
    if account is None:
        raise RefusedError(f'no account named "{args.name}"')
    count = store.transaction_count(account)
    if not args.yes:
        if sys.stdin is None or not sys.stdin.isatty():
            print(
                f'forgetting "{account.name}" needs --yes when standard input is not a terminal',
                file=sys.stderr,
            )
            return EXIT_USAGE
        sys.stderr.write(
            f'Forget account "{account.name}" and its {count} transactions? Type yes to continue: '
        )
        sys.stderr.flush()
        if sys.stdin.readline().strip() != "yes":
            raise RefusedError("nothing forgotten")
    count = store.forget_account(account, expected=None if args.yes else count)
    print(f'forgot account "{account.name}" and its {count} transactions', file=sys.stderr)
    return EXIT_OK


def import_run(args: argparse.Namespace, config: Config) -> int:
    """Logging on for this run only when ``--verbose`` asks (AC19), then the import."""
    if not args.verbose:
        return _import(args, config)
    log = logging.getLogger("tally")  # pragma: no mutate (the root logger carries the same lines)
    handler = logging.StreamHandler(sys.stderr)  # pragma: no mutate (None is standard error too)
    log.addHandler(handler)
    log.setLevel(logging.INFO)
    try:
        return _import(args, config)
    finally:
        log.removeHandler(handler)
        log.setLevel(logging.NOTSET)


def _import(args: argparse.Namespace, config: Config) -> int:
    """The import run of design § Lifecycles: refusals before the lock, rows under it."""
    layout = None
    if args.layout is not None:
        if args.layout not in config.layouts:
            raise ConfigError(f'no layout named "{args.layout}"')
        layout = Layout.from_config(args.layout, config.layouts[args.layout])
    path = Path(args.file)
    # The path as text the data file and JSON can hold: bytes that are not UTF-8 become U+FFFD.
    shown = os.fsencode(args.file).decode("utf-8", "replace")
    file_kind = kind(path)
    if file_kind == "csv" and layout is None:
        print("--layout is needed for a CSV file", file=sys.stderr)
        return EXIT_USAGE
    if file_kind != "csv" and layout is not None:
        print("--layout is for CSV files, and this is an OFX file", file=sys.stderr)
        return EXIT_USAGE
    with open_store(args, config) as store:
        account = store.account(args.account)
        if account is None:
            raise RefusedError(f'no account named "{args.account}"')
        if layout is None:
            outcomes = ofx.read(path, account.currency, account.scale)
        else:
            outcomes = read(path, layout, account.scale)
        summary = store.import_transactions(account, shown, outcomes)
    where = "line" if layout is not None else "transaction"  # what a row's number counts
    for unreadable in summary.unreadable[:UNREADABLE_LINES_SHOWN]:
        print(f"{where} {unreadable.line}: {unreadable.reason}", file=sys.stderr)
    if summary.unreadable_count > UNREADABLE_LINES_SHOWN:
        print(f"and {summary.unreadable_count - UNREADABLE_LINES_SHOWN} more", file=sys.stderr)
    if args.format == "table":
        print(
            f"added {summary.added}, already there {summary.duplicates},"
            f" unreadable {summary.unreadable_count}"
        )
    else:
        print(
            json.dumps(
                {
                    "account": account.name,
                    "file": shown,
                    "added": summary.added,
                    "duplicates": summary.duplicates,
                    "unreadable_count": summary.unreadable_count,
                    "unreadable": [{where: u.line, "reason": u.reason} for u in summary.unreadable],
                }
            )
        )
    return EXIT_OK


def main(argv: Sequence[str] | None = None) -> int:
    """Run the command line and return the exit code."""
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command is None:
        parser.print_usage(sys.stderr)
        return EXIT_USAGE
    try:
        config = load_config(args.config)
        code: int = args.run(args, config)
    except ConfigError as error:
        print(error, file=sys.stderr)
        return EXIT_USAGE
    except (RefusedError, NotAStatementError, sqlite3.Error) as error:
        failed = isinstance(error, sqlite3.Error)  # a damaged file, a full disk: no data in it
        print(f"the data file failed: {error}" if failed else error, file=sys.stderr)
        return EXIT_REFUSED
    except LockedError as error:
        print(error, file=sys.stderr)
        return EXIT_LOCKED
    except OSError as error:
        print(f"cannot open the data file: {error.strerror}: {error.filename}", file=sys.stderr)
        return EXIT_REFUSED
    return code


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
