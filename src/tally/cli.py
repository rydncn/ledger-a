"""The ``tally`` command line.

The only module that prints. Standard output carries data, standard error
carries messages; every refusal is one line on standard error and a non-zero
exit code: 1 when the data said no, 2 for a usage or configuration error, 3
when another copy of Tally holds the data file.
"""

from __future__ import annotations

import argparse
import json
import sys
import unicodedata
from collections.abc import Sequence

from tally import __version__
from tally.config import ConfigError, data_dir_for, load_config
from tally.store import LockedError, RefusedError, Store

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
    )
    parser.add_argument("--version", action="version", version=f"tally {__version__}")
    commands = parser.add_subparsers(dest="command", metavar="<command>")

    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--config", metavar="FILE", help="the tally.toml to read")
    common.add_argument("--data-dir", metavar="DIR", help="where the data file lives")

    account = commands.add_parser("account", help="add, list and forget accounts")
    actions = account.add_subparsers(metavar="<action>", required=True)
    add = actions.add_parser("add", parents=[common], help="add an account")
    add.add_argument("name", type=account_name)
    add.add_argument(
        "--currency", required=True, type=currency_code, help="three letters, e.g. GBP"
    )
    add.set_defaults(run=account_add)
    listing = actions.add_parser("list", parents=[common], help="list the accounts")
    listing.add_argument("--format", choices=["table", "json"], default="table")
    listing.set_defaults(run=account_list)
    forget = actions.add_parser(
        "forget", parents=[common], help="delete an account and everything imported into it"
    )
    forget.add_argument("name", type=account_name)
    forget.add_argument("--yes", action="store_true", help="do not ask first")
    forget.set_defaults(run=account_forget)
    return parser


def account_add(args: argparse.Namespace, store: Store) -> int:
    store.add_account(args.name, args.currency)
    return EXIT_OK


def account_list(args: argparse.Namespace, store: Store) -> int:
    accounts = store.accounts()
    if args.format == "table":
        for a in accounts:
            print(f"{a.name} {a.currency}")
    else:
        print(json.dumps([{"name": a.name, "currency": a.currency} for a in accounts]))
    return EXIT_OK


def account_forget(args: argparse.Namespace, store: Store) -> int:
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
    store.forget_account(account)
    print(f'forgot account "{account.name}" and its {count} transactions', file=sys.stderr)
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
        with Store.open(data_dir_for(args.data_dir, config)) as store:
            if store.tightened:
                print("tightened the data file's permissions to 0600", file=sys.stderr)
            code: int = args.run(args, store)
    except ConfigError as error:
        print(error, file=sys.stderr)
        return EXIT_USAGE
    except RefusedError as error:
        print(error, file=sys.stderr)
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
