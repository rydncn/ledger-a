# 002. CSV import

**Status:** active · **Satisfies:** AC5, AC9 to AC20, AC40, AC42, AC43, with AC34 and AC35 for `import`, and AC7 and AC8 re-proved through `import` · **Depends on:** 001

The first import: a bank's CSV, described once as a layout in `tally.toml`, read as hostile bytes into rows and reasons, fingerprinted (ADR 0008), written under one lock (ADR 0005) with its import record, and summarised for a person or a program.

**Door:** one-way. The import record and the transaction rows are the schema users keep data in (no migration this slice: schema version 1 already has both tables, but what goes in `fingerprint` and `amount_minor` is fixed from the first import); the fingerprint's text is ADR 0008 and cannot change without re-importing; `tally import`'s options, exit codes and JSON are the command line's contract. A human reads `src/tally/importers/csv_layout.py`, `src/tally/store.py` and `src/tally/cli.py` before merging.

## Decisions taken in this plan

- **A layout is validated before the data file opens (AC43).** `importers/csv_layout.py::Layout.from_config(name, table)` raises `ConfigError` naming `layouts.<name>` and the problem: no `date`, `description`, or neither `amount` nor both `money_in` and `money_out`; `amount` together with `money_in`/`money_out`; a column name that is not a string; `date_format` that `strptime` refuses or that does not give a day, month and year (checked by formatting a known date and reading it back); `decimal` and `thousands` not single characters or not distinct; `delimiter` not a single character; an unknown `encoding`; an unknown key (a typo like `date_fromat` would otherwise silently fall back to the default). Defaults: `delimiter = ","`, `decimal = "."`, `thousands = ","`, `encoding = "utf-8"`. No `balance` key: the design says the column is ignored, so a layout never names it. `cli.py` runs this before `Store.open`, so each command now opens the store itself through one helper (`open_store(args, config)`), which is the smallest change that puts the configuration error ahead of the data file.
- **Which importer reads a file is decided from its first bytes** (`importers/__init__.py::kind`): `OFXHEADER:` is OFX SGML, `<?xml`, `<?OFX` or `<OFX>` after an optional byte order mark is OFX XML, anything else is CSV. This slice refuses an OFX file with `OFX import is not available yet` (exit 1) and refuses `--layout` with an OFX file or a CSV file without `--layout` as usage errors (exit 2), so slice 3 fills in a branch rather than changing the shape.
- **Encoding is the layout's, once.** The file is opened as text with `errors="strict"` in the layout's encoding; UTF-8 is opened as `utf-8-sig`, so a byte order mark is never part of the first column's name (AC10). A file whose first 1 KB is empty is `empty file`; one holding a NUL byte there is `not a text file`; a decoding error anywhere refuses the whole file as `not a text file: line N is not valid <encoding>`, because the import is all-or-nothing anyway and the position cannot be trusted after a bad byte (AC17).
- **Line endings are the `csv` module's business**, with the file opened `newline=""` as its documentation requires: `\r\n`, `\n` and `\r` all end a row and never reach a description (AC10). Physical line numbers are counted by Tally's own line iterator, not read from `reader.line_num`, because the iterator is also where the flood guard lives.
- **The flood guard is per physical line (AC40):** a line longer than 1,048,576 characters is drained in bounded chunks and reported as `field longer than 1 MB` on its line number, and `csv.field_size_limit` is set to the same so a quoted field spread over many lines meets the same cap with the same message. The `csv` reader resets its state after its source raises, which was checked against the module before this plan was written.
- **Row outcomes are decided in the importer** (`read(path, layout, scale)` yields `Transaction | Unreadable`): too few or too many columns (`expected 5 columns, found 3`, against the header's count), a date `strptime` refuses (`date does not match %d/%m/%Y`), an amount `parse_amount` refuses (`amount is not a number`) or `to_minor` refuses (more decimals than the account's scale, or outside SQLite's integer), both money columns empty (`no amount`). Blank lines yield no outcome: `csv` gives an empty row for them and they carry no data. Descriptions are stripped of surrounding whitespace; nothing else about them changes.
- **The sign rule is the design's:** in money-in and money-out columns the value's magnitude counts (`copy_abs`, which the `Decimal` context never rounds) and the amount is in minus out, computed in integer minor units, never by `Decimal` arithmetic (the slice 1 lesson).
- **The fingerprint is ADR 0008**, built in the importer: `csv:<ISO date>|<minor units>|<description trimmed, whitespace-collapsed, case-folded>|<n>`, with `n` counted per file in a dictionary keyed by the first three parts. AC18 measures what that dictionary costs for 300,000 rows.
- **The store writes the import run as one `write()`** (`Store.import_transactions(account, file, outcomes)`): the import record first with zero counts (so every row can reference it), each `Transaction` as `INSERT ... ON CONFLICT (account_id, fingerprint) DO NOTHING` whose `rowcount` says added or already there, each `Unreadable` kept for the summary, then the record's counts updated, all before the commit. Any failure rolls the lot back, including the record (AC17, AC42). `SQLITE_READONLY` from `write()` is `RefusedError("the data file cannot be written (permissions 0400)")` with the mode read from the file, not changed.
- **The shared vocabulary of importers lives in `importers/__init__.py`:** `Transaction`, `Unreadable`, `NotAStatementError` and `kind`. `store.py` imports the first two; the OFX importer will reuse all four. `NotAStatementError` is the whole-file refusal (exit 1) and `cli.py` maps it beside `RefusedError`.
- **The summary.** Human form on standard output: `added 5, already there 0, unreadable 0`. JSON form: `{"account", "file", "added", "duplicates", "unreadable": [{"line", "reason"}]}` as one line. Unreadable rows go to standard error in both forms (they are messages): the first 50 as `line 3: date does not match %d/%m/%Y`, then `and 450 more` (AC13); the JSON carries them all (AC20). `file` is the path as given on the command line.
- **`--verbose`** turns on `logging` at INFO to standard error for the run (`cli.py` configures it; the importer logs through `logging.getLogger`): the encoding used, the header columns matched by position, and the row count. Never a description or an amount (AC19 asserts it with marker strings).
- **AC7 and AC8 move to `import`** as the brief asks: the two-process test imports a 2,000-row file from two processes and sums their `added`; AC8 holds a write transaction from the test past the timeout and expects exit 3 with no import record. The slice 1 versions on `account add` stay.
- **AC42 under root.** The session that builds this slice runs as root, for whom a `0400` file is writable, so the in-process test skips when `os.geteuid() == 0` with that reason and CI (a non-root runner) runs it; locally it was observed by running the one test as `nobody` (recorded in Task 6).

## Tasks

Each task: the test first, seen to fail for the right reason, then the code, then the test seen to pass. "Observed by" records what was actually seen.

### Task 1: A layout is validated before anything opens (AC43)

- **Test:** `tests/test_csv_layout.py::test_ac43_*`: the AC9 layout and the AC11 layout build; a layout missing `date`, one with `date_format = "%Q"`, one with `date_format = "%H"`, one with `decimal = ","` and `thousands = ","`, one with a two-character delimiter, one with an unknown encoding, one with `amount` and `money_in`, one with neither, one with an unknown key, one whose column is not a string each raise `ConfigError` naming `layouts.<name>` and the problem; through `main`, `--layout nosuch` and the missing-`date` case exit 2 with nothing on standard output and no data file created.
- **Code:** `importers/__init__.py` (the types), `importers/csv_layout.py::Layout`, `cli.py`'s `import` parser and `open_store`.
- **Observed by:**

### Task 2: Bytes become rows and reasons (AC10 to AC13, AC17, AC40, ADR 0008)

- **Test:** `tests/test_csv_layout.py`: `read()` on `samples/current-account.csv` gives five transactions with the AC9 amounts in minor units, ISO dates, `TESCO STORES 2045, LEEDS` whole, no `\r` anywhere, and the ADR 0008 fingerprints; on `samples/credit-card.csv` three with `CAFÉ NERO` intact and the AC11 amounts and dates; a file with a bad date, a bad amount and a short row yields three `Unreadable` with the AC13 reasons and the other rows; two identical rows get `n` 1 and 2; a PNG, an empty file, a header without `Date` and a header-only file are the AC17 refusals (the last imports nothing and refuses nothing); a 50 MB quoted field on line 4 is `field longer than 1 MB` with the other rows read, and peak traced memory stays bounded; a bad byte on line 3 of a UTF-8 file names line 3.
- **Code:** `importers/csv_layout.py::read`, the line iterator, `fingerprint`.
- **Observed by:**

### Task 3: The import run in the store (AC14 to AC16, AC17's "no import record")

- **Test:** `tests/test_import.py` at the store level: `import_transactions` with five rows writes five transactions and one record with the counts; the same rows again adds none and counts five duplicates in a second record; a mix of rows and unreadables counts each once; an exception from the outcomes iterator leaves no transaction and no record.
- **Code:** `store.py::import_transactions`, `ImportSummary`.
- **Observed by:**

### Task 4: `tally import` (AC5, AC9, AC11, AC12, AC14, AC15, AC16, AC19, AC20, AC34, AC35)

- **Test:** `tests/test_import.py` through `main(argv)` with a config file and `--data-dir` under `tmp_path`: AC9's five rows and amounts from the real data file; AC11 on the card sample; AC12's minor units 245000; AC14 twice; AC15 with an overlapping file; AC16 with two identical rows; AC5 refused into an unknown account with the data file's bytes unchanged; AC20's JSON object alone on standard output and the human form without `--format`; AC19 with marker strings and `--verbose`; AC34's usage errors (`--layout` missing for a CSV, an OFX file with `--layout`, a missing file) exit 2 or 1 with standard output empty; one subprocess test runs the console script for an import and reads its JSON; the top-level and `import` help screens whole.
- **Code:** `cli.py::import_run`, help text.
- **Observed by:**

### Task 5: Hostile files through the command (AC13, AC17, AC18, AC40)

- **Test:** `tests/test_import.py`: AC13's three unreadable rows on standard error by line and reason, none quoting the row, exit 0, the summary saying 3; 500 unreadable rows list 50 then `and 450 more` and the JSON lists 500; AC17's three refusals exit 1 with nothing written and no import record; AC18's 300,000-row file under `tracemalloc` stays under 100 MB with the count right; AC40 through `main`.
- **Code:** whatever the tests find.
- **Observed by:**

### Task 6: Two copies, and a file that cannot be written (AC7, AC8, AC42)

- **Test:** `tests/test_import.py`: two `tally import` processes on a 2,000-row file both exit 0 (or one exits 3), 2,000 transactions, `integrity_check` ok, the two `added` sum to 2,000; a write transaction held past the timeout makes `import` exit 3 with no record; AC42's `0400` file is refused with `the data file cannot be written`, same bytes after, no record, permissions still `0400`.
- **Code:** `store.py` mapping `SQLITE_READONLY`.
- **Observed by:**

### Task 7: What mutation testing and the fresh-context review found

- **Test:** whatever they ask for.
- **Code:** whatever they ask for.
- **Observed by:**

## Done when

- [ ] Every criterion above has a `test_acNN_` test seen to fail before its code and pass after, recorded in the tasks
- [ ] The four checks pass locally and in CI; mutation testing on the changed files has no survivors, or each is ruled on in the pull request
- [ ] The fresh-context review has run with the four questions answered by name (the `csv` module, the codecs, `strptime` and the terminal asked about by name); findings fixed test-first or ruled on in the pull request
- [ ] `docs/effort.md`, `docs/trial-log.md`, `docs/playbook-feedback.md` have this slice's rows; `docs/handoff.md` says where slice 3 starts
- [ ] The pull request is out of draft with CI green on its final commit
