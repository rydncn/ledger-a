# Handoff

Where the work is, for the next session. The work, not the machine: tools come from the environment's setup script, never from here.

## Where we are

- **Slices 0 to 2** merged: foundation (#1), accounts and the data file (#6), CSV import (#7 and #8).
- **Slice 3 (OFX import)** merged as pull request [#9](https://github.com/rydncn/ledger-a/pull/9) (3b21163), merged by the agent at the owner's explicit request once every CI job was green; ADR 0007 has the owner merge, so this was the owner's delegation, not a change of rule. It delivers `importers/ofx.py`, one scanner for OFX 1.x SGML and 2.x XML (no XML parser runs), and `tally import --account NAME FILE` for an OFX file. The plan is `docs/plans/003-ofx-import.md`; the review, the mutation rulings and the decisions kept are in #9's description.
- **The whole-codebase review has run** (slice 3 session, on `main` at 3b21163, a subagent in a worktree without the plans, this file or the trial records, briefed with `docs/review-brief.md`). Its findings are below. **Next, first: fix them** on branch `whole-codebase-review` (already pushed from `main` with this file), test-first, in their own pull request before slice 4's plan. Re-create each probe as a failing test; the reviewer's probe scripts lived in the old container's scratchpad and are gone.
- **Then: slice 4**, categorisation: rules, `tally uncategorised`, `tally explain`; AC26 to AC29 and AC38.

## The whole-codebase review's findings

Must fix:
1. **Account ids are reused, and `forget` and `import` act on an id read before the lock.** `accounts.id INTEGER PRIMARY KEY` without `AUTOINCREMENT` hands a forgotten account's id to the next `add`. Reproduced by the slice 3 session: copy A reads `current` (id 2) and waits at the forget prompt; copy B forgets `current`, adds `joint` (id 2) and imports a row; A's "yes" then deletes `joint`'s transactions. `import` has the same window (the lookup is before `BEGIN IMMEDIATE`, which can wait 10 s), so a file parsed with one account's currency can land in another's. Fix inside the write transaction: re-select `WHERE id = ? AND name = ?` (and the currency for import) and refuse if it changed; count the transactions there too. `AUTOINCREMENT` would also do it but is a migration (one-way).
2. **Unreadable rows cost about 100 times the file's size in memory.** `Store.import_transactions` keeps every `Unreadable` until the commit: an 8 MB CSV of `x\n` lines grew peak RSS by 824 MB, a 57 MB OFX of empty `STMTTRN` by 468 MB, against `CLAUDE.md`'s "bounded memory". AC18 measures only valid rows. Keeping the first 50 and a count collides with AC13 and AC20 ("the JSON lists them all"): **the owner decides** between capping the JSON list with a count, or spooling the rows to a temporary table.

Should fix:
3. **CSV layouts accept any codec**, where OFX has an allowlist (the `CLAUDE.md` lesson): `encoding = "utf-7"`, `unicode_escape` or `raw_unicode_escape` with `+2D8-` or `\ud800` in the file is a `UnicodeEncodeError` traceback showing a decoded character. Fix: the same allowlist, as a configuration error (exit 2).
4. **Tracebacks instead of one line** (AC34, and the lifecycle's "the disk fails"): a damaged data file (`database disk image is malformed`) or a full disk, because `main` does not catch `sqlite3.Error`; a statement path that is not valid UTF-8 (`UnicodeEncodeError` at the import record's `INSERT`); a deeply nested `tally.toml` (`RecursionError` from `tomllib`, should be exit 2).
5. **An unclosed quote in a CSV swallows the rows after it** (the `csv` module reads on to the closing quote): a quote opened on line 3 of six rows gave `added 1, unreadable 1` with `line 7: expected 3 columns, found 2`. Report the line the record started on, and say when it spans lines.
6. **The rule checks match words, not imports:** `from urllib import request as r`, `from http import client`, `import ssl`, `asyncio.open_connection` and `1 / 3` all pass `check-rules.js`. Fix: an AST check that every import under `src/` is on an allowlist of standard-library modules, beside the word checks.
7. **`money.parse_amount` uses `\d`** (`parse_amount("١٢٣.٤٥")` is 123.45, fullwidth digits too), where `ofx.py` uses `[0-9]`; `strptime` on CSV dates also takes them. **`money.from_minor` uses `scaleb`**, which a lesson forbids (exact today only because minor units are at most 19 digits): build it from a tuple.
8. **The documents no longer match the code:** ADR 0001 says `xml.etree` reads OFX XML, and AC39 says the DOCTYPE check is "on the first bytes before any XML parser runs"; no XML parser runs and the DOCTYPE is refused wherever it appears. Write an ADR replacing that part of 0001 and correct AC39. `CLAUDE.md` says every importer is tested with formula-looking descriptions; the OFX tests have none.
9. **`argparse` accepts abbreviations** (`account add c --cur GBP --data D`, `account list --form json`), which makes every prefix part of the command-line shape: `allow_abbrev=False` on every parser.

Agent configuration, **for the owner** (rule 18; the agent changes none of it on a reviewer's say-so):
- The "ask first" rules in `.claude/settings.json` miss `gh api ... /merge`, `git -C . push origin main`, `env git push ...` and every push to a feature branch, while `CLAUDE.md` says publishing and pushing ask first. Either widen the rules or make `CLAUDE.md` say what is enforced.
- The plugin marketplace `rydncn/ai-playbook` is not pinned to a commit, so its default branch becomes hooks and instructions in every session.
- `node scripts/check-rules.js` runs only in CI, not in `.claude/checks.json`'s `beforeStop` or `pre-push`.

Also for the owner: whether a data directory on a network or synced folder is supported (WAL needs shared memory on one host), and whether an OFX file should be checked against the account (no `ACCTID` is stored).

Checked and sound: the store's rollback, migrations re-checked under the lock, WAL readers of a `0400` file or `0500` directory as `nobody`, the creation modes, OFX's NUL, surrogate, depth and size limits, the fingerprint format, the bound before `int()`, the hooks (no shell), and CI (pinned actions, minimal permissions, checked downloads).

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
