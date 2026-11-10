# 001. Accounts and the data file

**Status:** active · **Satisfies:** AC1 to AC8, AC44, AC34 and AC35 for `account add|list|forget` · **Depends on:** 000

The first behaviour: a configuration file is found and read, a `Money` value parses every amount form a statement uses, the SQLite data file exists with the user's permissions and the schema the later slices write into, and the user can add, list and forget accounts. `import` arrives in slice 2, so AC7 and AC8 are proved here with `account add`, the one writing command this slice has.

**Door:** one-way. `store.py`'s schema (accounts, transactions with a fingerprint unique per account, import records) and the data file's layout on disk are hard to change once a user has data in them; the shape of `tally account ...`, its exit codes and its JSON are the command line's contract. A human reads `store.py` and `cli.py` before merging.

## Decisions taken in this plan

- **Where things are found.** Config: `--config`, else `$TALLY_CONFIG`, else `~/.config/tally/tally.toml`; the default may be absent (an empty configuration), a path given explicitly must exist (exit 2). Data directory: `--data-dir`, else `$TALLY_DATA_DIR`, else the config's `data_dir` (relative to the config file), else `~/.local/share/tally/` (`%LOCALAPPDATA%\tally\` on Windows). The design lists the first three of each; the config's `data_dir` slots in after the environment because a flag and a variable are more deliberate than a file.
- **Configuration validated only as far as this slice reads it:** `data_dir` is a string, `layouts` is a table of tables, `rules` is an array of tables, no other top-level key. The contents of layouts and rules are slice 2's and slice 4's (AC43, AC29).
- **Currency and scale.** A currency is three letters, stored upper-case; its scale (minor units per unit) is 2 unless the ISO 4217 table says otherwise (`JPY` 0, `KWD` 3 and the rest), held with the account as ADR 0004 says. No `--decimals` flag: a user who forgot it would get silently wrong amounts.
- **Busy timeout is 10 seconds, as ADR 0005 says, with no override.** The one test of AC8 therefore waits 10 seconds. An environment variable to shorten it would be a knob nobody asked for and a value to validate.
- **`forget` deletes with explicit `DELETE` statements** for transactions, import records and the account, in one `BEGIN IMMEDIATE`, rather than relying on `ON DELETE CASCADE` (which needs `PRAGMA foreign_keys` on every connection). Foreign keys are declared and the pragma is on, as a second line of defence.
- **AC3 is proved as far as this slice can observe it:** `account list`, and the rows in the real data file counted by SQL (no `import` or `report` yet). The transactions in the test are inserted by SQL into the real file. Slices 2 and 5 re-prove it through `import` and `report`.
- **`account list --format json`** is `[{"name": ..., "currency": ...}]`. CSV for `account list` waits for slice 5's CSV writer, where the formula escaping lives; `--format` here accepts `table` and `json`.
- **The prompt for `forget` goes to standard error** (standard output is data) and reads one line from standard input; only `yes` continues. Its in-process test stands in a stdin that says it is a terminal, which is the environment seam ADR 0002 allows; the subprocess test proves the non-terminal case (exit 2).
- **`store.py` and `config.py` never print.** `Store.open` reports a tightened permission as a flag that `cli.py` turns into the message; errors are exceptions `cli.py` maps to exit codes: `ConfigError` 2, `Refused` 1, `Locked` 3, `OSError` on the data file 1.

## Tasks

Each task: the test first, seen to fail for the right reason, then the code, then the test seen to pass. "Observed by" records what was actually seen.

### Task 1: Money parses every form a statement uses (AC44)

- **Test:** `tests/test_money.py::test_ac44_*`: the ten readable texts give the exact decimals; the eight unreadable ones raise with `amount is not a number`; the comma-decimal layout reads `1.234,56` and refuses `1,234.56`; minor units round-trip at scale 2, 0 and 3.
- **Code:** `money.py`: `Money`, `parse_amount(text, decimal, thousands)`, `to_minor`, `from_minor`, `scale_of(currency)`.
- **Observed by:** `ModuleNotFoundError: tally.money` before; 4 tests pass after.

### Task 2: The configuration file is found and read (part of AC1, AC6; exit 2 contract of AC34)

- **Test:** `tests/test_config.py`: no file is an empty configuration; `--config` and `$TALLY_CONFIG` are honoured in that order; a missing explicit file, a TOML syntax error (with its line), `data_dir` that is not a string, `layouts` that is not a table, `rules` that is not an array, and an unknown key are each `ConfigError` naming the key; `data_dir` resolves relative to the file; the data directory order is flag, variable, config, default.
- **Code:** `config.py`: `Config`, `ConfigError`, `find_config`, `load_config`, `data_dir_for`.
- **Observed by:** `ModuleNotFoundError: tally.config` before; the tests pass after.

### Task 3: The data file, with permissions and locking (AC6, AC7, AC8)

- **Test:** `tests/test_data_file.py`: `Store.open` on a fresh path creates the directory `0700` and the file `0600` and sets WAL; a pre-existing `0644` file is tightened and the flag is set; the schema has `accounts`, `transactions` with `UNIQUE(account_id, fingerprint)` and `imports`; a second connection holding `BEGIN IMMEDIATE` makes `store.write()` raise `Locked` after the timeout; `user_version` is 1.
- **Code:** `store.py`: `Store.open`, the schema and `user_version` migration, `write()` as `BEGIN IMMEDIATE` with commit or rollback, `Locked`, `Refused`, `add_account`, `accounts`, `account`, `transaction_count`, `forget_account`.
- **Observed by:** `ModuleNotFoundError: tally.store` before; the tests pass after.

### Task 4: `account add` and `account list` (AC1, AC2, AC34, AC35)

- **Test:** `tests/test_accounts.py`: AC1 through `main(argv)` with `--data-dir`, then permissions on disk; AC2 refused with exit 1, nothing on stdout, one line on stderr naming the account, currency still GBP; AC34: an invalid currency is exit 2 with stdout empty; AC35: `--format json` is exactly one JSON array with `name` and `currency`; one subprocess test runs the console script for add and list and checks exit codes and streams.
- **Code:** `cli.py`: the `account` subcommand group with `add`, `list`, the shared `--config`, `--data-dir`, `--format` options, the exit-code mapping.
- **Observed by:** `argparse` error `invalid choice: 'account'` (exit 2) before; the tests pass after.

### Task 5: `account forget` (AC3, AC4)

- **Test:** `tests/test_accounts.py`: two accounts with rows in the real file; `forget current --yes` leaves only `savings` in `list` and only its rows and import records in the file; `forget old --yes` is refused, exit 1; without `--yes` and not a terminal, exit 2 and nothing deleted; with a terminal stdin, the prompt on stderr names the account and the count, `no` refuses with exit 1 and deletes nothing, `yes` deletes.
- **Code:** `cli.py` `forget`; `store.py` `forget_account`.
- **Observed by:** `invalid choice: 'forget'` before; the tests pass after.

### Task 6: Two copies at once, through the real process (AC6, AC7, AC8)

- **Test:** `tests/test_data_file.py`: `TALLY_DATA_DIR` set to a fresh path and the console script run; two `account add` processes started together both exit 0, `list` shows both, `PRAGMA integrity_check` is `ok`; with a lock held from the test for 2 seconds, `account add` in a subprocess waits and exits 0; with a lock held past the timeout, `account add` in-process exits 3 with `another copy of tally is using the data file` on stderr and no account written.
- **Code:** none expected beyond Task 3; whatever the tests find.
- **Observed by:** recorded when run.

## Done when

- [ ] Every criterion above has a `test_acNN_` test seen to fail before its code and pass after, recorded in the tasks
- [ ] The four checks pass locally and in CI; mutation testing on the changed files has no survivors, or each is ruled on in the pull request
- [ ] The fresh-context review has run with the four questions answered by name; findings fixed test-first or ruled on in the pull request
- [ ] `docs/effort.md`, `docs/trial-log.md`, `docs/playbook-feedback.md` have this slice's rows; `docs/handoff.md` says where slice 2 starts
- [ ] The pull request is out of draft with CI green on its final commit
