# Handoff

Where the work is, for the next session. The work, not the machine: tools come from the environment's setup script, never from here.

## Where we are

- **Slices 0 to 3** merged: foundation (#1), accounts and the data file (#6), CSV import (#7, #8), OFX import (#9); the whole-codebase review's fixes (#10).
- **Slice 4 (categorisation)** is pull request [#11](https://github.com/rydncn/ledger-a/pull/11) on `slice-4-categorisation`: `rules.py` (`load`, `categorise(entry, rules) -> Match | NoMatch`), `tally uncategorised` and `tally explain ID`, `cli.printable` for AC38, `Store.entries()` and `Store.entry(id)`. The plan is `docs/plans/004-categorisation.md`; the review, its rulings and the mutation results are in #11's description. #11 is merged: the agent merged it at the owner's explicit request once every CI job was green (ADR 0007 has the owner merge; this was the owner's delegation).
- **Then: slice 5**, reports: `tally report`, `tally payees`, CSV and JSON export, colour; AC30 to AC33, AC35 to AC37, and the `report` checks AC26 and AC3 have waited for.

## How a slice goes

1. New session, new branch from `main` (`slice-5-reports`), `scripts/setup-dev.sh`, then `git fetch origin main`. Set `git config user.name` and `user.email`. Push with `git push origin <branch>`, never bare.
2. Plan in `docs/plans/005-reports.md` from `004-categorisation.md`'s shape: decisions, then `### Task N:` with the failing test first and "Observed by" filled in as it happens. Open the draft pull request with the plan and the door kind; its first line says it is not ready to merge.
3. Test-first per task: `test_acNN_...`, in-process `main(argv)`, one subprocess test per behaviour group. `tests/test_import.py::Place` and `tests/test_categorise.py::samples` give a test its own config with the layouts, AC26's rules and the three samples imported (ids 1 to 10). Write every file through Edit or Write, and invisible characters as `chr()`.
4. Before marking ready: the five checks, then the fresh-context review (subagent, worktree without `docs/plans/`, this file and the trial records, the diff without the plan, `docs/review-brief.md`), its fixes, then one mutation run on the final tree in the background (`UV_NO_BUILD=0 uv sync --locked --group mutation`, `uv run python scripts/mutation_changed.py origin/main`). For reports, name the parsers: the spreadsheet (AC32), the terminal (AC33, AC38), `--month`/`--from`/`--to` parsing (AC37: `strptime` takes `2026-1` and other short forms; probe it), SQLite's integer sums (overflow past 2^63 on a huge file), and `Decimal` on the way out.
5. Records: `docs/effort.md`, `docs/trial-log.md`, `docs/playbook-feedback.md`; peak context with the script in `docs/python-pack/README.md`.
6. Handoff here, push, mark ready once the quick CI checks are green, confirm the test and mutation jobs after, ask the owner to merge.

## What slice 5 builds on

- **The category is `rules.categorise`**, and nothing stores one. `report` totals by category in Python over `Store.entries()` (or a new read that filters by month in SQL and categorises the rows), never a stored column; uncategorised is `NoMatch`. Load the rules with `load_rules(config.rules)` before `open_store` (AC29), as `uncategorised` and `explain` do.
- **Rendering is in `cli.py`:** `printable` for every text that reaches the terminal (table lines and every error message), `_cell` for each CSV text cell (prefix decided by the original text, then replaced), `_fields` for a transaction's JSON. Amounts are `str(entry.amount)`, the account's own decimal places. Reuse these; AC32's tab and carriage-return cells come out as `'␉…` and `'␍…`.
- **Sums are exact integers:** sum `amount_minor` per currency (Python `int` or SQLite's integer `sum`, which raises on overflow), then `from_minor`. Never `Decimal` arithmetic (`CLAUDE.md` § Lessons). Never sum across currencies (AC36).
- **AC26's report check:** `tally report --month 2026-10 --format json` on `samples()` gives TESCO as Groceries, TFL as Travel, COUNCIL TAX as Big, the card's `PAYMENT RECEIVED` as Card payments, a TESCO −150.00 as Groceries, and the savings transfer as not Big. **AC3's:** after `account forget`, the report has none of its rows.
- **AC32 names `uncategorised --format csv` too**; its tab and CR cases are covered by `_cell` (`test_ac32_a_csv_cell_is_prefixed_by_what_the_text_starts_with`), but the AC's full check (round trip through the `csv` module, amount cells' shape) is slice 5's.
- **`--format csv` writes through `csv.writer(sys.stdout)`** with `\r\n`. On Windows the text stream would add its own `\r` (`\r\r\n`; the slice 4 review, F2). Decide it once for both commands: `lineterminator="\n"` loses `\r\n` on Linux, so `sys.stdout.reconfigure(newline="")` before writing is the likely fix. Windows is not in CI, so record the decision either way.

## Decisions taken that the next session should not reopen

- Everything in the earlier handoffs: exit codes and streams, the 10-second busy timeout, the fingerprint of ADR 0008, the sign rule, subprocess tests kill no mutants, the data directory order, unreadable rows on standard error (50 and then a count), the encoding allowlist, the 1 MB field guard, OFX read by Tally's own scanner, `to_minor` bounded before `int()`.
- **Rules (slice 4):** every value a TOML string; positions 1-based (`rules[2]`); `description_contains` ignores case, `description_matches` is `re.search` and case-sensitive; amounts in one shape (`[+-]?[0-9]{1,19}(\.[0-9]{1,3})?`), compared as exact `Decimal` and strictly; `amount_above` below `amount_below`; a rule with only a name matches everything; an empty contains or pattern is refused; names refuse control characters; a rule's `account` naming no account never matches.
- **AC38:** C0 controls as control pictures, DEL as `␡`, every other `C` category and line or paragraph separator as `?`; the JSON keeps the original; the CSV keeps the replacement.
- **`explain ID`:** 1 to 19 ASCII digits below 2^63, else exit 2; no such transaction is exit 1.

## Open

- For the owner, from the slice 4 review: AC35 says amounts have "two decimals" and `CLAUDE.md` says amount cells match `-?\d+\.\d{2}`, but a JPY amount is `1234` and a BHD one `1.234`. The code uses the currency's own places; the criterion and the rule should say so, or the code should change.
- For the owner: `uncategorised` collects every row before printing, so a failure part way prints nothing (AC34); memory grows with the data. Streaming would give that up.
- For the owner: a rule's `account` is not checked against the accounts, because the rules are validated before the data file opens.
- From slice 1: `account forget` keeps no tombstone; `account list` owes no CSV until slice 5.
- From the slice 3 review: the OFX `ACCTID` is compared with nothing; a file with no `CURDEF` takes the account's currency; the store keeps every unreadable row for the summary up to 1,000.
- The full suite takes about 56 s. If it passes 90 s, move the slow tests behind a marker the hook skips and CI runs, and record the ADR.
- From the whole-codebase review, for the owner (agent configuration, unchanged): the "ask first" rules in `.claude/settings.json` miss some push and merge forms; the plugin marketplace is not pinned; `check-rules.js` and `check_imports.py` run only in CI. Also undecided: a data directory on a network or synced folder.
