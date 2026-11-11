# Tally

A command-line tool that imports bank statement files (CSV in each bank's layout, OFX in SGML and XML), removes duplicates, categorises transactions by the user's own rules and reports spending by month. It runs entirely on the user's computer and never makes a network connection.

Set up against ai-playbook `dfc984a`. Its `CHANGELOG.md` lists what changed since, and what to do about each change.

Docs: design and acceptance criteria in `docs/design.md`, decisions in `docs/decisions/`, plans in `docs/plans/` (build only from one marked active; done plans are history), where the work is in `docs/handoff.md`. The trial's records: `docs/effort.md`, `docs/trial-log.md`, `docs/playbook-feedback.md`.

## Commands

```bash
scripts/setup-dev.sh                       # Install (locked, wheels only) and point git at .claude/hooks
uv run tally --help                        # Run locally
uv run pytest -q                           # Run all tests ONCE, in random order (never a watch-mode command)
uv run pytest -q tests/test_cli.py         # Run a single test file
uv run ruff format --check . && uv run ruff check .   # Format and lint check
uv run mypy                                # Type check (strict)
node scripts/check-rules.js scripts/rules.json        # Project rule checks
uv run python scripts/check_imports.py     # Every import under src/ on the allowed list
uv run python scripts/mutation_changed.py origin/main # Mutation testing on changed files (needs: UV_NO_BUILD=0 uv sync --locked --group mutation)
uv run python scripts/audit.py             # Dependency audit with the dated allowlist
```

`UV_NO_BUILD=1` is set for every session in `.claude/settings.json`: installs refuse source builds. The one exception is the mutation group (ADR 0003).

Commands that publish or push are set to ask first in `.claude/settings.json`. Never work around that.

At the start of a session, if the plugin check reports missing plugins, tell the user before starting work rather than doing their steps by hand.

## Architecture

`src/tally/`, standard library only (ADR 0001):

- `config.py`: finds and reads `tally.toml` (`--config`, `$TALLY_CONFIG`, the user's config directory): `data_dir`, the CSV layouts and the rules, each validated with the table or rule named in the error. A configuration error is exit 2 before the data file opens.
- `cli.py`: argument parsing and output. The only module that prints. Errors go to standard error with a non-zero exit code; colour only when standard output is a terminal and `NO_COLOR` is unset; every report has a plain, machine-readable form.
- `money.py`: exact amounts as `Decimal` with a currency; parsing of the formats statements use (`1,234.56`, `1.234,56`, `(12.50)`, a sign or a separate money-in and money-out column).
- `store.py`: the SQLite data file, created with permissions readable only by the user, opened under one lock so two copies running at once never corrupt it or count a transaction twice. Schema and migrations live here.
- `importers/`: one module per format (`csv_layout.py`, `ofx.py`), each turning bytes into rows and reasons for the rows it couldn't read. Encoding and line-ending detection happens here, once.
- `rules.py`: the user's categorisation rules from the TOML configuration, first match wins, with an explanation of why a transaction got its category.
- `report.py`: monthly totals by category and top payees, from SQL, as plain rows; `cli.py` renders them as a table or CSV.

Decisions and the options rejected for them are in `docs/decisions/`. Read the relevant one before proposing a different approach; to change a decision, write a new ADR that replaces it.

### Security boundaries

- **Money is exact.** No `float` anywhere under `src/`: checked by the `no-float-for-money` rule check over every `.py` file in `src/`, which fails if it finds no files. Amounts are `Decimal`, stored in SQLite as integer minor units with the currency.
- **No network.** Checked by the `no-network` rule check over `src/` (the standard library's network modules and the common third-party clients), by `scripts/check_imports.py`, which reads every import from the syntax tree and fails on one outside its allowed list (an alias or a from-import passes a word check), and by having no runtime dependencies at all.
- **Nothing personal in output the user didn't ask for.** Error messages name the file, the line number and the reason, never the row's content; logging is off unless `--verbose`, and even then descriptions and amounts are not logged. Tested by the error-message tests, which import a hostile file and assert its descriptions appear nowhere in standard error.
- **The data file is the user's alone.** Created with mode `0600` inside a directory created `0700`; the permission test fails when either is wider.
- **Statement files are hostile input.** Every importer is tested with a byte order mark, Windows line endings, Latin-1, quoted fields with commas, formula-looking descriptions, a file that isn't a statement, and a very large file (bounded memory: streamed, never read whole). CSV export escapes any text cell starting with `=`, `+`, `-`, `@`, a tab or a carriage return, so a spreadsheet never runs it; amount cells are plain decimals matching `-?\d+\.\d{2}` and are never prefixed.
- **Two copies at once.** Every import runs in one `BEGIN IMMEDIATE` transaction with a busy timeout; the two-process test imports the same file from two processes at once and asserts the count is right.

## Conventions

- Python 3.15, `from __future__ import annotations`, full type hints, `mypy --strict`. Ruff formats and lints (see `pyproject.toml` for the rule set); fix the code, not the rule, unless the rule is wrong for the whole project.
- Tests call `tally.cli.main(argv)` in-process (so mutation testing sees them) and, for each behaviour group, once through a real subprocess. Acceptance tests name their criterion: `test_ac12_...`.
- Every test gets its own temporary data directory and config file; nothing is shared between tests.
- British English in prose, messages and documentation. Commits: conventional commits (`feat:`, `fix:`, `docs:`, `test:`, `chore:`, `ci:`).

## Workflow

- Non-trivial work: written design, then a plan of test-first tasks. Each task states how its effect will be checked before any code is written.
- Every pull request says whether it is a one-way door (schema changes, data deletion, what leaves the machine, the shape of the command line or its machine-readable output, agent configuration, new dependencies, release settings) or a two-way door. A human reads the diff of every one-way file before merging.
- A task is done when its effect has been observed, not when the code has been read back.
- Before merging: a fresh-context review of the slice (a reviewer given the diff, the design and this file, not the session's reasoning), briefed with `docs/review-brief.md`, which asks the four questions by name. For changes to the data file, deletion, parsing or what the export writes: the security audit before the final review.
- Every few slices: a review of the whole codebase against these rules, reading the slices together, with the same brief.
- When the context budget warns, finish the step and write the handoff (`docs/handoff.md`): where the work is, what's next, what's undecided. Tools the next session needs go in a setup script it runs, never in the handoff as "installed": a fresh session may start in a fresh container.
- When the agent gets something wrong, record the lesson here or in the matching rules file, never only in local memory. If a rule is broken twice, turn it into a check.

## Lessons

- Never put an amount through `Decimal` arithmetic (`-x`, `x.scaleb(n)`, `+`): the default context rounds at 28 significant digits silently. Build the `Decimal` from text or from a `(sign, digits, exponent)` tuple. Found by the slice 1 review.
- Read before you lock: a command that only reads must not take `BEGIN IMMEDIATE` (a reader waiting on a writer and exiting 3 is against ADR 0005); check the schema version first and migrate only when it must change.
- Write source through the Edit or Write tools, not the shell: the after-edit hook watches those tools only, and a session that writes files with heredocs gets no format or lint feedback until it runs the checks by hand.
- mutmut only counts tests that run the mutated code in-process; a test that drives `tally` through `subprocess` kills no mutants. Drive behaviour through `main(argv)`.
- Run a sample file through the parser before writing a criterion that counts its rows: the brief's `current-account.csv` had an unquoted cell with a comma, six columns to every CSV reader, and the design counted five rows for two slices before a test ran it.
- A `0400` data file in WAL mode still accepts `BEGIN IMMEDIATE`; `SQLITE_READONLY` arrives at the first `INSERT`, inside the transaction. And the cloud session is root, for whom the file is writable regardless: a permission test skips under root and is observed as another user (`runuser -u nobody`) or in CI.
- A text decoder reads ahead of the lines, so a `UnicodeDecodeError` carries no trustworthy line number; say what the file is not, without one.
- `logging.basicConfig` outlives the command in an in-process test suite: attach a handler for the run and remove it after.
- "It writes ASCII as ASCII" is not an encoding check: UTF-7, `unicode_escape` and about 80 other codecs pass it and decode to lone surrogates, which SQLite refuses with a traceback. Allow the few codecs a format uses by name. Found by the slice 3 review.
- `int()` of a huge `Decimal` costs its length squared (1.6 s for 300,000 digits), and an amount's length is the file's choice: bound the digits before converting, as `to_minor` does.
- A probe beats a guess about a library: `html.unescape` follows HTML5 (`&ampfoo` is `&foo`), `strptime("2026111", "%Y%m%d")` is 1 November, and `\d` matches Arabic-Indic digits that `int` and `Decimal` accept. One line in the interpreter before choosing the function.
- A fresh cloud checkout has no local `origin/main`: run `git fetch origin main` before anything diffs against it (the mutation script does).
