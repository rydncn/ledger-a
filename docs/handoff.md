# Handoff

Where the work is, for the next session. The work, not the machine: tools come from the environment's setup script, never from here.

## Where we are

- **Slices 0 to 2** merged: foundation (#1), accounts and the data file (#6), CSV import (#7 and #8).
- **Slice 3 (OFX import)** merged as pull request [#9](https://github.com/rydncn/ledger-a/pull/9) (3b21163), merged by the agent at the owner's explicit request once every CI job was green; ADR 0007 has the owner merge, so this was the owner's delegation, not a change of rule. It delivers `importers/ofx.py`, one scanner for OFX 1.x SGML and 2.x XML (no XML parser runs), and `tally import --account NAME FILE` for an OFX file. The plan is `docs/plans/003-ofx-import.md`; the review, the mutation rulings and the decisions kept are in #9's description.
- **The whole-codebase review has run** (on `main` at 3b21163) and its findings are fixed in pull request [#10](https://github.com/rydncn/ledger-a/pull/10) on `whole-codebase-review`, with a fresh-context review of the fixes and its five findings fixed too. Merge #10 before slice 4 starts. What it changed that slice 4 builds on is under "Decisions" below; what it left for the owner is under "Open".
- **Then: slice 4**, categorisation: rules, `tally uncategorised`, `tally explain`; AC26 to AC29 and AC38.

## What the whole-codebase review changed

- `forget` and `import` check the account's id, name and currency again under the lock (SQLite reuses a forgotten account's id); `forget` after a prompt refuses when the count changed since the person confirmed it.
- An import keeps the first 1,000 unreadable rows and counts the rest: the JSON has `unreadable_count`, and AC13 and AC20 say so.
- One encoding allowlist for both importers (`importers/__init__.py::ENCODINGS`): UTF-8 with or without a byte order mark, cp1252, Latin-1, Latin-9, ASCII (AC43).
- A damaged data file, a full disk, a path that is not UTF-8 and a too-deep `tally.toml` are one line, not a traceback.
- A CSV record an open quote carries over lines is reported on the line it starts on, `in a record that runs to line N`.
- `scripts/check_imports.py` (in CI after the rule checks) reads every import under `src/` from the syntax tree against an allowed list of exact names, and refuses `__import__`, `__builtins__`, `exec`, `eval` and float literals. **Slice 4 adds no import outside that list without adding it there, as a decision.**
- Amounts take ASCII digits only; `from_minor` is built from digits. `argparse` refuses abbreviated options. ADR 0009 records the OFX scanner.

## How a slice goes

1. New session, new branch from `main` (`slice-4-categorisation`), `scripts/setup-dev.sh`. Set `git config user.name` and `user.email` in the checkout. Run `git fetch origin main` before anything diffs against `origin/main`: a fresh checkout here had no local ref, and the mutation script failed on its first call. Push with `git push origin <branch>`, never bare.
2. Plan in `docs/plans/004-categorisation.md` from `003-ofx-import.md`'s shape: the decisions taken, what changed from any draft, then `### Task N:` headings, each with the failing test first, the criteria it satisfies and an "Observed by" filled in as it happens. Open the draft pull request with the plan in the description and the door kind; its first line says it is not ready to merge.
3. Test-first per task: tests named `test_acNN_...` in a file per behaviour group; in-process `main(argv)` for behaviour, one subprocess test per behaviour group (ADR 0002). `tests/test_import.py::Place` gives a test its own config with the two sample layouts, a data directory and three accounts (`current` GBP, `card` EUR, `savings` GBP); write the rules into its config. Write every file through Edit or Write: the after-edit hook only sees those tools, and it reports each intermediate state of a multi-edit response, so finish the response and run the checks once.
4. Before marking ready: the fresh-context review first, then its fixes, then one mutation run on the final tree (`UV_NO_BUILD=0 uv sync --locked --group mutation`, then `uv run python scripts/mutation_changed.py origin/main` in the background; slice 3's 1,690 mutants took about 50 minutes, and a run started beside the review was wasted when the fixes changed the code). The fresh-context review from `docs/review-brief.md` runs as a subagent in a worktree at the commit with `docs/plans/`, this file and the trial records removed, given the diff without the plan. For rules, name the parsers it must ask about: `re` on the user's own patterns (catastrophic backtracking costs the user's CPU, accepted in the design), `tomllib` on the rule values, `Decimal` on `amount_below`, and the terminal for AC38.
5. Records: `docs/effort.md`, `docs/trial-log.md`, `docs/playbook-feedback.md`. Peak context from the transcript with the script in `docs/python-pack/README.md` § "Measuring a session".
6. Handoff here, push, mark ready once the quick CI checks are green, confirm the test and mutation jobs after, ask the owner to merge.

## What slice 4 builds on

- **Rules arrive as shapes only.** `config.load_config` gives `Config.rules` as a list of tables and checks nothing inside them; `rules.py` validates each (AC29: `rules[2]: description_matches is not a valid pattern: missing )`) and raises `ConfigError` before the data file opens, as `Layout.from_config` does for layouts (`cli._import` is the pattern: validate, then `open_store`).
- **One definition of a category.** `rules.categorise(transaction, rules) -> Match | NoMatch` (design § Lifecycles); `uncategorised`, `explain` and slice 5's `report` all call it, and nothing stores a category.
- **Amounts are integer minor units** in the data file with the account's `scale`; compare a rule's `amount_below` by turning it into minor units with `money.to_minor(Decimal(text), scale)`, never by `Decimal` arithmetic (`CLAUDE.md` § Lessons).
- **Descriptions are raw.** Both importers store descriptions as the file had them, trimmed: control characters, `=` formulas and, for OFX, text decoded from entities. AC38 is the first time any description reaches the terminal; it needs a replacement in `cli.py`'s rendering, and the JSON form keeps the original.
- **AC26 is written against `tally report`**, which is slice 5. Prove AC26's matching through `uncategorised`, `explain` or `rules.categorise` now, and leave the `report` form of it to slice 5, as AC3's report check was.
- **AC27's expected list includes the two savings rows** from `samples/savings.ofx`, now importable.
- **A transaction's id** is `transactions.id`; `explain <id>` reads one row. Add a store method for it rather than querying from `cli.py`.

## Decisions taken that the next session should not reopen

- Everything in the earlier lists: exit codes and streams, the 10-second busy timeout, the fingerprint of ADR 0008, the sign rule, subprocess tests kill no mutants, the data directory order, the quoted formula cell in the CSV sample, unreadable rows on standard error in both forms (50 and then a count), a decoding error refusing the whole file, the 1 MB field and 2 MB line guards, a layout refusing unknown keys, the `0400` data file tested as `nobody`.
- **OFX is read by Tally's own scanner, never an XML parser.** A DOCTYPE anywhere, or any other `<!` declaration, refuses the file; entities are the five XML ones, `&nbsp;` and numeric references, decoded by Tally.
- **An OFX unreadable entry is counted by position, not line:** `transaction 2: amount is not a number` on standard error and `{"transaction": 2, "reason": ...}` in the JSON. A CSV keeps `line`.
- **`TRNAMT` is OFX's one number shape** (`[+-]` then ASCII digits with an optional `.` fraction); `12,34` and `1,234` are `amount is not a number`.
- **A transaction with neither `NAME` nor `MEMO`** imports with an empty description; rules must cope with an empty one.
- **An OFX file holds at most one statement** (bank, card, investment or loan), and its `CURDEF` must be the account's. A transaction whose own `CURRENCY` is another currency is unreadable, never converted.
- **OFX encodings are an allowlist:** UTF-8, cp1252, Latin-1 and ASCII, from the SGML header or the XML prolog. Tag names are case-insensitive. A processing instruction in an SGML file is refused.
- **`to_minor` refuses more than 19 whole digits before converting**, for CSV and OFX alike.

## Open

- From slice 1: `account forget` keeps no tombstone; AC3's report check waits for slice 5; `account list` owes no CSV until slice 5.
- From the slice 3 review, for the owner: the OFX `ACCTID` is not compared with anything, because a Tally account has no bank account number, so a statement for another account imports if its currency matches. A file with no `CURDEF` takes the account's currency, as a CSV does. Both are kept; changing either is a design decision.
- From the slice 3 review: the store keeps every unreadable row in memory for the summary (AC13's JSON lists them all), so 2.3 million empty `STMTTRN` peaked at about 1 GB. This predates slice 3 and is the same for CSV; capping it changes AC13 and AC20.
- Numeric references to control characters (`&#27;`) are decoded, as a raw ESC byte in a CSV reaches the data file unchanged; AC38 must replace them on the terminal.
- The full suite takes about 60 s (AC18 under `tracemalloc` is 28 s of it, the two AC8 waits 20 s), and the stop hook runs it on every stop. If it passes 90 s, move the slow tests behind a marker the hook skips and CI runs, and record the ADR.
- From the whole-codebase review, for the owner (agent configuration, rule 18, unchanged): the "ask first" rules in `.claude/settings.json` miss `gh api ... /merge`, `git -C . push origin main`, `env git push ...` and every feature-branch push, while `CLAUDE.md` says publishing and pushing ask first; the plugin marketplace is not pinned to a commit; `scripts/check-rules.js` and `scripts/check_imports.py` run only in CI, not in the before-stop hook or `pre-push`. Also undecided: whether a data directory on a network or synced folder is supported (WAL needs shared memory on one host).
