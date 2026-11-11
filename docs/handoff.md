# Handoff

Where the work is, for the next session. The work, not the machine: tools come from the environment's setup script, never from here.

## Where we are

- **Slices 0 to 2** merged: foundation (#1), accounts and the data file (#6), CSV import (#7 and #8).
- **Slice 3 (OFX import)** is pull request [#9](https://github.com/rydncn/ledger-a/pull/9) on `slice-3-ofx-import`. It delivers `importers/ofx.py`, one scanner for OFX 1.x SGML and 2.x XML (no XML parser runs), and `tally import --account NAME FILE` for an OFX file. Criteria AC21 to AC25, AC39, AC41, with AC34 and AC35 for `import`. The plan with what each task observed is `docs/plans/003-ofx-import.md`. The review's findings, the mutation rulings and the whole-codebase review are in #9's description. The fresh-context review's eight findings were fixed test-first.
- **Next, first: the whole-codebase review**, which the slice 3 session did not run because its budget was spent (it was due after slice 3). A subagent in a worktree at `main` after #9 merges, with `docs/plans/`, this file and the trial records removed. Brief it with `docs/review-brief.md`, `CLAUDE.md`, `docs/design.md`, `docs/brief.md` and the ADRs. It reads slices 1 to 3 together and answers the four questions by name. Fix its findings test-first, or rule on them, in their own pull request before slice 4's plan.
- **Then: slice 4**, categorisation: rules, `tally uncategorised`, `tally explain`; AC26 to AC29 and AC38.

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
