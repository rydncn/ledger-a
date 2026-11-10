# Handoff

Where the work is, for the next session. The work, not the machine: tools come from the environment's setup script, never from here.

## Where we are

- **Slice 0 (foundation)** merged as pull request [#1](https://github.com/rydncn/ledger-a/pull/1).
- **Slice 1 (accounts and the data file)** is pull request [#5](https://github.com/rydncn/ledger-a/pull/5), branch `slice-1-accounts`, awaiting the owner's merge (ADR 0007). It delivers `config.py`, `money.py`, `store.py` and `tally account add|list|forget`; criteria AC1 to AC8, AC44, AC34 and AC35 for those commands. The plan with what each task observed is `docs/plans/001-accounts.md`.
- **Next: slice 2**, CSV import: AC9 to AC20, AC40, AC42, AC43. Read `docs/design.md` § Shape (the sign rule for money-in and money-out columns, which importer reads a file), § Lifecycles "An import run", and ADRs 0005 (locking) and 0008 (the fingerprint) before planning.

## How a slice goes

1. New session, new branch from `main` (`slice-2-csv-import`), `scripts/setup-dev.sh`.
2. Plan in `docs/plans/002-csv-import.md` from `docs/plans/001-accounts.md`'s shape: the decisions taken, then `### Task N:` headings, each with the failing test first, the criteria it satisfies and an "Observed by" filled in as it happens. Open the draft pull request straight away with the plan in the description and the door kind.
3. Test-first per task: tests named `test_acNN_...` in a file per behaviour group (`tests/test_accounts.py`, `tests/test_data_file.py` are the pattern); in-process `main(argv)` for behaviour, one subprocess test per behaviour group (ADR 0002). Every test gets `--data-dir` under its `tmp_path`; `tests/conftest.py` already gives each test its own `HOME` and clears `TALLY_CONFIG` and `TALLY_DATA_DIR`. The stop hook runs format, lint, mypy and the tests.
4. Before marking ready: `UV_NO_BUILD=0 uv sync --locked --group mutation` then `uv run python scripts/mutation_changed.py origin/main`; the fresh-context review from `docs/review-brief.md` by a subagent given only the diff, `CLAUDE.md`, `docs/design.md` and `docs/brief.md`; findings fixed test-first or ruled on in the pull request.
5. Records: `docs/effort.md`, `docs/trial-log.md`, `docs/playbook-feedback.md`. Peak context from the transcript with the script in `docs/python-pack/README.md` § "Measuring a session".
6. Handoff here, push, mark ready once CI is green, ask the owner to merge.

## What slice 2 builds on

- `Store.write()` is the one `BEGIN IMMEDIATE`; an import is one `with store.write() as connection:` holding the import record insert and every row's `INSERT ... ON CONFLICT (account_id, fingerprint) DO NOTHING` (ADR 0005). `LockedError` is already mapped to exit 3 and a failed `write()` rolls back everything (AC42's "nothing written"). `RefusedError` is exit 1; `ConfigError` is exit 2 and is raised before the data file opens.
- The schema (`store.MIGRATIONS[0]`): `transactions(account_id, import_id, date, description, amount_minor, fingerprint)` with `UNIQUE (account_id, fingerprint)`, `imports(account_id, file, imported_at, added, duplicates, unreadable)`. A schema change is a new entry in `MIGRATIONS` (and a one-way door).
- `money.parse_amount(text, decimal, thousands)` raises `AmountError("amount is not a number")`; `money.to_minor(amount, account.scale)` is what goes in the file. `Account.scale` comes from `money.scale_of`.
- `config.Config.layouts` is a `dict[str, dict[str, object]]` validated only for shape; AC43's checks of each layout's fields (the named columns, `date_format`, distinct separators) belong to the importer or a `layouts` validation in `config.py`, raised as `ConfigError` so they exit 2 before the data file opens.
- `cli.py` takes the common `--config` and `--data-dir` through a parent parser on each leaf command; `--format` is per command (`account list` has `table` and `json`). `import` needs `--account`, `--layout`, the file, `--format json` (AC20) and `--verbose` (AC19).
- `store.account(name)` is the one query for "present"; `import` into an unknown account is `RefusedError` from it (AC5).

## Decisions taken that the next session should not reopen

- Exit codes 0/1/2/3 and the stdout/stderr contract are in `docs/design.md` § Shape; `cli.py` is the only module that prints.
- The busy timeout is 10 seconds with no override (ADR 0005); the one AC8 test waits for it.
- The fingerprint for duplicates is ADR 0008; the amount sign convention (money in minus money out; a negative money-out is money back) is in § Shape.
- Subprocess tests kill no mutants (ADR 0002); don't move behaviour tests to subprocess to "be more real".
- The data directory order is flag, `TALLY_DATA_DIR`, the config's `data_dir` (relative to the config file), then the platform default.

## Open

- Whether `account forget` should keep a tombstone so a later import of the same file into a re-created account is not silently "all new": decided no for slice 1 (the brief says delete everything); revisit if a reviewer raises it.
- AC3's `report shows only savings' transactions` is proved by SQL counts until slice 5 has `report`.
- After slice 3: the whole-codebase review. Before the final review: `/security-audit`.
